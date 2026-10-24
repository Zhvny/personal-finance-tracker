"""Task 5: bilingual reward pool master + idempotent seeder (TDD)."""
import sqlite3

from packages.core.infrastructure.persistence.reward_pool import (
    CATEGORIES,
    TIERS,
    build_reward_pool_ddl,
    load_seed_items,
    seed_pool,
)


def _seeded():
    conn = sqlite3.connect(":memory:")
    first = seed_pool(conn)
    second = seed_pool(conn)
    assert first == second, "seed_pool() must be idempotent (upsert by name_en)"
    return conn, first


def test_seed_is_idempotent_and_large_enough():
    _, n = _seeded()
    assert n >= 300


def test_seed_names_categories_tiers_costs():
    conn, n = _seeded()
    items = load_seed_items()
    assert n == len(items) >= 300
    assert len({i["name_en"] for i in items}) == len(items), "name_en is the natural key: must be unique"
    assert all(i["name_en"].strip() and i["name_id"].strip() for i in items), "both languages non-empty"
    assert all(i["desc_en"].strip() and i["desc_id"].strip() for i in items), "bilingual descriptions non-empty"
    assert {i["kategori"] for i in items} <= set(CATEGORIES)
    assert {i["tier"] for i in items} <= set(TIERS)
    costs = {i["cost"] for i in items}
    assert len(costs) == 25, f"exactly 25 distinct costs, got {len(costs)}"
    assert all("halal" in i and isinstance(i["halal"], bool) for i in items)
    non_halal = {i["name_en"] for i in items if not i["halal"]}
    assert non_halal == {"Tonkotsu Ramen Bowl", "Ramen and Gyoza Set", "Personal Charcuterie Box"}
    mx = lambda t: max(i["cost"] for i in items if i["tier"] == t)
    mn = lambda t: min(i["cost"] for i in items if i["tier"] == t)
    assert mx("basic") < mn("mid") and mx("mid") < mn("premium") and mx("premium") < mn("ultra")
    assert mx("ultra") <= 15000, f"ultra cap must be <= 15000, got {mx('ultra')}"
    count, distinct = conn.execute("SELECT COUNT(*), COUNT(DISTINCT cost) FROM reward_pool_master").fetchone()
    assert (count, distinct) == (n, 25)


def test_seeded_table_has_bilingual_description_columns():
    conn, _ = _seeded()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(reward_pool_master)")}
    assert {"desc_en", "desc_id", "halal"} <= cols
    assert conn.execute("SELECT COUNT(*) FROM reward_pool_master WHERE halal = FALSE").fetchone()[0] == 3
    empty = conn.execute(
        "SELECT COUNT(*) FROM reward_pool_master WHERE TRIM(desc_en) = '' OR TRIM(desc_id) = ''"
    ).fetchone()[0]
    assert empty == 0


def test_ddl_follows_engagement_pattern():
    ddl = build_reward_pool_ddl("public")
    assert "reward_pool_master" in ddl
    assert "IF NOT EXISTS" in ddl and "CHECK" in ddl and "name_en" in ddl
    assert "desc_en TEXT NOT NULL" in ddl and "desc_id TEXT NOT NULL" in ddl
    assert "halal BOOLEAN NOT NULL DEFAULT TRUE" in ddl
