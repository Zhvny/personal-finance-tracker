"""
backend/routers/scheduler.py — Scheduler control + Net Worth history
=====================================================================
Extracted from api_server.py as part of Step 5 router split.
Architecture: High Cohesion — this file owns only /api/scheduler|/api/networth routes.
Low Coupling : depends only on backend/routers/deps.py and FastAPI. Never imports other routers.
"""

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from packages.api.backend.security.core import require_scope

router       = APIRouter(dependencies=[Depends(require_scope("write"))])
router_read  = APIRouter(dependencies=[Depends(require_scope("read"))])
logger       = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════
# SCHEDULER STATUS & NET WORTH HISTORY
# ═════════════════════════════════════════════════════════════════════

# ── Lazy-load scheduler module ────────────────────────────────────────────────
_scheduler_mod = None

def _get_scheduler_mod():
    """Lazy-load scheduler.py (for status/trigger/history only — not to start it)."""
    global _scheduler_mod
    if _scheduler_mod is None:
        try:
            import importlib.util as _ilu
            _sched_path = Path(__file__).parent.parent / "automation" / "scheduler.py"
            spec = _ilu.spec_from_file_location("scheduler_mod", str(_sched_path))
            mod  = _ilu.module_from_spec(spec)
            sys.modules["scheduler_mod"] = mod
            spec.loader.exec_module(mod)
            _scheduler_mod = mod
        except Exception:
            logger.exception("Error while running scheduled job")
            pass
    return _scheduler_mod


@router.get("/api/scheduler/status")
def scheduler_status():
    """Return last_run and last_status for each scheduled job."""
    sm = _get_scheduler_mod()
    if not sm:
        return {"ok": False, "error": "Scheduler module tidak tersedia.", "jobs": {}}
    return {"ok": True, **sm.get_status()}


@router.post("/api/scheduler/trigger")
def scheduler_trigger(body: dict):
    """
    Manually trigger a scheduled job (admin/debug).
    body: { job: "networth" | "prices" | "behavioral" | "recurring" }
    """
    job_name = (body.get("job") or "").strip()
    if not job_name:
        raise HTTPException(400, "job is required.")
    sm = _get_scheduler_mod()
    if not sm:
        logger.error("Scheduler module not available")
        raise HTTPException(503, "Scheduler module tidak tersedia.")
    result = sm.trigger_job(job_name)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Unknown error"))
    return result


@router_read.get("/api/networth/history")
def networth_history(days: int = 90):
    """
    Return net worth snapshots for graph visualisation (Phase 2).
    Falls back to empty list if no snapshots yet.
    """
    sm = _get_scheduler_mod()
    if not sm:
        return {"ok": True, "history": [], "days": days}
    history = sm.get_networth_history(days)
    return {"ok": True, "history": history, "days": days, "count": len(history)}


# ══════════════════════════════════════════════════════════════════════════════
