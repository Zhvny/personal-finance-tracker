"""
merchant_memory.py — Persistent Merchant-to-Category Memory
============================================================
Repository Pattern: encapsulates all merchant_map.db access.
Single Responsibility: ONLY manages merchant → category mapping.
Open/Closed: new lookup strategies can be added without changing callers.

Flow
----
  receipt scan → detect merchant_name
    → MerchantMemory.lookup(name)   → category (HIT)  — skip keyword engine
                                    → None     (MISS)  — fall through to keyword engine
  user edits category in UI
    → MerchantMemory.remember(name, category)          — UPSERT into DB

DB: data/merchant_map.db  (separate file, never conflicts with existing DBs)
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── DB path resolution ─────────────────────────────────────────────────────────
_DB_PATH = Path(__file__).parent.parent.parent / "data" / "merchant_map.db"


def _conn() -> sqlite3.Connection:
    """Open (or create) merchant_map.db and ensure schema exists."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(_DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""
        CREATE TABLE IF NOT EXISTS merchant_map (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_name TEXT    NOT NULL UNIQUE,
            category      TEXT    NOT NULL,
            last_seen     TEXT    NOT NULL,
            edit_count    INTEGER NOT NULL DEFAULT 1
        )
    """)
    con.commit()
    return con


# ══════════════════════════════════════════════════════════════════════════════
# § NORMALIZATION — deterministic key for fuzzy merchant names
#   "Starbucks Coffee #12" → "starbucks coffee"
#   "ALFAMART CIKARANG 02" → "alfamart"
# ══════════════════════════════════════════════════════════════════════════════

# Strip trailing branch/number patterns: " #12", " 02", " - CBD", " (JKT)"
_BRANCH_RE = re.compile(
    r"\s*[#\-–]\s*\w+$"          # " #12" / " - CBD"
    r"|\s+\d+$"                   # " 02"
    r"|\s*\(.*?\)$"               # " (JKT)"
    r"|\s*\bno\.?\s*\d+$"         # " No. 5"
    , re.IGNORECASE
)

def _normalize(name: str) -> str:
    """
    Produce a stable lowercase key from a raw merchant name.
    Strips branch suffixes, normalises whitespace.
    """
    if not name:
        return ""
    cleaned = _BRANCH_RE.sub("", name.strip())
    # collapse internal whitespace
    return re.sub(r"\s+", " ", cleaned).lower().strip()


# ══════════════════════════════════════════════════════════════════════════════
# § PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

class MerchantMemory:
    """
    Thin Repository over merchant_map.db.
    All methods are safe to call concurrently (WAL mode).
    """

    # ── Lookup ─────────────────────────────────────────────────────────────────
    @staticmethod
    def lookup(merchant_name: str) -> Optional[str]:
        """
        Return stored category for merchant, or None on MISS.
        Updates last_seen on every HIT.
        """
        key = _normalize(merchant_name)
        if not key:
            return None
        try:
            con = _conn()
            row = con.execute(
                "SELECT category FROM merchant_map WHERE merchant_name = ?", (key,)
            ).fetchone()
            if row:
                con.execute(
                    "UPDATE merchant_map SET last_seen=? WHERE merchant_name=?",
                    (datetime.now().isoformat(), key)
                )
                con.commit()
                return row["category"]
            return None
        except Exception:
            return None

    # ── Remember ───────────────────────────────────────────────────────────────
    @staticmethod
    def remember(merchant_name: str, category: str) -> bool:
        """
        UPSERT merchant → category mapping.
        Returns True on success, False on failure.
        edit_count increments on every update so high-confidence entries
        take priority in future fuzzy matching enhancements.
        """
        key = _normalize(merchant_name)
        if not key or not category:
            return False
        try:
            con = _conn()
            con.execute("""
                INSERT INTO merchant_map (merchant_name, category, last_seen, edit_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(merchant_name) DO UPDATE SET
                    category   = excluded.category,
                    last_seen  = excluded.last_seen,
                    edit_count = merchant_map.edit_count + 1
            """, (key, category, datetime.now().isoformat()))
            con.commit()
            return True
        except Exception:
            return False

    # ── Forget ─────────────────────────────────────────────────────────────────
    @staticmethod
    def forget(merchant_name: str) -> bool:
        """Remove a mapping (admin / correction flow)."""
        key = _normalize(merchant_name)
        if not key:
            return False
        try:
            con = _conn()
            con.execute("DELETE FROM merchant_map WHERE merchant_name=?", (key,))
            con.commit()
            return True
        except Exception:
            return False

    # ── List all ───────────────────────────────────────────────────────────────
    @staticmethod
    def list_all(limit: int = 200) -> list:
        """Return all stored mappings ordered by edit_count DESC."""
        try:
            con = _conn()
            rows = con.execute(
                "SELECT merchant_name, category, last_seen, edit_count "
                "FROM merchant_map ORDER BY edit_count DESC, last_seen DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    # ── Stats ──────────────────────────────────────────────────────────────────
    @staticmethod
    def stats() -> dict:
        """Return summary stats for the merchant memory DB."""
        try:
            con = _conn()
            total = con.execute("SELECT COUNT(*) FROM merchant_map").fetchone()[0]
            by_cat = con.execute(
                "SELECT category, COUNT(*) as cnt FROM merchant_map GROUP BY category ORDER BY cnt DESC"
            ).fetchall()
            return {
                "total_merchants": total,
                "by_category": [dict(r) for r in by_cat],
            }
        except Exception:
            return {"total_merchants": 0, "by_category": []}


# ══════════════════════════════════════════════════════════════════════════════
# § RECEIPT ENRICHMENT HELPER
#   Called from api_server.py scan paths — applies memory before keyword fallback
# ══════════════════════════════════════════════════════════════════════════════

def enrich_receipt_category(receipt: dict) -> dict:
    """
    Check MerchantMemory for the receipt's merchant_name.
    If found, overwrite the AI/keyword category with the remembered one.
    Adds 'category_source' field: "memory" | "ai" | "keyword".

    Mutates a COPY of receipt — never modifies the original dict.
    """
    result = dict(receipt)
    merchant = result.get("merchant_name", "")
    remembered = MerchantMemory.lookup(merchant)
    if remembered:
        result["category"]        = remembered
        result["category_source"] = "memory"
    else:
        result.setdefault("category_source", "ai")
    return result
