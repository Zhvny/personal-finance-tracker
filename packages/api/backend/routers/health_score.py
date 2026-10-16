"""
backend/routers/health_score.py — Behavioral Health Score API (Phase 14)
=========================================================================
GET /api/health-score — explainable composite score (0-100) from verified
backend data only. The legacy CLI-based /api/behavioral report remains
untouched; this is the canonical-ledger replacement (roadmap Phase 14).
"""

import logging

from fastapi import APIRouter, Depends

from packages.api.backend.finance.health_score_service import build_health_score
from packages.api.backend.security.core import require_scope
from packages.core.infrastructure.config import Config

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/health-score", dependencies=[Depends(require_scope("read"))])
def get_health_score():
    result = build_health_score(
        Config.get_db_path("finance"), Config.get_db_path("budget")
    )
    return {"ok": True, **result}
