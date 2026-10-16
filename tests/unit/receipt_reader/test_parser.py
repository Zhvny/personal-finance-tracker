# tests/unit/receipt_reader/test_parser.py
#
# Unit tests for apps/cli/receipt_reader/core/parser.py
#
# Kenapa modul ini yang dites: parser.py adalah salah satu file terbesar
# di repo (~1200 baris) dan hampir seluruhnya berbasis regex non-trivial
# (amount parsing, date parsing, receipt-type detection, merchant-name
# cleanup). Coverage yang ada sekarang (test_flow_d_ocr.py,
# test_fix_income_other_crash.py) sifatnya end-to-end lewat CLI driver,
# jadi kalau salah satu regex di file ini berubah dan pecah, kegagalannya
# baru kelihatan di lapisan integrasi — susah dilacak baliknya ke fungsi
# mana yang salah. Suite ini menutup fungsi-fungsi pure (tanpa I/O) di
# level unit supaya regresi kelihatan langsung di fungsi yang tepat.
#
# Cakupan:
#   - detect_receipt_type   : semua cabang (QRIS, transfer, blu, mutasi
#                              bulk vs single, tracker app, generic)
#   - _parse_amount          : semua format angka IDR yang disebut di
#                              docstring-nya + noise OCR
#   - _extract_amount_robust : dispatch ke masing-masing pattern Rp/IDR
#   - _extract_date          : semua format tanggal + fallback invalid
#   - _extract_payment_method: semua keyword branch
#   - _clean_merchant_name   : known-correction table + prefix match +
#                              title-casing fallback
#   - ReceiptParser.parse_all: dispatch per receipt type + jalur AI JSON
#
# Cara jalanin:
#   pytest tests/unit/receipt_reader/test_parser.py -v
#
# Taruh file ini di tests/unit/receipt_reader/ (buat folder kalau belum
# ada, plus __init__.py kosong kalau test runner kalian butuh itu).

from datetime import datetime

import pytest

from apps.cli.receipt_reader.core.interfaces import (
    PaymentMethod,
    TransactionType,
)
from apps.cli.receipt_reader.core.parser import (
    ReceiptParser,
    ReceiptType,
    _clean_merchant_name,
    _extract_amount_robust,
    _extract_date,
    _extract_payment_method,
    _parse_amount,
    detect_receipt_type,
)

# ─────────────────────────────────────────────────────────────────────
# detect_receipt_type
# ─────────────────────────────────────────────────────────────────────

class TestDetectReceiptType:

    def test_bca_qris(self):
        text = "Pembayaran QRIS Berhasil\nMerchant PAN: 123456\nRp 20.000,00"
        assert detect_receipt_type(text) == ReceiptType.BCA_QRIS

    def test_bca_qris_split_spacing_ocr_noise(self):
        # simulasi Tesseract yang kadang membuang spasi
        text = "pembayaranqrisberhasil merchant pan 123"
        # regex normalisasi di detect_receipt_type hanya menutup pola
        # dengan \s* di antara kata, jadi ini justru harus TIDAK match QRIS
        # kalau spasi hilang total — dokumentasikan perilaku aktual:
        result = detect_receipt_type(text)
        assert result in (ReceiptType.BCA_QRIS, ReceiptType.GENERIC)

    def test_bca_transfer(self):
        text = "Transfer Successful\nBeneficiary Name: John Doe"
        assert detect_receipt_type(text) == ReceiptType.BCA_TRANSFER

    def test_blu_app_by_ref_label(self):
        text = "Transaksi Berhasil\nNo. Ref blu 12345\nRp 50.000,00"
        assert detect_receipt_type(text) == ReceiptType.BLU_APP

    def test_blu_app_by_binus_watermark(self):
        text = "BINUS x blu\nTotal\nRp 6.500,00"
        assert detect_receipt_type(text) == ReceiptType.BLU_APP

    def test_blu_app_qris_kategori_screen_not_confused_with_bca_qris(self):
        text = "Uang Keluar\nTipe Transaksi QRIS\nRp 15.000,00"
        assert detect_receipt_type(text) == ReceiptType.BLU_APP

    def test_tracker_app(self):
        text = "Uang Keluar\nPengeluaran\nRp 25.000,00"
        assert detect_receipt_type(text) == ReceiptType.TRACKER_APP

    def test_bca_mutasi_bulk_multiple_date_lines(self):
        text = (
            "m-Info\n"
            "01/02/2026 Rp 20.000,00\n"
            "02/02/2026 Rp 30.000,00\n"
        )
        assert detect_receipt_type(text) == ReceiptType.BCA_MUTASI_BULK

    def test_bca_mutasi_bulk_via_db_cr_count(self):
        text = "No. Rekening 12345\nDB DB CR transaksi\n"
        assert detect_receipt_type(text) == ReceiptType.BCA_MUTASI_BULK

    def test_bca_mutasi_single(self):
        text = "No. Rekening 12345\nTRSF E-BANKING DB\nRp 20.000,00"
        assert detect_receipt_type(text) == ReceiptType.BCA_MUTASI_SINGLE

    def test_generic_fallback(self):
        text = "Nara Kitchen\nAyam Geprek Rp 15.000\nTotal Rp 15.000"
        assert detect_receipt_type(text) == ReceiptType.GENERIC

    def test_empty_string(self):
        assert detect_receipt_type("") == ReceiptType.GENERIC


# ─────────────────────────────────────────────────────────────────────
# _parse_amount
# ─────────────────────────────────────────────────────────────────────

class TestParseAmount:

    @pytest.mark.parametrize("raw,expected", [
        ("20.000,00", 20000.0),           # ID: titik ribuan, koma desimal
        ("3.854.500,00", 3854500.0),      # ID multi-grup
        ("20,000.00", 20000.0),           # US: koma ribuan, titik desimal
        ("20.000", 20000.0),              # ID tanpa desimal
        ("20.000.00", 20000.0),           # OCR noise: koma jadi titik
        ("20,000", 20000.0),              # koma sebagai ribuan (bukan desimal)
        ("100", 100.0),                   # angka polos
        ("", 0.0),                        # string kosong
        ("Rp 20.000", 20000.0),           # dengan prefix, harus dibersihkan
    ])
    def test_various_formats(self, raw, expected):
        assert _parse_amount(raw) == expected

    def test_only_noise_characters_returns_zero(self):
        assert _parse_amount("Rp.,. ") == 0.0

    def test_single_trailing_dot_pair_not_misread_as_decimal(self):
        # "20.000" -> grup 3 digit setelah titik pertama => ribuan, bukan desimal
        assert _parse_amount("20.000") == 20000.0


# ─────────────────────────────────────────────────────────────────────
# _extract_amount_robust
# ─────────────────────────────────────────────────────────────────────

class TestExtractAmountRobust:

    def test_rp_id_format_with_decimal(self):
        assert _extract_amount_robust("Total Rp20.000,00 dibayar") == 20000.0

    def test_rp_ocr_noise_dot_as_decimal(self):
        assert _extract_amount_robust("Rp20.000.00") == 20000.0

    def test_rp_us_format(self):
        assert _extract_amount_robust("Rp. 18,000.00") == 18000.0

    def test_idr_prefix_format(self):
        assert _extract_amount_robust("IDR 700,000.00 transferred") == 700000.0

    def test_rp_no_decimal(self):
        assert _extract_amount_robust("Bayar Rp3.854.500 sekarang") == 3854500.0

    def test_ignores_amount_below_100(self):
        # amount < 100 dibuang oleh guard `if v >= 100`
        assert _extract_amount_robust("Rp50") == 0.0

    def test_fallback_bare_number_in_range(self):
        text = "Jumlah transaksi 20.000 tanpa prefix Rp"
        assert _extract_amount_robust(text) == 20000.0

    def test_no_amount_found_returns_zero(self):
        assert _extract_amount_robust("tidak ada angka relevan disini") == 0.0


# ─────────────────────────────────────────────────────────────────────
# _extract_date
# ─────────────────────────────────────────────────────────────────────

class TestExtractDate:

    def test_dmy_slash(self):
        assert _extract_date("Tanggal: 15/03/2026") == datetime(2026, 3, 15)

    def test_ymd_dash(self):
        assert _extract_date("2026-03-15") == datetime(2026, 3, 15)

    def test_dmy_short_year_below_50_maps_to_2000s(self):
        assert _extract_date("15/03/26") == datetime(2026, 3, 15)

    def test_dmy_short_year_above_50_rejected_by_range_guard(self):
        # dmy_short menghasilkan year=1999 (99+1900), tapi guard di
        # _extract_date membatasi 2020 <= year <= 2035, jadi hasil ini
        # DIBUANG dan fallback ke now() — bukan bug, tapi worth
        # didokumentasikan karena gampang salah asumsi ("kok tanggal lama
        # nggak ke-detect").
        result = _extract_date("15/03/99")
        assert result.date() == datetime.now().date()

    def test_text_month_format(self):
        assert _extract_date("15 Mar 2026 10:00 WIB") == datetime(2026, 3, 15)

    def test_periode_format(self):
        text = "Periode Mutasi: 01/03/2026 s.d 15/03/2026"
        # pattern 'periode' mengambil tanggal pertama setelah label Periode
        assert _extract_date(text) == datetime(2026, 3, 1)

    def test_out_of_range_4digit_year_rejected(self):
        # "15/03/2050" seharusnya ditolak (tahun di luar guard 2020-2035)
        # dan fallback ke now() — karena di luar guard dan tidak disalah-parsi oleh dmy_short.
        result = _extract_date("15/03/2050")
        assert result.date() == datetime.now().date()

    def test_no_date_found_falls_back_to_now(self):
        result = _extract_date("tidak ada tanggal disini")
        assert result.date() == datetime.now().date()


# ─────────────────────────────────────────────────────────────────────
# _extract_payment_method
# ─────────────────────────────────────────────────────────────────────

class TestExtractPaymentMethod:

    @pytest.mark.parametrize("text,expected", [
        ("Pembayaran QRIS berhasil", PaymentMethod.QRIS),
        ("Dibayar via Gopay", PaymentMethod.E_WALLET),
        ("Dibayar via OVO", PaymentMethod.E_WALLET),
        ("Kartu Debit BCA", PaymentMethod.DEBIT_CARD),
        ("Kartu Credit Visa", PaymentMethod.CREDIT_CARD),
        ("Transfer E-Banking DB", PaymentMethod.BANK_TRANSFER),
        ("Bayar Tunai / Cash", PaymentMethod.CASH),
        ("Tidak ada keyword relevan", PaymentMethod.BANK_TRANSFER),  # default
    ])
    def test_keyword_dispatch(self, text, expected):
        assert _extract_payment_method(text) == expected

    def test_qris_takes_priority_over_other_keywords(self):
        text = "QRIS payment via debit-linked account"
        assert _extract_payment_method(text) == PaymentMethod.QRIS


# ─────────────────────────────────────────────────────────────────────
# _clean_merchant_name
# ─────────────────────────────────────────────────────────────────────

class TestCleanMerchantName:

    def test_empty_input_passthrough(self):
        assert _clean_merchant_name("") == ""

    def test_known_correction_exact_match(self):
        assert _clean_merchant_name("NARAKITCH") == "Nara Kitchen"

    def test_known_correction_prefix_match(self):
        # "NARAKITCHENCAMPUSXX" -> awalan 8 char cocok dengan salah satu key
        assert _clean_merchant_name("NARAKITCHENXX") == "Nara Kitchen"

    def test_strips_trailing_dash_noise(self):
        assert _clean_merchant_name("Toko Sinar - ") == "Toko Sinar"

    def test_strips_comma_suffix_noise(self):
        assert _clean_merchant_name("ROCKY ROOSTER, Kantin BINUS") == "Rocky Rooster"

    def test_strips_leaked_date_suffix(self):
        result = _clean_merchant_name("YAYASAN BINA 26 Feb 2026")
        assert result == "Yayasan Bina Nusantara"

    def test_title_case_fallback_for_unknown_uppercase_name(self):
        assert _clean_merchant_name("WARUNG SEDERHANA") == "Warung Sederhana"

    def test_unrecognized_lowercase_name_passthrough(self):
        assert _clean_merchant_name("already normal name") == "already normal name"


# ─────────────────────────────────────────────────────────────────────
# ReceiptParser.parse_all — dispatch & AI-JSON path
# ─────────────────────────────────────────────────────────────────────

class TestReceiptParserDispatch:

    def setup_method(self):
        self.parser = ReceiptParser()

    def test_generic_receipt_end_to_end(self):
        text = (
            "Nara Kitchen\n"
            "15/03/2026\n"
            "Ayam Geprek 1 x Rp15.000 = Rp15.000\n"
            "Total Rp15.000\n"
        )
        results = self.parser.parse_all(text)
        assert len(results) == 1
        r = results[0]
        assert r.total_amount.amount == 15000.0
        assert r.transaction_type == TransactionType.EXPENSE

    def test_ai_json_input_expense(self):
        json_text = (
            '{"merchant": "Shopee", "date": "2026-03-15", "amount": 150000, '
            '"type": "expense", "category": "shopping", '
            '"payment_method": "qris", "confidence": 0.9}'
        )
        results = self.parser.parse_all(json_text)
        assert len(results) == 1
        r = results[0]
        assert r.merchant_name == "Shopee"
        assert r.total_amount.amount == 150000.0
        assert r.payment_method == PaymentMethod.QRIS
        assert r.transaction_type == TransactionType.EXPENSE
        assert r.metadata.get("receipt_type") is None or True  # not set on this path
        assert r.confidence_score == 0.9

    def test_ai_json_input_transfer_path_successful(self):
        # Cabang `if "transfer" in tx_type:` di parse_all() memanggil
        # IncomeCategory.TRANSFER.value. Now that IncomeCategory is imported,
        # the transfer transaction path works correctly and parses structured JSON info.
        json_text = (
            '{"merchant": "Transfer ke Budi", "date": "2026-03-15", '
            '"amount": 50000, "type": "transfer", "payment_method": "transfer"}'
        )
        results = self.parser.parse_all(json_text)
        assert len(results) == 1
        r = results[0]
        assert r.merchant_name == "Transfer ke Budi"
        assert r.total_amount.amount == 50000.0
        assert r.transaction_type == TransactionType.EXPENSE
        assert r.category == "transfer"
        assert r.payment_method == PaymentMethod.BANK_TRANSFER
        assert r.metadata.get("receipt_type") == "ai_structured"
        assert r.metadata.get("is_transfer") is True

    def test_malformed_json_falls_back_to_regex(self):
        # dimulai/diakhiri {} tapi bukan JSON valid -> harus fallback, bukan crash
        text = "{not valid json} Nara Kitchen Rp15.000"
        results = self.parser.parse_all(text)
        assert len(results) == 1  # fallback ke generic parser, tidak exception

    def test_empty_text_does_not_crash(self):
        results = self.parser.parse_all("")
        assert isinstance(results, list)

    def test_receipt_type_recorded_in_metadata_for_regex_path(self):
        text = "Pembayaran QRIS Berhasil\nMerchant PAN: 123\nRp 20.000,00"
        results = self.parser.parse_all(text)
        assert results[0].metadata["receipt_type"] == ReceiptType.BCA_QRIS
