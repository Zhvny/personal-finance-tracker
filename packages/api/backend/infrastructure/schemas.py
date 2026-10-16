import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

from packages.core.infrastructure.config import Config
from packages.core.infrastructure.persistence.database import Database

logger = logging.getLogger("backend.infrastructure.schemas")

# Number of expected tables per profile schema (kept in sync with migration 015
# and packages/core/infrastructure/persistence/per_profile_ddl.py).
EXPECTED_TABLES_PER_PROFILE = 23


class SchemaInitializer:
    """
    Backward-compat entry point. After refactor (R1 schema-fix), this class is
    READ-ONLY at startup — it only verifies that expected schemas/tables exist.
    DDL is now driven by:
      - migrations/015_per_profile_schema.sql (default profiles, run via migrations/runner.py)
      - SchemaInitializer.provision_profile_schema(name) (custom profiles, called
        explicitly from ProfileService.add_profile)

    All legacy SQLite DDL helpers (`_expenses`, `_incomes`, etc.) are preserved
    as private methods for backward compat, but ensure_all() no longer invokes
    them — they would silently write to wrong DBs in Postgres-only deployments.
    """

    def __init__(self, db_resolver):
        self.db_resolver = db_resolver

    def _resolve_and_log_db(self, module: str, filename: str) -> str:
        db_path = self.db_resolver(module, filename)
        logger.debug(f"Resolved DB path: {filename} at {db_path}")
        return db_path

    def ensure_all(self):
        """
        Read-only schema verification. Logs warnings for missing tables but
        does NOT raise — app stays up so /health/ready can return a useful
        payload. To fail-fast on missing schemas, use SchemaVerifier instead.
        """
        try:
            active = Config.get_active_profile()
            if not active or active.startswith("qa_"):
                return

            count = self._count_tables_in_profile_schema(active)
            expected = EXPECTED_TABLES_PER_PROFILE
            if count < expected:
                logger.warning(
                    f"Schema '{active}' has {count}/{expected} tables. "
                    f"Run `python migrations/runner.py apply` to provision missing tables, "
                    f"or restart after SchemaInitializer.provision_profile_schema('{active}') is called."
                )
            else:
                logger.info(f"Schema '{active}' verified: {count}/{expected} tables present.")
        except Exception as e:
            logger.warning(f"Schema verification skipped due to error: {e}")

    def _count_tables_in_profile_schema(self, profile: str) -> int:
        """Query Postgres for the table count in a given profile schema."""
        from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
        rows = DatabaseManager.query(
            "SELECT COUNT(*) AS table_count FROM information_schema.tables WHERE table_schema = %s",
            (profile,),
        )
        return int(rows[0]["table_count"]) if rows else 0

    def provision_profile_schema(self, profile_name: str) -> None:
        """
        Atomically create a profile's schema + all 23 tables + indexes + default
        rows. All-or-nothing: if any DDL fails, the whole transaction rolls back
        and no partial schema is left behind.

        Called by ProfileService.add_profile() for custom profiles. Idempotent:
        re-running is safe (CREATE TABLE IF NOT EXISTS).

        Raises:
            ValueError: if profile_name fails the strict regex.
            RuntimeError: if any DDL fails (after rollback).
        """
        if not re.match(r"^[a-zA-Z0-9_]+$", profile_name):
            raise ValueError(f"Security error: Invalid profile identifier: {profile_name}")

        from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
        from packages.core.infrastructure.persistence.per_profile_ddl import (
            build_all_ddl_for_profile,
        )

        logger.info(f"Provisioning PostgreSQL profile schema: {profile_name}")

        DatabaseManager.execute("BEGIN")
        try:
            for ddl in build_all_ddl_for_profile(profile_name):
                DatabaseManager.execute(ddl)
            DatabaseManager.execute("COMMIT")
            logger.info(f"Schema '{profile_name}' provisioned: {EXPECTED_TABLES_PER_PROFILE} tables + indexes + seed rows.")
        except Exception as e:
            try:
                DatabaseManager.execute("ROLLBACK")
            except Exception as rb_err:
                logger.error(f"ROLLBACK also failed for {profile_name}: {rb_err}")
            logger.error(f"Failed to provision schema {profile_name}: {e}", exc_info=True)
            raise RuntimeError(f"Schema provisioning for '{profile_name}' failed: {e}") from e

    # ── Backward-compat alias ─────────────────────────────────────────────────
    def _ensure_postgres_profile_schema(self, target_profiles: Optional[list[str]] = None):
        """
        DEPRECATED: prefer SchemaInitializer.provision_profile_schema(name) or
        SchemaVerifier.verify_all(). Kept as alias for callers (e.g. test_migration_system)
        that still invoke this private name.
        """
        import warnings
        warnings.warn(
            "_ensure_postgres_profile_schema is deprecated; use provision_profile_schema() or run migrations/015_per_profile_schema.sql",
            DeprecationWarning,
            stacklevel=2,
        )

        # For backward-compat with the old list-style signature, provision each requested profile.
        profiles_to_ensure = set()
        active = Config.get_active_profile()
        if active and not active.startswith("qa_"):
            profiles_to_ensure.add(active)
        profiles_to_ensure.update(["personal", "business"])
        if target_profiles:
            profiles_to_ensure.update([p for p in target_profiles if not p.startswith("qa_")])

        for profile in profiles_to_ensure:
            try:
                self.provision_profile_schema(profile)
            except Exception as e:
                logger.error(f"Failed to ensure PostgreSQL profile schema: {e}", exc_info=True)

    # ── Legacy SQLite DDL helpers (preserved but not called by ensure_all) ───
    # These helpers are test-only. Production code must use Postgres
    # (provision_profile_schema / migrations). See _guard_legacy_sqlite.
    def _guard_legacy_sqlite(self, helper: str) -> None:
        """Fail closed if a legacy SQLite helper runs outside tests.

        Bypass only for an explicit one-off via ALLOW_LEGACY_SQLITE=1 (logged).
        """
        if os.environ.get("ALLOW_LEGACY_SQLITE") == "1":
            logger.warning("Legacy SQLite helper %s running with explicit ALLOW_LEGACY_SQLITE=1 bypass", helper)
            return
        if "pytest" in sys.modules:
            return
        raise RuntimeError(
            f"Legacy SQLite helper {helper} is test-only; refusing to touch SQLite outside tests. "
            "Set ALLOW_LEGACY_SQLITE=1 for an explicit one-off."
        )

    def _expenses(self):
        self._guard_legacy_sqlite("_expenses")
        db = self._resolve_and_log_db("expense_tracker", "expense.db")
        Database.execute(db, """CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL, description TEXT NOT NULL,
            category TEXT NOT NULL, payment_method TEXT NOT NULL,
            date TEXT NOT NULL, is_recurring INTEGER DEFAULT 0,
            recurring_period TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        Database.execute(db, """CREATE TABLE IF NOT EXISTS recurrence_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL, description TEXT,
            category TEXT, interval_days INTEGER, confidence REAL,
            last_seen TEXT, status TEXT DEFAULT 'pending')""")

    def _incomes(self):
        self._guard_legacy_sqlite("_incomes")
        db = self._resolve_and_log_db("income_tracker", "income.db")
        Database.execute(db, """CREATE TABLE IF NOT EXISTS incomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL, source TEXT NOT NULL,
            income_type TEXT NOT NULL, date TEXT NOT NULL,
            description TEXT, is_taxed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    def _investments(self):
        self._guard_legacy_sqlite("_investments")
        db = self._resolve_and_log_db("investment_tracker", "portfolio.db")
        Database.execute(db, """CREATE TABLE IF NOT EXISTS investments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_type TEXT NOT NULL, ticker TEXT NOT NULL,
            quantity REAL NOT NULL, buy_price REAL NOT NULL,
            buy_currency TEXT NOT NULL, buy_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'holding',
            remaining_quantity REAL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        Database.execute(db, """CREATE TABLE IF NOT EXISTS sell_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, investment_id INTEGER NOT NULL,
            sell_date TEXT NOT NULL, quantity REAL NOT NULL, sell_price REAL NOT NULL,
            sell_currency TEXT NOT NULL, fees REAL NOT NULL DEFAULT 0,
            fx_rate REAL NOT NULL DEFAULT 1,
            realized_pl_idr REAL NOT NULL, realized_pl_pct REAL NOT NULL,
            FOREIGN KEY (investment_id) REFERENCES investments(id))""")

    def _fx_rates(self):
        self._guard_legacy_sqlite("_fx_rates")
        db = self._resolve_and_log_db("investment_tracker", "portfolio.db")
        Database.execute(db, """CREATE TABLE IF NOT EXISTS fx_rates (
            pair TEXT NOT NULL,
            rate_date TEXT NOT NULL,
            rate REAL NOT NULL,
            PRIMARY KEY (pair, rate_date))""")

    def _goals(self):
        self._guard_legacy_sqlite("_goals")
        db = self._resolve_and_log_db("advanced_features", "goals.db")
        Database.execute(db, """CREATE TABLE IF NOT EXISTS goals (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT    NOT NULL,
            target_amount  REAL    NOT NULL,
            current_amount REAL    NOT NULL DEFAULT 0,
            target_date    TEXT,
            created_at     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")

    def _budgets(self):
        self._guard_legacy_sqlite("_budgets")
        db = self._resolve_and_log_db("advanced_features", "budget.db")
        Database.execute(db, """CREATE TABLE IF NOT EXISTS budgets (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            year      INTEGER NOT NULL,
            month     INTEGER NOT NULL,
            category  TEXT    NOT NULL DEFAULT 'total',
            limit_amt REAL    NOT NULL,
            UNIQUE(year, month, category)
        )""")

    def _rewards(self):
        self._guard_legacy_sqlite("_rewards")
        db = self._resolve_and_log_db("advanced_features", "goals.db")
        Database.execute(db, """CREATE TABLE IF NOT EXISTS reward_state (
            id         INTEGER PRIMARY KEY CHECK (id = 1),
            state_json TEXT    NOT NULL,
            updated_at TEXT    NOT NULL
        )""")

    def _balances(self):
        self._guard_legacy_sqlite("_balances")
        db = self._resolve_and_log_db("advanced_features", "goals.db")
        Database.execute(db, """CREATE TABLE IF NOT EXISTS manual_balances (
            key   TEXT PRIMARY KEY,
            value REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )""")
        Database.execute(db, """CREATE TABLE IF NOT EXISTS cash_split (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            physical_cash  REAL NOT NULL DEFAULT 0,
            bank_savings   REAL NOT NULL DEFAULT 0,
            updated_at  TEXT NOT NULL
        )""")
        Database.execute(db, """CREATE TABLE IF NOT EXISTS transfer_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            direction  TEXT NOT NULL,
            amount     REAL NOT NULL,
            note       TEXT,
            created_at TEXT NOT NULL
        )""")

    def _security(self):
        self._guard_legacy_sqlite("_security")
        db = str(Config.BASE_DIR / "data" / "audit_log.db")
        Path(db).parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initializing security database at {db}")
        Database.execute(db, """CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    NOT NULL,
            ip          TEXT    NOT NULL,
            method      TEXT    NOT NULL,
            path        TEXT    NOT NULL,
            scope       TEXT,
            status_code INTEGER,
            latency_ms  REAL,
            user_agent  TEXT,
            detail      TEXT
        )""")
        Database.execute(db, "CREATE INDEX IF NOT EXISTS idx_al_ts   ON audit_log(ts)")
        Database.execute(db, "CREATE INDEX IF NOT EXISTS idx_al_ip   ON audit_log(ip)")
        Database.execute(db, "CREATE INDEX IF NOT EXISTS idx_al_path ON audit_log(path)")

    def _behavioral(self):
        self._guard_legacy_sqlite("_behavioral")
        db = self._resolve_and_log_db("behavioral_finance", "behavioral.db")
        Database.execute(db, """CREATE TABLE IF NOT EXISTS behavioral_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT,
            data_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    def _validate_postgres(self):
        """Read-only sanity check. Kept for backward compat with test_migration_system."""
        critical_tables = [
            "expenses", "incomes", "investments", "fx_rates", "goals",
            "manual_balances", "cash_split", "reward_state"
        ]
        from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
        for table in critical_tables:
            try:
                res = DatabaseManager.query(
                    "SELECT 1 FROM information_schema.tables WHERE table_name = %s LIMIT 1",
                    (table,)
                )
                if not res:
                    logger.warning(f"DATABASE PARITY ALERT: Table '{table}' missing in PostgreSQL.")
            except Exception as e:
                logger.error(f"Postgres validation query for '{table}' failed: {e}")


class SchemaVerifier:
    """
    Explicit fail-fast schema verification for production lifespan.
    Use this when you want the app to refuse to start unless schemas are healthy.

    Returns a dict summary on success; raises RuntimeError on failure.
    """

    def __init__(self, db_resolver=None):
        # db_resolver kept for API symmetry with SchemaInitializer but unused.
        self.db_resolver = db_resolver

    def verify_all(self, expected: int = EXPECTED_TABLES_PER_PROFILE) -> dict:
        """
        Verify active profile schema is healthy. Raises RuntimeError if not.
        Returns: {"status": "ok", "profile": str, "table_count": int, "expected": int}
        """
        from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager

        active = Config.get_active_profile()
        if not active or active.startswith("qa_"):
            return {"status": "ok", "profile": active, "table_count": 0, "expected": 0,
                    "note": "QA profile; schema check skipped"}

        rows = DatabaseManager.query(
            "SELECT COUNT(*) AS table_count FROM information_schema.tables WHERE table_schema = %s",
            (active,),
        )
        # DatabaseManager.query uses RealDictCursor → rows are dicts.
        count = int(rows[0]["table_count"]) if rows else 0
        if count < expected:
            raise RuntimeError(
                f"Schema '{active}' is incomplete: {count}/{expected} tables. "
                f"Run `python migrations/runner.py apply` to provision missing tables."
            )
        return {
            "status": "ok",
            "profile": active,
            "table_count": count,
            "expected": expected,
        }
