# tests/unit/receipt_reader/test_parser_bulk_stateful.py
#
# Stateful and bulk parsing tests for apps/cli/receipt_reader/core/parser.py
# Covers: _find_merchant_bulk, _extract_from_ref, parse_bulk_mutasi, and _parse_blu_app

from datetime import datetime

from apps.cli.receipt_reader.core.interfaces import (
    ExpenseCategory,
    PaymentMethod,
    TransactionType,
)
from apps.cli.receipt_reader.core.parser import (
    ReceiptParser,
    _extract_from_ref,
    _find_merchant_bulk,
    parse_bulk_mutasi,
)

# ─────────────────────────────────────────────────────────────────────
# _extract_from_ref
# ─────────────────────────────────────────────────────────────────────

class TestExtractFromRef:

    def test_extract_wallet_name(self):
        assert _extract_from_ref("0502/FTFVA/WS95039358/OVO") == "OVO"
        assert _extract_from_ref("0502/FTFVA/WS95039358/GOPAY") == "GOPAY"

    def test_extract_merchant_with_spaces(self):
        assert _extract_from_ref("0402/FTSCY/WS95031  RATNAWATI SANTOSO  CR") == "RATNAWATI SANTOSO"

    def test_extract_no_merchant(self):
        assert _extract_from_ref("2002/FTSCY/WS95031 DB") == ""

    def test_extract_single_space_merchant(self):
        assert _extract_from_ref("0402/FTSCY/WS95031 RATNAWATI") == "RATNAWATI"

    def test_invalid_ref_format_returns_empty(self):
        assert _extract_from_ref("not-a-ref-line") == ""


# ─────────────────────────────────────────────────────────────────────
# _find_merchant_bulk
# ─────────────────────────────────────────────────────────────────────

class TestFindMerchantBulk:

    def test_normal_merchant_extraction(self):
        lines = [
            "05/02/2026",
            "Rp. 20.000,00",
            "NARA KITCHEN",
            "DB"
        ]
        assert _find_merchant_bulk(lines, 0) == "NARA KITCHEN"

    def test_ref_code_extraction(self):
        lines = [
            "05/02/2026",
            "0402/FTSCY/WS95031  RATNAWATI SANTOSO  CR"
        ]
        assert _find_merchant_bulk(lines, 0) == "RATNAWATI SANTOSO"

    def test_leaked_next_date_stops_search(self):
        lines = [
            "05/02/2026",
            "Rp. 20,000.00",
            "06/02/2026 NARA KITCHEN",
            "SOME OTHER MERCHANT"
        ]
        assert _find_merchant_bulk(lines, 0) == "Unknown"

    def test_noise_reduction_digit_ratio(self):
        lines = [
            "05/02/2026",
            "9823984729384729"
        ]
        assert _find_merchant_bulk(lines, 0) == "Unknown"

    def test_solitary_db_cr_ignored(self):
        lines = [
            "05/02/2026",
            "DB",
            "NARA KITCHEN"
        ]
        assert _find_merchant_bulk(lines, 0) == "NARA KITCHEN"


# ─────────────────────────────────────────────────────────────────────
# parse_bulk_mutasi
# ─────────────────────────────────────────────────────────────────────

class TestParseBulkMutasi:

    def test_format_a_expense(self):
        text = (
            "m-Info\n"
            "05/02/2026 Rp. 25,000.00 DB\n"
            "0502/FTSCY/WS95031  NARA KITCHEN  DB"
        )
        results = parse_bulk_mutasi(text)
        assert len(results) == 1
        r = results[0]
        assert r.merchant_name == "Nara Kitchen"
        assert r.total_amount.amount == 25000.0
        assert r.transaction_type == TransactionType.EXPENSE
        assert r.category == ExpenseCategory.FOOD

    def test_format_a_income_trusted_person(self):
        text = (
            "m-Info\n"
            "05/02/2026 Rp. 100,000.00 CR\n"
            "0502/FTSCY/WS95031  RATNAWATI SANTOSO  CR"
        )
        results = parse_bulk_mutasi(text)
        assert len(results) == 1
        r = results[0]
        assert r.merchant_name == "Ratnawati Santoso"
        assert r.total_amount.amount == 100000.0
        assert r.transaction_type == TransactionType.INCOME
        assert r.metadata.get("description_hint") == "Pocket Money"

    def test_format_b_qris_expense(self):
        text = (
            "TGL: 2602  QR 022  DB\n"
            "15000.00NARA KITCHEN"
        )
        results = parse_bulk_mutasi(text)
        assert len(results) == 1
        r = results[0]
        assert r.merchant_name == "Nara Kitchen"
        assert r.total_amount.amount == 15000.0
        assert r.transaction_type == TransactionType.EXPENSE
        assert r.payment_method == PaymentMethod.QRIS
        assert r.transaction_date.day == 26
        assert r.transaction_date.month == 2
        assert r.transaction_date.year == datetime.now().year

    def test_format_b_qris_income(self):
        text = (
            "TGL: 2602  QR 022  CR\n"
            "15000.00NARA KITCHEN"
        )
        results = parse_bulk_mutasi(text)
        assert len(results) == 1
        r = results[0]
        assert r.transaction_type == TransactionType.INCOME


# ─────────────────────────────────────────────────────────────────────
# ReceiptParser._parse_blu_app
# ─────────────────────────────────────────────────────────────────────

class TestParseBluApp:

    def test_blu_qris_payment_via_parse_all(self):
        text = (
            "BINUS x blu\n"
            "Transaksi Berhasil\n"
            "Tipe Transaksi QRIS\n"
            "Rp 12.500,00\n"
            "26 Feb 2026\n"
            "No. Ref blu 987654\n"
            "Stay Refreshed\n"
            "Kota Tangerang"
        )
        parser = ReceiptParser()
        results = parser.parse_all(text)
        assert len(results) == 1
        r = results[0]
        assert r.merchant_name == "Stay Refreshed"
        assert r.total_amount.amount == 12500.0
        assert r.payment_method == PaymentMethod.QRIS
        assert r.transaction_type == TransactionType.EXPENSE
        assert r.transaction_date == datetime(2026, 2, 26)

    def test_blu_bill_payment_via_direct_call(self):
        text = (
            "Transaksi Berhasil\n"
            "Tipe Transaksi Bayar Tagihan\n"
            "Rp 150.000,00\n"
            "01 Mar 2026\n"
            "No. Ref blu 987655\n"
            "BUBLU82SEIL\n"
            "Jakarta Pusat"
        )
        parser = ReceiptParser()
        # Direct call to _parse_blu_app
        r = parser._parse_blu_app(text, text)
        assert r.merchant_name == "Stay Refreshed" # verified BUBLU82SEIL mapping
        assert r.total_amount.amount == 150000.0
        assert r.payment_method == PaymentMethod.E_WALLET
        assert r.transaction_date == datetime(2026, 3, 1)
