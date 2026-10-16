"""
backend/routers/business_analytics.py — Business Profile Analytics Routes
=========================================================================
Owns all /api/business/* routes.
Depends only on BusinessAnalyticsService and FastAPI.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator

from packages.api.backend.security.core import require_scope
from packages.core.application.business_analytics_service import BusinessAnalyticsService

router = APIRouter(
    prefix="/api/business",
    tags=["Business Analytics"],
    dependencies=[Depends(require_scope("read"))]
)

logger = logging.getLogger(__name__)
_service = BusinessAnalyticsService()


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    code: str
    budget: float
    start_date: str
    end_date: str
    description: Optional[str] = None

    @field_validator("budget")
    @classmethod
    def budget_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Budget must be greater than 0")
        return v

    @field_validator("code")
    @classmethod
    def code_format(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Project code cannot be empty")
        return v.upper().strip()


class DailyProgressIn(BaseModel):
    project_id: int
    log_date: str
    planned_pct: float
    actual_pct: float
    actual_cost: float
    headcount: int = 0
    work_hours: float = 8.0
    tasks_completed: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("planned_pct", "actual_pct")
    @classmethod
    def pct_range(cls, v: float) -> float:
        if not (0.0 <= v <= 100.0):
            raise ValueError("Progress percentage must be between 0 and 100")
        return v

    @field_validator("actual_cost")
    @classmethod
    def cost_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Actual cost cannot be negative")
        return v


class AttendanceIn(BaseModel):
    project_id: int
    log_date: str
    worker_role: str
    present_count: int
    total_count: int
    man_hours: float

    @field_validator("man_hours")
    @classmethod
    def hours_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Man-hours cannot be negative")
        return v


class MilestoneIn(BaseModel):
    project_id: int
    title: str
    target_date: str
    weight: float = 1.0
    description: Optional[str] = None


# ── Project Endpoints ─────────────────────────────────────────────────────────

@router.get("/projects")
async def list_projects():
    """List all business projects."""
    try:
        return await _service.get_projects()
    except Exception as e:
        logger.error(f"list_projects error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects", dependencies=[Depends(require_scope("write"))])
async def create_project(body: ProjectCreate):
    """Create a new business project."""
    try:
        start_dt = datetime.fromisoformat(body.start_date)
        end_dt   = datetime.fromisoformat(body.end_date)
        return await _service.create_project(
            name=body.name,
            code=body.code,
            budget=body.budget,
            start_date=start_dt,
            end_date=end_dt,
            description=body.description,
        )
    except Exception as e:
        logger.error(f"create_project error: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# ── Daily Progress Logging ─────────────────────────────────────────────────────

@router.post("/daily-log", dependencies=[Depends(require_scope("write"))])
async def record_daily_progress(body: DailyProgressIn):
    """Submit a daily progress and cost entry for a project."""
    try:
        log_dt = datetime.fromisoformat(body.log_date)
        return await _service.record_daily_progress(
            project_id=body.project_id,
            log_date=log_dt,
            planned_pct=body.planned_pct,
            actual_pct=body.actual_pct,
            actual_cost=body.actual_cost,
            headcount=body.headcount,
            work_hours=body.work_hours,
            tasks_completed=body.tasks_completed,
            notes=body.notes,
        )
    except Exception as e:
        logger.error(f"record_daily_progress error: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# ── Labor & Attendance ─────────────────────────────────────────────────────────

@router.post("/attendance", dependencies=[Depends(require_scope("write"))])
async def record_attendance(body: AttendanceIn):
    """Record labor attendance and man-hours for a project."""
    try:
        log_dt = datetime.fromisoformat(body.log_date)
        return await _service.record_labor_attendance(
            project_id=body.project_id,
            log_date=log_dt,
            worker_role=body.worker_role,
            present_count=body.present_count,
            total_count=body.total_count,
            man_hours=body.man_hours,
        )
    except Exception as e:
        logger.error(f"record_attendance error: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# ── Milestones ─────────────────────────────────────────────────────────────────

@router.post("/milestones", dependencies=[Depends(require_scope("write"))])
async def add_milestone(body: MilestoneIn):
    """Add a milestone to a project."""
    try:
        target_dt = datetime.fromisoformat(body.target_date)
        return await _service.add_milestone(
            project_id=body.project_id,
            title=body.title,
            target_date=target_dt,
            weight=body.weight,
            description=body.description,
        )
    except Exception as e:
        logger.error(f"add_milestone error: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/milestones/{milestone_id}/complete", dependencies=[Depends(require_scope("write"))])
async def complete_milestone(milestone_id: int):
    """Mark a milestone as completed."""
    try:
        return await _service.complete_milestone(milestone_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Analytics & EVM ─────────────────────────────────────────────────────────────

@router.get("/analytics/{project_id}")
async def get_analytics(project_id: int):
    """
    Retrieve full EVM analytics (PV, EV, AC, CPI, SPI, CV, SV, EAC, ETC),
    S-Curve time series, labor summary, and milestone progress.
    """
    try:
        return await _service.get_project_analytics(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"get_analytics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Executive Report Generation ────────────────────────────────────────────────

@router.get("/reports/generate")
async def generate_report(
    project_id: int,
    period: str = "weekly",
    format: str = "json",
):
    """
    Generate an automated executive performance report.
    - format=json      → structured JSON (default)
    - format=markdown  → Markdown text
    - format=html      → Printable HTML (PDF-ready)
    """
    try:
        report = await _service.generate_executive_report(project_id, period_type=period)

        if format == "markdown" or format == "md":
            return Response(
                content=report["markdown"],
                media_type="text/markdown",
                headers={"Content-Disposition": f"attachment; filename=report_{project_id}_{period}.md"}
            )
        elif format == "html":
            return HTMLResponse(
                content=report["html"],
                headers={"Content-Disposition": f"attachment; filename=report_{project_id}_{period}.html"}
            )
        elif format == "pdf":
            # Printable PDF-optimized HTML wrapper
            pdf_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Executive Performance Report — Project {project_id}</title>
<style>
  @media print {{ @page {{ margin: 15mm; size: A4; }} body {{ -webkit-print-color-adjust: exact; }} }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 24px; color: #181a20; }}
</style>
</head>
<body onload="window.print()">
  {report['html']}
</body>
</html>"""
            return HTMLResponse(
                content=pdf_html,
                headers={"Content-Disposition": f"inline; filename=report_{project_id}_{period}.pdf.html"}
            )
        else:
            return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"generate_report error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
