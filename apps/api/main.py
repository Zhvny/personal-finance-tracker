#!/usr/bin/env python3
"""
Finance Tracker — Alpha Microservice (Clean Architecture)
=========================================================
Production-grade FastAPI microservice container for the Alpha platform.
Provides RESTful APIs, background schedulers, AI/ML inference, and database access.

FROZEN — LEGACY monolith. Do not add routes or features here.
Canonical entry points are services/* (6 domain services + gateway).
This module is kept for the old runner only; new work goes to services/*.
"""

import asyncio
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

# Enable Prisma debug generator if needed
os.environ["PRISMA_PY_DEBUG_GENERATOR"] = "1"

# ── Windows Asyncio Patch ───────────────────────────────────────────────────
if sys.platform == "win32":
    from asyncio.proactor_events import _ProactorBasePipeTransport

    def _call_connection_lost_patched(self, exc):
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except (OSError, AttributeError):
            pass
        self._call_connection_lost_orig(exc)

    if not hasattr(_ProactorBasePipeTransport, "_call_connection_lost_orig"):
        import socket

        _ProactorBasePipeTransport._call_connection_lost_orig = _ProactorBasePipeTransport._call_connection_lost
        _ProactorBasePipeTransport._call_connection_lost = _call_connection_lost_patched

# ── Path Resolution ──────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent
_PACKAGES_API_DIR = _PROJECT_ROOT / "packages" / "api"

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_PACKAGES_API_DIR) not in sys.path:
    sys.path.insert(0, str(_PACKAGES_API_DIR))

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.api.config import settings
from packages.api.backend.routers.deps import FX_RATE, _db

db = _db
# ── Logging Setup ────────────────────────────────────────────────────────────
from logging.handlers import RotatingFileHandler

from packages.api.backend.automation.market_scheduler import MarketScheduler
from packages.api.backend.infrastructure.encoders import ExtendedJSONResponse
from packages.api.backend.infrastructure.schemas import SchemaVerifier
from packages.api.backend.security.core import audit_middleware, require_scope, verify_api_key
from packages.core.infrastructure.logging import ColoredFormatter
from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager

_file_handler = RotatingFileHandler(_HERE / "alpha_microservice.log", maxBytes=5 * 1024 * 1024, backupCount=3)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))

_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(ColoredFormatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
if root_logger.hasHandlers():
    root_logger.handlers.clear()
root_logger.addHandler(_file_handler)
root_logger.addHandler(_stream_handler)

logger = logging.getLogger("alpha-microservice")
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

START_TIME = time.time()


# ── Microservice Lifespan ─────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[*] Starting Alpha Microservice engine...")

    # 1. Verify (not init) DB schemas on startup. After R1 schema-fix (2026-09-05),
    # ensure_all() is read-only — it only checks that expected schemas/tables exist.
    # If something is missing, the app logs a warning and continues; downstream
    # endpoints will return 503. Use SchemaVerifier for fail-fast (raises).
    schema_ok = False
    try:
        await asyncio.to_thread(SchemaVerifier(_db).verify_all)
        logger.info("Database schema verification completed.")
        schema_ok = True
    except Exception as e:
        logger.warning(
            f"Schema verification incomplete: {e}. "
            f"App will start but schema-dependent endpoints may return 503. "
            f"Run `python migrations/runner.py apply` to fix."
        )

    # 2. Connect Prisma client
    try:
        from packages.database.index import connect as prisma_connect

        await prisma_connect()
        logger.info("Prisma client connected.")
    except Exception as e:
        logger.error(f"CRITICAL: Prisma connection failed: {e}", exc_info=True)

    # 3. Start Market Background Scheduler
    scheduler = None
    if schema_ok:
        try:
            from packages.api.backend.automation.scheduler_lock import scheduler_ownership

            if not scheduler_ownership.try_acquire():
                raise RuntimeError("another scheduler owns the lock - refusing to start (TD-1)")
            scheduler = MarketScheduler()
            from packages.api.backend.automation.scheduler_registry import register_scheduler

            register_scheduler(scheduler)
            await asyncio.to_thread(scheduler.start)
            logger.info("Market background scheduler started.")
        except Exception as e:
            logger.error(f"CRITICAL: MarketScheduler failed to start: {e}", exc_info=True)
    else:
        logger.warning("Market background scheduler skipped due to schema initialization failure.")

    # 4. Start Telegram Bot Polling Background Task (Opt-in via ENABLE_TELEGRAM_POLL)
    telegram_task = None
    if os.getenv("ENABLE_TELEGRAM_POLL", "0") == "1":
        try:
            from packages.api.telegram_poll import poll

            telegram_task = asyncio.create_task(poll())
            logger.info("Telegram Bot Polling task started in background.")
        except Exception as e:
            logger.warning(f"Telegram Bot Polling task failed to start: {e}")
    else:
        logger.info("Telegram Bot Polling skipped in API server (set ENABLE_TELEGRAM_POLL=1 to enable).")

    yield

    # 5. Graceful Shutdown Cleanup
    logger.info("[*] Shutting down Alpha Microservice...")
    if telegram_task:
        telegram_task.cancel()
        logger.info("Telegram Bot Polling task cancelled.")

    if scheduler:
        try:
            await asyncio.to_thread(scheduler.shutdown)
            logger.info("Market background scheduler shut down.")
        except Exception as e:
            logger.error(f"Error during scheduler shutdown: {e}")

    try:
        from packages.api.backend.routers.deps import butterfly_service

        await asyncio.to_thread(butterfly_service.shutdown)
        logger.info("Butterfly service executors shut down.")
    except Exception as e:
        logger.error(f"Error during butterfly service shutdown: {e}")

    try:
        from packages.database.index import disconnect as prisma_disconnect

        await prisma_disconnect()
        logger.info("Prisma client disconnected.")
    except Exception as e:
        logger.error(f"Error during Prisma disconnect: {e}")


# ── Application Factory ──────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.SERVICE_NAME,
        version=settings.SERVICE_VERSION,
        description="Alpha Microservice API Container — Financial Analytics & Execution Gateway",
        lifespan=lifespan,
        default_response_class=ExtendedJSONResponse,
    )

    # HTTPS Redirection if certs present
    if settings.SSL_CERT_PATH.exists() and settings.SSL_KEY_PATH.exists():
        app.add_middleware(HTTPSRedirectMiddleware)
        logger.info("HTTPS redirection middleware enabled.")

    # CORS & Audit Middlewares
    # SECURITY: credentialed CORS + wildcard origin ditolak (settings-only fix).
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
                status_code=exc.status_code, content={"detail": exc.detail}, headers=getattr(exc, "headers", None)
            )
        logger.error(f"Unhandled error at {request.url.path}: {exc}", exc_info=True)
        return ExtendedJSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    # ── Microservice Health & Diagnostic Endpoints ───────────────────────────

    @app.get("/health", tags=["System"])
    @app.get("/api/health", tags=["System"])
    async def health_check():
        """Full system health inspection."""
        db_alive = False
        try:
            await asyncio.to_thread(DatabaseManager.query, "SELECT 1")
            db_alive = True
        except Exception as e:
            logger.error(f"Health check failed: Database unreachable: {e}")

        if not db_alive:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "service": "alpha-microservice",
                    "database": "down",
                    "uptime_seconds": time.time() - START_TIME,
                    "ts": time.time(),
                },
            )

        return {
            "status": "ok",
            "service": settings.SERVICE_NAME,
            "version": settings.SERVICE_VERSION,
            "database": "connected",
            "uptime_seconds": time.time() - START_TIME,
            "ts": time.time(),
        }

    @app.get("/healthz", tags=["System"])
    @app.get("/health/live", tags=["System"])
    @app.get("/api/health/live", tags=["System"])
    async def liveness_probe():
        """Kubernetes/Docker liveness probe endpoint."""
        return {"status": "alive", "service": "alpha-microservice"}

    @app.get("/health/ready", tags=["System"])
    @app.get("/api/health/ready", tags=["System"])
    async def readiness_probe():
        """Kubernetes/Docker readiness probe endpoint."""
        try:
            await asyncio.to_thread(DatabaseManager.query, "SELECT 1")
            return {"status": "ready", "service": "alpha-microservice", "database": "connected"}
        except Exception:
            return JSONResponse(status_code=503, content={"status": "not_ready"})

    @app.get("/info", tags=["System"], dependencies=[Depends(require_scope("read"))])
    @app.get("/version", tags=["System"], dependencies=[Depends(require_scope("read"))])
    async def service_info(token: str = Depends(verify_api_key)):
        """Returns microservice operational metadata (authenticated)."""
        return {
            "service": settings.SERVICE_NAME,
            "version": settings.SERVICE_VERSION,
            "environment": "production" if not settings.DEBUG else "development",
            "uptime_seconds": round(time.time() - START_TIME, 2),
        }

    # ── Core Dashboard & Config Endpoints ────────────────────────────────────

    @app.get("/api/dashboard", tags=["Dashboard"], dependencies=[Depends(require_scope("read"))])
    async def get_dashboard(year: Optional[int] = None, month: Optional[int] = None):
        try:
            from packages.api.backend.routers.deps import dashboard_service, get_active_profile

            profile_id = get_active_profile()
            return await dashboard_service.get_summary(profile_id, year, month)
        except Exception as e:
            logger.error(f"Dashboard error: {str(e)}", exc_info=True)
            return {
                "error": "Dashboard unavailable",
                "month_label": "System Error",
                "income": {"total_this": 0, "total_prev": 0},
                "expense": {"total_this": 0, "total_prev": 0, "by_category": {}},
                "investments": {"pl_total": 0, "holdings": []},
            }

    @app.get("/api/dashboard/metadata", tags=["Dashboard"], dependencies=[Depends(require_scope("read"))])
    async def get_dashboard_metadata(year: Optional[int] = None, month: Optional[int] = None):
        try:
            from packages.api.backend.routers.deps import dashboard_service, get_active_profile

            profile_id = get_active_profile()
            return await dashboard_service.get_metadata(profile_id, year, month)
        except Exception as e:
            logger.error(f"Dashboard metadata error: {str(e)}", exc_info=True)
            return {"month_label": "Error"}

    @app.get("/api/config", tags=["System"], dependencies=[Depends(require_scope("read"))])
    async def get_config():
        # Live rate dari FXService; fallback ke konstanta kalau sumber mati.
        try:
            from packages.api.backend.routers.deps import get_live_fx_rate

            rate = await get_live_fx_rate()
        except Exception:
            rate = FX_RATE
        return {"fx_rate": rate}

    @app.get("/api/genetic/universe/audit", tags=["Genetic Analytics"], dependencies=[Depends(require_scope("read"))])
    async def get_genetic_universe_audit():
        try:
            import pandas as pd

            from apps.cli.genetic_optimizer import PortfolioOptimizer
            from packages.core.infrastructure.persistence.postgres_ohlcv_repository import PostgresOHLCVRepository

            repo = PostgresOHLCVRepository()
            tickers = await asyncio.to_thread(DatabaseManager.query, "SELECT DISTINCT ticker FROM market.ohlcv_cache")
            ticker_list = [r["ticker"] for r in tickers]

            if not ticker_list:
                return {"total": 0, "eligible": 0, "excluded": [], "message": "No data in market cache"}

            import io as _io

            def _load_all_closes():
                """Satu roundtrip utk semua blob OHLCV '1y', ekstrak kolom Close saja."""
                rows = DatabaseManager.query("SELECT ticker, data FROM market.ohlcv_cache WHERE period = '1y'")
                closes = {}
                for r in rows:
                    raw = r["data"]
                    if isinstance(raw, memoryview):
                        raw = raw.tobytes()
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    try:
                        df = pd.read_json(_io.StringIO(raw), orient="split")
                    except Exception:
                        continue
                    if df is None or df.empty or len(df) < 30:
                        continue
                    df.columns = [str(c).capitalize() for c in df.columns]
                    if "Close" in df.columns:
                        closes[r["ticker"]] = df["Close"]
                return closes

            returns_map = await asyncio.to_thread(_load_all_closes)

            if not returns_map:
                return {
                    "total": len(ticker_list),
                    "eligible": 0,
                    "excluded": [{"ticker": t, "reason": "No valid historical data"} for t in ticker_list],
                }

            all_available_tickers = list(returns_map.keys())
            price_df = pd.DataFrame(returns_map).ffill().dropna()

            aligned_tickers = list(price_df.columns)
            dropped_during_alignment = set(all_available_tickers) - set(aligned_tickers)

            if price_df.empty:
                return {
                    "total": len(ticker_list),
                    "eligible": 0,
                    "excluded": [{"ticker": t, "reason": "No overlapping historical data"} for t in ticker_list],
                }

            returns_df = price_df.pct_change().dropna()
            optimizer = PortfolioOptimizer()
            audit_result = optimizer.get_universe_audit(returns_df)
            audit_result["total"] = len(ticker_list)

            pre_excluded = set(ticker_list) - set(all_available_tickers)
            for t in pre_excluded:
                audit_result["excluded"].append(
                    {"ticker": t, "reason": "Insufficient data history (< 30 days) or missing Close column"}
                )

            for t in dropped_during_alignment:
                audit_result["excluded"].append(
                    {"ticker": t, "reason": "No overlapping historical data range with other assets"}
                )

            return audit_result

        except Exception as e:
            logger.error(f"Universe audit error: {str(e)}", exc_info=True)
            return {"error": "Universe audit failed", "total": 0, "eligible": 0, "excluded": []}

    # ── Router Registration ──────────────────────────────────────────────────
    logger.info("Registering Alpha Microservice domain routers...")
    import importlib

    router_modules = [
        ("expenses", "expenses"),
        ("auth", "auth"),
        ("income", "income"),
        ("investments", "investments"),
        ("receipts", "receipts"),
        ("advanced", "advanced"),
        ("behavioral", "behavioral"),
        ("balances", "balances"),
        ("rewards", "rewards"),
        ("merchant", "merchant"),
        ("scheduler", "scheduler"),
        ("analytics", "analytics"),
        ("ai", "ai"),
        ("stocks", "stocks"),
        ("ml_stocks", "ml_stocks"),
        ("butterfly", "butterfly"),
        ("genetic", "genetic"),
        ("profiles", "profiles"),
        ("senate", "senate"),
        ("notifications", "notifications"),
        ("accounts", "accounts"),
        ("scheduler_status", "scheduler_status"),
        ("logs", "logs"),
        ("business_analytics", "business_analytics"),
        ("ledger", "ledger"),
        ("confirmations", "confirmations"),
        ("reports", "reports"),
        ("budget", "budget"),
        ("recurring", "recurring"),
        ("goals", "goals"),
        ("forecast", "forecast"),
        ("safe_spend", "safe_spend"),
        ("nl_finance", "nl_finance"),
        ("anomalies", "anomalies"),
        ("insights", "insights"),
        ("health_score", "health_score"),
        ("net_worth", "net_worth"),
        ("telegram_bot", "packages.api.telegram_bot"),
    ]

    registered_count = 0
    for name, module_name in router_modules:
        try:
            if module_name.startswith("packages."):
                mod = importlib.import_module(module_name)
            else:
                mod = importlib.import_module(f"packages.api.backend.routers.{module_name}")
            if hasattr(mod, "router"):
                app.include_router(mod.router)
                registered_count += 1
            if name == "scheduler" and hasattr(mod, "router_read"):
                app.include_router(mod.router_read)
                registered_count += 1
        except Exception as e:
            logger.error(f"Router registration failed for '{name}': {e}", exc_info=True)

    logger.info(f"Successfully registered {registered_count} domain routers.")

    # ── Static / Frontend Files Mounting ─────────────────────────────────────
    # NOTE: The canonical frontend is apps/web/ (Next.js 16 standalone).
    # This static file serving is a LEGACY fallback for the old Vite-based
    # packages/web (finance-tracker-gui) frontend. In production, the Next.js
    # frontend runs as a separate service and the API runs in pure API mode.
    # This block is kept for local development convenience only.
    _DIST = _PROJECT_ROOT / "packages" / "web" / "dist"

    if _DIST.exists():
        app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": f"API endpoint '/{full_path}' not found"})
            # SECURITY: resolve + containment check — blocks ../ traversal out of _DIST.
            file_path = (_DIST / full_path).resolve()
            if file_path.is_file() and file_path.is_relative_to(_DIST.resolve()):
                return FileResponse(file_path)
            index_path = _DIST / "index.html"
            if index_path.is_file():
                return FileResponse(index_path)
            return JSONResponse(status_code=404, content={"detail": "Not found"})

        logger.info(f"Frontend static files mounted from {_DIST}")
    else:
        logger.info("Frontend 'dist' not found. Microservice running in pure API mode.")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    host = settings.HOST
    port = settings.PORT

    use_https = settings.SSL_CERT_PATH.exists() and settings.SSL_KEY_PATH.exists()
    protocol = "https" if use_https else "http"

    print(f"\n[*] Launching {settings.SERVICE_NAME} v{settings.SERVICE_VERSION} ({protocol.upper()}) on {host}:{port}")

    if use_https:
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            reload=False,
            ssl_keyfile=str(settings.SSL_KEY_PATH),
            ssl_certfile=str(settings.SSL_CERT_PATH),
            log_level="info",
        )
    else:
        uvicorn.run("main:app", host=host, port=port, reload=False, log_level="info")
