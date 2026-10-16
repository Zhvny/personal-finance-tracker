"""
merchant_memory_bridge.py — CLI-side adapter for shared merchant_map.db with Database bridge.
========================================================================================
Single Responsibility : CLI categorizer reads from the same merchant_map.db
                        that the GUI writes to (via merchant_memory.py).
Low Coupling          : Zero import of GUI modules. Talks only to Database bridge.
Open/Closed           : DB path resolves automatically via Config or relative paths.
DRY                   : Normalization logic mirrors merchant_memory.py exactly.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

# Try to import shared Database utility for Postgres redirection
try:
    from packages.core.infrastructure.persistence.database import Database
except ImportError:
    # Fallback for local development if packages is not in path
    import sqlite3
    class Database:
        @staticmethod
        def query(db_path, sql, params=()):
            if not os.path.exists(db_path): return []
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                return [dict(r) for r in conn.execute(sql, params).fetchall()]
        @staticmethod
        def execute(db_path, sql, params=()):
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute(sql, params)
                return cursor.lastrowid if "INSERT" in sql.upper() else cursor.rowcount
        @staticmethod
        def execute_script(db_path, script):
            with sqlite3.connect(db_path) as conn:
                conn.executescript(script)

logger = logging.getLogger(__name__)

# ── DB path resolution ───────────────────────────────────────────────
# Default: finance-tracker-gui/data/merchant_map.db  (sibling of apps/cli)
_DEFAULT_DB = (
    Path(__file__).parent.parent.parent.parent  # → finance-tracker/
    / "finance-tracker-gui" / "data" / "merchant_map.db"
)

def _db_path() -> str:
    """Resolve merchant_map.db path. Env var MERCHANT_MAP_DB overrides default."""
    env = os.environ.get("MERCHANT_MAP_DB", "")
    p = Path(env) if env else _DEFAULT_DB
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p.resolve())


# ══════════════════════════════════════════════════════════════════════════════
# § NORMALIZATION — must be identical to merchant_memory.py
# ══════════════════════════════════════════════════════════════════════════════

_BRANCH_RE = re.compile(
    r"\s*[#\-–]\s*\w+$"       # " #12" / " - CBD"
    r"|\s+\d+$"               # " 02"
    r"|\s*\(.*?\)$"           # " (JKT)"
    r"|\s*\bno\.?\s*\d+$"     # " No. 5"
    , re.IGNORECASE
)

def _normalize(name: str) -> str:
    if not name:
        return ""
    cleaned = _BRANCH_RE.sub("", name.strip())
    return re.sub(r"\s+", " ", cleaned).lower().strip()


# ══════════════════════════════════════════════════════════════════════════════
# § BRIDGE
# ══════════════════════════════════════════════════════════════════════════════

class MerchantMemoryBridge:
    """
    Thin read/write adapter over merchant_map.db for the CLI layer.
    Thread-safe via Database bridge; safe to instantiate multiple times.
    """

    # ── Schema (mirrors merchant_memory.py) ──────────────────────────
    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS merchant_map (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant_name TEXT    NOT NULL UNIQUE,
        category      TEXT    NOT NULL,
        last_seen     TEXT    NOT NULL,
        edit_count    INTEGER NOT NULL DEFAULT 1
    )
    """

    def __init__(self):
        self.db_path = _db_path()
        self._init_db()

    def _init_db(self):
        try:
            Database.execute_script(self.db_path, self._SCHEMA)
        except Exception as e:
            logger.error(f"Failed to initialize merchant_map DB: {e}")

    # ── Lookup ───────────────────────────────────────────────────────
    def lookup(self, merchant_name: str) -> Optional[str]:
        """
        Return stored category string for merchant, or None on MISS.
        Updates last_seen on every HIT.
        """
        key = _normalize(merchant_name)
        if not key:
            return None
        try:
            rows = Database.query(self.db_path,
                "SELECT category FROM merchant_map WHERE merchant_name = ?", (key,)
            )
            if rows:
                Database.execute(self.db_path,
                    "UPDATE merchant_map SET last_seen=? WHERE merchant_name=?",
                    (datetime.now().isoformat(), key)
                )
                return rows[0]["category"]
            return None
        except Exception as e:
            logger.error(f"MerchantMemoryBridge lookup error: {e}")
            return None

    # ── Remember ─────────────────────────────────────────────────────
    def remember(self, merchant_name: str, category: str) -> bool:
        """
        UPSERT merchant → category.
        Called after a user corrects a category in the CLI.
        Returns True on success.
        """
        key = _normalize(merchant_name)
        if not key or not category:
            return False
        try:
            Database.execute(self.db_path, """
                INSERT INTO merchant_map (merchant_name, category, last_seen, edit_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(merchant_name) DO UPDATE SET
                    category   = excluded.category,
                    last_seen  = excluded.last_seen,
                    edit_count = merchant_map.edit_count + 1
            """, (key, category, datetime.now().isoformat()))
            return True
        except Exception as e:
            logger.error(f"MerchantMemoryBridge remember error: {e}")
            return False

    # ── DB available? ────────────────────────────────────────────────
    def is_available(self) -> bool:
        """Return True if merchant_map.db is reachable (GUI data dir exists)."""
        try:
            # Check if directory is writeable/readable
            return os.path.exists(os.path.dirname(self.db_path))
        except Exception:
            return False
