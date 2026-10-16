"""
backend/routers/reports.py — Daily / Weekly / Monthly report API (Phase 5)
==========================================================================
High Cohesion: owns only /api/reports routes backed by
packages/api/backend/finance/report_service.py.

All numbers are backend-computed from the canonical ledger (transactions
table) scoped to the active profile via the Postgres bridge.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from packages.api.backend.finance.report_service import (
    ReportError,
    build_report,
)
from packages.api.backend.security.core import require_scope
from packages.core.infrastructure.config import Config

router = APIRouter()
logger = logging.getLogger(__name__)


def _report_db() -> str:
    return Config.get_db_path("finance")


@router.get("/api/reports", dependencies=[Depends(require_scope("read"))])
def get_report(period: str = "month", top_n: int = 5):
    """Full period report: income/expense/net, PoP comparison, top categories,
    top merchants, largest transactions, and a trend series."""
    try:
        report = build_report(_report_db(), period=period, top_n=min(max(top_n, 1), 10))
    except ReportError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Report computation failed")
        raise HTTPException(status_code=500, detail=f"Report failed: {exc}")
    return {"ok": True, **report}
