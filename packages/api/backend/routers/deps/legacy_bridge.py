"""
backend/routers/deps/legacy_bridge.py — Thin wrappers over core utilities
========================================================================
Bridges used by the older router code that still talks to per-feature SQLite
DBs. New code should call the Postgres repositories in services.py.

Extracted from deps.py (M3 refactor, 2026-09-05).
"""
import logging
from pathlib import Path

from packages.core.infrastructure.config import Config
from packages.core.infrastructure.persistence.database import Database
from packages.core.utils.datetime_utils import month_range, prev_month

from packages.api.backend.routers.deps.services import reward_service

logger = logging.getLogger("backend.deps")

# Re-export the FX rate fallback (live rate via get_live_fx_rate()).
FX_RATE: float = 16_000.0  # fallback; live rate lewat get_live_fx_rate() di bawah


def _db(module: str, filename: str) -> str:
    """Legacy db resolver. (Kept for compatibility, but core logic uses Postgres)"""
    from packages.api.backend.routers.deps.db_paths import ROOT
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
    from packages.api.backend.routers.deps.services import fx_service
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
