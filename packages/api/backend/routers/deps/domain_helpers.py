"""
backend/routers/deps/domain_helpers.py — Small domain-specific helpers
======================================================================
Currently: cash split (legacy manual balance migration) and crypto portfolio
value calculator.

Extracted from deps.py (M3 refactor, 2026-09-05). The crypto helper has a
pre-existing bug (line `total += r["buy_price"] * get_live_fx_rate() * qty` —
get_live_fx_rate is async, called sync → coroutine). Tracked in test failure
test_get_crypto_from_portfolio_no_n1; not fixed in this refactor.
"""
import logging
import os
from datetime import datetime

from packages.core.infrastructure.config import Config
from packages.core.infrastructure.persistence.database import Database

from packages.api.backend.routers.deps.legacy_bridge import (
    _execute,
    _query,
    get_live_fx_rate,
)

logger = logging.getLogger("backend.deps")


def _get_cash_split(db: str) -> dict:
    """Return the current physical_cash / bank_savings row (auto-seeds if missing)."""
    rows = _query(db, "SELECT physical_cash, bank_savings FROM cash_split WHERE id=?", (1,))
    if rows:
        return {"physical_cash": rows[0]["physical_cash"], "bank_savings": rows[0]["bank_savings"]}

    # Seed: migrate legacy 'cash' balance into bank_savings
    legacy = _query(db, "SELECT value FROM manual_balances WHERE key=?", ("cash",))
    legacy_val = legacy[0]["value"] if legacy else 0.0
    _execute(db,
        "INSERT INTO cash_split (id, physical_cash, bank_savings, updated_at) "
        "VALUES (1,?,?,?) ON CONFLICT(id) DO UPDATE SET "
        "physical_cash=excluded.physical_cash, bank_savings=excluded.bank_savings, updated_at=excluded.updated_at",
        (0.0, legacy_val, datetime.now().isoformat()))
    return {"physical_cash": 0.0, "bank_savings": legacy_val}


def _get_crypto_from_portfolio() -> float:
    """Load crypto value directly from portfolio.db. READ-ONLY.

    Pre-existing bug: get_live_fx_rate() is async but called sync here, so
    on the buy_price fallback path this returns a coroutine, not a float.
    Tracked by test_get_crypto_from_portfolio_no_n1; not fixed in M3.
    """
    try:
        inv_db = Config.get_db_path("investment")
        if not os.path.exists(inv_db):
            return 0.0
        # Use Database utility with an optimized JOIN instead of a correlated subquery
        rows = Database.query(inv_db,
            """
            SELECT i.remaining_quantity, i.buy_price, i.buy_currency, h.price_idr AS current_price_idr
            FROM investments i
            LEFT JOIN (
                SELECT investment_id, MAX(id) as max_id
                FROM historical_prices
                GROUP BY investment_id
            ) hm ON hm.investment_id = i.id
            LEFT JOIN historical_prices h ON h.id = hm.max_id
            WHERE i.status != ? AND i.asset_type = ?
            """, ("sold", "crypto"))

        total = 0.0
        for r in rows:
            qty = r["remaining_quantity"] or 0
            if r["current_price_idr"]:
                total += r["current_price_idr"] * qty
            elif r["buy_currency"] == "IDR":
                total += r["buy_price"] * qty
            else:
                total += r["buy_price"] * get_live_fx_rate() * qty
        return total
    except Exception as e:
        logger.error(f"Error calculating crypto from portfolio: {e}")
        return 0.0
