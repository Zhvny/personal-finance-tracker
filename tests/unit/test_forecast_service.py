"""
Phase 9 — Deterministic cashflow forecast tests.

Covers packages/api/backend/finance/forecast_service.py:

  * window bounds and days validation
  * start balance from all-time income - expense (transfers excluded)
  * Known bucket = today's actuals; Expected = confirmed recurring templates
    due in window; Estimated = unconfirmed candidates; Forecast = composite
  * period-covered skip (transaction already recorded for the due date)
  * weekly and monthly cadence expansions across the window
  * cumulative series + low-point insight (warning when projected negative)
  * transparent sources list with labels
  * Telegram renderer (format_forecast_text)

All fixtures use hermetic SQLite paths that do NOT contain a canonical
Postgres bridge target substring (e.g. "finance.db").
"""
from datetime import date, timedelta

import pytest

from packages.api.backend.finance import forecast_service as fs
from packages.api.backend.finance import ledger_engine as ledger
from packages.api.backend.finance import recurring_service as rrs


@pytest.fixture
def ledger_db(tmp_path):
    path = str(tmp_path / "forecast_ledger.sqlite")
    ledger.seed_defaults(path)
    return path


def _tx(ledger_db, ttype, amount, tx_date, category, description=None, merchant=None):
    return ledger.record_transaction(
        ledger_db, ttype=ttype, amount=amount, tx_date=tx_date,
        category=category, description=description,
        merchant_id=(ledger.remember_merchant(ledger_db, merchant)["id"] if merchant else None),
        source="test",
    )


def _template(ledger_db, *, tx_type, amount, day_of_month=None, day_of_week=None,
              frequency=None, confirmed=True, as_of=date(2026, 8, 17), category="rent",
              description="Sewa Kos"):
    # seed 3 occurrences of the cadence in the past (<= as_of), then detect + verify
    if frequency == "weekly":
        for week in range(3):
            d = as_of - timedelta(days=7 * (week + 1))
            d = d - timedelta(days=d.weekday() - (day_of_week or 0))  # align weekday
            _tx(ledger_db, tx_type, amount, d, category, description=description)
    else:
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
    cand = rrs.list_candidates(ledger_db)[0]
    rrs.verify_candidate(ledger_db, cand["candidate_id"], confirmed=confirmed)
    return cand


# ═════════════════════════════════════════════════════════════════════════════
# § Window & balance
# ═════════════════════════════════════════════════════════════════════════════

def test_window_and_days_validation(ledger_db):
    as_of = date(2026, 8, 17)
    result = fs.build_cashflow_forecast(ledger_db, days=7, as_of=as_of)
    assert result["window_start"] == "2026-08-17"
    assert result["window_end"] == "2026-08-23"
    assert len(result["daily"]) == 7
    with pytest.raises(fs.ForecastError):
        fs.build_cashflow_forecast(ledger_db, days=0)
    with pytest.raises(fs.ForecastError):
        fs.build_cashflow_forecast(ledger_db, days=91)
    with pytest.raises(fs.ForecastError):
        fs.build_cashflow_forecast(ledger_db, days="abc")


def test_start_balance_excludes_transfers(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _tx(ledger_db, "expense", 2_000_000, date(2026, 8, 5), "Food", description="Belanja")
    accounts = {a["name"]: a for a in ledger.list_accounts(ledger_db)}
    a, b = list(accounts.values())[0], accounts.get("Cash")
    if b is None:
        b = ledger.create_account(ledger_db, "Cash", account_type="cash")
    ledger.record_transfer(
        ledger_db, from_account_id=a["id"], to_account_id=b["id"],
        amount=1_000_000, tx_date=date(2026, 8, 3), check_balance=False,
    )
    result = fs.build_cashflow_forecast(ledger_db, days=3, as_of=as_of)
    assert result["start_balance"] == 8_000_000.0


# ═════════════════════════════════════════════════════════════════════════════
# § Labeled components
# ═════════════════════════════════════════════════════════════════════════════

def test_known_expected_estimated_totals(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "expense", 50_000, as_of, "Food", description="Kopi")  # Known today
    _template(ledger_db, tx_type="expense", amount=250_000, day_of_month=20,
              confirmed=True, as_of=as_of)   # Expected due 20 Aug
    _template(ledger_db, tx_type="income", amount=3_000_000, day_of_month=25,
              confirmed=False, as_of=as_of, category="Salary", description="Gaji")  # Estimated

    result = fs.build_cashflow_forecast(ledger_db, days=30, as_of=as_of)
    totals = result["totals"]
    assert totals["known"] == -50_000.0
    assert totals["expected"] == -250_000.0
    assert totals["estimated"] == 3_000_000.0
    assert totals["forecast"] == 2_700_000.0
    # seeds: 3x expense 250k + 3x income 3jt (all before as_of) → 8.25jt;
    # today's 50k is on as_of so excluded from start balance
    assert result["start_balance"] == 8_250_000.0


def test_expected_skipped_when_period_covered(ledger_db):
    as_of = date(2026, 8, 17)
    _template(ledger_db, tx_type="expense", amount=250_000, day_of_month=17,
              confirmed=True, as_of=as_of)  # due today
    _tx(ledger_db, "expense", 250_000, as_of, "rent", description="Sewa Kos")  # already paid

    result = fs.build_cashflow_forecast(ledger_db, days=30, as_of=as_of)
    assert result["totals"]["expected"] == 0.0
    assert result["totals"]["known"] == -250_000.0


def test_monthly_due_dates_expand_across_months(ledger_db):
    as_of = date(2026, 8, 17)
    _template(ledger_db, tx_type="expense", amount=250_000, day_of_month=20,
              confirmed=True, as_of=as_of)
    result = fs.build_cashflow_forecast(ledger_db, days=45, as_of=as_of)
    due_dates = [s["due_date"] for s in result["sources"]]
    assert "2026-08-20" in due_dates
    assert "2026-09-20" in due_dates  # window extends into September


def test_weekly_due_dates(ledger_db):
    as_of = date(2026, 8, 17)  # Monday — template is due today and next Monday
    _template(ledger_db, tx_type="expense", amount=45_000, day_of_week=0,
              frequency="weekly", confirmed=True, as_of=as_of, category="food",
              description="GoFood")
    result = fs.build_cashflow_forecast(ledger_db, days=14, as_of=as_of)
    due_dates = [s["due_date"] for s in result["sources"]]
    assert due_dates[0] == "2026-08-17"
    assert due_dates[1] == "2026-08-24"
    assert all(date.fromisoformat(due_dates[i]) == date.fromisoformat(due_dates[i - 1]) + timedelta(days=7)
               for i in range(1, len(due_dates)))


def test_sources_carry_labels(ledger_db):
    as_of = date(2026, 8, 17)
    _template(ledger_db, tx_type="expense", amount=250_000, day_of_month=20,
              confirmed=True, as_of=as_of)
    _template(ledger_db, tx_type="income", amount=3_000_000, day_of_month=25,
              confirmed=False, as_of=as_of, category="Salary", description="Gaji")
    result = fs.build_cashflow_forecast(ledger_db, days=30, as_of=as_of)
    labels = {s["label"] for s in result["sources"]}
    assert labels == {"Expected", "Estimated"}
    expected_src = next(s for s in result["sources"] if s["label"] == "Expected")
    assert expected_src["amount"] == -250_000.0
    assert expected_src["description"] == "Sewa Kos"


def test_no_templates_means_flat_forecast(ledger_db):
    as_of = date(2026, 8, 17)
    result = fs.build_cashflow_forecast(ledger_db, days=7, as_of=as_of)
    assert result["totals"] == {"known": 0.0, "expected": 0.0, "estimated": 0.0, "forecast": 0.0}
    assert result["sources"] == []
    assert result["insight"]["warning"] is False


# ═════════════════════════════════════════════════════════════════════════════
# § Cumulative + insight
# ═════════════════════════════════════════════════════════════════════════════

def test_cumulative_series_and_negative_warning(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "expense", 1_000_000, date(2026, 8, 10), "Food", description="Belanja")
    _template(ledger_db, tx_type="expense", amount=500_000, day_of_month=18,
              confirmed=True, as_of=as_of, category="rent", description="Sewa")
    result = fs.build_cashflow_forecast(ledger_db, days=7, as_of=as_of)
    # seeds: 3x expense 500k before as_of + Belanja 1jt → start -2.5jt
    assert result["start_balance"] == -2_500_000.0
    # 18 Aug expense 500k → cumulative -3jt → low point warning
    assert result["insight"]["warning"] is True
    assert result["insight"]["low_point"] == -3_000_000.0
    assert result["insight"]["low_date"] == "2026-08-18"
    last = result["daily"][-1]["cumulative"]
    assert last == -3_000_000.0


def test_insight_safe_when_positive(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 10), "Salary", description="Gaji")
    result = fs.build_cashflow_forecast(ledger_db, days=7, as_of=as_of)
    assert result["insight"]["warning"] is False


# ═════════════════════════════════════════════════════════════════════════════
# § Telegram renderer
# ═════════════════════════════════════════════════════════════════════════════

def test_format_forecast_text(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "expense", 50_000, as_of, "Food", description="Kopi")
    _template(ledger_db, tx_type="expense", amount=250_000, day_of_month=20,
              confirmed=True, as_of=as_of)
    result = fs.build_cashflow_forecast(ledger_db, days=30, as_of=as_of)
    text = fs.format_forecast_text(result)
    assert "Proyeksi Arus Kas" in text
    assert "Known (transaksi nyata)" in text
    assert "Expected (langganan terkonfirmasi)" in text
    assert "Estimated (pola belum dikonfirmasi)" in text
    assert "Forecast (net jendela)" in text
    assert "Sumber:" in text
    assert "Sewa Kos" in text
    assert "Rp 250.000" in text
