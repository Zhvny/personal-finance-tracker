import concurrent.futures
import logging
import os
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from packages.core.application.market_data_service import MarketDataService
from packages.core.infrastructure.config import Config
from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
from packages.core.infrastructure.persistence.postgres_market_data_repository import PostgresMarketDataRepository
from packages.core.infrastructure.persistence.postgres_ohlcv_repository import PostgresOHLCVRepository

# Setup logging
logger = logging.getLogger("automation.market_scheduler")

class MarketScheduler:
    def __init__(self):
        self.repo = PostgresMarketDataRepository()
        self.ohlcv_repo = PostgresOHLCVRepository()
        self.market_service = MarketDataService(self.repo, self.ohlcv_repo)
        self.scheduler = BackgroundScheduler()
        self.watchlist_path = str(Config.BASE_DIR / "apps" / "cli" / "stock_analyzer" / "list.txt")
        self._job_state = {
            "market_update_incremental": {"last_run": None, "last_status": "pending", "last_duration_s": 0.0, "error_count": 0, "consecutive_failures": 0},
            "market_update_initial": {"last_run": None, "last_status": "pending", "last_duration_s": 0.0, "error_count": 0, "consecutive_failures": 0},
            "market_update_daily_full": {"last_run": None, "last_status": "pending", "last_duration_s": 0.0, "error_count": 0, "consecutive_failures": 0},
            "daily_financial_report": {"last_run": None, "last_status": "pending", "last_duration_s": 0.0, "error_count": 0, "consecutive_failures": 0}
        }

    def _update_job_state(self, job_name: str, duration: float, error: Exception = None):
        if job_name not in self._job_state:
            self._job_state[job_name] = {"last_run": None, "last_status": "pending", "last_duration_s": 0.0, "error_count": 0, "consecutive_failures": 0}
        state = self._job_state[job_name]
        state["last_run"] = datetime.now().isoformat()
        state["last_duration_s"] = duration
        if error:
            state["last_status"] = f"error: {error}"
            state["error_count"] += 1
            state["consecutive_failures"] += 1
        else:
            state["last_status"] = "ok"
            state["consecutive_failures"] = 0

    def _run_with_timeout(self, fn, timeout_seconds: int, job_name: str, *args, **kwargs):
        start_time = time.time()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(fn, *args, **kwargs)
                future.result(timeout=timeout_seconds)
            duration = time.time() - start_time
            self._update_job_state(job_name, duration)
        except concurrent.futures.TimeoutError as e:
            duration = time.time() - start_time
            logger.error(f"Job {job_name} timed out after {timeout_seconds} seconds")
            self._update_job_state(job_name, duration, e)
            raise e
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Job {job_name} failed: {e}")
            self._update_job_state(job_name, duration, e)
            raise e

    def _update_job_logic(self, period: str = "5d", mode: str = "full"):
        self._renew_lease()
        self.market_service.update_all_tickers(self.watchlist_path)

    def _update_job(self, job_name: str = "market_update_incremental"):
        self._run_with_timeout(self._update_job_logic, 300, job_name)

    def _daily_report_job_logic(self):
        self._renew_lease()
        logger.info("Running scheduled daily financial report...")
        import asyncio

        from packages.api.telegram_handler import get_active_profile, get_daily_report_text
        from packages.core.utils.telegram_notifier import send_telegram_notification

        profile_id = get_active_profile()

        # BackgroundScheduler jobs run in plain daemon threads — there is never
        # a running event loop in this context, so asyncio.run() is always safe.
        report_text = asyncio.run(get_daily_report_text(profile_id))
        send_telegram_notification(report_text)
        logger.info("Scheduled daily financial report sent to Telegram.")

    def _daily_report_job(self, job_name: str = "daily_financial_report"):
        self._run_with_timeout(self._daily_report_job_logic, 300, job_name)

    def get_health(self) -> dict:
        return self._job_state

    # ── Lease anti dual-run ────────────────────────────────────────────────
    # Kontrak: HANYA SATU instance MarketScheduler boleh hidup per database,
    # siapa pun entry point-nya (monolit apps/api ATAU services/runtime).
    # Kepemilikan dipegang via lease baris `system.scheduler_lease` yang
    # diperpanjang tiap job; mati >30 menit tanpa renewal = lease lepas.
    _LEASE_NAME = "market_scheduler"
    _LEASE_TTL = timedelta(minutes=30)

    def _acquire_lease(self) -> bool:
        self._lease_owner = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        try:
            DatabaseManager.execute(
                "CREATE TABLE IF NOT EXISTS system.scheduler_lease ("
                " name TEXT PRIMARY KEY, owner TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL)",
                schema="system",
            )
            row = DatabaseManager.query(
                "INSERT INTO system.scheduler_lease (name, owner, expires_at)"
                " VALUES (%s, %s, %s)"
                " ON CONFLICT (name) DO UPDATE SET owner = EXCLUDED.owner, expires_at = EXCLUDED.expires_at"
                " WHERE scheduler_lease.expires_at < NOW() OR scheduler_lease.owner = EXCLUDED.owner"
                " RETURNING owner",
                (self._LEASE_NAME, self._lease_owner, datetime.now(timezone.utc) + self._LEASE_TTL),
            )
            acquired = bool(row) and row[0]["owner"] == self._lease_owner
        except Exception as e:
            logger.error(f"[lease] DB nggak bisa dihubungi ({e}); scheduler tidak dinyalakan (fail-closed).")
            return False
        if not acquired:
            holder = "-"
            try:
                cur = DatabaseManager.query("SELECT owner FROM system.scheduler_lease WHERE name = %s", (self._LEASE_NAME,))
                if cur:
                    holder = cur[0]["owner"]
            except Exception:
                pass
            logger.warning(f"[lease] Dual-run dicegah: lease dipegang oleh {holder}.")
        return acquired

    def _renew_lease(self):
        try:
            DatabaseManager.execute(
                "UPDATE system.scheduler_lease SET expires_at = NOW() + INTERVAL '30 minutes'"
                " WHERE name = %s AND owner = %s",
                (self._LEASE_NAME, self._lease_owner),
                schema="system",
            )
        except Exception:
            pass

    def start(self):
        if not self._acquire_lease():
            return False

        # Schedule the job to run every 5 minutes (incremental sync)
        self.scheduler.add_job(self._update_job, 'interval', minutes=5, id='market_update_incremental', max_instances=1, misfire_grace_time=120, kwargs={"job_name": "market_update_incremental"})

        # Also run once immediately on startup (full sync)
        self.scheduler.add_job(self._update_job, id='market_update_initial', max_instances=1, kwargs={"job_name": "market_update_initial"})

        # Add a daily full refresh (at midnight)
        self.scheduler.add_job(self._update_job, 'cron', hour=0, minute=0, id='market_update_daily_full', max_instances=1, misfire_grace_time=600, kwargs={"job_name": "market_update_daily_full"})

        # Add a daily report sending job (at 08:00 AM every day)
        self.scheduler.add_job(self._daily_report_job, 'cron', hour=8, minute=0, id='daily_financial_report', max_instances=1, misfire_grace_time=600, kwargs={"job_name": "daily_financial_report"})

        self.scheduler.start()
        logger.info("Market Data Scheduler started (Interval: 5 minutes, Daily Report: 08:00 AM)")
        return True

    def shutdown(self):
        self.scheduler.shutdown()
        try:
            DatabaseManager.execute(
                "DELETE FROM system.scheduler_lease WHERE name = %s AND owner = %s",
                (self._LEASE_NAME, getattr(self, "_lease_owner", "")),
                schema="system",
            )
        except Exception:
            pass
        logger.info("Market Data Scheduler shut down")
