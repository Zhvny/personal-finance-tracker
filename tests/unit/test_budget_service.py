"""
Phase 6 — Budget engine + alerts tests.

Covers packages/api/backend/finance/budget_service.py:

  * limit upsert / delete (UNIQUE year, month, category)
  * budget vs actual status computed from the canonical ledger
  * configurable thresholds (env defaults 70 / 90 / 100) and level
    boundaries (ok → warn → alert → over)
  * transfers and out-of-month expenses excluded from actuals
  * idempotent alert generation: first check emits alerts, repeated checks
    are deduped; limit changes escalate/de-escalate levels correctly
  * alert history retrieval
  * invalid month / limit errors

All fixtures use hermetic SQLite paths that do NOT contain a canonical
Postgres bridge target substring (e.g. "budget.db" / "finance.db").
"""
from datetime import date

import pytest

from packages.api.backend.finance import budget_service as bs
from packages.api.backend.finance import ledger_engine as ledger


@pytest.fixture
def paths(tmp_path):
    return {
        "ledger": str(tmp_path / "budget_ledger.sqlite"),
        "budget": str(tmp_path / "budget_limits.sqlite"),
    }


def _tx(ledger_db, ttype, amount, tx_date, category=None):
    return ledger.record_transaction(
        ledger_db, ttype=ttype, amount=amount, tx_date=tx_date,
        category=category, source="test",
    )


def _set(paths, year=2026, month=8, category="food", limit=1_000_000):
    return bs.set_budget_limit(paths["budget"], year, month, category, limit)


# ═════════════════════════════════════════════════════════════════════════════
# § Limits
# ═════════════════════════════════════════════════════════════════════════════

def test_set_budget_limit_upserts(paths):
    ledger.seed_defaults(paths["ledger"])
    first = _set(paths)
    assert first == {"year": 2026, "month": 8, "category": "food", "limit": 1_000_000.0}
    updated = _set(paths, limit=2_000_000)
    assert updated["limit"] == 2_000_000.0
    limits = bs._limits_by_category(paths["budget"], 2026, 8)
    assert limits == {"food": 2_000_000.0}


def test_set_budget_limit_normalizes_category(paths):
    bs.set_budget_limit(paths["budget"], 2026, 8, "  Makanan  ", 500000)
    assert "makanan" in bs._limits_by_category(paths["budget"], 2026, 8)
    assert bs.set_budget_limit(paths["budget"], 2026, 8, "", 500000)["category"] == "total"


def test_set_budget_limit_rejects_bad_input(paths):
    with pytest.raises(bs.BudgetError):
        bs.set_budget_limit(paths["budget"], 2026, 8, "food", 0)
    with pytest.raises(bs.BudgetError):
        bs.set_budget_limit(paths["budget"], 2026, 8, "food", -5)
    with pytest.raises(bs.BudgetError):
        bs.set_budget_limit(paths["budget"], 2026, 8, "food", "abc")


def test_delete_budget_limit(paths):
    _set(paths)
    bs.delete_budget_limit(paths["budget"], 2026, 8, "food")
    assert bs._limits_by_category(paths["budget"], 2026, 8) == {}


def test_invalid_month_raises(paths):
    with pytest.raises(bs.BudgetError):
        _set(paths, month=13)
    with pytest.raises(bs.BudgetError):
        bs.build_budget_status(paths["ledger"], paths["budget"], 2026, 0)


# ═════════════════════════════════════════════════════════════════════════════
# § Status
# ═════════════════════════════════════════════════════════════════════════════

def test_status_no_limits_returns_empty_categories(paths):
    ledger.seed_defaults(paths["ledger"])
    status = bs.build_budget_status(paths["ledger"], paths["budget"], 2026, 8)
    assert status["categories"] == []
    assert status["thresholds"] == {"warn": 70.0, "alert": 90.0, "over": 100.0}


def test_status_computes_actuals_and_levels(paths):
    ledger.seed_defaults(paths["ledger"])
    _tx(paths["ledger"], "expense", 500_000, date(2026, 8, 10), category="food")   # 50% → ok
    _tx(paths["ledger"], "expense", 250_000, date(2026, 8, 12), category="food")   # 75% → warn
    _set(paths)
    status = bs.build_budget_status(paths["ledger"], paths["budget"], 2026, 8)
    row = status["categories"][0]
    assert row["category"] == "food"
    assert row["actual"] == 750_000.0
    assert row["remaining"] == 250_000.0
    assert row["pct_used"] == pytest.approx(75.0)
    assert row["level"] == "warn"


def test_status_level_boundaries(paths):
    ledger.seed_defaults(paths["ledger"])
    for pct, expected in [(60, "ok"), (70, "warn"), (90, "alert"), (100, "over"), (110, "over")]:
        _set(paths, limit=1000)
        _tx(paths["ledger"], "expense", pct * 10, date(2026, 8, 1), category="food")
        status = bs.build_budget_status(paths["ledger"], paths["budget"], 2026, 8)
        assert status["categories"][0]["level"] == expected, f"{pct}%"
        bs.delete_budget_limit(paths["budget"], 2026, 8, "food")
        ledger.delete_transaction(paths["ledger"], ledger.list_transactions(paths["ledger"])[0]["id"])


def test_status_custom_thresholds(paths):
    ledger.seed_defaults(paths["ledger"])
    _set(paths, limit=1000)
    _tx(paths["ledger"], "expense", 500, date(2026, 8, 1), category="food")  # 50%
    thr = {"warn": 40.0, "alert": 60.0, "over": 80.0}
    status = bs.build_budget_status(paths["ledger"], paths["budget"], 2026, 8, thresholds=thr)
    assert status["categories"][0]["level"] == "warn"
    assert status["thresholds"] == thr


def test_status_excludes_transfers_and_other_months(paths):
    ledger.seed_defaults(paths["ledger"])
    accounts = {a["name"]: a for a in ledger.list_accounts(paths["ledger"])}
    a, b = list(accounts.values())[0], accounts.get("Cash")
    if b is None:
        b = ledger.create_account(paths["ledger"], "Cash", account_type="cash")
    ledger.record_transfer(
        paths["ledger"], from_account_id=a["id"], to_account_id=b["id"],
        amount=900_000, tx_date=date(2026, 8, 5), check_balance=False,
    )
    _tx(paths["ledger"], "expense", 900_000, date(2026, 7, 31), category="food")   # prev month
    _set(paths)
    status = bs.build_budget_status(paths["ledger"], paths["budget"], 2026, 8)
    assert status["categories"][0]["actual"] == 0.0
    assert status["categories"][0]["level"] == "ok"


def test_status_only_reports_categories_with_limits(paths):
    ledger.seed_defaults(paths["ledger"])
    _tx(paths["ledger"], "expense", 100_000, date(2026, 8, 1), category="food")
    _set(paths, category="transport", limit=500_000)
    status = bs.build_budget_status(paths["ledger"], paths["budget"], 2026, 8)
    assert [c["category"] for c in status["categories"]] == ["transport"]


# ═════════════════════════════════════════════════════════════════════════════
# § Alerts (dedup)
# ═════════════════════════════════════════════════════════════════════════════

def test_check_alerts_emits_only_new(paths):
    ledger.seed_defaults(paths["ledger"])
    _set(paths, category="food", limit=1_000_000)
    _set(paths, category="transport", limit=100_000)
    _tx(paths["ledger"], "expense", 750_000, date(2026, 8, 10), category="food")   # warn
    _tx(paths["ledger"], "expense", 95_000, date(2026, 8, 11), category="transport")  # alert

    first = bs.check_budget_alerts(paths["ledger"], paths["budget"], 2026, 8)
    levels = {(a["category"], a["level"]) for a in first["new_alerts"]}
    assert levels == {("food", "warn"), ("transport", "alert")}

    second = bs.check_budget_alerts(paths["ledger"], paths["budget"], 2026, 8)
    assert second["new_alerts"] == []


def test_check_alerts_dedup_after_escalation(paths):
    ledger.seed_defaults(paths["ledger"])
    _set(paths, limit=1_000_000)
    _tx(paths["ledger"], "expense", 950_000, date(2026, 8, 10), category="food")  # alert
    first = bs.check_budget_alerts(paths["ledger"], paths["budget"], 2026, 8)
    assert [(a["category"], a["level"]) for a in first["new_alerts"]] == [("food", "alert")]

    _tx(paths["ledger"], "expense", 100_000, date(2026, 8, 12), category="food")  # → 105% over
    second = bs.check_budget_alerts(paths["ledger"], paths["budget"], 2026, 8)
    assert [(a["category"], a["level"]) for a in second["new_alerts"]] == [("food", "over")]

    third = bs.check_budget_alerts(paths["ledger"], paths["budget"], 2026, 8)
    assert third["new_alerts"] == []


def test_check_alerts_no_alert_when_ok(paths):
    ledger.seed_defaults(paths["ledger"])
    _set(paths, limit=1_000_000)
    _tx(paths["ledger"], "expense", 100_000, date(2026, 8, 10), category="food")  # 10% → ok
    result = bs.check_budget_alerts(paths["ledger"], paths["budget"], 2026, 8)
    assert result["new_alerts"] == []


def test_list_alerts_history_newest_first(paths):
    ledger.seed_defaults(paths["ledger"])
    _set(paths, category="food", limit=1_000_000)
    _set(paths, category="transport", limit=100_000)
    _tx(paths["ledger"], "expense", 95_000, date(2026, 8, 10), category="transport")  # alert
    _tx(paths["ledger"], "expense", 750_000, date(2026, 8, 11), category="food")      # warn
    bs.check_budget_alerts(paths["ledger"], paths["budget"], 2026, 8)

    history = bs.list_budget_alerts(paths["budget"], 2026, 8)
    assert {a["level"] for a in history} == {"warn", "alert"}
    assert history[0]["level"] == "alert"  # inserted last → newest first
    assert history[0]["pct_used"] == pytest.approx(95.0)
    assert history[1]["category"] == "food"
    assert history[1]["pct_used"] == pytest.approx(75.0)


def test_alerts_are_month_scoped(paths):
    ledger.seed_defaults(paths["ledger"])
    _set(paths, month=8, limit=1_000_000)
    _tx(paths["ledger"], "expense", 950_000, date(2026, 8, 10), category="food")
    bs.check_budget_alerts(paths["ledger"], paths["budget"], 2026, 8)
    assert bs.list_budget_alerts(paths["budget"], 2026, 7) == []
    assert len(bs.list_budget_alerts(paths["budget"], 2026, 8)) == 1
