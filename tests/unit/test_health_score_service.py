"""
Phase 14 — Behavioral Health Score tests.

Covers packages/api/backend/finance/health_score_service.py:

  * component scores at their boundary values
  * weighted composite, grade thresholds
  * all components carry explanations (verified-data reasoning)
  * renderer (format_health_score_text)

Hermetic SQLite fixtures — safe names without canonical bridge targets.
"""
from datetime import date, timedelta

import pytest

from packages.api.backend.finance import budget_service as bs
from packages.api.backend.finance import health_score_service as hs
from packages.api.backend.finance import ledger_engine as ledger
from packages.api.backend.finance import recurring_service as rrs


@pytest.fixture
def ledger_db(tmp_path):
    path = str(tmp_path / "health_ledger.sqlite")
    ledger.seed_defaults(path)
    return path


@pytest.fixture
def budget_db(tmp_path):
    path = str(tmp_path / "health_budget.sqlite")
    bs._ensure_budget_db(path)
    return path


def _tx(ledger_db, ttype, amount, tx_date, category, description=None):
    return ledger.record_transaction(
        ledger_db, ttype=ttype, amount=amount, tx_date=tx_date,
        category=category, description=description, source="test",
    )


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


def _seed_healthy(ledger_db, as_of=date(2026, 8, 17)):
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _tx(ledger_db, "expense", 3_000_000, date(2026, 8, 5), "food", description="Belanja")
    _tx(ledger_db, "expense", 4_000_000, date(2026, 7, 10), "food", description="Bulan lalu")
    _tx(ledger_db, "expense", 200_000, as_of, "Transport", description="Gojek")


# ═════════════════════════════════════════════════════════════════════════════
# § Component scores
# ═════════════════════════════════════════════════════════════════════════════

def test_savings_rate_full_and_zero(ledger_db):
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _tx(ledger_db, "expense", 2_000_000, date(2026, 8, 5), "food", description="Belanja")
    comp = hs._score_savings_rate(ledger_db, date(2026, 8, 17))
    assert comp["score"] == 100
    assert "Rasio tabungan" in comp["explanation"]

    # deficit
    _tx(ledger_db, "expense", 9_000_000, date(2026, 8, 6), "food", description="Gede")
    comp2 = hs._score_savings_rate(ledger_db, date(2026, 8, 17))
    assert comp2["score"] == 0


def test_budget_habits_scores(ledger_db, budget_db):
    _tx(ledger_db, "expense", 2_000_000, date(2026, 8, 5), "food", description="Belanja")
    bs.set_budget_limit(budget_db, year=2026, month=8, category="food", limit=1_000_000)
    comp = hs._score_budget_habits(ledger_db, budget_db, date(2026, 8, 17))
    assert comp["score"] == 0

    comp2 = hs._score_budget_habits(ledger_db, budget_db, date(2026, 8, 17))
    assert comp2["explanation"].startswith("1 kategori melampaui")

    # all clear
    bs.set_budget_limit(budget_db, year=2026, month=8, category="food", limit=5_000_000)
    comp3 = hs._score_budget_habits(ledger_db, budget_db, date(2026, 8, 17))
    assert comp3["score"] == 100


def test_anomaly_safety_scores(ledger_db):
    comp = hs._score_anomaly_safety(ledger_db, date(2026, 8, 17))
    assert comp["score"] == 100

    as_of = date(2026, 8, 17)
    for i in range(90):
        _tx(ledger_db, "expense", 500_000, as_of - timedelta(days=120 - i), "food", description="Rutin")
    for i in range(30):
        _tx(ledger_db, "expense", 2_000_000, as_of - timedelta(days=i), "food", description="Spike")
    comp2 = hs._score_anomaly_safety(ledger_db, as_of)
    assert comp2["score"] == 0


def test_safe_spend_scores(ledger_db):
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    comp = hs._score_safe_spend(ledger_db, date(2026, 8, 17))
    assert comp["score"] == 100

    _tx(ledger_db, "expense", 100_000, date(2026, 8, 16), "food", description="Belanja")
    _seed_template(ledger_db, tx_type="expense", amount=9_000_000, day_of_month=18,
                   confirmed=True, description="Sewa Kos")  # due tomorrow, exceeds balance
    comp2 = hs._score_safe_spend(ledger_db, date(2026, 8, 17))
    assert comp2["score"] == 0


def test_recurring_load_scores(ledger_db):
    comp = hs._score_recurring_load(ledger_db, date(2026, 8, 17))
    assert comp["score"] == 100

    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _seed_template(ledger_db, tx_type="expense", amount=6_000_000, day_of_month=20,
                   confirmed=True, description="Sewa Kos")  # 60% of income
    comp2 = hs._score_recurring_load(ledger_db, date(2026, 8, 17))
    assert comp2["score"] == 0


def test_trend_stability_scores(ledger_db):
    _tx(ledger_db, "expense", 5_000_000, date(2026, 7, 10), "food", description="Bulan lalu")
    _tx(ledger_db, "expense", 1_000_000, date(2026, 8, 10), "food", description="Bulan ini")
    comp = hs._score_trend_stability(ledger_db, date(2026, 8, 17))
    assert comp["score"] == 100  # spending down = stable

    _tx(ledger_db, "expense", 5_000_000, date(2026, 8, 11), "food", description="Bulan ini 2")
    comp2 = hs._score_trend_stability(ledger_db, date(2026, 8, 17))
    assert comp2["score"] == 0  # +20%+


# ═════════════════════════════════════════════════════════════════════════════
# § Composite & renderer
# ═════════════════════════════════════════════════════════════════════════════

def test_composite_weights_and_grade(ledger_db, budget_db):
    _seed_healthy(ledger_db)
    result = hs.build_health_score(ledger_db, budget_db, as_of=date(2026, 8, 17))
    assert len(result["components"]) == 6
    assert result["weights"] == hs.WEIGHTS
    expected = round(
        sum(c["score"] * c["weight"] for c in result["components"]) / 100
    )
    assert result["total_score"] == expected
    assert result["grade"] in ("Sehat", "Cukup", "Perlu Perhatian", "Kritis")
    assert all("explanation" in c for c in result["components"])
    assert all(c["weight"] == hs.WEIGHTS[c["key"]] for c in result["components"])


def test_composite_zero_and_kritis(ledger_db, budget_db):
    as_of = date(2026, 8, 17)
    for i in range(90):
        _tx(ledger_db, "expense", 500_000, as_of - timedelta(days=120 - i), "food", description="Rutin")
    for i in range(30):
        _tx(ledger_db, "expense", 2_000_000, as_of - timedelta(days=i), "food", description="Spike")
    _tx(ledger_db, "expense", 10_000_000, as_of - timedelta(days=30), "food", description="Defisit")
    bs.set_budget_limit(budget_db, year=2026, month=8, category="food", limit=100_000)
    result = hs.build_health_score(ledger_db, budget_db, as_of=as_of)
    assert result["total_score"] <= 40
    assert result["grade"] == "Kritis"


def test_format_health_score_text(ledger_db, budget_db):
    _seed_healthy(ledger_db)
    result = hs.build_health_score(ledger_db, budget_db, as_of=date(2026, 8, 17))
    text = hs.format_health_score_text(result)
    assert "Skor Kesehatan Keuangan" in text
    assert f"{result['total_score']}/100" in text
    assert "bobot" in text
