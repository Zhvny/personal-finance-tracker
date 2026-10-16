"""alpha-platform :8450 — auth, profiles, logs, notifications(WS), telegram."""

from packages.api.backend.routers.deps import FX_RATE, get_live_fx_rate
from services.runtime.bootstrap import create_service_app, run_service

ROUTERS = [
    "auth",
    "profiles",
    "logs",
    "notifications",
    "admin_audit",
    "packages.api.telegram_bot",
]

DEFAULT_PORT = 8450


def register_inline(app, logger):
    from fastapi import Depends

    from packages.api.backend.security.core import require_scope

    @app.get("/api/config", tags=["System"], dependencies=[Depends(require_scope("read"))])
    async def get_config():
        return {"fx_rate": await get_live_fx_rate(), "fx_rate_fallback": FX_RATE}


app = create_service_app(
    service_name="alpha-platform",
    default_port=DEFAULT_PORT,
    routers=ROUTERS,
    register_inline=register_inline,
    telegram_optin=True,
)

if __name__ == "__main__":
    run_service(app, "alpha-platform")
