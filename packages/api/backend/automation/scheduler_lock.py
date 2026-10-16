"""Single-owner contract for the market scheduler (TD-1).

Session-level Postgres advisory lock keyed by LOCK_KEY: whichever process
acquires it owns scheduling; process death auto-releases. Both start paths
(apps/api/main.py legacy + services/runtime/bootstrap.py) must call
try_acquire() before starting MarketScheduler. Fail-closed: if the database
is unreachable, the scheduler does NOT start.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

LOCK_KEY = "alpha-market-scheduler"


def _dsn() -> str:
    # Prisma-style URLs carry ?schema=public which libpq rejects; strip it.
    return os.getenv("DATABASE_URL", "").split("?", 1)[0]


class SchedulerOwnershipLock:
    def __init__(self, key: str = LOCK_KEY):
        self.key = key
        self._conn = None

    def try_acquire(self) -> bool:
        if self._conn is not None:
            return True
        try:
            import psycopg2

            conn = psycopg2.connect(_dsn(), connect_timeout=5)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(hashtext(%s))", (self.key,))
                acquired = cur.fetchone()[0]
            if acquired:
                self._conn = conn
                logger.info("Scheduler ownership lock acquired (%s).", self.key)
                return True
            conn.close()
            logger.warning(
                "Another scheduler instance already owns the lock (%s) - not starting.", self.key
            )
            return False
        except Exception as error:
            logger.error(
                "Could not acquire scheduler ownership lock (fail-closed): %s", error
            )
            return False

    def release(self) -> None:
        if self._conn is None:
            return
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(hashtext(%s))", (self.key,))
        except Exception as error:
            logger.warning("Error releasing scheduler lock: %s", error)
        finally:
            try:
                self._conn.close()
            finally:
                self._conn = None


scheduler_ownership = SchedulerOwnershipLock()
