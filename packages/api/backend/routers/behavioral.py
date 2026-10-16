import logging

"""

backend/routers/behavioral.py â€” Behavioral Finance routes

==========================================================

Extracted from api_server.py as part of Step 5 router split.

Architecture: High Cohesion — this file owns only /api/behavioral routes.

Low Coupling : depends only on backend/routers/deps.py and FastAPI. Never imports other routers.

"""


import json
import sys
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from packages.api.backend.routers.deps import (
    _BEHAVIORAL_CACHE,
    _BEHAVIORAL_CACHE_TIME,
    _BEHAVIORAL_CACHE_TTL,
    ROOT,
    _balances_db,
    _behavioral_db,
    _db,
    _execute,
    _get_cash_split,
    _get_crypto_from_portfolio,
    _init_behavioral_db,
    _month_range,
    _query,
    get_live_fx_rate,
)
from packages.api.backend.security.core import require_scope

router = APIRouter(dependencies=[Depends(require_scope("read"))])

logger = logging.getLogger(__name__)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

# Behavioral Finance â€” /api/behavioral

# Clean Architecture: this endpoint is the Interface layer.

# All domain computation is delegated to CLI domain models.

# GUI receives only the pre-computed result â€” no business logic on frontend.

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


@router.get("/api/behavioral")
def get_behavioral_report():
    """

    Compute and return the full behavioral finance report for the current month.

    Delegates all scoring to the CLI's domain layer (behavioral_finance.domain.models).

    Persists the computed snapshot to the CLI SQLite database.

    GUI receives a parsed result object â€” zero business logic on the frontend.



    Cache: results are memoised for _BEHAVIORAL_CACHE_TTL seconds (1 hour).

    Cache is busted immediately by any POST/PUT/DELETE on expenses, income, or investments.

    architecture.md Â§S.8: behavioral recompute reads 4 DBs + runs FBS/fragility scoring;

    caching reduces peak API response time by ~80% on repeated navigations.

    """

    global _BEHAVIORAL_CACHE, _BEHAVIORAL_CACHE_TIME

    now = datetime.now()

    cache_key = now.strftime("%Y-%m")

    if cache_key in _BEHAVIORAL_CACHE and (time.time() - _BEHAVIORAL_CACHE_TIME) < _BEHAVIORAL_CACHE_TTL:
        return _BEHAVIORAL_CACHE[cache_key]

    try:
        # Add ROOT (apps/cli/) to sys.path so modules can be found

        if str(ROOT) not in sys.path:
            sys.path.append(str(ROOT))

        _stale = [k for k in list(sys.modules) if k.startswith("behavioral_finance")]
        [sys.modules.pop(k) for k in _stale]
        from behavioral_finance.domain.models import (
            Transaction,
            compute_fbs,
            compute_fragility,
        )

    except ImportError as e:
        logger.exception("CLI import error in behavioral report")

        raise HTTPException(status_code=500, detail=f"CLI logic not found in {ROOT}. Error: {e}")

    try:
        # Also need this for compute_impulse_score later in the function

        from behavioral_finance.domain.models import compute_impulse_score

    except ImportError:
        pass

    now = datetime.now()

    y, m = now.year, now.month

    prevM = m - 1 if m > 1 else 12

    prevY = y if m > 1 else y - 1

    this_str = f"{y}-{m:02d}"

    prev_str = f"{prevY}-{prevM:02d}"

    # â”€â”€ Fetch raw data from existing CLI databases â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    exp_db = _db("expense_tracker", "expense.db")

    inc_db = _db("income_tracker", "income.db")

    inv_db = _db("investment_tracker", "portfolio.db")

    # Query only this month + prev month directly â€” avoids LIMIT 1000 truncation

    s_this, e_this = _month_range(y, m)

    s_prev, e_prev = _month_range(prevY, prevM)

    all_expenses = _query(
        exp_db,
        "SELECT date, amount, category, payment_method, description FROM expenses " "WHERE date>=? AND date<?",
        (s_this, e_this),
    ) + _query(
        exp_db,
        "SELECT date, amount, category, payment_method, description FROM expenses " "WHERE date>=? AND date<?",
        (s_prev, e_prev),
    )

    all_income = _query(
        inc_db, "SELECT date, amount, income_type FROM incomes " "WHERE date>=? AND date<?", (s_this, e_this)
    ) + _query(inc_db, "SELECT date, amount, income_type FROM incomes " "WHERE date>=? AND date<?", (s_prev, e_prev))

    investments = _query(
        inv_db,
        "SELECT i.id, i.asset_type, i.ticker, i.buy_price, i.buy_currency, i.quantity,"
        " i.remaining_quantity, i.status,"
        " (SELECT h.price_idr FROM historical_prices h WHERE h.investment_id=i.id"
        "  ORDER BY h.id DESC LIMIT 1) AS current_price_idr"
        " FROM investments i WHERE i.status != ?",
        ("sold",),
    )

    # â”€â”€ Filter by month â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    exp_this = [e for e in all_expenses if str(e.get("date", "")).startswith(this_str)]

    exp_prev = [e for e in all_expenses if str(e.get("date", "")).startswith(prev_str)]

    inc_this = [i for i in all_income if str(i.get("date", "")).startswith(this_str)]

    inc_prev = [i for i in all_income if str(i.get("date", "")).startswith(prev_str)]

    exp_total_this = sum(e["amount"] for e in exp_this)

    exp_total_prev = sum(e["amount"] for e in exp_prev)

    inc_total_this = sum(i["amount"] for i in inc_this)

    inc_total_prev = sum(i["amount"] for i in inc_prev)

    # â”€â”€ Build domain Transaction objects â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    domain_txs = [
        Transaction(date=e["date"], amount=e["amount"], category=e.get("category", "other"), is_income=False)
        for e in exp_this
    ] + [Transaction(date=i["date"], amount=i["amount"], category="income", is_income=True) for i in inc_this]

    # Load balances via accounting model (authoritative all-time net: Incomes - Expenses)
    try:
        bal_db = _balances_db()
        split = _get_cash_split(bal_db)
        ef_rows = _query(bal_db, "SELECT value FROM manual_balances WHERE key=?", ("emergency_fund",))
        manual_ef = ef_rows[0]["value"] if ef_rows else 0.0
        physical_cash = float(split.get("physical_cash", 0.0))
        bank_savings = float(split.get("bank_savings", 0.0))

    except Exception:
        manual_ef = 0.0
        physical_cash = 0.0
        bank_savings = 0.0

    # Total Credit = Income - Expense (authoritative; split is informational)

    cash_savings = max(0.0, inc_total_this - exp_total_this)

    # All-time net for net_worth (same formula as get_balances/bank_savings)

    try:
        all_inc_nw = _query(inc_db, "SELECT COALESCE(SUM(amount),0) AS t FROM incomes")[0]["t"]

        all_exp_nw = _query(exp_db, "SELECT COALESCE(SUM(amount),0) AS t FROM expenses")[0]["t"]

        all_time_savings = max(0.0, float(all_inc_nw) - float(all_exp_nw))

    except Exception:
        all_time_savings = cash_savings

    # Use only the manually-set EF â€” never auto-invent one

    emergency_fund = manual_ef

    # Feature 3: crypto always from portfolio.db, never from manual_balances

    manual_crypto = _get_crypto_from_portfolio()

    # â”€â”€ Domain scoring â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    fbs_result = compute_fbs(
        transactions=domain_txs,
        income_this=inc_total_this,
        income_prev=inc_total_prev,
        expense_this=exp_total_this,
        expense_prev=exp_total_prev,
        emergency_fund=emergency_fund,
    )

    def _idr_val(inv):
        qty = inv["remaining_quantity"] if inv["remaining_quantity"] is not None else inv["quantity"]

        if inv.get("current_price_idr"):
            return inv["current_price_idr"] * qty

        if inv.get("buy_currency") == "IDR":
            return inv["buy_price"] * qty

        return inv["buy_price"] * get_live_fx_rate() * qty

    asset_values = {}

    for inv in investments:
        atype = inv.get("asset_type", "other")

        asset_values[atype] = asset_values.get(atype, 0.0) + _idr_val(inv)

    # Merge manual crypto balance into asset_values

    if manual_crypto > 0:
        asset_values["crypto"] = asset_values.get("crypto", 0.0) + manual_crypto

    income_sources = len({i.get("income_type", "other") for i in inc_this})

    frag_result = compute_fragility(
        income_sources=max(1, income_sources),
        expense_this=exp_total_this,
        emergency_fund=emergency_fund,
        asset_values=asset_values,
    )

    # â”€â”€ Impulse breakdown by category â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    from behavioral_finance.domain.models import compute_impulse_score

    # Compute impulse score ONCE per transaction, cache in list

    per_tx_scored = []

    category_impulse: dict = {}

    for e in exp_this:
        tx = Transaction(date=e["date"], amount=e["amount"], category=e.get("category", "other"))

        cat = e.get("category", "other")

        is_ = compute_impulse_score(tx)

        per_tx_scored.append((e, is_))

        category_impulse.setdefault(cat, []).append(is_)

    by_category_impulse = {k: round(sum(v) / len(v) * 100, 1) for k, v in category_impulse.items()}

    # ── Demo Data Fallback ──────────────────────────────────────────────
    is_empty = inc_total_this == 0 and exp_total_this == 0 and sum(asset_values.values()) == 0

    if is_empty:
        logger.info("No data found for behavioral report. Returning demo payload.")
        return {
            "month_label": now.strftime("%B %Y") + " (Demo)",
            "is_demo": True,
            "fbs": {
                "score": 72.5,
                "grade": "B",
                "label": "Good",
                "color": "#60a5fa",
                "component_scores": {
                    "saving_rate": 80,
                    "budget_adherence": 90,
                    "impulse_control": 65,
                    "consistency": 70,
                    "emergency_buffer": 40,
                },
                "saving_rate": 24.5,
                "impulse_index": 35.0,
            },
            "fragility": {
                "score": 65.0,
                "grade": "B",
                "label": "Stable",
                "color": "#60a5fa",
                "income_sources": 2,
                "emergency_months": 1.2,
                "asset_concentration": 0.45,
                "asset_values": {"cash": 5000000, "stock": 12000000, "crypto": 3000000},
            },
            "summary": {
                "exp_total_this": 7500000,
                "inc_total_this": 10000000,
                "net_worth": 20000000,
                "cash_savings": 2500000,
                "emergency_fund": 9000000,
            },
        }

    # Ensure cash asset value reflects liquid cash_savings
    asset_values["cash"] = cash_savings

    # ── Build response payload ───────────────────────────────────────────
    payload = {
        "month_label": now.strftime("%B %Y"),
        "fbs": {
            "score": fbs_result.score,
            "grade": fbs_result.grade,
            "label": fbs_result.label,
            "color": fbs_result.color,
            "component_scores": fbs_result.component_scores,
            "saving_rate": fbs_result.saving_rate,
            "impulse_index": fbs_result.impulse_index,
        },
        "fragility": {
            "score": frag_result.score,
            "grade": frag_result.grade,
            "label": frag_result.label,
            "color": frag_result.color,
            "income_sources": frag_result.income_sources,
            "emergency_months": frag_result.emergency_months,
            "asset_concentration": frag_result.asset_concentration,
            "asset_values": asset_values,
        },
        "impulse": {
            "index": fbs_result.impulse_index,
            "by_category": by_category_impulse,
            "per_tx": [
                {
                    "tx": {
                        "date": str(e.get("date", "")),
                        "amount": float(e.get("amount", 0)),
                        "category": e.get("category", "other"),
                        "description": e.get("description") or e.get("category", "other"),
                        "payment_method": e.get("payment_method", ""),
                    },
                    "is": round(is_, 3),
                }
                for e, is_ in per_tx_scored
            ],
        },
        "summary": {
            "exp_total_this": float(exp_total_this),
            "exp_total_prev": float(exp_total_prev),
            "inc_total_this": float(inc_total_this),
            "inc_total_prev": float(inc_total_prev),
            "cash_savings": float(cash_savings),
            "bank_savings": float(bank_savings),
            "physical_cash": float(physical_cash),
            "emergency_fund": float(emergency_fund),
            "cash_on_hand": float(max(0.0, cash_savings - emergency_fund)),
            "total_investment_value": float(sum(v for k, v in asset_values.items() if k != "cash")),
            "net_worth": float(cash_savings + sum(v for k, v in asset_values.items() if k != "cash")),
            "crypto_source": "portfolio.db",
        },
    }

    # â”€â”€ Persist snapshot to CLI database â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    try:
        db_path = _behavioral_db()

        _init_behavioral_db(db_path)

        _execute(
            db_path,
            "INSERT INTO behavioral_snapshots (created_at, year, month, payload) VALUES (?,?,?,?)"
            " ON CONFLICT(year, month) DO UPDATE SET payload=excluded.payload, created_at=excluded.created_at",
            (now.isoformat(), y, m, json.dumps(payload)),
        )

    except Exception:
        logger.exception("Error while running behavioral analysis step")
        pass  # Persistence failure must never break the read response

    # â”€â”€ Populate cache â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    _BEHAVIORAL_CACHE[cache_key] = payload

    _BEHAVIORAL_CACHE_TIME = time.time()

    return payload


@router.get("/api/behavioral/history")
def get_behavioral_history(limit: int = 12):
    """Return the last N persisted behavioral snapshots from the CLI database."""

    try:
        db_path = _behavioral_db()

        _init_behavioral_db(db_path)

        rows = _query(
            db_path,
            "SELECT year, month, created_at, payload FROM behavioral_snapshots " "ORDER BY id DESC LIMIT ?",
            (limit,),
        )

        return [{**json.loads(r["payload"]), "recorded_at": r["created_at"]} for r in rows]

    except Exception:
        logger.exception("Error fetching behavioral history")

        raise HTTPException(status_code=500, detail="Internal server error. Check server logs for details.")
