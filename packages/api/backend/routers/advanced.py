"""
backend/routers/advanced.py — Advanced Features: Goals, Forecast, Budget
=========================================================================
Extracted from api_server.py as part of Step 5 router split.
Architecture: High Cohesion — this file owns only /api/goals|/api/forecast|/api/budget routes.
Low Coupling : depends only on backend/routers/deps.py and FastAPI. Never imports other routers.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from packages.api.backend.routers.deps import (
    _budget_db,
    _db,
    _execute,
    _month_range,
    _query,
)
from packages.api.backend.security.core import require_scope

"""
backend/routers/advanced.py — Advanced Features: Goals, Forecast, Budget
=========================================================================
Extracted from api_server.py as part of Step 5 router split.
Architecture: High Cohesion — this file owns only /api/goals|/api/forecast|/api/budget routes.
Low Coupling : depends only on backend/routers/deps.py and FastAPI. Never imports other routers.
"""







router = APIRouter(dependencies=[Depends(require_scope("write"))])
logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════
# § SECTION 7 — ADVANCED FEATURES
#   Goal-Based Saving  ·  Cashflow Forecasting  ·  Budget Planning
# ═════════════════════════════════════════════════════════════════════

# ── Goals ──────────────────────────────────────────────────────────────────────
# Moved to routers/goals.py (Phase 8): typed PATCH fix, progress/status
# endpoints (n8n WF-11), goals_service.py canonical engine.


# ── Cashflow Forecasting ──────────────────────────────────────────────────────
# Moved to routers/forecast.py (Phase 9): deterministic engine, transparent
# Known/Expected/Estimated/Forecast labels, canonical-ledger based.


# ── Budget Planning ────────────────────────────────────────────────────────────

@router.get("/api/budget/{year}/{month}")
def get_budget(year: int, month: int):
    """Budget status + auto-suggestion (10% below prev month) + recommendation messages."""
    if not (1 <= month <= 12):
        raise HTTPException(400, "Invalid month. Month must be between 1 and 12.")
    exp_db = _db("expense_tracker", "expense.db")
    bdb    = _budget_db()
    s,  e  = _month_range(year, month)
    py, pm = (year - 1, 12) if month == 1 else (year, month - 1)
    ps, pe = _month_range(py, pm)

    current: dict = {}
    prev:    dict = {}
    try:
        rows = _query(exp_db, "SELECT category, SUM(amount) as total FROM expenses WHERE date>=? AND date<? GROUP BY category", (s, e))
        for r in rows: current[r["category"]] = float(r["total"] or 0)

        prows = _query(exp_db, "SELECT category, SUM(amount) as total FROM expenses WHERE date>=? AND date<? GROUP BY category", (ps, pe))
        for r in prows: prev[r["category"]] = float(r["total"] or 0)
    except Exception as ex:
        logger.error(f"Error fetching actuals for budget: {ex}")

    limits: dict = {}
    try:
        lrows = _query(bdb, "SELECT category, limit_amt FROM budgets WHERE year=? AND month=?", (year, month))
        for r in lrows: limits[r["category"]] = float(r["limit_amt"] or 0)
    except Exception as ex:
        logger.error(f"Error fetching budget limits: {ex}")

    result = []
    for cat in sorted(set(list(current) + list(prev) + list(limits))):
        cur_amt  = current.get(cat, 0)
        prev_amt = prev.get(cat, 0)
        lim      = limits.get(cat)
        pct_chg  = round((cur_amt - prev_amt) / prev_amt * 100, 1) if (prev_amt or 0) > 0 else None
        result.append({
            "category":       cat,
            "current":        cur_amt,
            "prev_month":     prev_amt,
            "limit":          lim,
            "suggestion":     round(prev_amt * 0.90, 0) if prev_amt > 0 else None,
            "pct_change":     pct_chg,
            "near_limit":     bool(lim and cur_amt >= lim * 0.80),
            "over_limit":     bool(lim and cur_amt >= lim),
            "recommendation": (
                f"Your {cat} spending increased {pct_chg:.0f}% this month."
                if pct_chg is not None and pct_chg > 20 else None
            ),
        })

    return {"year": year, "month": month, "categories": result}


@router.post("/api/budget/{year}/{month}")
def set_budget(year: int, month: int, body: dict):
    cat   = body.get("category", "total").strip().lower()
    limit = float(body.get("limit", 0))
    if limit <= 0:
        raise HTTPException(400, "limit must be > 0")
    bdb = _budget_db()
    _execute(bdb,
        "INSERT INTO budgets(year,month,category,limit_amt) VALUES(?,?,?,?)"
        " ON CONFLICT(year,month,category) DO UPDATE SET limit_amt=excluded.limit_amt",
        (year, month, cat, limit))
    return {"ok": True}


@router.delete("/api/budget/{year}/{month}/{category}")
def delete_budget(year: int, month: int, category: str):
    _execute(_budget_db(), "DELETE FROM budgets WHERE year=? AND month=? AND category=?", (year, month, category))
    return {"ok": True}


