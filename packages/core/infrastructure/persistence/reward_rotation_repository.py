"""Persistence layer for reward weekly rotation, history, and claims.

Supports both PostgreSQL (prod) and SQLite (testing/local).
Tables:
  - reward_weekly_pool: 12-item weekly selections
  - reward_history: 26-week history of selected items
  - reward_claims: per-profile claimed rewards with 14-day expiry
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set


def _is_sqlite(conn: Any) -> bool:
    return type(conn).__module__.split(".")[0] == "sqlite3"


class RewardRotationRepository:
    def __init__(self, schema: Optional[str] = "public"):
        self.schema = schema

    def _qualify(self, table: str, conn: Any) -> str:
        if self.schema and not _is_sqlite(conn):
            return f"{self.schema}.{table}"
        return table

    def ensure_tables(self, conn: Any) -> None:
        """Create weekly rotation tables if they do not exist."""
        pool_tbl = self._qualify("reward_weekly_pool", conn)
        hist_tbl = self._qualify("reward_history", conn)
        claims_tbl = self._qualify("reward_claims", conn)

        id_col = "INTEGER PRIMARY KEY AUTOINCREMENT" if _is_sqlite(conn) else "SERIAL PRIMARY KEY"

        ddl_pool = (
            f"CREATE TABLE IF NOT EXISTS {pool_tbl} ("
            "week_start TEXT PRIMARY KEY, "
            "item_ids TEXT NOT NULL, "
            "backfilled BOOLEAN NOT NULL DEFAULT 0, "
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        ddl_hist = (
            f"CREATE TABLE IF NOT EXISTS {hist_tbl} ("
            "item_id INTEGER NOT NULL, "
            "week_start TEXT NOT NULL, "
            "PRIMARY KEY (item_id, week_start))"
        )
        ddl_claims = (
            f"CREATE TABLE IF NOT EXISTS {claims_tbl} ("
            f"id {id_col}, "
            "profile_id TEXT NOT NULL, "
            "item_id INTEGER NOT NULL, "
            "week_start TEXT NOT NULL, "
            "expires_at TEXT NOT NULL, "
            "redeemed_at TEXT, "
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "UNIQUE (profile_id, item_id, week_start))"
        )

        cur = conn.cursor()
        cur.execute(ddl_pool)
        cur.execute(ddl_hist)
        cur.execute(ddl_claims)
        try:
            conn.commit()
        except Exception:
            pass

    def get_weekly_pool(self, week_start_str: str, conn: Any) -> Optional[Dict[str, Any]]:
        pool_tbl = self._qualify("reward_weekly_pool", conn)
        cur = conn.cursor()
        cur.execute(f"SELECT week_start, item_ids, backfilled FROM {pool_tbl} WHERE week_start = ?", (week_start_str,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "week_start": row[0],
            "item_ids": json.loads(row[1]),
            "backfilled": bool(row[2]),
        }

    def get_latest_weekly_pool(self, conn: Any) -> Optional[Dict[str, Any]]:
        pool_tbl = self._qualify("reward_weekly_pool", conn)
        cur = conn.cursor()
        cur.execute(f"SELECT week_start, item_ids, backfilled FROM {pool_tbl} ORDER BY week_start DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            return None
        return {
            "week_start": row[0],
            "item_ids": json.loads(row[1]),
            "backfilled": bool(row[2]),
        }

    def save_weekly_pool(self, week_start_str: str, item_ids: List[int], backfilled: bool, conn: Any) -> None:
        pool_tbl = self._qualify("reward_weekly_pool", conn)
        cur = conn.cursor()
        json_ids = json.dumps(item_ids)
        if _is_sqlite(conn):
            cur.execute(
                f"INSERT OR REPLACE INTO {pool_tbl} (week_start, item_ids, backfilled) VALUES (?, ?, ?)",
                (week_start_str, json_ids, 1 if backfilled else 0),
            )
        else:
            cur.execute(
                f"INSERT INTO {pool_tbl} (week_start, item_ids, backfilled) VALUES (%s, %s, %s) "
                "ON CONFLICT (week_start) DO UPDATE SET item_ids = EXCLUDED.item_ids, backfilled = EXCLUDED.backfilled",
                (week_start_str, json_ids, backfilled),
            )
        try:
            conn.commit()
        except Exception:
            pass

    def add_history(self, item_ids: List[int], week_start_str: str, conn: Any) -> None:
        hist_tbl = self._qualify("reward_history", conn)
        cur = conn.cursor()
        for item_id in item_ids:
            if _is_sqlite(conn):
                cur.execute(
                    f"INSERT OR IGNORE INTO {hist_tbl} (item_id, week_start) VALUES (?, ?)",
                    (int(item_id), week_start_str),
                )
            else:
                cur.execute(
                    f"INSERT INTO {hist_tbl} (item_id, week_start) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (int(item_id), week_start_str),
                )
        try:
            conn.commit()
        except Exception:
            pass

    def get_history_items_since(self, since_date_str: str, conn: Any) -> List[Dict[str, Any]]:
        """Return history rows since cutoff date, ordered by week_start ascending."""
        hist_tbl = self._qualify("reward_history", conn)
        cur = conn.cursor()
        cur.execute(
            f"SELECT item_id, week_start FROM {hist_tbl} WHERE week_start >= ? ORDER BY week_start ASC",
            (since_date_str,),
        )
        return [{"item_id": int(r[0]), "week_start": str(r[1])} for r in cur.fetchall()]

    def create_claim(
        self, profile_id: str, item_id: int, week_start_str: str, expires_at_str: str, conn: Any
    ) -> Dict[str, Any]:
        claims_tbl = self._qualify("reward_claims", conn)
        cur = conn.cursor()
        if _is_sqlite(conn):
            cur.execute(
                f"INSERT INTO {claims_tbl} (profile_id, item_id, week_start, expires_at) VALUES (?, ?, ?, ?)",
                (profile_id, int(item_id), week_start_str, expires_at_str),
            )
            claim_id = cur.lastrowid
        else:
            cur.execute(
                f"INSERT INTO {claims_tbl} (profile_id, item_id, week_start, expires_at) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (profile_id, int(item_id), week_start_str, expires_at_str),
            )
            claim_id = cur.fetchone()[0]
        try:
            conn.commit()
        except Exception:
            pass
        return {
            "id": claim_id,
            "profile_id": profile_id,
            "item_id": int(item_id),
            "week_start": week_start_str,
            "expires_at": expires_at_str,
            "redeemed_at": None,
        }

    def get_claim(self, claim_id: int, conn: Any) -> Optional[Dict[str, Any]]:
        claims_tbl = self._qualify("reward_claims", conn)
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, profile_id, item_id, week_start, expires_at, redeemed_at FROM {claims_tbl} WHERE id = ?",
            (claim_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "profile_id": row[1],
            "item_id": row[2],
            "week_start": row[3],
            "expires_at": row[4],
            "redeemed_at": row[5],
        }

    def get_claims_by_profile_and_week(self, profile_id: str, week_start_str: str, conn: Any) -> List[Dict[str, Any]]:
        claims_tbl = self._qualify("reward_claims", conn)
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, profile_id, item_id, week_start, expires_at, redeemed_at FROM {claims_tbl} "
            "WHERE profile_id = ? AND week_start = ?",
            (profile_id, week_start_str),
        )
        return [
            {
                "id": r[0],
                "profile_id": r[1],
                "item_id": r[2],
                "week_start": r[3],
                "expires_at": r[4],
                "redeemed_at": r[5],
            }
            for r in cur.fetchall()
        ]

    def mark_claim_redeemed(self, claim_id: int, redeemed_at_str: str, conn: Any) -> Optional[Dict[str, Any]]:
        claims_tbl = self._qualify("reward_claims", conn)
        cur = conn.cursor()
        cur.execute(
            f"UPDATE {claims_tbl} SET redeemed_at = ? WHERE id = ?",
            (redeemed_at_str, claim_id),
        )
        try:
            conn.commit()
        except Exception:
            pass
        return self.get_claim(claim_id, conn)

    def _user_stats_tbl(self, profile_id: str, conn: Any) -> str:
        if _is_sqlite(conn):
            cur = conn.cursor()
            for cand in [f"{profile_id}_user_stats", "user_stats", f"{profile_id}.user_stats"]:
                try:
                    cur.execute(f"SELECT 1 FROM {cand} LIMIT 1")
                    return cand
                except Exception:
                    continue
            tbl = f"{profile_id}_user_stats" if profile_id and profile_id != "default" else "user_stats"
            try:
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS {tbl} (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"
                )
                conn.commit()
            except Exception:
                pass
            return tbl
        return f"{profile_id}.user_stats"

    def get_halal_preference(self, profile_id: str, conn: Any) -> bool:
        """Get halal_only preference for profile (default True)."""
        tbl = self._user_stats_tbl(profile_id, conn)
        cur = conn.cursor()
        try:
            cur.execute(f"SELECT value FROM {tbl} WHERE key = ?", ("halal_only",))
            row = cur.fetchone()
            if row and row[0] is not None:
                val = str(row[0]).strip().lower()
                return val in ("1", "true", "yes")
        except Exception:
            pass
        return True

    def set_halal_preference(self, profile_id: str, enabled: bool, conn: Any) -> None:
        """Set halal_only preference for profile ('1' or '0')."""
        tbl = self._user_stats_tbl(profile_id, conn)
        cur = conn.cursor()
        val_str = "1" if enabled else "0"
        if _is_sqlite(conn):
            cur.execute(
                f"INSERT INTO {tbl} (key, value) VALUES (?, ?) "
                f"ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP",
                ("halal_only", val_str),
            )
        else:
            cur.execute(
                f"INSERT INTO {tbl} (key, value) VALUES (%s, %s) "
                f"ON CONFLICT(key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()",
                ("halal_only", val_str),
            )
        try:
            conn.commit()
        except Exception:
            pass
