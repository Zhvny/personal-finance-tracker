"""
backend/routers/income.py — Income Tracker routes
==================================================
Extracted from api_server.py as part of Step 5 router split.
Architecture: High Cohesion — this file owns only /api/income routes.
Low Coupling : depends only on backend/routers/deps.py and FastAPI. Never imports other routers.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from packages.api.backend.routers.deps import (
    _balances_db,
    _bust_behavioral_cache,
    _check_and_apply_reward_unlocks,
    _db,
    _execute,
    _get_cash_split,
    _query,
    income_service,
)
from packages.api.backend.security.core import require_scope
from packages.core.domain.models.income import IncomeType

router = APIRouter(dependencies=[Depends(require_scope("write"))])
logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════
# INCOME
# ═════════════════════════════════════════════════════════════════════

from pydantic import field_validator


class IncomeIn(BaseModel):
    source: str
    amount: float
    income_type: str
    date: str
    description: Optional[str] = None
    is_taxed: bool = False

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v

    @field_validator("source")
    @classmethod
    def source_check(cls, v: str) -> str:
        if len(v) > 100:
            raise ValueError("Source name is too long")
        if not v.strip():
            raise ValueError("Source cannot be empty")
        return v

    @field_validator("date")
    @classmethod
    def date_not_in_future(cls, v: str) -> str:
        try:
            clean_date = v.replace("Z", "+00:00") if isinstance(v, str) else v
            dt = datetime.fromisoformat(clean_date)
            now = datetime.now(dt.tzinfo) if dt.tzinfo is not None else datetime.now()
            if dt > now + timedelta(hours=1):
                raise ValueError("Date cannot be in the future")
        except ValueError as e:
            if "isoformat" in str(e):
                raise ValueError("Invalid date format (ISO-8601 expected)")
            raise e
        return v


@router.get("/api/income")
async def list_income(
    income_type: Optional[str] = None,
    search: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    period: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
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
            dt_end = (datetime(now.year, end_m + 1, 1) if end_m < 12 else datetime(now.year + 1, 1, 1)) - timedelta(
                microseconds=1
            )

    items = await income_service.get_incomes(
        start_date=dt_start, end_date=dt_end, income_type=income_type, search=search
    )
    return {
        "items": [vars(i) for i in items[offset : offset + limit]],
        "total": len(items),
        "limit": limit,
        "offset": offset,
        "filter": {
            "start": dt_start.isoformat() if dt_start else None,
            "end": dt_end.isoformat() if dt_end else None,
            "income_type": income_type,
            "search": search,
            "period": period,
        },
    }


@router.post("/api/income")
async def add_income(body: IncomeIn):
    clean_date = body.date.replace("Z", "+00:00") if body.date else None
    dt = datetime.fromisoformat(clean_date) if clean_date else datetime.now()
    result = await income_service.record_income(
        amount=body.amount,
        source=body.source,
        income_type=body.income_type,
        date=dt,
        description=body.description,
        is_taxed=body.is_taxed,
        apply_allocation=True,
    )

    # ── Legacy Side Effects (Atomic SQL Updates) ───────────────────────────
    allocation_result = result["allocation"]
    if allocation_result and allocation_result.get("enabled"):
        bal_db = _balances_db()
        now_iso = datetime.now().isoformat()
        db_writes = allocation_result.get("db_writes", {})

        # Ensure row exists (Lazy seed)
        _get_cash_split(bal_db)

        if "bank_savings" in db_writes:
            # Atomic Increment
            _execute(
                bal_db,
                "UPDATE cash_split SET bank_savings = bank_savings + ?, updated_at = ? WHERE id = 1",
                (db_writes["bank_savings"], now_iso),
            )

        if "emergency_fund" in db_writes:
            # Atomic Increment using ON CONFLICT (for SQLite/Postgres safety)
            _execute(
                bal_db,
                "INSERT INTO manual_balances (key, value, updated_at) VALUES (?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value = manual_balances.value + excluded.value, updated_at = excluded.updated_at",
                ("emergency_fund", db_writes["emergency_fund"], now_iso),
            )

    auto_unlocked = _check_and_apply_reward_unlocks()
    _bust_behavioral_cache()

    return {
        "id": result["income_id"],
        "ok": True,
        "auto_unlocked": auto_unlocked,
        "allocation": allocation_result,
    }


@router.put("/api/income/{income_id}")
async def update_income(income_id: int, body: IncomeIn):
    from packages.api.backend.routers.deps import _inc_repo
    from packages.core.domain.models.income import Income

    clean_date = body.date.replace("Z", "+00:00") if body.date else None
    dt = datetime.fromisoformat(clean_date) if clean_date else datetime.now()

    income = Income(
        amount=body.amount,
        source=body.source,
        income_type=IncomeType.from_str(body.income_type),
        date=dt,
        description=body.description,
        is_taxed=body.is_taxed,
        id=income_id,
    )
    try:
        success = await _inc_repo.save(income)
        if not success:
            logger.error(f"Failed to update income record id={income_id}: not found")
            raise HTTPException(404, "Income not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating income id={income_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error. Check server logs for details.")

    _bust_behavioral_cache()
    return {"ok": True}


@router.delete("/api/income/{income_id}")
async def delete_income(income_id: int):
    if income_id <= 0:
        raise HTTPException(400, "Invalid income ID")
    success = await income_service.delete_income(income_id)
    if not success:
        raise HTTPException(404, "Income not found")
    _bust_behavioral_cache()
    return {"ok": True}


@router.get("/api/income/summary/{year}/{month}")
async def income_monthly_summary(year: int, month: int):
    summary = await income_service.get_monthly_summary(year, month)
    return summary


@router.get("/api/income/tax/{year}")
def income_tax_estimate(year: int):
    db = _db("income_tracker", "income.db")
    s, e = f"{year:04d}-01-01", f"{year+1:04d}-01-01"
    rows = _query(db, "SELECT amount FROM incomes WHERE date>=? AND date<?", (s, e))
    annual = sum(r["amount"] for r in rows)

    # PPh 21 progressive — PTKP K/0 = 58.5 juta
    ptkp = 58_500_000
    taxable = max(0, annual - ptkp)
    if taxable <= 60_000_000:
        tax = taxable * 0.05
    elif taxable <= 250_000_000:
        tax = 3_000_000 + (taxable - 60_000_000) * 0.15
    elif taxable <= 500_000_000:
        tax = 31_500_000 + (taxable - 250_000_000) * 0.25
    elif taxable <= 5_000_000_000:
        tax = 94_000_000 + (taxable - 500_000_000) * 0.30
    else:
        tax = 1_444_000_000 + (taxable - 5_000_000_000) * 0.35

    eff_rate = tax / annual * 100 if annual else 0
    monthly_net = (annual - tax) / 12
    return {
        "annual_income": annual,
        "taxable": taxable,
        "ptkp": ptkp,
        "tax": tax,
        "effective_rate": eff_rate,
        "monthly_net": monthly_net,
    }
