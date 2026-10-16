"""
backend/routers/net_worth.py — Net Worth API (Phase 15)
=======================================================
GET /api/net-worth          — canonical cash (transfers never change it)
                              + legacy investment positions at latest prices.
GET /api/net-worth/history  — daily cumulative series (transfers excluded).
"""

import logging

from fastapi import APIRouter, Depends

from packages.api.backend.finance.net_worth_service import (
    build_net_worth,
    net_worth_history,
)
from packages.api.backend.security.core import require_scope
from packages.core.infrastructure.config import Config

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/net-worth", dependencies=[Depends(require_scope("read"))])
def get_net_worth():
    result = build_net_worth(
        Config.get_db_path("finance"), Config.get_db_path("investment")
    )
    return {"ok": True, **result}


@router.get("/api/net-worth/history", dependencies=[Depends(require_scope("read"))])
def get_net_worth_history(days: int = 90):
    result = net_worth_history(
        Config.get_db_path("finance"), Config.get_db_path("investment"), days=days
    )
    return {"ok": True, **result}
