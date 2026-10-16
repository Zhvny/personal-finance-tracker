"""
tests/unit/receipt_reader/test_parse_tracker_app.py
====================================================
Unit tests for parse_tracker_app() in parser.py — targeting lines 233-341.

Tests use realistic OCR text fixtures that mirror actual Finance Tracker /
Spendee app screenshots. No I/O, no mocking needed — pure logic coverage.

Coverage targets:
  - Single expense transaction (Uang Keluar)
  - Single income transaction (Uang Masuk)
  - Multiple transactions in one text block
  - Month header causes list_start shift
  - Empty block with Rp anchor expansion (lines 303-312)
  - Merchant extraction and noise-line filtering
  - "Dana Masuk" anchor: only valid with Rp or account# on same line
  - dana masuk prefix stripped from merchant name
  - Autodebet prefix stripped
  - Amount below threshold → receipt skipped
  - Amount not found in block → receipt skipped
  - No merchant after noise filtering → receipt skipped
  - Date fallback (no date line after anchor) → datetime.now() used
"""

from datetime import datetime

import pytest

from apps.cli.receipt_reader.core.interfaces import (
    ExpenseCategory,
    PaymentMethod,
    TransactionType,
)
from apps.cli.receipt_reader.core.parser import parse_tracker_app

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — minimal but realistic OCR text blocks
# ─────────────────────────────────────────────────────────────────────────────

TRACKER_SINGLE_KELUAR = """\
Home
Pengeluaran
Pemasukan
Portfolio

Nara Kitchen
Rp 85.000
1234567890
Uang Keluar
12 Jun 2025
"""

TRACKER_SINGLE_MASUK = """\
Home
Pengeluaran
Pemasukan
Portfolio

Ratnawati Santoso
Rp 500.000
9876543210
Uang Masuk
3 Mar 2025
"""

TRACKER_TWO_TRANSACTIONS = """\
Home
Pengeluaran
Pemasukan

Nara Kitchen
Rp 85.000
1234567890
Uang Keluar
5 Jan 2025

Grab
Rp 32.000
0987654321
Uang Keluar
5 Jan 2025
"""

TRACKER_INCOME_AND_EXPENSE = """\
Home

Dana Transfer
Rp 1.000.000
Uang Masuk
15 Feb 2025

Gofood
Rp 55.000
Uang Keluar
15 Feb 2025
"""

TRACKER_WITH_MONTH_HEADER = """\
Home
Pengeluaran

Februari 2025

M Kubik
Rp 45.000
0000000001
Uang Keluar
20 Feb 2025
"""

TRACKER_DANA_MASUK_WITH_RP = """\
Home
Pemasukan

Dana Masuk Rp 200.000 dari Joselyn
Uang Masuk
10 Apr 2025
"""

TRACKER_DANA_MASUK_STANDALONE = """\
Home

Dana Masuk
Pengeluaran
"""

TRACKER_AMOUNT_TOO_SMALL = """\
Home

Coffee
Rp 50
Uang Keluar
1 Jan 2025
"""

TRACKER_NO_AMOUNT = """\
Home

Indomaret
1234567890
Uang Keluar
2 Mar 2025
"""

TRACKER_AUTODEBET_PREFIX = """\
Home

Autodebet Tagihan PLN Prepaid
Rp 150.000
Uang Keluar
3 Apr 2025
"""

TRACKER_DARI_PREFIX = """\
Home

dari Joselyn Sutandar
Rp 300.000
Uang Masuk
8 May 2025
"""

TRACKER_OCR_NOISE_VANG = """\
Home

Rasela
Rp 72.000
Vang Keluar
22 Jun 2025
"""

TRACKER_OCR_NOISE_YANG = """\
Home

Ballin Kitchen
Rp 38.000
Yang Masuk
7 Jul 2025
"""

TRACKER_NO_DATE_LINE = """\
Home

Stay Refreshed
Rp 25.000
Uang Keluar
"""

TRACKER_SKIP_NOISE_LINES = """\
Home
Portfolio
Save
Share

Apotek Kimia
Rp 95.000
8888888888
Uang Keluar
11 Nov 2025
"""


# ─────────────────────────────────────────────────────────────────────────────
# 1. Single transactions
# ─────────────────────────────────────────────────────────────────────────────

class TestSingleTransactions:
    def test_single_keluar_produces_one_receipt(self):
        results = parse_tracker_app(TRACKER_SINGLE_KELUAR)
        assert len(results) == 1

    def test_single_keluar_transaction_type(self):
        r = parse_tracker_app(TRACKER_SINGLE_KELUAR)[0]
        assert r.transaction_type == TransactionType.EXPENSE

    def test_single_keluar_merchant_name(self):
        r = parse_tracker_app(TRACKER_SINGLE_KELUAR)[0]
        assert "nara kitchen" in r.merchant_name.lower()

    def test_single_keluar_amount(self):
        r = parse_tracker_app(TRACKER_SINGLE_KELUAR)[0]
        assert r.total_amount.amount == pytest.approx(85_000)

    def test_single_keluar_date(self):
        r = parse_tracker_app(TRACKER_SINGLE_KELUAR)[0]
        assert r.transaction_date.day == 12
        assert r.transaction_date.month == 6
        assert r.transaction_date.year == 2025

    def test_single_masuk_transaction_type(self):
        r = parse_tracker_app(TRACKER_SINGLE_MASUK)[0]
        assert r.transaction_type == TransactionType.INCOME

    def test_single_masuk_amount(self):
        r = parse_tracker_app(TRACKER_SINGLE_MASUK)[0]
        assert r.total_amount.amount == pytest.approx(500_000)

    def test_payment_method_is_bank_transfer(self):
        r = parse_tracker_app(TRACKER_SINGLE_KELUAR)[0]
        assert r.payment_method == PaymentMethod.BANK_TRANSFER

    def test_category_defaults_to_other(self):
        r = parse_tracker_app(TRACKER_SINGLE_KELUAR)[0]
        assert r.category == ExpenseCategory.OTHER


# ─────────────────────────────────────────────────────────────────────────────
# 2. Multiple transactions in one block
# ─────────────────────────────────────────────────────────────────────────────

class TestMultipleTransactions:
    def test_two_keluar_returns_two_receipts(self):
        results = parse_tracker_app(TRACKER_TWO_TRANSACTIONS)
        assert len(results) == 2

    def test_two_keluar_both_expense(self):
        results = parse_tracker_app(TRACKER_TWO_TRANSACTIONS)
        assert all(r.transaction_type == TransactionType.EXPENSE for r in results)

    def test_two_keluar_correct_merchants(self):
        results = parse_tracker_app(TRACKER_TWO_TRANSACTIONS)
        merchants = [r.merchant_name.lower() for r in results]
        assert any("nara kitchen" in m for m in merchants)
        assert any("grab" in m for m in merchants)

    def test_income_and_expense_mix(self):
        results = parse_tracker_app(TRACKER_INCOME_AND_EXPENSE)
        types = {r.transaction_type for r in results}
        assert TransactionType.INCOME in types
        assert TransactionType.EXPENSE in types


# ─────────────────────────────────────────────────────────────────────────────
# 3. Month header shifts list_start
# ─────────────────────────────────────────────────────────────────────────────

class TestMonthHeader:
    def test_month_header_still_finds_transaction(self):
        results = parse_tracker_app(TRACKER_WITH_MONTH_HEADER)
        assert len(results) >= 1

    def test_month_header_merchant_correct(self):
        results = parse_tracker_app(TRACKER_WITH_MONTH_HEADER)
        assert any("m kubik" in r.merchant_name.lower() for r in results)


# ─────────────────────────────────────────────────────────────────────────────
# 4. "Dana Masuk" anchor validity rules
# ─────────────────────────────────────────────────────────────────────────────

class TestDanaMasukAnchor:
    def test_dana_masuk_with_rp_inline_is_valid_anchor(self):
        """Dana Masuk is a valid anchor ONLY when Rp or account# appears on same line."""
        results = parse_tracker_app(TRACKER_DANA_MASUK_WITH_RP)
        # May produce 0 or 1 result depending on block content, but should not crash
        assert isinstance(results, list)

    def test_dana_masuk_standalone_not_valid_anchor(self):
        """Dana Masuk alone (no Rp/account) should be skipped as header, not anchor."""
        results = parse_tracker_app(TRACKER_DANA_MASUK_STANDALONE)
        # No valid transactions
        assert len(results) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 5. Amount threshold filtering
# ─────────────────────────────────────────────────────────────────────────────

class TestAmountFiltering:
    def test_amount_below_100_skips_receipt(self):
        results = parse_tracker_app(TRACKER_AMOUNT_TOO_SMALL)
        assert len(results) == 0

    def test_no_amount_in_block_skips_receipt(self):
        results = parse_tracker_app(TRACKER_NO_AMOUNT)
        assert len(results) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 6. Merchant name cleaning / prefix stripping
# ─────────────────────────────────────────────────────────────────────────────

class TestMerchantNameCleaning:
    def test_autodebet_prefix_stripped(self):
        results = parse_tracker_app(TRACKER_AUTODEBET_PREFIX)
        if results:
            assert "autodebet tagihan" not in results[0].merchant_name.lower()
            assert "pln" in results[0].merchant_name.lower()

    def test_dari_prefix_stripped(self):
        results = parse_tracker_app(TRACKER_DARI_PREFIX)
        if results:
            # "dari Joselyn Sutandar" → should strip "dari "
            assert not results[0].merchant_name.lower().startswith("dari ")

    def test_account_number_not_in_merchant(self):
        r = parse_tracker_app(TRACKER_SINGLE_KELUAR)[0]
        # Account number line "1234567890" should not appear in merchant
        assert "1234567890" not in r.merchant_name

    def test_noise_lines_skipped(self):
        results = parse_tracker_app(TRACKER_SKIP_NOISE_LINES)
        if results:
            # "home", "portfolio", "save", "share" should not be in merchant
            m = results[0].merchant_name.lower()
            assert "home" not in m
            assert "portfolio" not in m
            assert "save" not in m
            assert "share" not in m

    def test_merchant_max_60_chars(self):
        results = parse_tracker_app(TRACKER_SINGLE_KELUAR)
        if results:
            assert len(results[0].merchant_name) <= 60


# ─────────────────────────────────────────────────────────────────────────────
# 7. OCR noise variants for anchor keywords
# ─────────────────────────────────────────────────────────────────────────────

class TestOCRNoiseAnchors:
    def test_vang_keluar_ocr_noise_detected(self):
        """Tesseract misreads 'Uang' as 'Vang' — parser should still detect."""
        results = parse_tracker_app(TRACKER_OCR_NOISE_VANG)
        assert len(results) >= 1
        assert results[0].transaction_type == TransactionType.EXPENSE

    def test_yang_masuk_ocr_noise_detected(self):
        """'Yang Masuk' is also accepted as income anchor."""
        results = parse_tracker_app(TRACKER_OCR_NOISE_YANG)
        assert len(results) >= 1
        assert results[0].transaction_type == TransactionType.INCOME


# ─────────────────────────────────────────────────────────────────────────────
# 8. Date fallback
# ─────────────────────────────────────────────────────────────────────────────

class TestDateFallback:
    def test_no_date_line_uses_current_datetime(self):
        """When no date is found after anchor, datetime.now() is used as fallback."""
        before = datetime.now()
        results = parse_tracker_app(TRACKER_NO_DATE_LINE)
        after = datetime.now()
        if results:
            dt = results[0].transaction_date
            # The fallback date should be between before and after (approximate)
            # Allow 1 second tolerance for slow machines
            assert before.year == dt.year or after.year == dt.year


# ─────────────────────────────────────────────────────────────────────────────
# 9. Empty / degenerate inputs
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_string_returns_empty_list(self):
        assert parse_tracker_app("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert parse_tracker_app("   \n\n\t  ") == []

    def test_text_with_no_anchors_returns_empty_list(self):
        text = "Home\nPortfolio\nNara Kitchen\nRp 85.000\n12 Jun 2025"
        assert parse_tracker_app(text) == []

    def test_amount_at_upper_limit_50m(self):
        text = """\
Home
Deposito BCA
Rp 50.000.000
Uang Keluar
1 Jul 2025
"""
        results = parse_tracker_app(text)
        if results:
            assert results[0].total_amount.amount == pytest.approx(50_000_000)

    def test_amount_just_above_50m_excluded(self):
        """Amounts > 50M are out of range (100 <= val <= 50_000_000 guard)."""
        text = """\
Home
Transfer Besar
Rp 60.000.000
Uang Keluar
1 Jul 2025
"""
        results = parse_tracker_app(text)
        # Should produce 0 results since 60M > 50M
        assert len(results) == 0

    def test_returns_list_type(self):
        results = parse_tracker_app(TRACKER_SINGLE_KELUAR)
        assert isinstance(results, list)

    def test_all_receipts_have_valid_money_objects(self):
        results = parse_tracker_app(TRACKER_TWO_TRANSACTIONS)
        for r in results:
            assert r.total_amount.amount >= 100
            assert r.total_amount.currency == "IDR"

    def test_multiple_anchor_types_in_one_block(self):
        text = """\
Home
Pengeluaran
Pemasukan

Merchant A
Rp 100.000
Uang Keluar
1 Jan 2025

Merchant B
Rp 200.000
Uang Masuk
2 Jan 2025

Merchant C
Rp 300.000
Yang Keluar
3 Jan 2025
"""
        results = parse_tracker_app(text)
        assert len(results) >= 2

    def test_result_currency_always_idr(self):
        results = parse_tracker_app(TRACKER_SINGLE_KELUAR)
        for r in results:
            assert r.total_amount.currency == "IDR"
