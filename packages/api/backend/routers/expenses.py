"""
backend/routers/expenses.py — Expense Tracker routes
=====================================================
Extracted from api_server.py as part of Step 5 router split.
Architecture: High Cohesion — this file owns only /api/expenses routes.
Low Coupling : depends only on backend/routers/deps.py and FastAPI. Never imports other routers.
"""

import csv as csv_mod
import io
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from packages.api.backend.routers.deps import (
    _bust_behavioral_cache,
    _db,
    _execute,
    _exp_repo,
    _get_recurrence_detector,
    _query,
    expense_service,
    income_service,
)
from packages.api.backend.security.core import require_scope

router = APIRouter(dependencies=[Depends(require_scope("write"))])
logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════
# EXPENSES
# ═════════════════════════════════════════════════════════════════════

from pydantic import field_validator


def _query_expenses(sql: str, params: tuple = ()):
    return _query("expense.db", sql, params)

def _execute_expenses(sql: str, params: tuple = ()):
    return _execute("expense.db", sql, params)


class ExpenseIn(BaseModel):
    description: str
    amount:      float
    category:    str
    payment_method: str
    date:        str
    is_recurring:    bool = False
    recurring_period: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v

    @field_validator("description")
    @classmethod
    def description_length(cls, v: str) -> str:
        if len(v) > 500:
            raise ValueError("Description is too long (max 500 chars)")
        if not v.strip():
            raise ValueError("Description cannot be empty")
        return v

    @field_validator("date")
    @classmethod
    def date_not_in_future(cls, v: str) -> str:
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            if dt > now + timedelta(hours=1):
                raise ValueError("Date cannot be in the future")
        except ValueError as e:
            if "isoformat" in str(e):
                raise ValueError("Invalid date format (ISO-8601 expected)")
            raise e
        return v


@router.get("/api/expenses")
async def list_expenses(
    category: Optional[str] = None,
    search: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    period: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    dt_start: Optional[datetime] = None
    dt_end: Optional[datetime] = None
    now = datetime.now()

    if start_date and end_date:
        dt_start = datetime.fromisoformat(start_date)
        dt_end = datetime.fromisoformat(end_date)
    elif year and month:
        dt_start = datetime(year, month, 1)
        if month == 12:
            dt_end = datetime(year + 1, 1, 1) - timedelta(microseconds=1)
        else:
            dt_end = datetime(year, month + 1, 1) - timedelta(microseconds=1)
    elif year and not month:
        dt_start = datetime(year, 1, 1)
        dt_end = datetime(year, 12, 31, 23, 59, 59)
    elif period:
        p = period.lower()
        if p == "this_month":
            dt_start = datetime(now.year, now.month, 1)
            dt_end = now
        elif p == "last_month":
            py, pm = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
            dt_start = datetime(py, pm, 1)
            dt_end = datetime(now.year, now.month, 1) - timedelta(microseconds=1)
        elif p == "ytd":
            dt_start = datetime(now.year, 1, 1)
            dt_end = now
        elif p.startswith("q") and len(p) == 2 and p[1].isdigit():
            q_num = int(p[1])
            start_m = (q_num - 1) * 3 + 1
            end_m = start_m + 2
            dt_start = datetime(now.year, start_m, 1)
            dt_end = (datetime(now.year, end_m + 1, 1) if end_m < 12 else datetime(now.year + 1, 1, 1)) - timedelta(microseconds=1)

    total_count = await _exp_repo.count(category=category, search=search)
    items = await _exp_repo.get_all(
        start_date=dt_start,
        end_date=dt_end,
        category=category,
        search=search,
        limit=limit,
        offset=offset
    )

    rows = []
    for item in items:
        rows.append({
            "id": item.id,
            "amount": item.amount,
            "description": item.description,
            "category": item.category.value if hasattr(item.category, "value") else str(item.category),
            "payment_method": item.payment_method.value if hasattr(item.payment_method, "value") else str(item.payment_method),
            "date": item.date.isoformat(),
            "is_recurring": item.is_recurring,
            "recurring_period": item.recurring_period
        })

    return {
        "items": rows,
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "filter": {
            "start": dt_start.isoformat() if dt_start else None,
            "end": dt_end.isoformat() if dt_end else None,
            "period": period
        }
    }



@router.post("/api/expenses")
async def add_expense(body: ExpenseIn):
    dt = datetime.fromisoformat(body.date)
    result = await expense_service.record_expense(
        amount=body.amount,
        description=body.description,
        category=body.category,
        payment_method=body.payment_method,
        date=dt,
        is_recurring=body.is_recurring,
        recurring_period=body.recurring_period
    )
    _bust_behavioral_cache()
    return {"id": result["id"], "ok": True, "auto_unlocked": result["newly_unlocked"]}


@router.put("/api/expenses/{expense_id}")
def update_expense(expense_id: int, body: ExpenseIn):
    # For update, we can use the repository directly or add a service method.
    # Instruction says "use PostgresExpenseRepository and DatabaseManager"
    sql = """
        UPDATE expenses 
        SET amount=?, description=?, category=?, payment_method=?, date=?, 
            is_recurring=?, recurring_period=? 
        WHERE id=?
    """
    params = (body.amount, body.description, body.category, body.payment_method, body.date,
              body.is_recurring, body.recurring_period, expense_id)
    rows = _execute_expenses(sql, params)
    if not rows:
        logger.error(f"Failed to update expense record id={expense_id}: not found")
        raise HTTPException(404, "Expense not found")
    _bust_behavioral_cache()
    return {"ok": True}


@router.get("/api/expenses/recurring")
def list_recurring_expenses():
    """Return all expense templates marked is_recurring=True, used as monthly templates."""
    sql = "SELECT * FROM expenses WHERE is_recurring=? ORDER BY category, description"
    return _query_expenses(sql, (True,))


@router.post("/api/expenses/recurring/apply")
def apply_recurring_expenses():
    """
    Auto-generate entries for this month from all is_recurring=True templates.
    """
    sql = "SELECT * FROM expenses WHERE is_recurring=?"
    templates = _query_expenses(sql, (True,))

    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    month_start = today.replace(day=1).date()
    month_end = (today.replace(day=28) + timedelta(days=4)).replace(day=1).date()

    applied, skipped = 0, 0
    entries = []
    for tmpl in templates:
        # Check if already applied this month
        check_sql = """
            SELECT id FROM expenses 
            WHERE description=? AND category=? AND date>=? AND date<? AND is_recurring=?
        """
        existing = _query_expenses(check_sql, (tmpl["description"], tmpl["category"], month_start, month_end, False))
        if existing:
            skipped += 1
            continue

        insert_sql = """
            INSERT INTO expenses (amount, description, category, payment_method, date, is_recurring)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
        """
        new_id = _execute_expenses(insert_sql, (tmpl["amount"], tmpl["description"], tmpl["category"], tmpl["payment_method"], today_str, False))
        applied += 1
        entries.append({"id": new_id, "description": tmpl["description"], "amount": float(tmpl["amount"])})

    return {"applied": applied, "skipped": skipped, "entries": entries}

@router.post("/api/expenses/detect-recurring")
def detect_recurring_expenses():
    """
    Run recurring expense detection algorithm on expense.db.
    Persists candidates to recurrence_candidates table.
    """
    db = _db("expense_tracker", "expense.db")
    rd = _get_recurrence_detector()
    if not rd:
        logger.error("Recurrence detector not available")
        raise HTTPException(503, "Recurrence detector tidak tersedia.")
    result = rd.run_detection(db)
    return {"ok": True, **result}


@router.get("/api/expenses/recurring-detected")
def list_recurring_detected():
    """
    Return all auto-detected recurring expense candidates.
    """
    db = _db("expense_tracker", "expense.db")
    rd = _get_recurrence_detector()
    if not rd:
        return {"ok": True, "candidates": []}

    # ensure_schema now uses Database helper
    try:
        rd.ensure_schema(db)
        rows = _query(db, "SELECT * FROM recurrence_candidates ORDER BY confidence DESC, description")
        return {"ok": True, "candidates": rows}
    except Exception:
        logger.exception("Error listing recurring candidates")
        return {"ok": True, "candidates": []}


@router.post("/api/expenses/recurring-detected/{candidate_id}/confirm")
def confirm_recurring_detected(candidate_id: int):
    """
    Mark a detected recurring candidate as confirmed by the user.
    """
    db = _db("expense_tracker", "expense.db")
    rd = _get_recurrence_detector()
    if not rd:
        logger.error("Recurrence detector not available")
        raise HTTPException(503, "Recurrence detector tidak tersedia.")

    try:
        rd.ensure_schema(db)
        # Use _execute bridge
        rows = _execute(db, "UPDATE recurrence_candidates SET is_confirmed=? WHERE id=?", (1, candidate_id))
        if not rows:
            raise HTTPException(404, f"Candidate id={candidate_id} tidak ditemukan.")
        return {"ok": True, "id": candidate_id, "is_confirmed": True}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error confirming candidate")
        raise HTTPException(500, "Failed to confirm recurring candidate. Check server logs.")




@router.delete("/api/expenses/{expense_id}")
async def delete_expense(expense_id: int):
    if expense_id <= 0:
        raise HTTPException(400, "Invalid expense ID")
    success = await _exp_repo.delete(expense_id)
    if not success:
        raise HTTPException(404, "Expense not found")
    _bust_behavioral_cache()
    return {"ok": True}


@router.get("/api/expenses/export")
async def export_expenses(year: Optional[int] = None, format: str = "csv"):
    """Export all expenses (optionally filtered by year) as CSV."""
    if year:
        s, e = datetime(year, 1, 1), datetime(year + 1, 1, 1)
        items = await _exp_repo.get_all(start_date=s, end_date=e)
        fname = f"expenses_{year}.csv"
    else:
        items = await _exp_repo.get_all()
        fname = "expenses_all.csv"

    buf = io.StringIO()
    if items:
        # Convert to dict for csv writer
        rows = []
        for item in items:
            rows.append({
                "id": item.id,
                "amount": item.amount,
                "description": item.description,
                "category": item.category.value,
                "payment_method": item.payment_method.value,
                "date": item.date.isoformat(),
                "is_recurring": item.is_recurring,
                "recurring_period": item.recurring_period
            })
        writer = csv_mod.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )


@router.get("/api/income/export")
async def export_income(year: Optional[int] = None, format: str = "csv"):
    """Export all income (optionally filtered by year) as CSV."""
    if year:
        s, e = datetime(year, 1, 1), datetime(year + 1, 1, 1)
        items = await income_service.get_incomes(start_date=s, end_date=e)
        fname = f"income_{year}.csv"
    else:
        items = await income_service.get_incomes()
        fname = "income_all.csv"

    buf = io.StringIO()
    if items:
        # Assuming Income models also need dict conversion
        rows = []
        for i in items:
            rows.append({
                "id": i.id,
                "amount": i.amount,
                "source": i.source,
                "income_type": i.income_type.value,
                "date": i.date.isoformat(),
                "description": i.description,
                "is_taxed": i.is_taxed
            })
        writer = csv_mod.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )


@router.get("/api/expenses/trend")
def expense_trend(months: int = 12):
    """Return last N months of expense totals + top categories for trend chart."""
    now = datetime.now()
    y, m = now.year, now.month

    start_mo = m - months + 1
    start_yr = y
    while start_mo <= 0:
        start_mo += 12
        start_yr -= 1
    start_dt = datetime(start_yr, start_mo, 1)

    # Use Postgres query for aggregation
    sql = """
        SELECT to_char(date, 'YYYY-MM') AS ym, category, SUM(amount) AS total 
        FROM expenses 
        WHERE date >= ? 
        GROUP BY ym, category 
        ORDER BY ym
    """
    rows = _query_expenses(sql, (start_dt.date(),))

    # Build month buckets
    buckets: dict = {}
    for r in rows:
        ym  = r["ym"]
        cat = r["category"]
        buckets.setdefault(ym, {})["by_category"] = buckets.get(ym, {}).get("by_category") or {}
        buckets[ym].setdefault("by_category", {})[cat] = round(float(r["total"]), 2)
        buckets[ym]["total"] = round(buckets[ym].get("total", 0) + float(r["total"]), 2)

    result = []
    for offset in range(months - 1, -1, -1):
        mo = m - offset
        yr = y
        while mo <= 0: mo += 12; yr -= 1
        ym  = f"{yr:04d}-{mo:02d}"
        lbl = date(yr, mo, 1).strftime("%b %Y")
        bkt = buckets.get(ym, {})
        result.append({"label": lbl, "total": bkt.get("total", 0), "by_category": bkt.get("by_category", {})})
    return result


@router.get("/api/income/trend")
def income_trend(months: int = 12):
    """Return last N months of income totals for trend chart."""
    now = datetime.now()
    y, m = now.year, now.month
    start_mo = m - months + 1
    start_yr = y
    while start_mo <= 0:
        start_mo += 12
        start_yr -= 1
    start_dt = datetime(start_yr, start_mo, 1)

    sql = """
        SELECT to_char(date, 'YYYY-MM') AS ym, income_type, SUM(amount) AS total 
        FROM incomes 
        WHERE date >= ? 
        GROUP BY ym, income_type 
        ORDER BY ym
    """
    rows = _query("income.db", sql, (start_dt.date(),))

    buckets: dict = {}
    for r in rows:
        ym = r["ym"]
        buckets.setdefault(ym, {"total": 0, "by_type": {}})
        buckets[ym]["by_type"][r["income_type"]] = round(float(r["total"]), 2)
        buckets[ym]["total"] = round(buckets[ym]["total"] + float(r["total"]), 2)

    result = []
    for offset in range(months - 1, -1, -1):
        mo = m - offset
        yr = y
        while mo <= 0: mo += 12; yr -= 1
        ym  = f"{yr:04d}-{mo:02d}"
        bkt = buckets.get(ym, {})
        result.append({"label": date(yr, mo, 1).strftime("%b %Y"),
                       "total": bkt.get("total", 0), "by_type": bkt.get("by_type", {})})
    return result


@router.get("/api/expenses/summary/{year}/{month}")
async def expense_monthly_summary(year: int, month: int):
    summary = await _exp_repo.get_monthly_summary(year, month)
    return summary


@router.get("/api/expenses/budget/{year}/{month}")
async def expense_budget_status(year: int, month: int):
    """
    Budget vs Actual — uses limits from PostgreSQL financials.budgets.
    """
    DEFAULT_BUDGETS = {
        "Food & Drink": 2_000_000, "transport": 1_000_000, "housing": 3_000_000,
        "entertainment": 500_000, "health": 500_000, "shopping": 1_000_000,
        "education": 500_000, "other": 300_000,
    }

    # Get actual spending — now native async, no thread needed
    summary = await _exp_repo.get_monthly_summary(year, month)
    actual = summary["by_category"]

    # Load user-set limits from PostgreSQL
    user_limits = await _exp_repo.get_budgets(year, month)

    # Union of: actual categories + user-set limits + default categories
    all_cats = set(list(actual) + list(user_limits) + list(DEFAULT_BUDGETS))
    result = {}
    for cat in all_cats:
        budget = user_limits.get(cat) or DEFAULT_BUDGETS.get(cat)
        if budget is None:
            continue
        spent = actual.get(cat, 0)
        pct   = spent / budget * 100 if budget else 0
        result[cat] = {
            "budget": budget, "actual": spent,
            "remaining": budget - spent, "pct_used": pct,
            "status": "over" if pct >= 100 else "warning" if pct >= 80 else "under",
        }
    return result


