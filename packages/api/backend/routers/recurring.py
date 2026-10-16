"""
backend/routers/recurring.py — Recurring detection + reminders API (Phase 7)
============================================================================
High Cohesion: owns only /api/recurring routes backed by
packages/api/backend/finance/recurring_service.py.

  POST /api/recurring/detect                  — n8n WF-09 (idempotent detection)
  GET  /api/recurring/candidates?status       — pending/confirmed candidates
  POST /api/recurring/candidates/{id}/verify  — user confirmation gate
  POST /api/recurring/reminders/check         — n8n WF-10 (dedup reminders)
  GET  /api/recurring/reminders?status        — reminder history
  POST /api/recurring/reminders/{id}/sent     — mark delivered
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from packages.api.backend.finance.recurring_service import (
    RecurringError,
    detect_recurring,
    generate_reminders,
    list_candidates,
    list_reminders,
    mark_reminder_sent,
    verify_candidate,
)
from packages.api.backend.security.core import require_scope
from packages.core.infrastructure.config import Config

router = APIRouter()
logger = logging.getLogger(__name__)


def _ledger_db() -> str:
    return Config.get_db_path("finance")


@router.post("/api/recurring/detect", dependencies=[Depends(require_scope("write"))])
def post_recurring_detect(months_lookback: int = 6):
    """Run canonical-ledger recurring detection (idempotent upsert)."""
    try:
        result = detect_recurring(_ledger_db(), months_lookback=months_lookback)
    except RecurringError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Recurring detection failed")
        raise HTTPException(status_code=500, detail=f"Recurring detection failed: {exc}") from None
    return {"ok": True, **result}


@router.get("/api/recurring/candidates", dependencies=[Depends(require_scope("read"))])
def get_recurring_candidates(status: str | None = None, min_confidence: float = 0.0):
    """List detection candidates (pending/confirmed), highest confidence first."""
    try:
        candidates = list_candidates(_ledger_db(), status=status, min_confidence=min_confidence)
    except RecurringError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Recurring candidate listing failed")
        raise HTTPException(status_code=500, detail=f"Recurring candidates failed: {exc}") from None
    return {"ok": True, "candidates": candidates}


@router.post("/api/recurring/candidates/{candidate_id}/verify", dependencies=[Depends(require_scope("write"))])
def post_recurring_verify(candidate_id: int, confirmed: bool = True):
    """Confirm or reject a detected candidate (verification gate)."""
    try:
        result = verify_candidate(_ledger_db(), candidate_id, confirmed=confirmed)
    except RecurringError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Recurring candidate verification failed")
        raise HTTPException(status_code=500, detail=f"Recurring verification failed: {exc}") from None
    return {"ok": True, **result}


@router.post("/api/recurring/reminders/check", dependencies=[Depends(require_scope("write"))])
def post_recurring_reminders_check():
    """Generate reminders for confirmed templates due in the window (dedup)."""
    try:
        result = generate_reminders(_ledger_db())
    except Exception as exc:  # noqa: BLE001
        logger.exception("Recurring reminder generation failed")
        raise HTTPException(status_code=500, detail=f"Recurring reminders failed: {exc}") from None
    return {"ok": True, **result}


@router.get("/api/recurring/reminders", dependencies=[Depends(require_scope("read"))])
def get_recurring_reminders(status: str | None = None):
    """Reminder history, newest first."""
    try:
        reminders = list_reminders(_ledger_db(), status=status)
    except RecurringError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Recurring reminder listing failed")
        raise HTTPException(status_code=500, detail=f"Recurring reminders failed: {exc}") from None
    return {"ok": True, "as_of": date.today().isoformat(), "reminders": reminders}


@router.post("/api/recurring/reminders/{reminder_id}/sent", dependencies=[Depends(require_scope("write"))])
def post_recurring_reminder_sent(reminder_id: int):
    """Mark a reminder as delivered by WF-10."""
    try:
        result = mark_reminder_sent(_ledger_db(), reminder_id)
    except RecurringError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Recurring reminder mark-sent failed")
        raise HTTPException(status_code=500, detail=f"Recurring reminder update failed: {exc}") from None
    return {"ok": True, **result}
