"""
backend/routers/goals.py — Goal CRUD + progress/status API (Phase 8)
====================================================================
High Cohesion: owns only /api/goals routes backed by
packages/api/backend/finance/goals_service.py. Replaces the legacy goals
routes previously living in advanced.py (same response shape: name/title and
target_date/deadline aliases preserved for compatibility).

  GET    /api/goals                    — list (with computed progress)
  POST   /api/goals                    — create
  PATCH  /api/goals/{id}               — fixed typed partial update
  DELETE /api/goals/{id}               — delete
  GET    /api/goals/progress           — n8n WF-11 monitoring payload
  GET    /api/goals/{id}/status        — single-goal status
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from packages.api.backend.finance.goals_service import (
    GoalError,
    create_goal,
    delete_goal,
    goal_status,
    goals_progress,
    list_goals,
    update_goal,
)
from packages.api.backend.security.core import require_scope
from packages.core.infrastructure.config import Config

router = APIRouter()
logger = logging.getLogger(__name__)


def _goals_db() -> str:
    return Config.get_db_path("goals")


def _as_goal_error(exc: GoalError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(exc))


@router.get("/api/goals", dependencies=[Depends(require_scope("read"))])
def get_goals():
    try:
        return {"ok": True, "goals": list_goals(_goals_db())}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Goal listing failed")
        raise HTTPException(status_code=500, detail=f"Goals failed: {exc}") from None


@router.post("/api/goals", dependencies=[Depends(require_scope("write"))])
def post_goals(body: dict):
    try:
        goal = create_goal(
            _goals_db(),
            name=body.get("name"),
            title=body.get("title"),
            target_amount=body.get("target_amount"),
            current_amount=body.get("current_amount", 0),
            target_date=body.get("target_date"),
            deadline=body.get("deadline"),
        )
    except GoalError as exc:
        raise _as_goal_error(exc) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Goal creation failed")
        raise HTTPException(status_code=500, detail=f"Goal creation failed: {exc}") from None
    return {"ok": True, "goal": goal}


@router.patch("/api/goals/{goal_id}", dependencies=[Depends(require_scope("write"))])
def patch_goals(goal_id: int, body: dict):
    """Fixed PATCH: typed amounts, parsed dates, current <= target enforced."""
    try:
        goal = update_goal(_goals_db(), goal_id, **body)
    except GoalError as exc:
        raise _as_goal_error(exc, status_code=404 if "tidak ditemukan" in str(exc) else 400) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Goal update failed")
        raise HTTPException(status_code=500, detail=f"Goal update failed: {exc}") from None
    return {"ok": True, "goal": goal}


@router.delete("/api/goals/{goal_id}", dependencies=[Depends(require_scope("write"))])
def delete_goals(goal_id: int):
    try:
        return {"ok": True, **delete_goal(_goals_db(), goal_id)}
    except GoalError as exc:
        raise _as_goal_error(exc, status_code=404) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Goal deletion failed")
        raise HTTPException(status_code=500, detail=f"Goal deletion failed: {exc}") from None


@router.get("/api/goals/progress", dependencies=[Depends(require_scope("read"))])
def get_goals_progress():
    """n8n WF-11 goal monitoring payload (all goals + statuses)."""
    try:
        return {"ok": True, **goals_progress(_goals_db())}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Goal progress computation failed")
        raise HTTPException(status_code=500, detail=f"Goal progress failed: {exc}") from None


@router.get("/api/goals/{goal_id}/status", dependencies=[Depends(require_scope("read"))])
def get_goal_status(goal_id: int):
    try:
        return {"ok": True, "goal": goal_status(_goals_db(), goal_id)}
    except GoalError as exc:
        raise _as_goal_error(exc, status_code=404) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Goal status computation failed")
        raise HTTPException(status_code=500, detail=f"Goal status failed: {exc}") from None
