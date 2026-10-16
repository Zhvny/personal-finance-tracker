"""
backend/routers/balances.py — Balances — Core accounting model
===============================================================
Extracted from api_server.py as part of Step 5 router split.
Architecture: High Cohesion — this file owns only /api/balances routes.
Low Coupling : depends only on backend/routers/deps.py and FastAPI. Never imports other routers.
"""

import logging
import os
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException

from packages.api.backend.routers.deps import (
    _balances_db,
    _db,
    _execute,
    _get_cash_split,
    _get_crypto_from_portfolio,
    _month_range,
    _query,
    get_live_fx_rate,
)
from packages.api.backend.security.core import require_scope

router = APIRouter(dependencies=[Depends(require_scope("write"))])
logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════
# ═════════════════════════════════════════════════════════════════════
# BALANCES — Core accounting model
#
# Data model:
#   physical_cash   — editable via transfer system only
#   bank_savings    — editable via transfer system only
#   emergency_fund  — directly editable (the ONLY manually editable field)
#   cash_on_hand    — COMPUTED: (physical_cash + bank_savings) - emergency_fund
#   crypto          — READ-ONLY, sourced from portfolio.db
#
# Invariant:
#   Total Credit = Income - Expense = physical_cash + bank_savings
#   Transfers only move value between physical_cash <-> bank_savings,
#   they never change Total Credit.
# ═════════════════════════════════════════════════════════════════════



def _get_crypto_from_portfolio() -> float:
    """
    Feature 3: Load crypto value directly from portfolio.db.
    This is READ-ONLY — never edited via the balance API.
    """
    try:
        inv_db = _db("investment_tracker", "portfolio.db")
        if not os.path.exists(inv_db):
            return 0.0
        rows = _query(inv_db,
            "SELECT i.remaining_quantity, i.buy_price, i.buy_currency, "
            "  (SELECT price_idr FROM historical_prices h WHERE h.investment_id=i.id "
            "   ORDER BY h.id DESC LIMIT 1) AS current_price_idr "
            "FROM investments i WHERE i.status != ? AND i.asset_type = ?", ("sold", "crypto"))
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
    except Exception:
        logger.warning("Failed to computing balance", exc_info=True)
        return 0.0


@router.get("/api/balances")
def get_balances():
    """
    Returns the full balance state.
    bank_savings = authoritative all-time net (Income - Expense), auto-synced on each call.
    physical_cash is informational split managed via Transfer.
    emergency_fund is the only manually-editable field.
    """
    db = _balances_db()
    split = _get_cash_split(db)
    physical_cash = split["physical_cash"]

    # Authoritative total credit = all-time net (Income - Expense)
    exp_db = _db("expense_tracker", "expense.db")
    inc_db = _db("income_tracker",  "income.db")
    try:
        all_inc = _query(inc_db, "SELECT COALESCE(SUM(amount),0) AS t FROM incomes")[0]["t"]
        all_exp = _query(exp_db, "SELECT COALESCE(SUM(amount),0) AS t FROM expenses")[0]["t"]
        total_credit = max(0.0, float(all_inc) - float(all_exp))
    except Exception:
        total_credit = split["bank_savings"] + split["physical_cash"]

    # Preserve the physical_cash / bank_savings split ratio when total changes.
    # If total_credit changed, scale physical_cash proportionally so the user's
    # transfer allocation is maintained rather than silently reset.
    stored_total = split["physical_cash"] + split["bank_savings"]
    if stored_total > 0.01 and abs(stored_total - total_credit) > 0.01:
        ratio = split["physical_cash"] / stored_total
        physical_cash = round(total_credit * ratio, 2)
        bank_savings  = round(total_credit - physical_cash, 2)
        _execute(db,
            "INSERT INTO cash_split (id, physical_cash, bank_savings, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET physical_cash=excluded.physical_cash, bank_savings=excluded.bank_savings, updated_at=excluded.updated_at",
            (1, physical_cash, bank_savings, datetime.now().isoformat()))
    elif stored_total <= 0.01:
        # First time / fresh seed: put everything in bank_savings
        physical_cash = 0.0
        bank_savings  = total_credit
        _execute(db,
            "INSERT INTO cash_split (id, physical_cash, bank_savings, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET physical_cash=excluded.physical_cash, bank_savings=excluded.bank_savings, updated_at=excluded.updated_at",
            (1, physical_cash, bank_savings, datetime.now().isoformat()))
    else:
        bank_savings = split["bank_savings"]

    ef_rows = _query(db, "SELECT value FROM manual_balances WHERE key=?", ('emergency_fund',))

    emergency_fund = ef_rows[0]["value"] if ef_rows else 0.0

    cash_on_hand = (physical_cash + bank_savings) - emergency_fund
    crypto = _get_crypto_from_portfolio()

    return {
        "physical_cash":  physical_cash,
        "bank_savings":   bank_savings,
        "emergency_fund": emergency_fund,
        "cash_on_hand":   cash_on_hand,
        "crypto":         crypto,
        "crypto_source":  "portfolio.db",
    }


@router.put("/api/balances/emergency_fund")
def set_emergency_fund(body: dict):
    """
    Feature 1: Only Emergency Fund is directly editable.
    Validates that emergency_fund <= bank_savings (Total Credit = Bank Savings).
    """
    value = float(body.get("value", 0))
    if value < 0:
        raise HTTPException(status_code=400, detail="Emergency Fund cannot be negative.")

    db = _balances_db()
    split = _get_cash_split(db)
    total_credit = split["bank_savings"]  # Total Credit = Bank Savings (net current position)

    if value > total_credit:
        raise HTTPException(
            status_code=400,
            detail=f"Emergency Fund (Rp{value:,.0f}) cannot exceed Bank Savings (Rp{total_credit:,.0f})."
        )

    _execute(db,
        "INSERT INTO manual_balances (key, value, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        ("emergency_fund", value, datetime.now().isoformat()))
    return {"key": "emergency_fund", "value": value}


@router.put("/api/balances/{key}")
def set_balance_legacy(key: str, body: dict):
    """
    Legacy endpoint kept for backward compatibility.
    'cash' and 'crypto' keys are no longer directly writable.
    Routes 'emergency_fund' to the new handler logic.
    """
    if key == "emergency_fund":
        return set_emergency_fund(body)
    if key in ("cash", "crypto"):
        raise HTTPException(
            status_code=400,
            detail=f"'{key}' is not directly editable. "
                   "Cash is managed via the transfer system. Crypto is synced from portfolio.db."
        )
    raise HTTPException(status_code=400, detail=f"Unknown balance key: {key}")


@router.post("/api/balances/sync-total-credit")
def sync_total_credit(body: dict):
    """
    Called automatically when income or expenses change.
    Distributes new Total Credit proportionally into physical_cash / bank_savings
    while preserving the existing split ratio.
    """
    new_total = float(body.get("total_credit", 0))
    if new_total < 0:
        raise HTTPException(status_code=400, detail="Total Credit cannot be negative.")

    db = _balances_db()
    split = _get_cash_split(db)
    old_total = split["physical_cash"] + split["bank_savings"]

    if old_total == 0:
        # Default: all goes to bank_savings
        new_physical = 0.0
        new_savings  = new_total
    else:
        ratio = split["physical_cash"] / old_total
        new_physical = round(new_total * ratio, 2)
        new_savings  = round(new_total * (1 - ratio), 2)

    _execute(db,
        "INSERT INTO cash_split (id, physical_cash, bank_savings, updated_at) VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET physical_cash=excluded.physical_cash, bank_savings=excluded.bank_savings, updated_at=excluded.updated_at",
        (1, new_physical, new_savings, datetime.now().isoformat()))
    return {"physical_cash": new_physical, "bank_savings": new_savings, "total_credit": new_total}


@router.post("/api/balances/transfer")
def transfer_balance(body: dict):
    """
    Feature 2: Internal transfer between physical_cash and bank_savings.
    Does NOT affect Total Credit. Validates no negative balances result.
    Direction: 'physical_to_bank' or 'bank_to_physical'
    """
    direction = body.get("direction", "")
    amount    = float(body.get("amount", 0))
    note      = body.get("note", "")

    if direction not in ("physical_to_bank", "bank_to_physical"):
        logger.error(f"Invalid transfer direction: {direction}")
        raise HTTPException(status_code=400, detail="direction must be 'physical_to_bank' or 'bank_to_physical'")
    if amount <= 0:
        logger.error(f"Invalid transfer amount: {amount}")
        raise HTTPException(status_code=400, detail="Transfer amount must be positive.")


    db = _balances_db()
    now = datetime.now().isoformat()

    if direction == "physical_to_bank":
        # Atomic Update: Decrease physical, increase bank, only if physical >= amount
        rowcount = _execute(db,
            "UPDATE cash_split SET physical_cash = physical_cash - ?, bank_savings = bank_savings + ?, updated_at = ? "
            "WHERE id = 1 AND physical_cash >= ?",
            (amount, amount, now, amount))
        if not rowcount:
            raise HTTPException(status_code=400, detail="Insufficient Physical Cash or transaction failed.")
    else:
        # Atomic Update: Decrease bank, increase physical, only if bank >= amount
        rowcount = _execute(db,
            "UPDATE cash_split SET physical_cash = physical_cash + ?, bank_savings = bank_savings - ?, updated_at = ? "
            "WHERE id = 1 AND bank_savings >= ?",
            (amount, amount, now, amount))
        if not rowcount:
            raise HTTPException(status_code=400, detail="Insufficient Bank Savings or transaction failed.")

    _execute(db,
        "INSERT INTO transfer_log (direction, amount, note, created_at) VALUES (?,?,?,?)",
        (direction, amount, note, now))

    # Fetch final state for response
    final_split = _get_cash_split(db)
    return {
        "physical_cash": final_split["physical_cash"],
        "bank_savings":  final_split["bank_savings"],
        "transferred":   amount,
        "direction":     direction,
    }


@router.get("/api/balances/transfers")
def get_transfer_log():
    """Return the last 50 internal transfer records."""
    db = _balances_db()
    rows = _query(db,
        "SELECT id, direction, amount, note, created_at FROM transfer_log ORDER BY id DESC LIMIT 50")
    return rows



@router.get("/api/balances/total-credit")
def get_total_credit():
    """
    Returns Total Credit (Income - Expense):
      - this_month : current calendar month
      - all_time   : sum of ALL recorded transactions ever
      - by_month   : last 12 months breakdown for history/sparkline
    """
    exp_db = _db("expense_tracker", "expense.db")
    inc_db = _db("income_tracker",  "income.db")

    inc_rows = _query(inc_db, "SELECT COALESCE(SUM(amount), 0) as t FROM incomes")
    all_income = inc_rows[0]["t"] if inc_rows else 0.0
    exp_rows = _query(exp_db, "SELECT COALESCE(SUM(amount), 0) as t FROM expenses")
    all_expense = exp_rows[0]["t"] if exp_rows else 0.0
    all_time_credit = all_income - all_expense

    now = datetime.now()
    y, m = now.year, now.month
    s, e = _month_range(y, m)
    inc_this_rows = _query(inc_db, "SELECT COALESCE(SUM(amount), 0) as t FROM incomes WHERE date>=? AND date<?", (s, e))
    inc_this = inc_this_rows[0]["t"] if inc_this_rows else 0.0
    exp_this_rows = _query(exp_db, "SELECT COALESCE(SUM(amount), 0) as t FROM expenses WHERE date>=? AND date<?", (s, e))
    exp_this = exp_this_rows[0]["t"] if exp_this_rows else 0.0
    this_month_credit = inc_this - exp_this

    # Single GROUP BY query per DB replaces 12 separate queries each
    start_mo = m - 11
    start_yr = y
    while start_mo <= 0:
        start_mo += 12; start_yr -= 1
    period_start = f"{start_yr:04d}-{start_mo:02d}-01"
    period_end   = e  # already computed above

    inc_rows = _query(inc_db,
        "SELECT to_char(date, 'YYYY-MM') AS ym, SUM(amount) AS t "
        "FROM incomes WHERE date>=? AND date<? GROUP BY ym", (period_start, period_end))
    exp_rows = _query(exp_db,
        "SELECT to_char(date, 'YYYY-MM') AS ym, SUM(amount) AS t "
        "FROM expenses WHERE date>=? AND date<? GROUP BY ym", (period_start, period_end))


    inc_map = {r["ym"]: r["t"] for r in inc_rows}
    exp_map = {r["ym"]: r["t"] for r in exp_rows}

    by_month = []
    for offset in range(11, -1, -1):
        mo = m - offset
        yr = y
        while mo <= 0: mo += 12; yr -= 1
        ym  = f"{yr:04d}-{mo:02d}"
        mi  = inc_map.get(ym, 0.0)
        mex = exp_map.get(ym, 0.0)
        by_month.append({
            "label":   date(yr, mo, 1).strftime("%b %Y"),
            "income":  round(mi, 2),
            "expense": round(mex, 2),
            "credit":  round(mi - mex, 2),
        })

    return {
        "this_month":  round(this_month_credit, 2),
        "all_time":    round(all_time_credit, 2),
        "all_income":  round(all_income, 2),
        "all_expense": round(all_expense, 2),
        "by_month":    by_month,
    }


