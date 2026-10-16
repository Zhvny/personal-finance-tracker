"""
backend/routers/deps/db_paths.py — DB path resolvers + schema init
==================================================================
Bridge to the legacy per-feature SQLite database layout. New code should
prefer the Postgres repositories in services.py.

Extracted from deps.py (M3 refactor, 2026-09-05). The 5 inline CREATE TABLE
statements in _goals_db are kept as-is — schema migration is out of scope
for this refactor (see HONEY_DEBT entry: goals_db schema inline DDL).
"""
from pathlib import Path

from packages.core.infrastructure.config import Config

from packages.api.backend.routers.deps.legacy_bridge import _execute

# Re-export the path constants used by the older routers.
ROOT = Config.get_cli_data_root()
_GUI = Config.BASE_DIR / "packages" / "api"
BALANCES_DB_PATH = Path(Config.get_db_path("goals"))


def _balances_db() -> str:
    return _goals_db()


def _goals_db() -> str:
    db = Config.get_db_path("goals")
    # Goals table
    _execute(db, """CREATE TABLE IF NOT EXISTS goals (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        name           TEXT    NOT NULL,
        target_amount  REAL    NOT NULL,
        current_amount REAL    NOT NULL DEFAULT 0,
        target_date    TEXT,
        created_at     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    # Balances tables (shared in goals.db)
    _execute(db, """CREATE TABLE IF NOT EXISTS manual_balances (
        key   TEXT PRIMARY KEY,
        value REAL NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL
    )""")
    _execute(db, """CREATE TABLE IF NOT EXISTS cash_split (
        id          INTEGER PRIMARY KEY CHECK (id = 1),
        physical_cash  REAL NOT NULL DEFAULT 0,
        bank_savings   REAL NOT NULL DEFAULT 0,
        updated_at  TEXT NOT NULL
    )""")
    _execute(db, """CREATE TABLE IF NOT EXISTS transfer_log (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        direction  TEXT NOT NULL,
        amount     REAL NOT NULL,
        note       TEXT,
        created_at TEXT NOT NULL
    )""")
    # Reward state (Legacy fallback)
    _execute(db, """CREATE TABLE IF NOT EXISTS reward_state (
        id          INTEGER PRIMARY KEY CHECK (id = 1),
        state_json  TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    )""")
    return db


def _budget_db() -> str:
    db = Config.get_db_path("budget")
    _execute(db, """CREATE TABLE IF NOT EXISTS budgets (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        year      INTEGER NOT NULL,
        month     INTEGER NOT NULL,
        category  TEXT    NOT NULL DEFAULT 'total',
        limit_amt REAL    NOT NULL,
        UNIQUE(year, month, category)
    )""")
    return db


def _behavioral_db() -> str:
    return Config.get_db_path("behavioral")


def _init_behavioral_db(db_path: str) -> None:
    """Ensure behavioral data tables exist in the CLI database."""
    # This remains in SQLite for now as it's localized snapshots
    from packages.core.infrastructure.persistence.database import Database
    Database.execute(db_path, """
        CREATE TABLE IF NOT EXISTS behavioral_snapshots (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            year       INTEGER NOT NULL,
            month      INTEGER NOT NULL,
            payload    TEXT NOT NULL,
            UNIQUE(year, month)
        )
    """)
    Database.execute(db_path, "CREATE INDEX IF NOT EXISTS idx_bsnap_ym ON behavioral_snapshots(year, month)")


def _rewards_db() -> str:
    # Reward state is in Postgres financials.reward_state, but for legacy calls
    # that expect a path, we return goals path.
    return _goals_db()
