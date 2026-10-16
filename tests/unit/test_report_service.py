"""
Phase 5 — Daily / Weekly / Monthly report service tests.

Covers packages/api/backend/finance/report_service.py:

  * period bounds (today / rolling-7-day week / month-to-date) and the
    immediately-preceding comparison windows (yesterday / prior 7 days /
    previous month to-date)
  * income / expense / net cashflow aggregates, transfer exclusion
  * top categories, top merchants, largest transactions
  * period-over-period % change (None when base period is empty)
  * daily trend buckets (week/month) and hourly buckets (today)
  * empty-ledger behaviour and invalid-period errors

All fixtures use a hermetic SQLite ledger path that does NOT contain a
canonical-Postgres bridge target substring (e.g. "finance.db"), so the bridge
never redirects during the test run.
"""
from datetime import date

import pytest

from packages.api.backend.finance import ledger_engine as ledger
from packages.api.backend.finance import report_service as rs


@pytest.fixture
def ledger_db(tmp_path):
    path = str(tmp_path / "report_ledger.sqlite")
    ledger.seed_defaults(path)
    return path


def _accounts(ledger_db):
    return {a["name"]: a for a in ledger.list_accounts(ledger_db)}


def _tx(ledger_db, ttype, amount, tx_date, category=None, merchant=None, description=None):
    return ledger.record_transaction(
        ledger_db,
        ttype=ttype,
        amount=amount,
        tx_date=tx_date,
        category=category,
        merchant_id=(ledger.remember_merchant(ledger_db, merchant)["id"] if merchant else None),
        description=description,
        source="test",
    )


# ═════════════════════════════════════════════════════════════════════════════
# § Period bounds
# ═════════════════════════════════════════════════════════════════════════════

def test_bounds_today():
    as_of = date(2026, 8, 17)
    assert rs._period_bounds("today", as_of) == (as_of, as_of)
    assert rs._previous_bounds("today", as_of) == (date(2026, 8, 16), date(2026, 8, 16))


def test_bounds_week_rolling_7_days():
    as_of = date(2026, 8, 17)  # a Monday
    assert rs._period_bounds("week", as_of) == (date(2026, 8, 11), as_of)
    assert rs._previous_bounds("week", as_of) == (date(2026, 8, 4), date(2026, 8, 10))


def test_bounds_month_to_date():
    as_of = date(2026, 8, 17)
    assert rs._period_bounds("month", as_of) == (date(2026, 8, 1), as_of)
    assert rs._previous_bounds("month", as_of) == (date(2026, 7, 1), date(2026, 7, 17))


def test_previous_month_to_date_caps_at_previous_month_end():
    as_of = date(2026, 3, 31)
    start, end = rs._previous_bounds("month", as_of)
    assert (start, end) == (date(2026, 2, 1), date(2026, 2, 28))


def test_invalid_period_raises():
    with pytest.raises(rs.ReportError):
        rs._period_bounds("year", date(2026, 8, 17))
    with pytest.raises(rs.ReportError):
        rs.build_report("x.sqlite", period="year")


# ═════════════════════════════════════════════════════════════════════════════
# § Aggregates
# ═════════════════════════════════════════════════════════════════════════════

def test_report_month_totals_exclude_out_of_range(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "expense", 50000, date(2026, 8, 10), category="Food")
    _tx(ledger_db, "expense", 30000, date(2026, 8, 15), category="Transport")
    _tx(ledger_db, "income", 2_500_000, date(2026, 8, 5), category="Salary")
    _tx(ledger_db, "expense", 999999, date(2026, 7, 31), category="Old")

    report = rs.build_report(ledger_db, "month", as_of=as_of)
    assert report["totals"] == {"income": 2_500_000.0, "expense": 80_000.0, "net": 2_420_000.0}


def test_report_week_totals(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "expense", 10000, date(2026, 8, 11), category="Food")
    _tx(ledger_db, "expense", 20000, date(2026, 8, 16), category="Food")
    _tx(ledger_db, "expense", 99999, date(2026, 8, 10), category="Old")  # outside 7-day window
    _tx(ledger_db, "income", 100000, date(2026, 8, 17), category="Salary")

    report = rs.build_report(ledger_db, "week", as_of=as_of)
    assert report["totals"] == {"income": 100_000.0, "expense": 30_000.0, "net": 70_000.0}


def test_report_today_totals(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "expense", 5000, as_of, category="Food")
    _tx(ledger_db, "expense", 7000, date(2026, 8, 16), category="Old")
    _tx(ledger_db, "income", 200000, as_of, category="Salary")

    report = rs.build_report(ledger_db, "today", as_of=as_of)
    assert report["totals"] == {"income": 200_000.0, "expense": 5_000.0, "net": 195_000.0}


def test_transfers_excluded_from_aggregates(ledger_db):
    accounts = _accounts(ledger_db)
    a, b = list(accounts.values())[0], accounts.get("Cash")
    if b is None:
        b = ledger.create_account(ledger_db, "Cash", account_type="cash")
    as_of = date(2026, 8, 17)
    ledger.record_transfer(
        ledger_db, from_account_id=a["id"], to_account_id=b["id"],
        amount=300000, tx_date=as_of, description="Pindah dana", check_balance=False,
    )
    report = rs.build_report(ledger_db, "today", as_of=as_of)
    assert report["totals"] == {"income": 0.0, "expense": 0.0, "net": 0.0}


# ═════════════════════════════════════════════════════════════════════════════
# § Breakdowns
# ═════════════════════════════════════════════════════════════════════════════

def test_top_categories_merchants_and_largest(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "expense", 50000, as_of, category="Food", merchant="Starbucks")
    _tx(ledger_db, "expense", 70000, as_of, category="Food", merchant="Starbucks")
    _tx(ledger_db, "expense", 150000, as_of, category="Transport", merchant="Grab")
    _tx(ledger_db, "income", 3_000_000, as_of, category="Salary")
    _tx(ledger_db, "income", 500000, as_of, category="Freelance")

    report = rs.build_report(ledger_db, "month", as_of=as_of, top_n=5)

    assert report["top_categories"][0] == {"name": "Transport", "total": 150_000.0, "count": 1}
    assert report["top_categories"][1] == {"name": "Food", "total": 120_000.0, "count": 2}
    assert [c["name"] for c in report["top_income_categories"]] == ["Salary", "Freelance"]

    assert report["top_merchants"][0] == {"name": "grab", "total": 150_000.0, "count": 1}
    assert report["top_merchants"][1] == {"name": "starbucks", "total": 120_000.0, "count": 2}

    largest = report["largest_transactions"]
    assert len(largest) == 5
    assert largest[0]["type"] == "income" and largest[0]["amount"] == 3_000_000.0
    assert largest[1]["type"] == "income" and largest[1]["amount"] == 500_000.0
    assert largest[2]["name"] == "grab"
    assert largest[3]["amount"] == 70_000.0
    assert largest[4]["amount"] == 50_000.0


def test_top_n_limit_applied(ledger_db):
    as_of = date(2026, 8, 17)
    for i in range(5):
        _tx(ledger_db, "expense", 1000 * (i + 1), as_of, category=f"Cat{i}")
    report = rs.build_report(ledger_db, "month", as_of=as_of, top_n=3)
    assert len(report["top_categories"]) == 3
    assert report["top_categories"][0]["name"] == "Cat4"


# ═════════════════════════════════════════════════════════════════════════════
# § Comparison
# ═════════════════════════════════════════════════════════════════════════════

def test_comparison_pct_with_previous_period(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "expense", 100000, date(2026, 8, 10), category="Food")  # current
    _tx(ledger_db, "expense", 50000, date(2026, 7, 10), category="Food")   # previous month
    _tx(ledger_db, "income", 1_000_000, date(2026, 8, 1), category="Salary")
    _tx(ledger_db, "income", 2_000_000, date(2026, 7, 1), category="Salary")

    report = rs.build_report(ledger_db, "month", as_of=as_of)
    assert report["comparison"]["expense_pct"] == pytest.approx(100.0)
    assert report["comparison"]["income_pct"] == pytest.approx(-50.0)
    assert report["comparison"]["net_pct"] is not None


def test_comparison_none_when_previous_empty(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "expense", 100000, as_of, category="Food")
    report = rs.build_report(ledger_db, "month", as_of=as_of)
    assert report["comparison"] == {
        "income_pct": None, "expense_pct": None, "net_pct": None,
    }


# ═════════════════════════════════════════════════════════════════════════════
# § Trend
# ═════════════════════════════════════════════════════════════════════════════

def test_trend_daily_buckets_zero_filled(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "expense", 30000, date(2026, 8, 15), category="Food")
    _tx(ledger_db, "income", 100000, date(2026, 8, 15), category="Salary")

    report = rs.build_report(ledger_db, "month", as_of=as_of)
    trend = report["trend"]
    assert len(trend) == 17  # 1..17 Aug
    assert trend[0] == {"label": "01/08", "income": 0.0, "expense": 0.0, "net": 0.0}
    assert trend[14] == {"label": "15/08", "income": 100_000.0, "expense": 30_000.0, "net": 70_000.0}
    assert trend[-1]["label"] == "17/08"


def test_trend_week_daily_buckets(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "expense", 5000, as_of, category="Food")
    report = rs.build_report(ledger_db, "week", as_of=as_of)
    assert len(report["trend"]) == 7
    assert report["trend"][-1]["expense"] == 5_000.0


def test_trend_today_hourly(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "expense", 15000, as_of, category="Food")
    report = rs.build_report(ledger_db, "today", as_of=as_of)
    trend = report["trend"]
    assert trend and trend[0]["label"] == "00:00"
    assert all(isinstance(b["label"], str) and ":" in b["label"] for b in trend)
    assert sum(b["expense"] for b in trend) == 15_000.0


# ═════════════════════════════════════════════════════════════════════════════
# § Empty ledger
# ═════════════════════════════════════════════════════════════════════════════

def test_empty_ledger_report(ledger_db):
    as_of = date(2026, 8, 17)
    report = rs.build_report(ledger_db, "month", as_of=as_of)
    assert report["totals"] == {"income": 0.0, "expense": 0.0, "net": 0.0}
    assert report["top_categories"] == []
    assert report["top_merchants"] == []
    assert report["largest_transactions"] == []
    assert len(report["trend"]) == 17
