"""
backend/routers/deps.py — Shared dependencies for all routers (Postgres Migration)
==============================================================
This module acts as a bridge between the legacy routers and the new 
Clean Architecture 'packages.core' layer with PostgreSQL backend.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

from packages.core.application.butterfly_service import ButterflyService
from packages.core.application.dashboard_service import DashboardService
from packages.core.application.expense_service import ExpenseService
from packages.core.application.income_service import IncomeService
from packages.core.application.investment_service import InvestmentService
from packages.core.application.market_data_service import MarketDataService
from packages.core.application.reward_service import RewardService
from packages.core.application.whale_analysis_service import WhaleAnalysisService

# ── Import from Core ─────────────────────────────────────────────────────────
from packages.core.infrastructure.config import Config
from packages.core.infrastructure.external.fx_service import FXService
from packages.core.infrastructure.persistence.database import Database
from packages.core.infrastructure.persistence.postgres_expense_repository import PostgresExpenseRepository
from packages.core.infrastructure.persistence.postgres_fx_repository import PostgresFXRepository
from packages.core.infrastructure.persistence.postgres_income_repository import PostgresIncomeRepository
from packages.core.infrastructure.persistence.postgres_investment_repository import PostgresInvestmentRepository
from packages.core.infrastructure.persistence.postgres_ohlcv_repository import PostgresOHLCVRepository
from packages.core.infrastructure.persistence.sqlite_account_repository import SqliteVirtualAccountRepository
from packages.core.utils.datetime_utils import month_range, prev_month

# ── Initialization ───────────────────────────────────────────────────────────
logger = logging.getLogger("backend.deps")

# Initialize DB Pool - REMOVED top-level call to prevent startup crash if Postgres is down.
# DatabaseManager.get_connection() will initialize the pool lazily when first needed.
# DatabaseManager.initialize()

# Persistence Layer
_exp_repo = PostgresExpenseRepository()
_inc_repo = PostgresIncomeRepository()
_inv_repo = PostgresInvestmentRepository()
_mkt_repo = PostgresOHLCVRepository()
_fx_repo  = PostgresFXRepository()
_acc_repo = SqliteVirtualAccountRepository()

# Service Layer (Singletons)
reward_service = RewardService()
fx_service = FXService(_fx_repo)
expense_service = ExpenseService(_exp_repo, reward_service)
income_service = IncomeService(_inc_repo, reward_service)
investment_service = InvestmentService(_inv_repo, fx_service)
dashboard_service = DashboardService(_exp_repo, _inc_repo, _inv_repo, _acc_repo, fx_service, investment_service)
market_service = MarketDataService(_mkt_repo)
butterfly_service = ButterflyService(_mkt_repo)
whale_service = WhaleAnalysisService()

# ── Legacy Compatibility Wrappers ────────────────────────────────────────────
ROOT = Config.get_cli_data_root()
_GUI = Config.BASE_DIR / "packages" / "api"
BALANCES_DB_PATH = Path(Config.get_db_path("goals"))

def _db(module: str, filename: str) -> str:
    """Legacy db resolver. (Kept for compatibility, but core logic uses Postgres)"""
    return str(ROOT / module / "data" / filename)

def _query(db_path: str, sql: str, params: tuple = ()):
    """Bridge to core Database utility (supports Postgres redirection)."""
    return Database.query(db_path, sql, params)

def _execute(db_path: str, sql: str, params: tuple = ()):
    """Bridge to core Database utility (supports Postgres redirection)."""
    return Database.execute(db_path, sql, params)


def _month_range(year: int, month: int):
    return month_range(year, month)

def _prev_month(year: int, month: int):
    return prev_month(year, month)

async def get_live_fx_rate() -> float:
    """Bridge to FXService (offload thread agar event loop tak macet)."""
    import asyncio
    return await asyncio.to_thread(fx_service.get_rate)

def get_active_profile() -> str:
    """Read the currently active profile from the shared project state."""
    try:
        path = Path(Config.BASE_DIR) / "data" / "active_profile.txt"
        if path.exists():
            return path.read_text().strip() or "personal"
    except Exception as e:
        logger.error(f"Error reading active profile: {e}")
    return "personal"

FX_RATE: float = 16_000.0  # fallback; live rate lewat get_live_fx_rate() di atas


# ── Lazy-loaders (Legacy) ─────────────────────────────────────────────────────

_merchant_memory    = None
_allocation_engine  = None
_recurrence_detect  = None

def _get_merchant_memory():
    global _merchant_memory
    if _merchant_memory is None:
        try:
            import importlib.util as _ilu
            _path = Path(Config.BASE_DIR) / "packages" / "api" / "backend" / "receipt" / "merchant_memory.py"
            if not _path.exists():
                logger.warning(f"merchant_memory.py not found at {_path}")
                return None
            spec = _ilu.spec_from_file_location("merchant_memory", str(_path))
            if spec is None or spec.loader is None:
                logger.error(f"Failed to create spec for merchant_memory at {_path}")
                return None
            mod  = _ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _merchant_memory = mod
            logger.info("merchant_memory module lazy-loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load merchant_memory: {e}")
    return _merchant_memory

def _get_allocation_engine():
    global _allocation_engine
    if _allocation_engine is None:
        try:
            import importlib.util as _ilu
            _path = Path(Config.BASE_DIR) / "packages" / "api" / "backend" / "finance" / "allocation_engine.py"
            if not _path.exists():
                logger.warning(f"allocation_engine.py not found at {_path}")
                return None
            spec = _ilu.spec_from_file_location("allocation_engine", str(_path))
            if spec is None or spec.loader is None:
                logger.error(f"Failed to create spec for allocation_engine at {_path}")
                return None
            mod  = _ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _allocation_engine = mod
            logger.info("allocation_engine module lazy-loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load allocation_engine: {e}")
    return _allocation_engine

def _get_recurrence_detector():
    global _recurrence_detect
    if _recurrence_detect is None:
        try:
            _path = Path(Config.BASE_DIR) / "packages" / "api" / "backend" / "expenses" / "recurrence_detector.py"
            if not _path.exists():
                logger.warning(f"recurrence_detector.py not found at {_path}")
                return None

            import importlib.util as _ilu
            spec = _ilu.spec_from_file_location("recurrence_detector", str(_path))
            if spec is None or spec.loader is None:
                logger.error(f"Failed to create spec for recurrence_detector at {_path}")
                return None

            mod  = _ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _recurrence_detect = mod
            logger.info("recurrence_detector module lazy-loaded successfully")
        except Exception as e:
            logger.error(f"Failed to lazy-load recurrence_detector: {e}")
            return None
    return _recurrence_detect

# ── Behavioral & Reward Helpers (Bridge to new RewardService) ────────────────

_BEHAVIORAL_CACHE: dict = {}
_BEHAVIORAL_CACHE_TIME: float = 0.0
_BEHAVIORAL_CACHE_TTL: float = 3600.0

def _bust_behavioral_cache() -> None:
    global _BEHAVIORAL_CACHE, _BEHAVIORAL_CACHE_TIME
    _BEHAVIORAL_CACHE = {}
    _BEHAVIORAL_CACHE_TIME = 0.0

def _check_and_apply_reward_unlocks() -> list:
    """Bridge to the new RewardService for auto-unlocks."""
    try:
        return reward_service.check_and_apply()
    except Exception as e:
        logger.error(f"Reward unlock error: {e}")
        return []

# ── DB Paths (Bridge) ────────────────────────────────────────────────────────

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

def _get_cash_split(db: str) -> dict:
    """Return the current physical_cash / bank_savings row (auto-seeds if missing)."""
    rows = _query(db, "SELECT physical_cash, bank_savings FROM cash_split WHERE id=?", (1,))
    if rows:
        return {"physical_cash": rows[0]["physical_cash"], "bank_savings": rows[0]["bank_savings"]}

    # Seed: migrate legacy 'cash' balance into bank_savings
    legacy = _query(db, "SELECT value FROM manual_balances WHERE key=?", ("cash",))
    legacy_val = legacy[0]["value"] if legacy else 0.0
    _execute(db,
        "INSERT INTO cash_split (id, physical_cash, bank_savings, updated_at) "
        "VALUES (1,?,?,?) ON CONFLICT(id) DO UPDATE SET "
        "physical_cash=excluded.physical_cash, bank_savings=excluded.bank_savings, updated_at=excluded.updated_at",
        (0.0, legacy_val, datetime.now().isoformat()))
    return {"physical_cash": 0.0, "bank_savings": legacy_val}

def _get_crypto_from_portfolio() -> float:
    """Load crypto value directly from portfolio.db. READ-ONLY."""
    try:
        inv_db = Config.get_db_path("investment")
        if not os.path.exists(inv_db):
            return 0.0
        # Use Database utility with an optimized JOIN instead of a correlated subquery
        rows = Database.query(inv_db,
            """
            SELECT i.remaining_quantity, i.buy_price, i.buy_currency, h.price_idr AS current_price_idr
            FROM investments i
            LEFT JOIN (
                SELECT investment_id, MAX(id) as max_id
                FROM historical_prices
                GROUP BY investment_id
            ) hm ON hm.investment_id = i.id
            LEFT JOIN historical_prices h ON h.id = hm.max_id
            WHERE i.status != ? AND i.asset_type = ?
            """, ("sold", "crypto"))

        total = 0.0
        for r in rows:
            qty = r["remaining_quantity"] or 0
            if r["current_price_idr"]:
                total += r["current_price_idr"] * qty
            elif r["buy_currency"] == "IDR":
                total += r["buy_price"] * qty
            else:
                total += r["buy_price"] * get_live_fx_rate() * qty
        return total
    except Exception as e:
        logger.error(f"Error calculating crypto from portfolio: {e}")
        return 0.0
