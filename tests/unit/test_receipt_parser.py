"""
TDD R1: Test untuk packages/api/backend/ai/ai_rule_engine.py:rule_based_receipt_parse
dan class RuleBasedReceiptParser.

Tujuan:
1. Lock-in behavior existing SEBELUM refactor R1 (regression guard).
2. Setelah R1, hanya 1 import line yang berubah (dari ai_rule_engine ke receipt_parser).
3. Coverage minimum: happy path, unknown merchant, empty input, payment method,
   amount formatting IDR, callable public API.

Hermetic — no DB, no env, no OCR, no network. Pure regex/keyword test.
"""
from packages.api.backend.ai import receipt_parser as eng


def test_parse_alfamart_receipt_happy_path():
    """Indonesian minimarket receipt: merchant + amount + date detected."""
    text = (
        "ALFAMART\n"
        "Jl. Sudirman No. 1\n"
        "Total: Rp 45.000\n"
        "12/08/2024\n"
    )
    result = eng.rule_based_receipt_parse(text)
    assert result["merchant_name"] == "Alfamart"
    assert result["total_amount"] == 45000.0
    assert result["currency"] == "IDR"
    assert result["transaction_type"] == "expense"
    # Alfamart text has no category keyword → default 'other' is acceptable
    assert result["category"] in (
        "food", "transport", "shopping", "health",
        "entertainment", "education", "other",
    )
    # Confidence: amount>0 (0.55) + merchant (0.10) + date (0.10) = 0.75
    assert result["confidence"] == 0.75
    assert 0.0 <= result["confidence"] <= 0.85


def test_parse_grabfood_merchant_and_transport_category():
    """GrabFood keyword → merchant + transport category both detected."""
    text = (
        "GRAB\n"
        "Total Rp 25000\n"
        "12 agustus 2024\n"
    )
    result = eng.rule_based_receipt_parse(text)
    assert result["merchant_name"] == "GrabFood"
    assert result["total_amount"] == 25000.0
    assert result["category"] == "transport"  # "grab" in CATEGORY_KEYWORDS[transport]


def test_parse_empty_text_returns_safe_defaults():
    """Empty OCR text → no crash, sensible defaults."""
    result = eng.rule_based_receipt_parse("")
    assert result["merchant_name"] == "Unknown Merchant"
    assert result["total_amount"] == 0.0
    assert result["currency"] == "IDR"
    assert result["category"] == "other"
    assert result["payment_method"] == "cash"
    assert result["confidence"] == 0.30  # amount=0 → base 0.30
    assert result["transaction_type"] == "expense"
    assert result["items"] == []
    assert result["notes"] == ""


def test_parse_qris_payment_method_detected():
    """QRIS payment keyword in text → payment_method 'qris'."""
    text = (
        "TOKOPEDIA\n"
        "Total: Rp 150.000\n"
        "Pembayaran: QRIS\n"
        "01/09/2024\n"
    )
    result = eng.rule_based_receipt_parse(text)
    assert result["merchant_name"] == "Tokopedia"
    assert result["total_amount"] == 150000.0
    assert result["payment_method"] == "qris"


def test_parse_amount_with_thousands_separator():
    """IDR 'Rp 1.500.000' (with dots) parsed correctly, no false /1000."""
    text = (
        "HYpermart\n"
        "TOTAL Rp 1.500.000\n"
    )
    result = eng.rule_based_receipt_parse(text)
    assert result["merchant_name"] == "Hypermart"
    assert result["total_amount"] == 1500000.0
    # 1.5M < 1B threshold, so no /1000 division
    assert result["total_amount"] < 1_000_000_000


def test_parse_date_in_dmy_format_normalized_to_iso():
    """Date 25/12/2024 (DD/MM/YYYY) → transaction_date '2024-12-25'."""
    text = (
        "INDOMARET\n"
        "Total: Rp 50.000\n"
        "25/12/2024\n"
    )
    result = eng.rule_based_receipt_parse(text)
    assert result["merchant_name"] == "Indomaret"
    assert result["total_amount"] == 50000.0
    # Date format DD/MM/YYYY → ISO YYYY-MM-DD
    assert result["transaction_date"] == "2024-12-25"


def test_rule_based_receipt_parse_is_public_callable():
    """Public function (api_server.py / routers/ai.py call this) is callable."""
    assert callable(eng.rule_based_receipt_parse)
    # Sanity: function returns a dict with required schema keys
    required_keys = {
        "merchant_name", "transaction_date", "total_amount", "currency",
        "payment_method", "transaction_type", "category", "confidence",
        "items", "notes", "ai_analysis",
    }
    result = eng.rule_based_receipt_parse("KFC Rp 75.000")
    assert required_keys.issubset(result.keys())
    assert result["merchant_name"] == "KFC"


def test_provider_strategy_load_receipt_parser_path_based():
    """routers/ai.py accesses receipt parser via path-based loader.
    After R1, _load_receipt_parser() returns the standalone receipt_parser module
    (not the merged ai_rule_engine module). This verifies the lazy-loader works.
    """
    from packages.api.backend.ai import provider_strategy as _ps
    rp = _ps._load_receipt_parser()
    assert rp is not None
    assert hasattr(rp, "rule_based_receipt_parse")
    assert callable(rp.rule_based_receipt_parse)
    # Result via path-loaded module matches direct import
    result = rp.rule_based_receipt_parse("STARBUCKS Total Rp 120.000")
    assert result["merchant_name"] == "Starbucks"
    assert result["total_amount"] == 120000.0


def test_ai_rule_engine_no_longer_exposes_receipt_parse():
    """R1 moved rule_based_receipt_parse out of ai_rule_engine.
    Regression guard: any caller that still imports the old path will fail loudly.
    """
    from packages.api.backend.ai import ai_rule_engine as _are
    assert not hasattr(_are, "rule_based_receipt_parse"), (
        "rule_based_receipt_parse was moved to receipt_parser in R1; "
        "remove this guard if you intentionally re-added it."
    )
    assert not hasattr(_are, "RuleBasedReceiptParser"), (
        "RuleBasedReceiptParser was moved to receipt_parser in R1."
    )
