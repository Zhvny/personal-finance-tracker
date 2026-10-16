"""
backend/routers/anomalies.py — Anomaly Detection API (Phase 12)
================================================================
High Cohesion: owns only /api/anomalies backed by
packages/api/backend/finance/anomaly_service.py. Deterministic, explainable
rules; `POST /api/anomalies/check` is the idempotent n8n WF-12 entry point
(persists only new (year, month, rule, category) keys).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from packages.api.backend.finance.anomaly_service import (
    AnomalyError,
    check_anomaly_alerts,
    detect_anomalies,
    list_anomaly_alerts,
)
from packages.api.backend.security.core import require_scope
from packages.core.infrastructure.config import Config

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/anomalies", dependencies=[Depends(require_scope("read"))])
def get_anomaly_alerts(year: int | None = None, month: int | None = None):
    return {"ok": True, "alerts": list_anomaly_alerts(Config.get_db_path("finance"), year, month)}


@router.get("/api/anomalies/status", dependencies=[Depends(require_scope("read"))])
def get_anomaly_status(
    window_days: int = 30,
    baseline_days: int = 90,
    spike_ratio: float = 2.0,
    min_delta: float = 100_000.0,
    oversized_factor: float = 15.0,
    min_large: float = 500_000.0,
):
    try:
        result = detect_anomalies(
            Config.get_db_path("finance"),
            window_days=window_days,
            baseline_days=baseline_days,
            spike_ratio=spike_ratio,
            min_delta=min_delta,
            oversized_factor=oversized_factor,
            min_large=min_large,
        )
    except AnomalyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Anomaly detection failed")
        raise HTTPException(status_code=500, detail=f"Anomaly detection failed: {exc}") from None
    return {"ok": True, **result}


@router.post("/api/anomalies/check", dependencies=[Depends(require_scope("read"))])
def post_anomaly_check():
    try:
        result = check_anomaly_alerts(Config.get_db_path("finance"))
    except AnomalyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Anomaly alert check failed")
        raise HTTPException(status_code=500, detail=f"Anomaly alert check failed: {exc}") from None
    return {"ok": True, **result}
