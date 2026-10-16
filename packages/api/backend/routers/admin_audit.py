"""Admin-only audit query (SECURITY-AUDIT API5/CR-5 — menghidupkan tier admin)."""

from fastapi import APIRouter, Depends, HTTPException, Query

from packages.api.backend.security.core import query_audit_log, require_scope
from packages.api.backend.infrastructure.schemas import (
    EXPECTED_TABLES_PER_PROFILE,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_scope("admin"))],
)


@router.get("/audit")
def get_audit(
    limit: int = Query(default=100, le=1000),
    ip: str | None = Query(default=None),
    path: str | None = Query(default=None),
    since: str | None = Query(default=None),
):
    """Query audit log. Hanya token dengan scope admin (master key / dev)."""
    return {"entries": query_audit_log(limit=limit, ip=ip, path=path, since=since)}


@router.get("/schema/status")
def get_schema_status():
    """
    Health check for profile schemas (R1 schema-fix observability).

    Returns the active profile, table count, expected count, and per-schema
    status. Returns 503 if any profile schema is incomplete so monitoring
    systems can alert. Admin scope only.
    """
    from packages.core.infrastructure.config import Config
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager

    active = Config.get_active_profile()
    profiles = [active] if active and not active.startswith("qa_") else []

    # All known profiles (from registry)
    try:
        from packages.core.application.profile_service import ProfileService
        svc = ProfileService(Config.BASE_DIR)
        all_profiles = svc.get_available_profiles()
    except Exception:
        all_profiles = []

    schemas_status = []
    any_incomplete = False
    for profile in profiles:
        try:
            rows = DatabaseManager.query(
                "SELECT COUNT(*) AS table_count FROM information_schema.tables WHERE table_schema = %s",
                (profile,),
            )
            # DatabaseManager.query uses RealDictCursor → rows are dicts.
            count = int(rows[0]["table_count"]) if rows else 0
            healthy = count >= EXPECTED_TABLES_PER_PROFILE
            schemas_status.append({
                "profile": profile,
                "table_count": count,
                "expected": EXPECTED_TABLES_PER_PROFILE,
                "healthy": healthy,
            })
            if not healthy:
                any_incomplete = True
        except Exception as e:
            schemas_status.append({
                "profile": profile,
                "error": str(e),
            })
            any_incomplete = True

    payload = {
        "status": "ok" if not any_incomplete else "degraded",
        "active_profile": active,
        "all_known_profiles": all_profiles,
        "schemas": schemas_status,
        "remediation": (
            "Run `python migrations/runner.py apply` to provision missing tables."
            if any_incomplete else None
        ),
    }
    if any_incomplete:
        raise HTTPException(status_code=503, detail=payload)
    return payload
