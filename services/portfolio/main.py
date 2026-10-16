"""alpha-portfolio :8452 — investments (FIFO), reports, dashboard aggregator."""

from services.runtime.bootstrap import create_service_app, run_service

ROUTERS = [
    "investments",
    "reports",
]

DEFAULT_PORT = 8452


def register_inline(app, logger):
    # Moved verbatim from legacy apps/api/main.py (/api/dashboard*)
    from typing import Optional

    from fastapi import Depends
    from fastapi.responses import JSONResponse

    from packages.api.backend.security.core import require_scope

    @app.get("/api/dashboard", tags=["Dashboard"], dependencies=[Depends(require_scope("read"))])
    async def get_dashboard(year: Optional[int] = None, month: Optional[int] = None):
        try:
            from packages.api.backend.routers.deps import dashboard_service, get_active_profile

            profile_id = get_active_profile()
            return await dashboard_service.get_summary(profile_id, year, month)
        except Exception as e:
            logger.error(f"Dashboard error: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Dashboard unavailable",
                    "month_label": "System Error",
                    "income": {"total_this": 0, "total_prev": 0},
                    "expense": {"total_this": 0, "total_prev": 0, "by_category": {}},
                    "investments": {"pl_total": 0, "holdings": []},
                },
            )

    @app.get("/api/dashboard/metadata", tags=["Dashboard"], dependencies=[Depends(require_scope("read"))])
    async def get_dashboard_metadata(year: Optional[int] = None, month: Optional[int] = None):
        try:
            from packages.api.backend.routers.deps import dashboard_service, get_active_profile

            profile_id = get_active_profile()
            return await dashboard_service.get_metadata(profile_id, year, month)
        except Exception as e:
            logger.error(f"Dashboard metadata error: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=503, content={"month_label": "Error", "error": "Dashboard metadata unavailable"}
            )


app = create_service_app(
    service_name="alpha-portfolio",
    default_port=DEFAULT_PORT,
    routers=ROUTERS,
    register_inline=register_inline,
)

if __name__ == "__main__":
    run_service(app, "alpha-portfolio")
