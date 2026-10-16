"""
Phase 7 — Recurring detection + reminders tests.

Covers packages/api/backend/finance/recurring_service.py:

  * monthly cadence detection (day-of-month +/- tolerance), weekly cadence
    (same weekday), confidence scoring, min occurrences, idempotent upsert
    keyed by SHA-256 (WF-09)
  * verification gate (pending -> confirmed template)
  * reminder generation: due-window, period coverage (transaction already
    recorded), period_key dedup (WF-10), next-due recomputation
  * history + mark-sent
  * invalid input errors

All fixtures use hermetic SQLite paths that do NOT contain a canonical
Postgres bridge target substring (e.g. "finance.db").
"""
from datetime import date, timedelta

import pytest

from packages.api.backend.finance import ledger_engine as ledger
from packages.api.backend.finance import recurring_service as rs


@pytest.fixture
def ledger_db(tmp_path):
    path = str(tmp_path / "recurring_ledger.sqlite")
    ledger.seed_defaults(path)
    return path


def _tx(ledger_db, ttype, amount, tx_date, category, description=None, merchant=None):
    return ledger.record_transaction(
        ledger_db, ttype=ttype, amount=amount, tx_date=tx_date,
        category=category, description=description,
        merchant_id=(ledger.remember_merchant(ledger_db, merchant)["id"] if merchant else None),
        source="test",
    )


# ═════════════════════════════════════════════════════════════════════════════
# § Detection
# ═════════════════════════════════════════════════════════════════════════════

def test_detect_monthly_cadence(ledger_db):
    _tx(ledger_db, "expense", 250000, date(2026, 6, 10), "rent", description="Sewa Kos", merchant="kos")
    _tx(ledger_db, "expense", 250000, date(2026, 7, 12), "rent", description="Sewa Kos", merchant="kos")
    _tx(ledger_db, "expense", 250000, date(2026, 8, 11), "rent", description="Sewa Kos", merchant="kos")

    result = rs.detect_recurring(ledger_db, as_of=date(2026, 8, 17))
    assert result["detected"] == 1
    cand = result["candidates"][0]
    assert cand["frequency"] == "monthly"
    assert cand["amount"] == 250_000.0
    assert cand["occurrences"] == 3
    assert cand["confidence"] >= 0.35
    assert cand["next_due"] >= "2026-08-17"
    assert cand["category"] == "rent"


def test_detect_weekly_cadence(ledger_db):
    for week in range(3):
        _tx(ledger_db, "expense", 45000, date(2026, 8, 3) + timedelta(days=7 * week), "food", description="GoFood")
    result = rs.detect_recurring(ledger_db, as_of=date(2026, 8, 17))
    cand = result["candidates"][0]
    assert cand["frequency"] == "weekly"
    assert cand["day_of_week"] == 0  # Mondays
    assert cand["occurrences"] == 3


def test_detect_ignores_single_occurrence_and_irregular(ledger_db):
    _tx(ledger_db, "expense", 100000, date(2026, 7, 1), "other", description="Sekali bayar")
    _tx(ledger_db, "expense", 200000, date(2026, 6, 2), "other", description="Acak")
    _tx(ledger_db, "expense", 50000, date(2026, 8, 2), "other", description="Acak")
    result = rs.detect_recurring(ledger_db, as_of=date(2026, 8, 17))
    assert result["detected"] == 0


def test_detect_excludes_transfers(ledger_db):
    accounts = {a["name"]: a for a in ledger.list_accounts(ledger_db)}
    a, b = list(accounts.values())[0], accounts.get("Cash")
    if b is None:
        b = ledger.create_account(ledger_db, "Cash", account_type="cash")
    for month in (6, 7, 8):
        ledger.record_transfer(
            ledger_db, from_account_id=a["id"], to_account_id=b["id"],
            amount=500000, tx_date=date(2026, month, 15), check_balance=False,
        )
    result = rs.detect_recurring(ledger_db, as_of=date(2026, 8, 17))
    assert result["detected"] == 0


def test_detect_detects_income_cadence(ledger_db):
    for month in (6, 7, 8):
        _tx(ledger_db, "income", 5_000_000, date(2026, month, 1), "Salary", description="Gaji")
    result = rs.detect_recurring(ledger_db, as_of=date(2026, 8, 17))
    cand = result["candidates"][0]
    assert cand["tx_type"] == "income"
    assert cand["frequency"] == "monthly"
    assert cand["day_of_month"] == 1


def test_detect_idempotent_upsert(ledger_db):
    _tx(ledger_db, "expense", 250000, date(2026, 6, 10), "rent", description="Sewa Kos")
    _tx(ledger_db, "expense", 250000, date(2026, 7, 12), "rent", description="Sewa Kos")
    _tx(ledger_db, "expense", 250000, date(2026, 8, 11), "rent", description="Sewa Kos")
    rs.detect_recurring(ledger_db, as_of=date(2026, 8, 17))
    candidates = rs.list_candidates(ledger_db)
    assert len(candidates) == 1
    rs.detect_recurring(ledger_db, as_of=date(2026, 8, 17))
    assert len(rs.list_candidates(ledger_db)) == 1


def test_detect_rejects_bad_lookback(ledger_db):
    with pytest.raises(rs.RecurringError):
        rs.detect_recurring(ledger_db, months_lookback=1)


# ═════════════════════════════════════════════════════════════════════════════
# § Verification
# ═════════════════════════════════════════════════════════════════════════════

def test_verify_candidate_gate(ledger_db):
    _tx(ledger_db, "expense", 250000, date(2026, 6, 10), "rent", description="Sewa Kos")
    _tx(ledger_db, "expense", 250000, date(2026, 7, 12), "rent", description="Sewa Kos")
    _tx(ledger_db, "expense", 250000, date(2026, 8, 11), "rent", description="Sewa Kos")
    rs.detect_recurring(ledger_db, as_of=date(2026, 8, 17))

    pending = rs.list_candidates(ledger_db, status="pending")
    assert len(pending) == 1 and not pending[0]["is_confirmed"]

    result = rs.verify_candidate(ledger_db, pending[0]["candidate_id"], confirmed=True)
    assert result["is_confirmed"] is True
    confirmed = rs.list_candidates(ledger_db, status="confirmed")
    assert len(confirmed) == 1 and confirmed[0]["is_confirmed"]

    rs.verify_candidate(ledger_db, confirmed[0]["candidate_id"], confirmed=False)
    assert rs.list_candidates(ledger_db, status="pending")


def test_verify_unknown_candidate_raises(ledger_db):
    with pytest.raises(rs.RecurringError):
        rs.verify_candidate(ledger_db, 9999, confirmed=True)


def test_list_candidates_bad_status(ledger_db):
    with pytest.raises(rs.RecurringError):
        rs.list_candidates(ledger_db, status="bogus")


# ═════════════════════════════════════════════════════════════════════════════
# § Reminders
# ═════════════════════════════════════════════════════════════════════════════

def _monthly_template(ledger_db, day=10, amount=250000, as_of=date(2026, 8, 17)):
    _tx(ledger_db, "expense", amount, date(2026, 5, day), "rent", description="Sewa Kos")
    _tx(ledger_db, "expense", amount, date(2026, 6, day), "rent", description="Sewa Kos")
    _tx(ledger_db, "expense", amount, date(2026, 7, day), "rent", description="Sewa Kos")
    rs.detect_recurring(ledger_db, as_of=as_of)
    cand = rs.list_candidates(ledger_db)[0]
    rs.verify_candidate(ledger_db, cand["candidate_id"], confirmed=True)
    return cand


def test_reminder_generated_when_due_in_window(ledger_db):
    """Due 16 Aug, check runs 17 Aug → past-due within lookback → remind."""
    cand = _monthly_template(ledger_db, day=16)
    result = rs.generate_reminders(ledger_db, as_of=date(2026, 8, 17))
    assert len(result["new_reminders"]) == 1
    reminder = result["new_reminders"][0]
    assert reminder["candidate_id"] == cand["candidate_id"]
    assert reminder["amount"] == 250_000.0
    assert reminder["due_date"] == "2026-08-16"
    assert reminder["period_key"] == "2026-08"


def test_reminder_dedup_on_repeat_checks(ledger_db):
    _monthly_template(ledger_db, day=16)
    rs.generate_reminders(ledger_db, as_of=date(2026, 8, 17))
    second = rs.generate_reminders(ledger_db, as_of=date(2026, 8, 17))
    assert second["new_reminders"] == []


def test_reminder_skipped_when_transaction_recorded(ledger_db):
    _monthly_template(ledger_db, day=16)
    _tx(ledger_db, "expense", 250000, date(2026, 8, 16), "rent", description="Sewa Kos")
    result = rs.generate_reminders(ledger_db, as_of=date(2026, 8, 17))
    assert result["new_reminders"] == []
    assert len(rs.list_reminders(ledger_db)) == 0


def test_reminder_not_generated_when_not_due(ledger_db):
    """Due 20 Aug, check runs 17 Aug (horizon 19 Aug) → not due yet."""
    _monthly_template(ledger_db, day=20)
    result = rs.generate_reminders(ledger_db, as_of=date(2026, 8, 17))
    assert result["new_reminders"] == []


def test_reminder_weekly_next_due(ledger_db):
    for week in range(3):
        _tx(ledger_db, "expense", 45000, date(2026, 8, 3) + timedelta(days=7 * week), "food", description="GoFood")
    rs.detect_recurring(ledger_db, as_of=date(2026, 8, 17))
    cand = rs.list_candidates(ledger_db)[0]
    rs.verify_candidate(ledger_db, cand["candidate_id"], confirmed=True)

    result = rs.generate_reminders(ledger_db, as_of=date(2026, 8, 24))
    assert len(result["new_reminders"]) == 1
    assert result["new_reminders"][0]["due_date"] == "2026-08-24"
    assert result["new_reminders"][0]["period_key"].startswith("2026-W")


def test_reminder_period_key_prevents_next_month_duplicate(ledger_db):
    _monthly_template(ledger_db, day=16)
    rs.generate_reminders(ledger_db, as_of=date(2026, 8, 17))
    # Next month's check without new transactions: new period key → new reminder
    result = rs.generate_reminders(ledger_db, as_of=date(2026, 9, 17))
    assert len(result["new_reminders"]) == 1
    assert result["new_reminders"][0]["period_key"] == "2026-09"


def test_reminder_mark_sent_and_history(ledger_db):
    _monthly_template(ledger_db, day=16)
    result = rs.generate_reminders(ledger_db, as_of=date(2026, 8, 17))
    reminder_id = result["new_reminders"][0]["reminder_id"]

    sent = rs.mark_reminder_sent(ledger_db, reminder_id)
    assert sent["status"] == "sent"
    pending = rs.list_reminders(ledger_db, status="pending")
    assert pending == []
    sent_list = rs.list_reminders(ledger_db, status="sent")
    assert len(sent_list) == 1 and sent_list[0]["reminder_id"] == reminder_id
    assert rs.list_reminders(ledger_db)[0]["status"] == "sent"


def test_reminder_mark_sent_unknown_raises(ledger_db):
    with pytest.raises(rs.RecurringError):
        rs.mark_reminder_sent(ledger_db, 9999)
