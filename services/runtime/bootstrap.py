"""
Alpha Services Runtime — shared bootstrap for Alpha domain microservices.

Stage-1 architecture (honey: shared DB + shared router library; split
persistence per-service when a context needs independent scaling — trigger:
any service needing its own DB or deploy cadence).

Each service = own process/port, mounting ONLY its routers from the shared
library `packages.api.backend.routers` (+ optional inline routes).
"""

import asyncio
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from logging.handlers import RotatingFileHandler

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.api.config import settings
from packages.api.backend.infrastructure.encoders import ExtendedJSONResponse
from packages.api.backend.infrastructure.schemas import SchemaInitializer
from packages.api.backend.routers.deps import _db as db
from packages.api.backend.security.core import audit_middleware, require_scope, verify_api_key
from packages.core.infrastructure.logging import ColoredFormatter

LOG_DIR = _PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
START_TIME = time.time()


class _RequestIdFilter(logging.Filter):
    """Suntikkan request_id (dari security.core contextvar) ke tiap record log."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from packages.api.backend.security.core import get_request_id
            record.request_id = get_request_id()
        except Exception:
            record.request_id = "-"
        return True


def _setup_logging(service_name: str) -> logging.Logger:
    logger = logging.getLogger(service_name)
    handler_path = LOG_DIR / f"{service_name}.log"
    rid_filter = _RequestIdFilter()
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s - %(message)s"
    )
    file_handler = RotatingFileHandler(handler_path, maxBytes=5 * 1024 * 1024, backupCount=3)
    file_handler.setFormatter(fmt)
    file_handler.addFilter(rid_filter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(ColoredFormatter("%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s - %(message)s"))
    stream_handler.addFilter(rid_filter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if root.hasHandlers():
        root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    return logger


def create_service_app(
    service_name: str,
    default_port: int,
    routers: list[str],
    register_inline=None,
    scheduler_enabled: bool = False,
    butterfly_cleanup: bool = False,
    telegram_optin: bool = False,
) -> FastAPI:
    logger = _setup_logging(service_name)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(f"[*] Starting {service_name}...")
        schema_ok = False
        try:
            await asyncio.to_thread(SchemaInitializer(db).ensure_all)
            schema_ok = True
            logger.info("Database schema verification completed.")
        except Exception as e:
            logger.error(f"CRITICAL: Schema initialization failed: {e}", exc_info=True)

        try:
            from packages.database.index import connect as prisma_connect
            await prisma_connect()
            logger.info("Prisma client connected.")
        except Exception as e:
            logger.error(f"CRITICAL: Prisma connection failed: {e}", exc_info=True)

        scheduler = None
        if scheduler_enabled and schema_ok:
            try:
                from packages.api.backend.automation.market_scheduler import MarketScheduler
                from packages.api.backend.automation.scheduler_lock import scheduler_ownership
                from packages.api.backend.automation.scheduler_registry import register_scheduler

                if not scheduler_ownership.try_acquire():
                    raise RuntimeError("another scheduler owns the lock - refusing to start (TD-1)")
                scheduler = MarketScheduler()
                register_scheduler(scheduler)
                await asyncio.to_thread(scheduler.start)
                logger.info("Market background scheduler started.")
            except Exception as e:
                logger.error(f"CRITICAL: MarketScheduler failed to start: {e}", exc_info=True)

        telegram_task = None
        if telegram_optin and os.getenv("ENABLE_TELEGRAM_POLL", "0") == "1":
            try:
                from packages.api.telegram_poll import poll
                telegram_task = asyncio.create_task(poll())
                logger.info("Telegram Bot Polling task started in background.")
            except Exception as e:
                logger.warning(f"Telegram Bot Polling task failed to start: {e}")

        yield

        logger.info(f"[*] Shutting down {service_name}...")
        if telegram_task:
            telegram_task.cancel()
        if scheduler:
            try:
                await asyncio.to_thread(scheduler.shutdown)
            except Exception as e:
                logger.error(f"Error during scheduler shutdown: {e}")
        if butterfly_cleanup:
            try:
                from packages.api.backend.routers.deps import butterfly_service
                await asyncio.to_thread(butterfly_service.shutdown)
            except Exception as e:
                logger.error(f"Error during butterfly service shutdown: {e}")
        try:
            from packages.database.index import disconnect as prisma_disconnect
            await prisma_disconnect()
        except Exception as e:
            logger.error(f"Error during Prisma disconnect: {e}")

    app = FastAPI(
        title=service_name,
        version=settings.SERVICE_VERSION,
        description=f"Alpha platform domain service: {service_name}",
        lifespan=lifespan,
        default_response_class=ExtendedJSONResponse,
    )

    # honey: HTTPS kini OPT-IN via ENABLE_HTTPS=1 (cert dev menyebabkan semua
    # klien HTTP ditolak -> socket hang up massal, lihat audit 2026-08-24)
    if os.getenv('ENABLE_HTTPS') == '1' and settings.SSL_CERT_PATH.exists() and settings.SSL_KEY_PATH.exists():
        app.add_middleware(HTTPSRedirectMiddleware)

    # SECURITY: credentialed CORS + wildcard origin ditolak — browser abaikan
    # allow-credentials bila origin "*", jadi paksa False + warning.
    _cors_credentials = True
    if "*" in settings.ALLOWED_ORIGINS:
        logger.warning("CORS origins contain '*': forcing allow_credentials=False")
        _cors_credentials = False
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=_cors_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Request-Signature", "Accept"],
    )
    app.middleware("http")(audit_middleware)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        if isinstance(exc, (HTTPException, StarletteHTTPException)):
            return ExtendedJSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=getattr(exc, "headers", None),
            )
        logger.error(f"Unhandled error at {request.url.path}: {exc}", exc_info=True)
        return ExtendedJSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    @app.get("/health", tags=["System"])
    @app.get("/health/live", tags=["System"])
    async def liveness():
        return {"status": "ok", "service": service_name, "uptime_seconds": round(time.time() - START_TIME, 2)}

    @app.get("/health/ready", tags=["System"])
    async def readiness():
        try:
            await asyncio.to_thread(SchemaInitializer(db).ensure_all)
            return {"status": "ready", "service": service_name}
        except Exception:
            return JSONResponse(status_code=503, content={"status": "not_ready", "service": service_name})

    @app.get("/info", tags=["System"], dependencies=[Depends(require_scope("read"))])
    async def info(token: str = Depends(verify_api_key)):
        return {
            "service": service_name,
            "version": settings.SERVICE_VERSION,
            "environment": "production" if not settings.DEBUG else "development",
            "uptime_seconds": round(time.time() - START_TIME, 2),
        }

    import importlib

    registered = 0
    for module_name in routers:
        try:
            if "." in module_name:
                mod = importlib.import_module(module_name)
            else:
                mod = importlib.import_module(f"packages.api.backend.routers.{module_name}")
            if hasattr(mod, "router"):
                app.include_router(mod.router)
                registered += 1
            if hasattr(mod, "router_read"):
                app.include_router(mod.router_read)
                registered += 1
        except Exception as e:
            logger.error(f"Router registration failed for '{module_name}': {e}", exc_info=True)
    logger.info(f"Registered {registered} routers for {service_name}.")

    if register_inline is not None:
        register_inline(app, logger)
        logger.info(f"Inline routes registered for {service_name}.")

    app.state.default_port = default_port
    return app


def run_service(app: FastAPI, service_name: str):
    host = settings.HOST
    port = int(os.getenv("ALPHA_SERVICE_PORT", app.state.default_port))
    use_https = settings.SSL_CERT_PATH.exists() and settings.SSL_KEY_PATH.exists()
    protocol = "https" if use_https else "http"
    print(f"\n[*] Launching {service_name} v{settings.SERVICE_VERSION} ({protocol.upper()}) on {host}:{port}")
    kwargs = {"host": host, "port": port, "reload": False, "log_level": "info"}
    if use_https:
        kwargs.update(ssl_keyfile=str(settings.SSL_KEY_PATH), ssl_certfile=str(settings.SSL_CERT_PATH))
    uvicorn.run(app, **kwargs)
