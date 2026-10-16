"""
backend/routers/safe_spend.py — Safe-to-Spend API (Phase 10)
=============================================================
High Cohesion: owns only /api/safe-to-spend backed by
packages/api/backend/finance/safe_spend_service.py. Deterministic,
transparent: current balance − upcoming outflows (Expected/Estimated) −
buffer, with sources and reasoning surfaced to the client.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from packages.api.backend.finance.safe_spend_service import (
    SafeSpendError,
    build_safe_to_spend,
)
from packages.api.backend.security.core import require_scope
from packages.core.infrastructure.config import Config

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/safe-to-spend", dependencies=[Depends(require_scope("read"))])
def get_safe_to_spend(horizon: str = "month", buffer_pct: float = 10.0):
    try:
        result = build_safe_to_spend(
            Config.get_db_path("finance"), horizon=horizon, buffer_pct=buffer_pct
        )
    except SafeSpendError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Safe-to-spend computation failed")
        raise HTTPException(status_code=500, detail=f"Safe-to-spend failed: {exc}") from None
    return {"ok": True, **result}
