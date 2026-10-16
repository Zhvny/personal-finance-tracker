import logging
import threading
from contextlib import contextmanager
from typing import Any, Dict, List

from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from ..config import Config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages PostgreSQL connection pooling for the Finance Tracker ecosystem.
    Supports multi-agent concurrency and real-time synchronization.
    """

    _pool = None
    _lock = threading.Lock()

    @classmethod
    def initialize(cls):
        """Initialize the connection pool once, thread-safely."""
        if cls._pool is None:
            with cls._lock:
                if cls._pool is None:
                    try:
                        cls._pool = pool.ThreadedConnectionPool(
                            minconn=5,
                            maxconn=100,
                            dbname=Config.POSTGRES_DB,
                            user=Config.POSTGRES_USER,
                            password=Config.POSTGRES_PASSWORD,
                            host=Config.POSTGRES_HOST,
                            port=Config.POSTGRES_PORT,
                        )
                        logger.info(
                            f"PostgreSQL Pool initialized (host={Config.POSTGRES_HOST}, db={Config.POSTGRES_DB})"
                        )
                    except Exception as e:
                        logger.error(f"Failed to initialize PostgreSQL pool: {e}")
                        raise

    @classmethod
    @contextmanager
    def get_connection(cls, schema: str = None):
        """
        Context manager to get and release a connection from the pool.
        :param schema: Optional Postgres schema to set for this connection.
        """
        if cls._pool is None:
            cls.initialize()

        # Capture the pool reference to ensure we return the connection to the SAME pool
        # even if cls._pool were to be reassigned (though the lock prevents it now).
        active_pool = cls._pool
        conn = active_pool.getconn()
        try:
            # Always set search_path to include project schemas
            import re
            raw_profile = Config.get_active_profile()
            active_profile = raw_profile if (raw_profile and re.match(r"^[a-zA-Z0-9_]+$", raw_profile)) else "personal"
            target_schemas = [active_profile, "financials", "core", "investment", "market", "audit", "system", "public"]
            if schema:
                if schema in target_schemas:
                    target_schemas.remove(schema)
                target_schemas = [schema] + target_schemas

            search_path = ",".join(target_schemas)
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {search_path}")
            yield conn
        finally:
            active_pool.putconn(conn)

    @staticmethod
    def query(sql: str, params: tuple = (), schema: str = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return rows as dictionaries."""
        try:
            with DatabaseManager.get_connection(schema=schema) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, params)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"PostgreSQL query error: {e}")
            raise

    @staticmethod
    def execute(sql: str, params: tuple = (), schema: str = None) -> Any:
        """
        Execute an INSERT, UPDATE, or DELETE query.
        Returns the ID of the affected row for INSERTs (if RETURNING used), or rowcount.
        """
        try:
            with DatabaseManager.get_connection(schema=schema) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    # Note: commit is handled by the connection,
                    # but the context manager doesn't commit automatically.
                    # We must commit manually if not in a transaction.
                    conn.commit()

                    sql_upper = sql.lstrip().upper()
                    if "RETURNING" in sql_upper:
                        row = cur.fetchone()
                        return row[0] if row else None
                    return cur.rowcount
        except Exception as e:
            # Rollback to prevent leaving the connection in an aborted state
            # Since get_connection yields the connection, we can catch and rollback
            if 'conn' in locals() and conn:
                try:
                    conn.rollback()
                except Exception as rollback_err:
                    logger.error(f"Failed to rollback connection: {rollback_err}")
            logger.error(f"PostgreSQL execution error: {e}")
            raise

    @classmethod
    @contextmanager
    def transaction(cls, schema: str = None):
        """Context manager for multi-statement atomic transactions."""
        if cls._pool is None:
            cls.initialize()

        active_pool = cls._pool
        conn = active_pool.getconn()
        try:
            import re
            raw_profile = Config.get_active_profile()
            active_profile = raw_profile if (raw_profile and re.match(r"^[a-zA-Z0-9_]+$", raw_profile)) else "personal"
            target_schemas = [active_profile, "financials", "core", "investment", "market", "audit", "system", "public"]
            if schema:
                if schema in target_schemas:
                    target_schemas.remove(schema)
                target_schemas = [schema] + target_schemas

            search_path = ",".join(target_schemas)
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {search_path}")

            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"PostgreSQL transaction failed, rolling back: {e}")
            raise
        finally:
            active_pool.putconn(conn)

# Alias for backward compatibility if needed, or migration bridge
class PostgresDatabase(DatabaseManager):
    pass
