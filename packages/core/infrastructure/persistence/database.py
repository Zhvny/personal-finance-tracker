import datetime as _dt
import fnmatch
import logging
import os
import sqlite3
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

# Import shared DatabaseManager for Postgres redirection
try:
    from ..config import Config
    from .postgres_manager import DatabaseManager
except ImportError:
    # Fallback for direct execution or mixed environments
    from packages.core.infrastructure.config import Config
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager

logger = logging.getLogger("core.infrastructure.persistence.database")


class CanonicalPersistenceUnavailableError(RuntimeError):
    """Raised when a canonical PostgreSQL persistence operation cannot complete.

    Callers must surface this as an infrastructure failure; silently writing the
    same financial record to a legacy SQLite file creates split-brain data.
    """


class Database:
    """
    Bridge utility for SQLite operations with transparent Postgres redirection.
    Used by core services and legacy trackers.
    """

    SCHEMA_DEFAULTS = {
        "cash_split": [{"physical_cash": 0.0, "bank_savings": 0.0}],
        "manual_balances": [],
        "reward_state": [{"state_json": "{}"}],
        "goals": [],
        "budgets": [],
        "investments": [],
        "expenses": [],
        "incomes": [],
        "transactions": [],
        "recurrence_candidates": [],
    }

    # Local-only SQLite allowlist (by filename). Anything else must go through
    # canonical Postgres; refusing a silent SQLite fallback avoids split-brain data.
    _LOCAL_SQLITE_FILES = ("behavioral.db", "merchant_memory.db")
    _LOCAL_SQLITE_GLOB = "*.cache.db"

    @staticmethod
    def _enforce_no_sqlite_hatch_in_production() -> None:
        # Fail fast if the test-isolation hatch leaks into production. Repo-wide
        # env convention is ENVIRONMENT with APP_ENV fallback (apps/api/config.py
        # defines no ENVIRONMENT of its own).
        env = (os.environ.get("ENVIRONMENT") or os.environ.get("APP_ENV") or "").lower()
        if env == "production" and os.environ.get("ALPHA_FORCE_SQLITE"):
            raise RuntimeError("ALPHA_FORCE_SQLITE must not be set in production")

    @staticmethod
    def _is_local_sqlite_allowed(db_path: str) -> bool:
        name = os.path.basename(str(db_path)).lower()
        return name in Database._LOCAL_SQLITE_FILES or fnmatch.fnmatch(name, Database._LOCAL_SQLITE_GLOB)

    @staticmethod
    def _require_explicit_sqlite_target(db_path: str) -> None:
        # Under the test-isolation hatch each process owns disposable SQLite files
        # of any name, so the allowlist yields to it there.
        if os.environ.get("ALPHA_FORCE_SQLITE") == "1":
            return
        if not Database._is_local_sqlite_allowed(db_path):
            raise CanonicalPersistenceUnavailableError(
                f"Unknown persistence target {db_path!r}; refusing silent SQLite fallback"
            )

    @staticmethod
    def _is_postgres_target(db_path: str) -> bool:
        """Check if the database path corresponds to a migrated Postgres target."""
        # Test isolation escape hatch: when ALPHA_FORCE_SQLITE=1, never redirect to
        # Postgres. Each process then reads/writes its own SQLite files under
        # FINANCE_DATA_ROOT, giving automation flows a fully isolated, disposable
        # database instead of the shared live Postgres schema.
        Database._enforce_no_sqlite_hatch_in_production()
        if os.environ.get("ALPHA_FORCE_SQLITE") == "1":
            return False
        path_str = str(db_path).lower()
        targets = [
            "expense.db",
            "income.db",
            "portfolio.db",
            "market.db",
            "goals.db",
            "budget.db",
            "finance.db",
            "chat.db",
        ]
        return any(t in path_str for t in targets)

    @staticmethod
    def _get_schema(db_path: str) -> Optional[str]:
        """Maps a file path to its corresponding PostgreSQL schema."""
        path_str = str(db_path).lower()

        if Config:
            profile = Config.get_active_profile()
            profile_targets = ["expense.db", "income.db", "portfolio.db", "goals.db", "budget.db", "finance.db"]
            if any(t in path_str for t in profile_targets):
                return profile

        if "investment" in path_str or "portfolio" in path_str:
            return "investment"
        if "expense" in path_str or "income" in path_str:
            return "financials"
        if "market" in path_str:
            return "market"
        if "audit" in path_str:
            return "audit"
        if "goals" in path_str or "budget" in path_str:
            return "core"
        if "chat" in path_str:
            return "public"
        return None

    @staticmethod
    def _translate_sql(sql: str) -> str:
        """Simple translation from SQLite to PostgreSQL dialect."""
        sql = sql.replace("?", "%s")
        if "strftime" in sql:
            sql = sql.replace("strftime('%Y-%m', date)", "to_char(date, 'YYYY-MM')")
            sql = sql.replace("strftime('%Y-%m-%d', date)", "to_char(date, 'YYYY-MM-DD')")
        if "price_snapshots" in sql:
            sql = (
                sql.replace("price_snapshots", "historical_prices")
                .replace(" date ", " snapshot_date ")
                .replace("(date", "(snapshot_date")
                .replace(", date", ", snapshot_date")
            )
        return sql

    @staticmethod
    def _cast_decimals(data: Any) -> Any:
        """Recursively cast non-JSON-native types returned by PostgreSQL.

        - decimal.Decimal  -> float   (psycopg2 returns Decimal for NUMERIC)
        - datetime.datetime -> str    (ISO 8601, e.g. '2026-08-11T06:07:51')
        - datetime.date     -> str    (ISO 8601, e.g. '2026-08-11')
        - datetime.time     -> str    (e.g. '06:07:51')
        """
        if isinstance(data, list):
            return [Database._cast_decimals(i) for i in data]
        if isinstance(data, dict):
            return {k: Database._cast_decimals(v) for k, v in data.items()}
        if isinstance(data, Decimal):
            return float(data)
        if isinstance(data, _dt.datetime):
            return data.isoformat()
        if isinstance(data, _dt.date):
            return data.isoformat()
        if isinstance(data, _dt.time):
            return str(data)
        return data

    @staticmethod
    def _get_fallback_for_sql(sql: str) -> List[Dict[str, Any]]:
        """Determine if a query should return default data on failure."""
        sql_upper = sql.upper()
        for table, default in Database.SCHEMA_DEFAULTS.items():
            table_upper = table.upper()
            if f"FROM {table_upper}" in sql_upper or f"INTO {table_upper}" in sql_upper:
                if "SUM(" in sql_upper or "COUNT(" in sql_upper:
                    return [{"t": 0, "n": 0, "value": 0, "amount": 0}]
                return default
        return []

    @staticmethod
    def query(db_path: str, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        if Database._is_postgres_target(db_path):
            if not DatabaseManager:
                raise CanonicalPersistenceUnavailableError(
                    "Canonical PostgreSQL driver is unavailable; legacy SQLite fallback is disabled"
                )
            try:
                translated_sql = Database._translate_sql(sql)
                schema = Database._get_schema(db_path)
                rows = DatabaseManager.query(translated_sql, params, schema=schema)
                return Database._cast_decimals(rows)
            except Exception as e:
                logger.error(f"Postgres query error for {db_path}: {e}")
                raise CanonicalPersistenceUnavailableError(
                    "Canonical PostgreSQL read failed; legacy SQLite fallback is disabled"
                ) from e

        Database._require_explicit_sqlite_target(db_path)
        if not os.path.exists(db_path):
            return Database._get_fallback_for_sql(sql)
        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                return [dict(r) for r in conn.execute(sql, params).fetchall()]
        except Exception as e:
            logger.error(f"SQLite query error for {db_path}: {e}")
            return Database._get_fallback_for_sql(sql)

    @staticmethod
    def execute(db_path: str, sql: str, params: tuple = ()) -> Union[int, None]:
        if Database._is_postgres_target(db_path):
            if not DatabaseManager:
                raise CanonicalPersistenceUnavailableError(
                    "Canonical PostgreSQL driver is unavailable; legacy SQLite fallback is disabled"
                )
            sql_upper = sql.lstrip().upper()
            if (
                sql_upper.startswith("CREATE TABLE")
                or sql_upper.startswith("CREATE INDEX")
                or sql_upper.startswith("ALTER TABLE")
            ):
                return 1

            try:
                translated_sql = Database._translate_sql(sql)
                schema = Database._get_schema(db_path)
                return DatabaseManager.execute(translated_sql, params, schema=schema)
            except Exception as e:
                logger.error(f"Postgres execution error for {db_path}: {e}")
                raise CanonicalPersistenceUnavailableError(
                    "Canonical PostgreSQL write failed; legacy SQLite fallback is disabled"
                ) from e

        Database._require_explicit_sqlite_target(db_path)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute(sql, params)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"SQLite execution error for {db_path}: {e}")
            raise

    @staticmethod
    def execute_script(db_path: str, script: str):
        if Database._is_postgres_target(db_path):
            if not DatabaseManager:
                raise CanonicalPersistenceUnavailableError(
                    "Canonical PostgreSQL driver is unavailable; legacy SQLite fallback is disabled"
                )
            return 1

        Database._require_explicit_sqlite_target(db_path)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        try:
            with sqlite3.connect(db_path) as conn:
                conn.executescript(script)
                conn.commit()
        except Exception as e:
            logger.error(f"SQLite script error for {db_path}: {e}")
            raise
