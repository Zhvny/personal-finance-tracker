"""
postgres_fx_repository.py
==========================
FX rate repository using direct psycopg2 (via DatabaseManager) instead of Prisma.

This avoids the "event loop is already running" error that occurs when 
synchronous methods (called from FXService) try to use asyncio.run() inside 
an already-running FastAPI async event loop.

The fx_rates table lives in the active profile schema (e.g. qa_financial.fx_rates).
DatabaseManager.get_connection() sets search_path to include the profile schema 
first, so we can use unqualified table names.
"""
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from packages.core.domain.repositories.fx_repository import IFXRepository
from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager

logger = logging.getLogger(__name__)


class PostgresFXRepository(IFXRepository):
    """
    PostgreSQL implementation of the FX Repository using psycopg2 (sync).
    Stores exchange rates in the profile-schema fx_rates table.

    NOTE: This is intentionally synchronous — FXService is called from both
    sync and async contexts. Using psycopg2 directly avoids asyncio event loop
    conflicts when called within a running FastAPI async handler.
    The search_path set by DatabaseManager.get_connection() resolves the
    unqualified 'fx_rates' table to the correct active profile schema.
    """

    def save_rate(self, pair: str, rate_date: date, rate: float) -> None:
        """
        Save an exchange rate for a specific pair and date to PostgreSQL.
        Uses psycopg2 directly (sync) to avoid event-loop conflicts.
        """
        try:
            sql = """
                INSERT INTO fx_rates (pair, rate_date, rate)
                VALUES (%s, %s, %s)
                ON CONFLICT (pair, rate_date) DO UPDATE SET rate = EXCLUDED.rate
            """
            DatabaseManager.execute(sql, (pair, rate_date, rate))
        except Exception as e:
            logger.warning(f"[FXRepo] Failed to save rate {pair} @ {rate_date}: {e}")

    def get_closest_rate(self, pair: str, rate_date: date) -> Optional[float]:
        """
        Retrieve the closest exchange rate for a pair on or before the given date.
        Uses psycopg2 directly (sync) to avoid event-loop conflicts.
        """
        try:
            sql = """
                SELECT rate FROM fx_rates 
                WHERE pair = %s AND rate_date <= %s 
                ORDER BY rate_date DESC LIMIT 1
            """
            rows: List[Dict[str, Any]] = DatabaseManager.query(sql, (pair, rate_date))
            if rows:
                return float(rows[0]["rate"])
        except Exception as e:
            logger.warning(f"[FXRepo] Failed to get rate {pair} @ {rate_date}: {e}")
        return None
