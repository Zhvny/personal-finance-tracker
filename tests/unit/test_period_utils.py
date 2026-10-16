"""
TDD M2: Test untuk _period_covered (rencana M2 refactor: pindah ke period_utils).

Behavior locked-in sebelum refactor (import dari recurring_service),
test akan tetap PASS setelah refactor (import dari period_utils).
Hanya 1 baris import yang berubah.

Behavior yang diuji:
  - True bila ada transaksi matching (amount dalam tolerance, type+category+description sama)
    di window [due - LOOKBACK, min(due + LOOKAHEAD, as_of)]
  - False bila tidak ada transaksi sama sekali
  - False bila amount di luar tolerance (>25%)
  - True bila amount = 0 (skip tolerance check, line 375)
  - True bila amount persis sama (exact match)
  - Window start di-trim ke as_of (line 360: min(due + LA, as_of))
"""
from datetime import date

import pytest

# Pre-refactor: import dari recurring_service.
# Post-refactor: ganti ke `from packages.api.backend.finance import period_utils as pu`
from packages.api.backend.finance import period_utils as pu
from packages.api.backend.finance import recurring_service as rs
from packages.api.backend.finance import ledger_engine as ledger


@pytest.fixture
def ledger_db(tmp_path):
    path = str(tmp_path / "period_covered_ledger.sqlite")
    ledger.seed_defaults(path)
    return path


def _tx(ledger_db, ttype, amount, tx_date, category, description=None):
    return ledger.record_transaction(
        ledger_db, ttype=ttype, amount=amount, tx_date=tx_date,
        category=category, description=description, source="test",
    )


def test_period_covered_returns_false_when_no_transaction(ledger_db):
    """Empty DB → no match → False."""
    candidate = {
        "tx_type": "expense", "category": "rent",
        "description": "Sewa Kos", "amount": 250_000.0,
    }
    assert rs._period_covered(ledger_db, candidate, due=date(2026, 8, 17), as_of=date(2026, 8, 17)) is False


def test_period_covered_true_when_exact_match_in_window(ledger_db):
    """Transaction with same amount/type/category/description within window → True."""
    _tx(ledger_db, "expense", 250_000, date(2026, 8, 17), "rent", description="Sewa Kos")
    candidate = {
        "tx_type": "expense", "category": "rent",
        "description": "Sewa Kos", "amount": 250_000.0,
    }
    assert rs._period_covered(ledger_db, candidate, due=date(2026, 8, 17), as_of=date(2026, 8, 17)) is True


def test_period_covered_true_within_lookback_window(ledger_db):
    """Transaction 2 days BEFORE due (within LOOKBACK=3) → True."""
    _tx(ledger_db, "expense", 250_000, date(2026, 8, 15), "rent", description="Sewa Kos")
    candidate = {
        "tx_type": "expense", "category": "rent",
        "description": "Sewa Kos", "amount": 250_000.0,
    }
    assert rs._period_covered(ledger_db, candidate, due=date(2026, 8, 17), as_of=date(2026, 8, 17)) is True


def test_period_covered_false_outside_lookback_window(ledger_db):
    """Transaction 5 days BEFORE due (outside LOOKBACK=3) → False."""
    _tx(ledger_db, "expense", 250_000, date(2026, 8, 12), "rent", description="Sewa Kos")
    candidate = {
        "tx_type": "expense", "category": "rent",
        "description": "Sewa Kos", "amount": 250_000.0,
    }
    assert rs._period_covered(ledger_db, candidate, due=date(2026, 8, 17), as_of=date(2026, 8, 17)) is False


def test_period_covered_false_when_amount_outside_tolerance(ledger_db):
    """Transaction with amount >25% different from candidate → False."""
    _tx(ledger_db, "expense", 500_000, date(2026, 8, 17), "rent", description="Sewa Kos")  # 2x
    candidate = {
        "tx_type": "expense", "category": "rent",
        "description": "Sewa Kos", "amount": 250_000.0,
    }
    # abs(500_000 - 250_000) / 250_000 = 1.0 > 0.25 tolerance
    assert rs._period_covered(ledger_db, candidate, due=date(2026, 8, 17), as_of=date(2026, 8, 17)) is False


def test_period_covered_true_when_amount_within_tolerance(ledger_db):
    """Transaction with amount within 25% of candidate → True."""
    _tx(ledger_db, "expense", 260_000, date(2026, 8, 17), "rent", description="Sewa Kos")  # +4%
    candidate = {
        "tx_type": "expense", "category": "rent",
        "description": "Sewa Kos", "amount": 250_000.0,
    }
    # abs(260_000 - 250_000) / 250_000 = 0.04 <= 0.25
    assert rs._period_covered(ledger_db, candidate, due=date(2026, 8, 17), as_of=date(2026, 8, 17)) is True


def test_period_covered_true_when_candidate_amount_zero(ledger_db):
    """Candidate amount=0 skips tolerance check (line 375 short-circuit)."""
    _tx(ledger_db, "expense", 500_000, date(2026, 8, 17), "rent", description="Sewa Kos")
    candidate = {
        "tx_type": "expense", "category": "rent",
        "description": "Sewa Kos", "amount": 0,
    }
    # amount=0 → first branch of `if amount == 0 or ...` is True
    assert rs._period_covered(ledger_db, candidate, due=date(2026, 8, 17), as_of=date(2026, 8, 17)) is True


def test_period_covered_false_when_description_differs(ledger_db):
    """Same amount but different description → False (no match in WHERE)."""
    _tx(ledger_db, "expense", 250_000, date(2026, 8, 17), "rent", description="Different")
    candidate = {
        "tx_type": "expense", "category": "rent",
        "description": "Sewa Kos", "amount": 250_000.0,
    }
    assert rs._period_covered(ledger_db, candidate, due=date(2026, 8, 17), as_of=date(2026, 8, 17)) is False


def test_period_covered_window_clipped_to_as_of(ledger_db):
    """window_end = min(due + LOOKAHEAD, as_of) — future transactions beyond as_of excluded."""
    # Transaction 3 days AFTER due (within LOOKAHEAD=2? No, beyond) AND beyond as_of
    _tx(ledger_db, "expense", 250_000, date(2026, 8, 25), "rent", description="Sewa Kos")
    candidate = {
        "tx_type": "expense", "category": "rent",
        "description": "Sewa Kos", "amount": 250_000.0,
    }
    # due=2026-08-17, as_of=2026-08-17 → window_end = min(2026-08-19, 2026-08-17) = 2026-08-17
    # 2026-08-25 > 2026-08-17 → outside window
    assert rs._period_covered(ledger_db, candidate, due=date(2026, 8, 17), as_of=date(2026, 8, 17)) is False


def test_period_covered_true_within_lookahead_when_as_of_in_future(ledger_db):
    """When as_of > due, lookahead is allowed; transaction 1 day after due matches."""
    _tx(ledger_db, "expense", 250_000, date(2026, 8, 18), "rent", description="Sewa Kos")
    candidate = {
        "tx_type": "expense", "category": "rent",
        "description": "Sewa Kos", "amount": 250_000.0,
    }
    # due=2026-08-17, as_of=2026-08-20 → window_end = min(2026-08-19, 2026-08-20) = 2026-08-19
    # 2026-08-18 within window
    assert rs._period_covered(ledger_db, candidate, due=date(2026, 8, 17), as_of=date(2026, 8, 20)) is True


def test_period_utils_public_name_callable_directly(ledger_db):
    """M2 refactor: the new canonical name is `pu.period_covered`.
    Existing tests above use the `rs._period_covered` alias for backward-compat;
    this test exercises the new public name directly.
    """
    _tx(ledger_db, "expense", 250_000, date(2026, 8, 17), "rent", description="Sewa Kos")
    candidate = {
        "tx_type": "expense", "category": "rent",
        "description": "Sewa Kos", "amount": 250_000.0,
    }
    assert pu.period_covered(ledger_db, candidate, due=date(2026, 8, 17), as_of=date(2026, 8, 17)) is True


def test_recurring_service_alias_points_to_period_utils():
    """The `_period_covered` shim in recurring_service is the same callable as
    `period_covered` in period_utils — not a copy, an alias.
    """
    assert rs._period_covered is pu.period_covered


def test_period_utils_constants_exported():
    """Constants live in period_utils; recurring_service re-imports them.
    No duplicate definition should exist in recurring_service module globals.
    """
    assert pu.AMOUNT_TOLERANCE == 0.25
    assert pu.DEFAULT_REMINDER_LOOKAHEAD_DAYS == 2
    assert pu.DEFAULT_REMINDER_LOOKBACK_DAYS == 3
    # Same identity, not a copy
    assert rs.AMOUNT_TOLERANCE is pu.AMOUNT_TOLERANCE
    assert rs.DEFAULT_REMINDER_LOOKAHEAD_DAYS is pu.DEFAULT_REMINDER_LOOKAHEAD_DAYS
    assert rs.DEFAULT_REMINDER_LOOKBACK_DAYS is pu.DEFAULT_REMINDER_LOOKBACK_DAYS
