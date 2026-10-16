"""
backend/routers/forecast.py — Deterministic cashflow forecast API (Phase 9)
===========================================================================
High Cohesion: owns only /api/forecast backed by
packages/api/backend/finance/forecast_service.py. Replaces the legacy SMA
projection that lived in advanced.py (expense.db/income.db path).

Every number is backend-computed from the canonical ledger with a transparent
Known / Expected / Estimated / Forecast label, plus an insight (warning when
the projected cumulative balance turns negative).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from packages.api.backend.finance.forecast_service import (
    ForecastError,
    build_cashflow_forecast,
)
from packages.api.backend.security.core import require_scope
from packages.core.infrastructure.config import Config

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/forecast", dependencies=[Depends(require_scope("read"))])
def get_forecast(days: int = 30):
    try:
        result = build_cashflow_forecast(Config.get_db_path("finance"), days=days)
    except ForecastError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Cashflow forecast computation failed")
        raise HTTPException(status_code=500, detail=f"Forecast failed: {exc}") from None
    return {"ok": True, **result}
