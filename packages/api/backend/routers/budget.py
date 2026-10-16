"""
backend/routers/budget.py — Budget status + alerts API (Phase 6)
================================================================
High Cohesion: owns only /api/budget routes backed by
packages/api/backend/finance/budget_service.py.

  GET  /api/budget/status?year&month   — budget vs actual (canonical ledger)
  GET  /api/budget/alerts?year&month   — alert history
  POST /api/budget/alerts/check        — idempotent alert generation (n8n WF-08)

Thresholds are env-configurable (BUDGET_WARN_PCT / BUDGET_ALERT_PCT /
BUDGET_OVER_PCT, defaults 70 / 90 / 100).
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from packages.api.backend.finance.budget_service import (
    BudgetError,
    build_budget_status,
    check_budget_alerts,
    list_budget_alerts,
)
from packages.api.backend.security.core import require_scope
from packages.core.infrastructure.config import Config

router = APIRouter()
logger = logging.getLogger(__name__)


def _year_month(year: int | None, month: int | None) -> tuple:
    now = date.today()
    return year or now.year, month or now.month


@router.get("/api/budget/status", dependencies=[Depends(require_scope("read"))])
def get_budget_status(year: int | None = None, month: int | None = None):
    """Budget vs actual per category, computed from the canonical ledger."""
    y, m = _year_month(year, month)
    try:
        status = build_budget_status(
            Config.get_db_path("finance"), Config.get_db_path("budget"), y, m
        )
    except BudgetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Budget status computation failed")
        raise HTTPException(status_code=500, detail=f"Budget status failed: {exc}") from None
    return {"ok": True, **status}


@router.get("/api/budget/alerts", dependencies=[Depends(require_scope("read"))])
def get_budget_alerts(year: int | None = None, month: int | None = None):
    """Alert history for the month (deduped by design), newest first."""
    y, m = _year_month(year, month)
    try:
        alerts = list_budget_alerts(Config.get_db_path("budget"), y, m)
    except BudgetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Budget alert history failed")
        raise HTTPException(status_code=500, detail=f"Budget alerts failed: {exc}") from None
    return {"ok": True, "year": y, "month": m, "alerts": alerts}


@router.post("/api/budget/alerts/check", dependencies=[Depends(require_scope("write"))])
def post_budget_alerts_check(year: int | None = None, month: int | None = None):
    """n8n WF-08 entry: persist only NEW budget alerts (idempotent, dedup)."""
    y, m = _year_month(year, month)
    try:
        result = check_budget_alerts(
            Config.get_db_path("finance"), Config.get_db_path("budget"), y, m
        )
    except BudgetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Budget alert check failed")
        raise HTTPException(status_code=500, detail=f"Budget alert check failed: {exc}") from None
    return {"ok": True, **result}
