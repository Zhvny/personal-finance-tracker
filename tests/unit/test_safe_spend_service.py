"""
Phase 10 — Safe-to-Spend tests.

Covers packages/api/backend/finance/safe_spend_service.py:

  * horizon validation ('today'/'week'/'month'/'N' days, bounds)
  * buffer_pct validation (0..50)
  * balance_now = income - expense including today (transfers excluded)
  * upcoming outflows: only expense templates; Expected vs Estimated labels;
    window excludes today (tomorrow..window_end)
  * safe_to_spend = balance - outflows - buffer
  * negative insight warning when outflows exceed safe balance
  * income templates never reduce safe-to-spend
  * Telegram renderer (format_safe_to_spend_text)

Hermetic SQLite fixture — safe name without a canonical bridge target.
"""
from datetime import date, timedelta

import pytest

from packages.api.backend.finance import ledger_engine as ledger
from packages.api.backend.finance import recurring_service as rrs
from packages.api.backend.finance import safe_spend_service as sss


@pytest.fixture
def ledger_db(tmp_path):
    path = str(tmp_path / "safespend_ledger.sqlite")
    ledger.seed_defaults(path)
    return path


def _tx(ledger_db, ttype, amount, tx_date, category, description=None):
    return ledger.record_transaction(
        ledger_db, ttype=ttype, amount=amount, tx_date=tx_date,
        category=category, description=description, source="test",
    )


def _template(ledger_db, *, tx_type, amount, day_of_month=None, day_of_week=None,
              frequency=None, confirmed=True, as_of=date(2026, 8, 17), category="rent",
              description="Sewa Kos"):
    if frequency == "weekly":
        for week in range(3):
            d = as_of - timedelta(days=7 * (week + 1))
            d = d - timedelta(days=d.weekday() - (day_of_week or 0))
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
# § Validation
# ═════════════════════════════════════════════════════════════════════════════

def test_horizon_validation(ledger_db):
    assert sss._horizon_days("today") == 1
    assert sss._horizon_days("week") == 7
    assert sss._horizon_days("month") == 30
    assert sss._horizon_days(14) == 14
    with pytest.raises(sss.SafeSpendError):
        sss._horizon_days("year")
    with pytest.raises(sss.SafeSpendError):
        sss._horizon_days(0)
    with pytest.raises(sss.SafeSpendError):
        sss._horizon_days(91)
    with pytest.raises(sss.SafeSpendError):
        sss._horizon_days(None)


def test_buffer_validation(ledger_db):
    assert sss._validate_buffer_pct(0) == 0.0
    assert sss._validate_buffer_pct("12.5") == 12.5
    assert sss._validate_buffer_pct(50) == 50.0
    with pytest.raises(sss.SafeSpendError):
        sss._validate_buffer_pct(-1)
    with pytest.raises(sss.SafeSpendError):
        sss._validate_buffer_pct(51)
    with pytest.raises(sss.SafeSpendError):
        sss._validate_buffer_pct("abc")


# ═════════════════════════════════════════════════════════════════════════════
# § Balance & outflows
# ═════════════════════════════════════════════════════════════════════════════

def test_balance_includes_today_excludes_transfers(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _tx(ledger_db, "expense", 500_000, date(2026, 8, 16), "Food", description="Belanja")
    _tx(ledger_db, "expense", 50_000, as_of, "Food", description="Kopi hari ini")
    accounts = {a["name"]: a for a in ledger.list_accounts(ledger_db)}
    other = accounts.get("Cash")
    if other is None:
        other = ledger.create_account(ledger_db, "Cash", account_type="cash")
    first = list(accounts.values())[0]
    ledger.record_transfer(
        ledger_db, from_account_id=first["id"], to_account_id=other["id"],
        amount=2_000_000, tx_date=date(2026, 8, 10), check_balance=False,
    )
    result = sss.build_safe_to_spend(ledger_db, horizon="week", buffer_pct=0, as_of=as_of)
    assert result["current_balance"] == 9_450_000.0


def test_only_expense_templates_reduce_safe_to_spend(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _template(ledger_db, tx_type="expense", amount=250_000, day_of_month=20,
              confirmed=True, as_of=as_of, description="Sewa Kos")   # due 20 Aug
    _template(ledger_db, tx_type="income", amount=3_000_000, day_of_month=25,
              confirmed=True, as_of=as_of, category="Salary", description="Bonus")  # inflow ignored

    result = sss.build_safe_to_spend(ledger_db, horizon="month", buffer_pct=0, as_of=as_of)
    assert result["expected_outflows"] == -250_000.0
    assert result["estimated_outflows"] == 0.0
    assert result["upcoming_outflows"] == -250_000.0
    # balance 10jt + 9jt income seeds - 750k expense seeds = 18.25jt
    assert result["safe_to_spend"] == 18_250_000.0 - 250_000.0
    assert len(result["sources"]) == 1
    src = result["sources"][0]
    assert src["label"] == "Expected"
    assert src["due_date"] == "2026-08-20"


def test_estimated_and_expected_split(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _template(ledger_db, tx_type="expense", amount=250_000, day_of_month=20,
              confirmed=True, as_of=as_of, description="Sewa Kos")
    _template(ledger_db, tx_type="expense", amount=75_000, day_of_month=21,
              confirmed=False, as_of=as_of, category="food", description="GoFood")
    result = sss.build_safe_to_spend(ledger_db, horizon="week", buffer_pct=0, as_of=as_of)
    assert result["expected_outflows"] == -250_000.0
    assert result["estimated_outflows"] == -75_000.0
    labels = {s["label"] for s in result["sources"]}
    assert labels == {"Expected", "Estimated"}


def test_window_excludes_today_but_includes_weekend(ledger_db):
    as_of = date(2026, 8, 17)  # Monday
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _template(ledger_db, tx_type="expense", amount=45_000, day_of_week=0,
              frequency="weekly", confirmed=True, as_of=as_of, category="food",
              description="GoFood")  # due every Monday incl. today + next Mon
    result = sss.build_safe_to_spend(ledger_db, horizon="week", buffer_pct=0, as_of=as_of)
    due_dates = [s["due_date"] for s in result["sources"]]
    assert due_dates == ["2026-08-24"]  # today excluded, next Monday included


# ═════════════════════════════════════════════════════════════════════════════
# § Buffer & insight
# ═════════════════════════════════════════════════════════════════════════════

def test_buffer_amount_and_safe_formula(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _template(ledger_db, tx_type="expense", amount=250_000, day_of_month=20,
              confirmed=True, as_of=as_of, description="Sewa Kos")
    result = sss.build_safe_to_spend(ledger_db, horizon="month", buffer_pct=10, as_of=as_of)
    # balance = 10jt - 750k seeds = 9.25jt; buffer 10% = 925k
    assert result["buffer_amount"] == 925_000.0
    assert result["safe_to_spend"] == 9_250_000.0 - 250_000.0 - 925_000.0
    assert result["insight"]["warning"] is False


def test_negative_insight_warning(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "expense", 100_000, date(2026, 8, 16), "Food", description="Belanja")
    _template(ledger_db, tx_type="expense", amount=250_000, day_of_month=18,
              confirmed=True, as_of=as_of, description="Sewa Kos")  # due tomorrow
    result = sss.build_safe_to_spend(ledger_db, horizon="week", buffer_pct=0, as_of=as_of)
    # balance -100k - 750k seeds = -850k; outflow -250k → -1.1jt
    assert result["safe_to_spend"] == -1_100_000.0
    assert result["insight"]["warning"] is True
    assert "tidak cukup" in result["insight"]["message_id"]


# ═════════════════════════════════════════════════════════════════════════════
# § Telegram renderer
# ═════════════════════════════════════════════════════════════════════════════

def test_format_safe_to_spend_text(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _template(ledger_db, tx_type="expense", amount=250_000, day_of_month=20,
              confirmed=True, as_of=as_of, description="Sewa Kos")
    result = sss.build_safe_to_spend(ledger_db, horizon="month", buffer_pct=10, as_of=as_of)
    text = sss.format_safe_to_spend_text(result)
    assert "Aman Belanja" in text
    assert "Saldo saat ini" in text
    assert "Expected" in text
    assert "Buffer aman" in text
    assert "Safe-to-spend" in text
    assert "Sumber pengeluaran" in text
    assert "Sewa Kos" in text
    assert "Rp 250.000" in text
