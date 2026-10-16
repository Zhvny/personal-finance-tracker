"""
backend/routers/deps/__init__.py — Backward-compat shim
=======================================================
All routers import as `from packages.api.backend.routers.deps import ...`.
This module re-exports every public symbol from the split sub-modules so
existing imports keep working unchanged.

Sub-modules:
  - services       — DI container (service singletons)
  - db_paths       — DB path resolvers + schema init
  - legacy_bridge  — _db / _query / _execute / FX / profile / behavioral cache
  - lazy_loaders   — 3 path-based module loaders
  - domain_helpers — cash_split + crypto portfolio value

Extracted from deps.py (M3 refactor, 2026-09-05). Original deps.py deleted
in the same commit; this package takes its place.
"""
# Re-export 'os' so tests can monkeypatch 'packages.api.backend.routers.deps.os'
# (used by domain_helpers._get_crypto_from_portfolio internally).
import os  # noqa: F401 — re-export for test monkeypatch

# Services
from packages.api.backend.routers.deps.services import (
    butterfly_service,
    dashboard_service,
    expense_service,
    fx_service,
    income_service,
    investment_service,
    market_service,
    reward_service,
    whale_service,
)

# DB paths
from packages.api.backend.routers.deps.db_paths import (
    BALANCES_DB_PATH,
    ROOT,
    _GUI,
    _balances_db,
    _behavioral_db,
    _budget_db,
    _goals_db,
    _init_behavioral_db,
    _rewards_db,
)

# Legacy bridge
from packages.api.backend.routers.deps.legacy_bridge import (
    FX_RATE,
    _BEHAVIORAL_CACHE,
    _BEHAVIORAL_CACHE_TIME,
    _BEHAVIORAL_CACHE_TTL,
    _bust_behavioral_cache,
    _check_and_apply_reward_unlocks,
    _db,
    _execute,
    _month_range,
    _prev_month,
    _query,
    get_active_profile,
    get_live_fx_rate,
)

# Lazy loaders
from packages.api.backend.routers.deps.lazy_loaders import (
    _get_allocation_engine,
    _get_merchant_memory,
    _get_recurrence_detector,
)

# Domain helpers
from packages.api.backend.routers.deps.domain_helpers import (
    _get_cash_split,
    _get_crypto_from_portfolio,
)

# Re-export repository singletons used by a few routers
from packages.api.backend.routers.deps.services import (  # noqa: F401 — re-export
    _acc_repo,  # sqlite virtual-account repo
    _exp_repo,
    _fx_repo,
    _inc_repo,
    _inv_repo,
    _mkt_repo,
)
