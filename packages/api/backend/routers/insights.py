"""
backend/routers/insights.py — AI Insights API (Phase 13)
=========================================================
GET /api/insights — deterministic insight cards computed ONLY from verified
backend data (Phases 5-12). An LLM may rephrase these cards for a chat
answer, but the numbers always come from here.
"""

import logging

from fastapi import APIRouter, Depends

from packages.api.backend.finance.insights_service import build_insights
from packages.api.backend.security.core import require_scope
from packages.core.infrastructure.config import Config

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/insights", dependencies=[Depends(require_scope("read"))])
def get_insights():
    result = build_insights(
        Config.get_db_path("finance"), Config.get_db_path("budget")
    )
    return {"ok": True, **result}
