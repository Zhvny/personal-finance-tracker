from fastapi import APIRouter, Depends, HTTPException, status

from packages.api.backend.automation.scheduler_registry import get_scheduler
from packages.api.backend.security.core import require_scope

router = APIRouter(prefix='/scheduler', tags=['Scheduler'])

@router.get('/health')
async def scheduler_health(scope=Depends(require_scope('read'))):
    scheduler = get_scheduler()
    if not scheduler:
        return {"status": "not_running", "jobs": {}}
    return {"status": "running", "jobs": scheduler.get_health()}

@router.post('/trigger/{job_name}')
async def trigger_scheduler_job(job_name: str, scope=Depends(require_scope('admin'))):
    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Scheduler is not running")

    jobs = {
        "market_update_incremental": scheduler._update_job,
        "market_update_initial": scheduler._update_job,
        "market_update_daily_full": scheduler._update_job,
        "daily_financial_report": scheduler._daily_report_job
    }

    if job_name not in jobs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_name} not found")

    try:
        # Trigger it synchronously in a separate thread/executor if needed, but for manual trigger we can just run it
        # Actually _update_job uses ThreadPoolExecutor internally via _run_with_timeout
        jobs[job_name](job_name)
        return {"status": "triggered", "job": job_name}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
