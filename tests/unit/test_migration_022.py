"""Tests for migration 022: add halal to reward_pool_master."""

import sqlite3
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "migrations"
    / "022_add_halal_to_reward_pool_master.sql"
)


def test_migration_022_file_structure():
    assert MIGRATION_PATH.exists(), "Migration 022 file must exist"
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "reward_pool_master" in sql
    assert "ALTER TABLE reward_pool_master ADD COLUMN" in sql
    assert "halal BOOLEAN NOT NULL DEFAULT TRUE" in sql
    assert "Tonkotsu Ramen Bowl" in sql
    assert "Ramen and Gyoza Set" in sql
    assert "Personal Charcuterie Box" in sql
    assert "DO $$" in sql
    assert "IF NOT EXISTS" in sql


def apply_sqlite_migration_022(conn: sqlite3.Connection) -> None:
    """Execute equivalent migration on SQLite connection."""
    cur = conn.cursor()
    cols = {r[1] for r in cur.execute("PRAGMA table_info(reward_pool_master)").fetchall()}
    if "halal" not in cols:
        cur.execute("ALTER TABLE reward_pool_master ADD COLUMN halal BOOLEAN NOT NULL DEFAULT 1")
    cur.execute(
        """
        UPDATE reward_pool_master
        SET halal = 0
        WHERE name_en IN (
            'Tonkotsu Ramen Bowl',
            'Ramen and Gyoza Set',
            'Personal Charcuterie Box'
        )
        """
    )
    conn.commit()


def test_sqlite_migration_on_pre_022_schema():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()

    # Pre-022 schema without halal column
    cur.execute(
        """
        CREATE TABLE reward_pool_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_en TEXT NOT NULL UNIQUE,
            name_id TEXT NOT NULL,
            desc_en TEXT NOT NULL,
            desc_id TEXT NOT NULL,
            kategori TEXT NOT NULL,
            tier TEXT NOT NULL,
            cost INTEGER NOT NULL,
            active BOOLEAN NOT NULL DEFAULT 1
        )
        """
    )

    items = [
        ("Bottled Mineral Water", "Air Mineral", "Desc en", "Desc id", "minuman", "basic", 50),
        ("Tonkotsu Ramen Bowl", "Ramen Tonkotsu", "Pork ramen", "Ramen babi", "makanan", "mid", 800),
        ("Ramen and Gyoza Set", "Set Ramen", "Ramen gyoza", "Ramen gyoza", "makanan", "premium", 2500),
        ("Personal Charcuterie Box", "Charcuterie", "Cured meats", "Daging olahan", "snack", "premium", 4000),
        ("Boba Milk Tea", "Boba Susu", "Sweet tea", "Teh boba", "minuman", "mid", 300),
    ]

    for item in items:
        cur.execute(
            """
            INSERT INTO reward_pool_master (name_en, name_id, desc_en, desc_id, kategori, tier, cost)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            item,
        )
    conn.commit()

    # Apply migration
    apply_sqlite_migration_022(conn)

    cols = {r[1] for r in cur.execute("PRAGMA table_info(reward_pool_master)").fetchall()}
    assert "halal" in cols

    non_halal = cur.execute("SELECT name_en FROM reward_pool_master WHERE halal = 0").fetchall()
    assert {r[0] for r in non_halal} == {
        "Tonkotsu Ramen Bowl",
        "Ramen and Gyoza Set",
        "Personal Charcuterie Box",
    }

    halal = cur.execute("SELECT name_en FROM reward_pool_master WHERE halal = 1").fetchall()
    assert {r[0] for r in halal} == {
        "Bottled Mineral Water",
        "Boba Milk Tea",
    }

    # Verify idempotency
    apply_sqlite_migration_022(conn)
    count_non_halal = cur.execute("SELECT COUNT(*) FROM reward_pool_master WHERE halal = 0").fetchone()[0]
    assert count_non_halal == 3
