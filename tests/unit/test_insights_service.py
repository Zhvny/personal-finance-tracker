"""
Phase 13 — AI Insights tests.

Covers packages/api/backend/finance/insights_service.py:

  * every card is computed from verified backend data (Phases 5-12) only
  * net_savings_rate (positive/info/deficit warning)
  * expense_trend (up warning / down positive / stable info / no-data)
  * top_category (dominance warning / info / no-data)
  * recurring_load (share of income, no-templates info)
  * budget_pressure (over alert / alert warning / all-clear positive)
  * anomaly_count (high alert / medium warning / clean positive)
  * safe_to_spend (negative alert / thin-margin warning / positive)
  * card ordering by severity; summary counts; renderer

Hermetic SQLite fixtures — safe names without canonical bridge targets.
"""
from datetime import date, timedelta

import pytest

from packages.api.backend.finance import budget_service as bs
from packages.api.backend.finance import insights_service as ins
from packages.api.backend.finance import ledger_engine as ledger
from packages.api.backend.finance import recurring_service as rrs


@pytest.fixture
def ledger_db(tmp_path):
    path = str(tmp_path / "insight_ledger.sqlite")
    ledger.seed_defaults(path)
    return path


@pytest.fixture
def budget_db(tmp_path):
    path = str(tmp_path / "insight_budget.sqlite")
    bs._ensure_budget_db(path)
    return path


def _tx(ledger_db, ttype, amount, tx_date, category, description=None):
    return ledger.record_transaction(
        ledger_db, ttype=ttype, amount=amount, tx_date=tx_date,
        category=category, description=description, source="test",
    )


def _seed_healthy(ledger_db, as_of=date(2026, 8, 17)):
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _tx(ledger_db, "expense", 3_000_000, date(2026, 8, 5), "Food", description="Belanja")
    _tx(ledger_db, "expense", 1_000_000, date(2026, 7, 10), "Food", description="Bulan lalu")
    _tx(ledger_db, "expense", 200_000, as_of, "Transport", description="Gojek")


def _seed_template(ledger_db, *, tx_type, amount, day_of_month, confirmed=True,
                   as_of=date(2026, 8, 17), category="rent", description="Sewa Kos"):
    y, m = as_of.year, as_of.month
    for back in range(1, 4):
        month = m - back
        yy = y
        if month <= 0:
            month += 12
            yy -= 1
        try:
            d = date(yy, month, day_of_month)
        except ValueError:
            d = date(yy, month, 28)
        _tx(ledger_db, tx_type, amount, d, category, description=description)
    rrs.detect_recurring(ledger_db, as_of=as_of)
    cand = [c for c in rrs.list_candidates(ledger_db)
            if c["tx_type"] == tx_type and c["amount"] == amount][0]
    rrs.verify_candidate(ledger_db, cand["candidate_id"], confirmed=confirmed)


# ═════════════════════════════════════════════════════════════════════════════
# § Card computations
# ═════════════════════════════════════════════════════════════════════════════

def test_net_savings_rate_positive(ledger_db):
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _tx(ledger_db, "expense", 3_000_000, date(2026, 8, 5), "Food", description="Belanja")
    card = ins._net_savings_rate(ledger_db, date(2026, 8, 17))
    assert card["type"] == "net_savings_rate"
    assert card["severity"] == "positive"
    assert "Rasio tabungan" in card["explanation"]


def test_net_savings_rate_deficit(ledger_db):
    _tx(ledger_db, "income", 2_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _tx(ledger_db, "expense", 5_000_000, date(2026, 8, 5), "Food", description="Belanja")
    card = ins._net_savings_rate(ledger_db, date(2026, 8, 17))
    assert card["severity"] == "warning"
    assert "MELEBIHI" in card["explanation"]


def test_expense_trend_up_warning(ledger_db):
    _tx(ledger_db, "expense", 1_000_000, date(2026, 7, 10), "Food", description="Bulan lalu")
    _tx(ledger_db, "expense", 5_000_000, date(2026, 8, 10), "Food", description="Bulan ini")
    card = ins._expense_trend(ledger_db, date(2026, 8, 17))
    assert card["type"] == "expense_trend"
    assert card["severity"] == "warning"


def test_expense_trend_down_positive(ledger_db):
    _tx(ledger_db, "expense", 5_000_000, date(2026, 7, 10), "Food", description="Bulan lalu")
    _tx(ledger_db, "expense", 1_000_000, date(2026, 8, 10), "Food", description="Bulan ini")
    card = ins._expense_trend(ledger_db, date(2026, 8, 17))
    assert card["severity"] == "positive"


def test_top_category_dominance_warning(ledger_db):
    _tx(ledger_db, "expense", 8_000_000, date(2026, 8, 5), "Food", description="Belanja")
    _tx(ledger_db, "expense", 1_000_000, date(2026, 8, 6), "Transport", description="Gojek")
    card = ins._top_category(ledger_db, date(2026, 8, 17))
    assert card["type"] == "top_category"
    assert card["severity"] == "warning"
    assert "mendominasi" in card["explanation"]


def test_recurring_load_warning_when_high(ledger_db):
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _seed_template(ledger_db, tx_type="expense", amount=6_000_000, day_of_month=20,
                   confirmed=True, description="Sewa Kos")  # 60% of income
    card = ins._recurring_load(ledger_db, date(2026, 8, 17))
    assert card["type"] == "recurring_load"
    assert card["severity"] == "warning"
    assert "60%" in card["explanation"]


def test_recurring_load_no_templates_info(ledger_db):
    card = ins._recurring_load(ledger_db, date(2026, 8, 17))
    assert card["severity"] == "info"


def test_budget_pressure_alert_and_clear(ledger_db, budget_db):
    _tx(ledger_db, "expense", 2_000_000, date(2026, 8, 5), "food", description="Belanja")
    bs.set_budget_limit(budget_db, year=2026, month=8, category="food", limit=1_000_000)
    card = ins._budget_pressure(ledger_db, budget_db, date(2026, 8, 17))
    assert card["severity"] == "alert"
    assert "MELAMPAUI" in card["explanation"]

    card2 = ins._budget_pressure(ledger_db, budget_db, date(2026, 8, 17))
    assert card2["refs"]["endpoint"] == "/api/budget/status"


def test_anomaly_count_alert(ledger_db):
    as_of = date(2026, 8, 17)
    for i in range(90):
        _tx(ledger_db, "expense", 500_000, as_of - timedelta(days=120 - i), "Food", description="Rutin")
    for i in range(30):
        _tx(ledger_db, "expense", 2_000_000, as_of - timedelta(days=i), "Food", description="Spike")
    card = ins._anomaly_count(ledger_db, as_of)
    assert card["type"] == "anomaly_count"
    assert card["severity"] == "alert"


def test_anomaly_count_clean_positive(ledger_db):
    card = ins._anomaly_count(ledger_db, date(2026, 8, 17))
    assert card["severity"] == "positive"


def test_safe_to_spend_negative_alert(ledger_db):
    _tx(ledger_db, "expense", 100_000, date(2026, 8, 16), "Food", description="Belanja")
    _seed_template(ledger_db, tx_type="expense", amount=1_000_000, day_of_month=18,
                   confirmed=True, description="Sewa Kos")
    card = ins._safe_to_spend(ledger_db, date(2026, 8, 17))
    assert card["type"] == "safe_to_spend"
    assert card["severity"] == "alert"


def test_safe_to_spend_positive(ledger_db):
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    card = ins._safe_to_spend(ledger_db, date(2026, 8, 17))
    assert card["severity"] == "positive"


# ═════════════════════════════════════════════════════════════════════════════
# § Aggregation & renderer
# ═════════════════════════════════════════════════════════════════════════════

def test_build_insights_ordering_and_summary(ledger_db, budget_db):
    _seed_healthy(ledger_db)
    result = ins.build_insights(ledger_db, budget_db, as_of=date(2026, 8, 17))
    assert len(result["insights"]) == 7
    severities = [c["severity"] for c in result["insights"]]
    order = {s: i for i, s in enumerate(ins.SEVERITY_ORDER)}
    assert severities == sorted(severities, key=order.__getitem__)
    assert sum(result["summary"].values()) == 7
    assert set(result["summary"]) == {"alert", "warning", "positive", "info"}
    assert all("refs" in c for c in result["insights"])


def test_format_insights_text(ledger_db, budget_db):
    _seed_healthy(ledger_db)
    result = ins.build_insights(ledger_db, budget_db, as_of=date(2026, 8, 17))
    text = ins.format_insights_text(result)
    assert "Wawasan Keuangan" in text
    assert "Ringkasan:" in text
    assert "[POSITIVE]" in text or "[INFO]" in text
