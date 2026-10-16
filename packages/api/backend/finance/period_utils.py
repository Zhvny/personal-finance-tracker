"""
backend/finance/period_utils.py — Period coverage check
======================================================
Standalone helper extracted from recurring_service.py (M2 refactor, 2026-09-05).

The function is shared between:
  - recurring_service.generate_reminders   (was a sibling cross-import, line 449)
  - forecast_service.build_cashflow_forecast (was importing a private _period_covered)

Extracted so the constant set (AMOUNT_TOLERANCE, *_LOOK*_DAYS) lives in one
place and the function has a stable public name (period_covered) instead of
a private-underscore symbol leaking across module boundaries.

Schema of `candidate` dict (input contract):
  {
    "tx_type":     str,        # "expense" | "income"
    "category":    str,        # e.g. "rent", "food"
    "description": Optional[str],
    "amount":      float,      # 0 means "skip tolerance check"
  }
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict

from packages.core.infrastructure.persistence.database import Database


# Single source of truth — previously duplicated across recurring_service callers.
AMOUNT_TOLERANCE = 0.25
DEFAULT_REMINDER_LOOKAHEAD_DAYS = 2
DEFAULT_REMINDER_LOOKBACK_DAYS = 3


def period_covered(
    ledger_db: str,
    candidate: Dict[str, Any],
    due: date,
    as_of: date,
) -> bool:
    """True when a transaction matching the template already exists in the
    period around the due date (amount within tolerance).

    The window is [due - LOOKBACK_DAYS, min(due + LOOKAHEAD_DAYS, as_of)].
    Used by both reminder generation and cashflow forecasting to suppress
    duplicates for transactions the user has already recorded.
    """
    window_start = due - timedelta(days=DEFAULT_REMINDER_LOOKBACK_DAYS)
    window_end = min(due + timedelta(days=DEFAULT_REMINDER_LOOKAHEAD_DAYS), as_of)
    rows = Database.query(
        ledger_db,
        "SELECT t.amount, COALESCE(m.name, '') AS merchant"
        " FROM transactions t LEFT JOIN merchants m ON m.id = t.merchant_id"
        " WHERE t.type = ? AND t.category = ? AND t.tx_date >= ? AND t.tx_date <= ?"
        " AND COALESCE(t.description, '') = ?",
        (
            candidate["tx_type"], candidate["category"],
            window_start.isoformat(), window_end.isoformat(),
            candidate["description"] or "",
        ),
    )
    if not rows:
        return False
    amount = float(candidate["amount"] or 0)
    for r in rows:
        if amount == 0 or abs(float(r["amount"] or 0) - amount) / amount <= AMOUNT_TOLERANCE:
            return True
    return False


# Backward-compat shim — old private name aliased to new public name.
# Removing this requires updating all callers; for the M2 refactor we keep it
# to avoid breaking external imports (e.g. ad-hoc notebooks, debug scripts).
_period_covered = period_covered
