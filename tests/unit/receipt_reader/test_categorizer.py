"""
tests/unit/receipt_reader/test_categorizer.py
=============================================
Unit tests for UniversalCategorizer (categorizer.py) — 0% → target ≥80% coverage.

Covers:
  - classify()  : transfer guard, user-defined rules, metadata hints, income/expense routing
  - classify_item() : per-item classification
  - _detect_transaction_type()
  - _classify_expense_universal()
  - _classify_income()
  - _score_patterns()
  - _analyze_merchant_structure()
  - _score_amount()
  - _analyze_context()
  - _get_matched_keywords()
  - _generate_reasoning()
"""

from datetime import datetime

import pytest

from apps.cli.receipt_reader.core.categorizer import ClassificationResult, UniversalCategorizer
from apps.cli.receipt_reader.core.interfaces import (
    ExpenseCategory,
    IncomeCategory,
    Money,
    ReceiptData,
    TransactionType,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_receipt(
    merchant: str = "Test Merchant",
    amount: float = 50_000,
    ocr_text: str = "",
    tx_date: datetime | None = None,
    metadata: dict | None = None,
) -> ReceiptData:
    return ReceiptData(
        merchant_name=merchant,
        total_amount=Money(amount, "IDR"),
        raw_ocr_text=ocr_text,
        transaction_date=tx_date or datetime(2025, 6, 15, 12, 0, 0),
        metadata=metadata or {},
    )


@pytest.fixture
def cat() -> UniversalCategorizer:
    return UniversalCategorizer()


# ─────────────────────────────────────────────────────────────────────────────
# 1. classify() — Transfer Guard (Step 0, highest priority)
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyTransferGuard:
    def test_transfer_keyword_in_merchant(self, cat):
        r = make_receipt(merchant="Transfer BCA", ocr_text="pembayaran")
        result = cat.classify(r)
        assert result.category == IncomeCategory.TRANSFER
        assert result.confidence == pytest.approx(0.98)
        assert result.method == "banking_logic"

    def test_transfer_keyword_in_ocr_text(self, cat):
        r = make_receipt(merchant="Unknown", ocr_text="Top Up Dana berhasil")
        result = cat.classify(r)
        assert result.category == IncomeCategory.TRANSFER

    def test_trf_abbreviation_triggers_transfer(self, cat):
        r = make_receipt(merchant="trf ke rekening", ocr_text="")
        result = cat.classify(r)
        assert result.category == IncomeCategory.TRANSFER

    def test_transfer_result_has_matched_keywords(self, cat):
        r = make_receipt(merchant="", ocr_text="transfer masuk hari ini")
        result = cat.classify(r)
        assert len(result.matched_keywords) > 0


# ─────────────────────────────────────────────────────────────────────────────
# 2. classify() — User-defined food merchants (Step 1)
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyUserDefinedRules:
    @pytest.mark.parametrize("merchant", [
        "M Kubik", "mkubik", "Nara Kitchen", "ballin kitchen", "Stay Refreshed", "Rasela"
    ])
    def test_user_food_merchants(self, cat, merchant):
        r = make_receipt(merchant=merchant, ocr_text="")
        result = cat.classify(r)
        assert result.category == ExpenseCategory.FOOD
        assert result.confidence == pytest.approx(1.0)
        assert result.method == "user_defined_rule"

    @pytest.mark.parametrize("person", [
        "Ratnawati Santoso", "Joselyn", "Ardiyanto"
    ])
    def test_user_income_people(self, cat, person):
        r = make_receipt(merchant=person, ocr_text="")
        result = cat.classify(r)
        assert result.category == IncomeCategory.OTHER
        assert result.confidence == pytest.approx(1.0)
        assert r.transaction_type == TransactionType.INCOME

    def test_metadata_hint_pocket_money(self, cat):
        r = make_receipt(merchant="Unknown", metadata={"description_hint": "Pocket Money"})
        result = cat.classify(r)
        assert result.category == IncomeCategory.OTHER
        assert result.method == "metadata_hint"
        assert r.transaction_type == TransactionType.INCOME

    def test_metadata_hint_case_insensitive(self, cat):
        r = make_receipt(merchant="X", metadata={"description_hint": "pocket money"})
        result = cat.classify(r)
        assert result.category == IncomeCategory.OTHER


# ─────────────────────────────────────────────────────────────────────────────
# 3. classify() — Income detection routing
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyIncomeRouting:
    def test_received_keyword_routes_to_income_path(self, cat):
        r = make_receipt(merchant="BCA", ocr_text="Dana diterima dari klien")
        result = cat.classify(r)
        # Should route through _classify_income
        assert result.category in list(IncomeCategory)

    def test_salary_income_classification(self, cat):
        r = make_receipt(merchant="PT ABC", ocr_text="gaji bulanan payroll transfer")
        result = cat.classify(r)
        # Force income routing: patch detect_transaction_type
        r2 = make_receipt(merchant="PT ABC", ocr_text="salary gaji monthly payroll incoming")
        r2.transaction_type = TransactionType.INCOME
        result2 = cat._classify_income(r2)
        assert result2.category == IncomeCategory.SALARY

    def test_freelance_income_classification(self, cat):
        r = make_receipt(merchant="", ocr_text="freelance project consultation jasa")
        r.transaction_type = TransactionType.INCOME
        result = cat._classify_income(r)
        assert result.category == IncomeCategory.FREELANCE

    def test_investment_income_classification(self, cat):
        r = make_receipt(merchant="", ocr_text="dividend interest bunga return")
        r.transaction_type = TransactionType.INCOME
        result = cat._classify_income(r)
        assert result.category == IncomeCategory.INVESTMENT

    def test_side_hustle_income_classification(self, cat):
        r = make_receipt(merchant="", ocr_text="side sampingan part time reseller")
        r.transaction_type = TransactionType.INCOME
        result = cat._classify_income(r)
        assert result.category == IncomeCategory.SIDE_HUSTLE

    def test_transfer_income_classification(self, cat):
        # If we somehow reach _classify_income with transfer keywords:
        r = make_receipt(merchant="", ocr_text="transfer masuk trf")
        r.transaction_type = TransactionType.INCOME
        result = cat._classify_income(r)
        assert result.category == IncomeCategory.TRANSFER

    def test_unknown_income_defaults_to_other(self, cat):
        r = make_receipt(merchant="Random", ocr_text="masuk saldo")
        r.transaction_type = TransactionType.INCOME
        result = cat._classify_income(r)
        assert result.category == IncomeCategory.OTHER

    def test_income_result_confidence_capped_at_1(self, cat):
        # With 3+ keywords, confidence should cap at 1.0
        r = make_receipt(merchant="", ocr_text="salary gaji monthly payroll")
        r.transaction_type = TransactionType.INCOME
        result = cat._classify_income(r)
        assert result.confidence <= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# 4. _detect_transaction_type()
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectTransactionType:
    def test_diterima_is_income(self, cat):
        r = make_receipt(ocr_text="dana telah diterima")
        assert cat._detect_transaction_type(r) == TransactionType.INCOME

    def test_received_is_income(self, cat):
        r = make_receipt(ocr_text="payment received confirmation")
        assert cat._detect_transaction_type(r) == TransactionType.INCOME

    def test_transfer_masuk_is_income(self, cat):
        r = make_receipt(ocr_text="transfer masuk ke rekening")
        assert cat._detect_transaction_type(r) == TransactionType.INCOME

    def test_pembayaran_berhasil_is_expense(self, cat):
        r = make_receipt(ocr_text="pembayaran berhasil Rp50000")
        assert cat._detect_transaction_type(r) == TransactionType.EXPENSE

    def test_bayar_is_expense(self, cat):
        r = make_receipt(ocr_text="bayar tagihan listrik checkout paid")
        assert cat._detect_transaction_type(r) == TransactionType.EXPENSE

    def test_neutral_defaults_to_expense(self, cat):
        r = make_receipt(merchant="Coffee Shop", ocr_text="americano")
        result = cat._detect_transaction_type(r)
        # With no strong signals, defaults to EXPENSE
        assert result == TransactionType.EXPENSE

    def test_income_keywords_in_merchant_count(self, cat):
        r = make_receipt(merchant="gaji bonus dari income", ocr_text="")
        assert cat._detect_transaction_type(r) == TransactionType.INCOME


# ─────────────────────────────────────────────────────────────────────────────
# 5. _score_patterns()
# ─────────────────────────────────────────────────────────────────────────────

class TestScorePatterns:
    def test_returns_zero_for_empty_text(self, cat):
        patterns = {"words": ["nasi", "ayam"]}
        assert cat._score_patterns("", patterns) == 0

    def test_keyword_hit_adds_score(self, cat):
        patterns = {"food_types": ["nasi", "ayam"]}
        score = cat._score_patterns("nasi goreng", patterns)
        assert score > 0

    def test_word_boundary_bonus(self, cat):
        # "\b" regex gives extra points for whole word match
        patterns = {"words": ["rice"]}
        score_exact = cat._score_patterns("I ate rice today", patterns)
        score_partial = cat._score_patterns("pricelist", patterns)
        # "rice" as whole word should score >= partial
        assert score_exact >= score_partial

    def test_multiple_keywords_add_up(self, cat):
        patterns = {"words": ["nasi", "ayam", "mie"]}
        score = cat._score_patterns("nasi ayam mie goreng", patterns)
        assert score > cat._score_patterns("nasi goreng", patterns)


# ─────────────────────────────────────────────────────────────────────────────
# 6. _analyze_merchant_structure()
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzeMerchantStructure:
    def test_kitchen_merchant_scores_food(self, cat):
        scores = cat._analyze_merchant_structure("nara kitchen")
        assert scores[ExpenseCategory.FOOD] > 0

    def test_gojek_scores_transport(self, cat):
        scores = cat._analyze_merchant_structure("gojek order")
        assert scores[ExpenseCategory.TRANSPORT] > 0

    def test_mart_scores_shopping(self, cat):
        scores = cat._analyze_merchant_structure("indomaret supermart")
        assert scores[ExpenseCategory.SHOPPING] > 0

    def test_unknown_merchant_all_zeros(self, cat):
        scores = cat._analyze_merchant_structure("xyzabc123")
        assert all(v == 0.0 for v in scores.values())


# ─────────────────────────────────────────────────────────────────────────────
# 7. _score_amount()
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreAmount:
    def test_food_typical_amount_gets_score(self, cat):
        # Food: 5000-500000; midrange 50k should score well
        scores = cat._score_amount(50_000)
        assert scores[ExpenseCategory.FOOD] > 0

    def test_housing_large_amount_gets_score(self, cat):
        scores = cat._score_amount(2_000_000)
        assert scores[ExpenseCategory.HOUSING] > 0

    def test_out_of_range_amount_scores_zero(self, cat):
        # 1 IDR is below all ranges → should score 0 for food
        scores = cat._score_amount(1)
        assert scores[ExpenseCategory.FOOD] == 0.0

    def test_scores_are_non_negative(self, cat):
        scores = cat._score_amount(100_000)
        assert all(v >= 0 for v in scores.values())

    def test_center_amount_scores_higher_than_edge(self, cat):
        # Transport: 3000-200000, center ≈ 101500
        center_score = cat._score_amount(101_500)[ExpenseCategory.TRANSPORT]
        edge_score = cat._score_amount(3_001)[ExpenseCategory.TRANSPORT]
        assert center_score >= edge_score


# ─────────────────────────────────────────────────────────────────────────────
# 8. _analyze_context()
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzeContext:
    def test_lunch_hour_boosts_food(self, cat):
        r = make_receipt(tx_date=datetime(2025, 6, 1, 13, 0, 0))
        scores = cat._analyze_context(r)
        assert scores[ExpenseCategory.FOOD] >= 3

    def test_breakfast_commute_hour_boosts_transport(self, cat):
        r = make_receipt(tx_date=datetime(2025, 6, 1, 8, 0, 0))
        scores = cat._analyze_context(r)
        assert scores[ExpenseCategory.TRANSPORT] >= 2

    def test_evening_boosts_food_and_entertainment(self, cat):
        r = make_receipt(tx_date=datetime(2025, 6, 1, 19, 0, 0))
        scores = cat._analyze_context(r)
        assert scores[ExpenseCategory.FOOD] >= 2
        assert scores[ExpenseCategory.ENTERTAINMENT] >= 2

    def test_qris_in_text_boosts_food_and_transport(self, cat):
        r = make_receipt(ocr_text="QRIS payment confirmed", tx_date=datetime(2025, 6, 1, 15, 0))
        scores = cat._analyze_context(r)
        assert scores[ExpenseCategory.FOOD] >= 1
        assert scores[ExpenseCategory.TRANSPORT] >= 1

    def test_midday_non_food_hour(self, cat):
        # 3pm = hour 15 — no special boost, all zeros
        r = make_receipt(tx_date=datetime(2025, 6, 1, 15, 0, 0), ocr_text="random text")
        scores = cat._analyze_context(r)
        # All zero since no special time slot or qris
        assert scores[ExpenseCategory.FOOD] == 0
        assert scores[ExpenseCategory.ENTERTAINMENT] == 0

    def test_no_transaction_date_defaults_to_hour_12(self, cat):
        r = ReceiptData(
            merchant_name="Test",
            total_amount=Money(50_000, "IDR"),
            raw_ocr_text="",
            transaction_date=None,  # type: ignore
            metadata={},
        )
        # Should not raise; hour fallback = 12 → food boost
        scores = cat._analyze_context(r)
        assert scores[ExpenseCategory.FOOD] >= 3


# ─────────────────────────────────────────────────────────────────────────────
# 9. _classify_expense_universal()
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyExpenseUniversal:
    def test_food_merchant_and_text_classifies_food(self, cat):
        r = make_receipt(
            merchant="Nara Kitchen",
            ocr_text="nasi goreng ayam bakar menu makan siang restaurant",
            amount=45_000,
            tx_date=datetime(2025, 6, 1, 13, 0),
        )
        result = cat._classify_expense_universal(r)
        # Should classify as FOOD (high linguistic score)
        assert result.category == ExpenseCategory.FOOD
        assert result.method == "universal_multi_factor"

    def test_low_confidence_returns_other(self, cat):
        # A completely ambiguous receipt with no keywords
        r = make_receipt(merchant="XYZ", ocr_text="abc 123", amount=1)
        result = cat._classify_expense_universal(r)
        assert result.category == ExpenseCategory.OTHER
        assert result.confidence == pytest.approx(0.3)

    def test_transport_fuel_classifies_transport(self, cat):
        r = make_receipt(
            merchant="Pertamina Shell",
            ocr_text="bensin solar fuel petrol full tank",
            amount=100_000,
        )
        result = cat._classify_expense_universal(r)
        assert result.category == ExpenseCategory.TRANSPORT

    def test_result_has_all_required_fields(self, cat):
        r = make_receipt(merchant="Store", ocr_text="beli baju sepatu tas diskon")
        result = cat._classify_expense_universal(r)
        assert isinstance(result, ClassificationResult)
        assert result.method == "universal_multi_factor"
        assert isinstance(result.matched_keywords, list)
        assert isinstance(result.reasoning, str)

    def test_health_keywords_classify_health(self, cat):
        r = make_receipt(
            merchant="Apotek Kimia Farma",
            ocr_text="obat tablet vitamin apotek pharmacy dokter periksa",
            amount=75_000,
        )
        result = cat._classify_expense_universal(r)
        assert result.category == ExpenseCategory.HEALTH

    def test_education_keywords_classify_education(self, cat):
        r = make_receipt(
            merchant="Kampus",
            ocr_text="uang sekolah tuition biaya pendaftaran buku textbook kursus",
            amount=500_000,
        )
        result = cat._classify_expense_universal(r)
        assert result.category == ExpenseCategory.EDUCATION


# ─────────────────────────────────────────────────────────────────────────────
# 10. classify_item()
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyItem:
    def test_food_item_classified(self, cat):
        result = cat.classify_item("nasi goreng spesial")
        assert result == ExpenseCategory.FOOD

    def test_transport_item_classified(self, cat):
        result = cat.classify_item("bensin full tank motor")
        assert result == ExpenseCategory.TRANSPORT

    def test_no_match_returns_none(self, cat):
        result = cat.classify_item("zxqwqw")
        assert result is None

    def test_health_item_classified(self, cat):
        result = cat.classify_item("obat tablet vitamin pharmacy")
        assert result == ExpenseCategory.HEALTH


# ─────────────────────────────────────────────────────────────────────────────
# 11. _get_matched_keywords()
# ─────────────────────────────────────────────────────────────────────────────

class TestGetMatchedKeywords:
    def test_returns_matched_keywords_for_food(self, cat):
        matched = cat._get_matched_keywords("makan nasi ayam restaurant", ExpenseCategory.FOOD)
        assert len(matched) > 0
        assert all(k in "makan nasi ayam restaurant" for k in matched)

    def test_max_five_keywords_returned(self, cat):
        # Fill with many food keywords
        text = "nasi rice mie chicken ikan sayur buah snack restaurant makan"
        matched = cat._get_matched_keywords(text, ExpenseCategory.FOOD)
        assert len(matched) <= 5

    def test_unknown_category_returns_empty(self, cat):
        matched = cat._get_matched_keywords("some text", ExpenseCategory.OTHER)
        assert matched == []


# ─────────────────────────────────────────────────────────────────────────────
# 12. _generate_reasoning()
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateReasoning:
    @pytest.mark.parametrize("category,expected_fragment", [
        (ExpenseCategory.FOOD, "Food"),
        (ExpenseCategory.TRANSPORT, "transport"),
        (ExpenseCategory.SHOPPING, "commerce"),
        (ExpenseCategory.ENTERTAINMENT, "Entertainment"),
        (ExpenseCategory.HEALTH, "healthcare"),
        (ExpenseCategory.HOUSING, "Housing"),
        (ExpenseCategory.EDUCATION, "education"),
        (ExpenseCategory.INVESTMENT, "investment"),
    ])
    def test_reasoning_contains_category_context(self, cat, category, expected_fragment):
        reasoning = cat._generate_reasoning(category, "some text", 50_000)
        assert expected_fragment.lower() in reasoning.lower()

    def test_unknown_category_returns_generic(self, cat):
        reasoning = cat._generate_reasoning(ExpenseCategory.OTHER, "text", 100)
        assert reasoning  # Non-empty fallback


# ─────────────────────────────────────────────────────────────────────────────
# 13. End-to-end classify() flows
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyEndToEnd:
    def test_full_food_receipt(self, cat):
        r = make_receipt(
            merchant="Ballin Kitchen",
            ocr_text="nasi goreng ayam bakar minum es teh pesanan",
            amount=85_000,
            tx_date=datetime(2025, 6, 1, 12, 30),
        )
        result = cat.classify(r)
        assert result.category == ExpenseCategory.FOOD

    def test_full_transfer_receipt_overrides_all(self, cat):
        # Even if text has food keywords, TRANSFER wins
        r = make_receipt(
            merchant="Transfer BCA",
            ocr_text="nasi ayam makan tapi transfer berhasil",
            amount=200_000,
        )
        result = cat.classify(r)
        assert result.category == IncomeCategory.TRANSFER

    def test_income_person_sets_tx_type_income(self, cat):
        r = make_receipt(merchant="joselyn")
        cat.classify(r)
        assert r.transaction_type == TransactionType.INCOME

    def test_metadata_hint_overrides_merchant_classification(self, cat):
        r = make_receipt(
            merchant="Something Ambiguous",
            metadata={"description_hint": "Pocket Money"},
        )
        result = cat.classify(r)
        assert result.category == IncomeCategory.OTHER
        assert r.transaction_type == TransactionType.INCOME
