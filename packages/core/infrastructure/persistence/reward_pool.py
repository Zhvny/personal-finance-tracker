"""Bilingual reward pool master + idempotent seeder.

Decision (brief req 1): no table like this exists yet — the only reward table
is per-profile `reward_state` (points/state, not a catalogue). So this is a
NEW global master table, deliberately NOT added to `per_profile_ddl.py`
(adding it there would bump the 23-table count asserted by
`test_per_profile_ddl_user_id.py`).

Pattern follows `per_profile_ddl.py`: `_q()` literal escaping, CREATE TABLE
IF NOT EXISTS, INSERT ... ON CONFLICT upsert (works on both Postgres and
SQLite, so tests run without a database).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

TABLE = "reward_pool_master"
CATEGORIES = ("minuman", "makanan", "snack", "barang", "pengalaman")
TIERS = ("basic", "mid", "premium", "ultra")
SEED_PATH = Path(__file__).with_name("reward_pool_seed.json")


def _q(value: str) -> str:
    """SQL string literal with single-quote escaping (same as per_profile_ddl)."""
    return "'" + str(value).replace("'", "''") + "'"


def build_reward_pool_ddl(schema: Optional[str] = "public") -> str:
    """DDL for the pool master table. `schema=None` → unqualified (tests)."""
    table = f"{schema}.{TABLE}" if schema else TABLE
    cats = ", ".join(_q(c) for c in CATEGORIES)
    tiers = ", ".join(_q(t) for t in TIERS)
    return (
        f"CREATE TABLE IF NOT EXISTS {table} ("
        "id SERIAL PRIMARY KEY, "
        "name_en TEXT NOT NULL UNIQUE, "
        "name_id TEXT NOT NULL, "
        "desc_en TEXT NOT NULL, "
        "desc_id TEXT NOT NULL, "
        f"kategori TEXT NOT NULL CHECK (kategori IN ({cats})), "
        f"tier TEXT NOT NULL CHECK (tier IN ({tiers})), "
        "cost INTEGER NOT NULL CHECK (cost > 0), "
        "active BOOLEAN NOT NULL DEFAULT TRUE)"
    )


def load_seed_items() -> List[Dict[str, Any]]:
    """Curated bilingual seed items from the sibling JSON file."""
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def _is_sqlite(conn: Any) -> bool:
    return type(conn).__module__.split(".")[0] == "sqlite3"


def seed_pool(conn: Any, schema: Optional[str] = None) -> int:
    """Create the table if needed, then upsert every seed item by `name_en`.

    Idempotent: running twice yields the same row count. Returns row count.
    Accepts any DB-API connection (sqlite3 for tests, psycopg2 in prod).
    """
    table = f"{schema}.{TABLE}" if schema and not _is_sqlite(conn) else TABLE
    ddl = build_reward_pool_ddl(schema if schema and not _is_sqlite(conn) else None)
    if _is_sqlite(conn):  # SERIAL is Postgres-only
        ddl = ddl.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
    cur = conn.cursor()
    cur.execute(ddl)
    for item in load_seed_items():
        cur.execute(
            f"INSERT INTO {table} (name_en, name_id, desc_en, desc_id, kategori, tier, cost, active) "
            f"VALUES ({_q(item['name_en'])}, {_q(item['name_id'])}, "
            f"{_q(item['desc_en'])}, {_q(item['desc_id'])}, "
            f"{_q(item['kategori'])}, {_q(item['tier'])}, {int(item['cost'])}, "
            f"{'TRUE' if item.get('active', True) else 'FALSE'}) "
            "ON CONFLICT (name_en) DO UPDATE SET name_id=excluded.name_id, "
            "desc_en=excluded.desc_en, desc_id=excluded.desc_id, "
            "kategori=excluded.kategori, tier=excluded.tier, "
            "cost=excluded.cost, active=excluded.active"
        )
    try:
        conn.commit()
    except Exception:
        pass
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    row = cur.fetchone()
    return int(row[0] if isinstance(row, (list, tuple)) else row["count"])
