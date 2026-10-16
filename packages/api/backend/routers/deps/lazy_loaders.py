"""
backend/routers/deps/lazy_loaders.py — Path-based module loaders
================================================================
3 modules (merchant_memory, allocation_engine, recurrence_detector) are loaded
lazily via importlib.util because they pull in heavy optional dependencies.

Extracted from deps.py (M3 refactor, 2026-09-05). Pattern is the same as
provider_strategy._load_rule_engine / _load_receipt_parser — kept consistent.
"""
import importlib.util
import logging
from typing import Any, Optional

from packages.core.infrastructure.config import Config

logger = logging.getLogger("backend.deps")

_merchant_memory: Optional[Any] = None
_allocation_engine: Optional[Any] = None
_recurrence_detect: Optional[Any] = None


def _lazy_load(name: str, relative_path: str) -> Optional[Any]:
    """Generic path-based lazy loader. Returns module or None on failure.

    Each call caches the result in a global so subsequent calls are O(1).
    Used by the 3 named wrappers below and by provider_strategy for the
    AI modules — same pattern.
    """
    global _merchant_memory, _allocation_engine, _recurrence_detect
    cache = {
        "merchant_memory": _merchant_memory,
        "allocation_engine": _allocation_engine,
        "recurrence_detector": _recurrence_detect,
    }
    cached = cache.get(name)
    if cached is not None:
        return cached
    try:
        path = Config.BASE_DIR / relative_path
        if not path.exists():
            logger.warning(f"{name} not found at {path}")
            return None
        spec = importlib.util.spec_from_file_location(name, str(path))
        if spec is None or spec.loader is None:
            logger.error(f"Failed to create spec for {name} at {path}")
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if name == "merchant_memory":
            _merchant_memory = mod
        elif name == "allocation_engine":
            _allocation_engine = mod
        elif name == "recurrence_detector":
            _recurrence_detect = mod
        logger.info(f"{name} module lazy-loaded successfully")
        return mod
    except Exception as e:
        logger.error(f"Failed to load {name}: {e}")
        return None


def _get_merchant_memory():
    return _lazy_load("merchant_memory", "packages/api/backend/receipt/merchant_memory.py")


def _get_allocation_engine():
    return _lazy_load("allocation_engine", "packages/api/backend/finance/allocation_engine.py")


def _get_recurrence_detector():
    return _lazy_load("recurrence_detector", "packages/api/backend/expenses/recurrence_detector.py")
