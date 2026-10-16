import sqlite3


def test_deployment_schema_upgrade_and_rollback(tmp_path):
    """
    Verifies database migration upgrade and rollback execution integrity.
    """
    db_file = tmp_path / "migration_test.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # V1 Schema (Initial)
    cursor.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
    cursor.execute("INSERT INTO schema_version (version) VALUES (1)")
    cursor.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()

    # V2 Upgrade (Add cost column)
    cursor.execute("ALTER TABLE items ADD COLUMN cost REAL DEFAULT 0.0")
    cursor.execute("UPDATE schema_version SET version = 2")
    conn.commit()

    # Verify V2
    cursor.execute("PRAGMA table_info(items)")
    cols = [row[1] for row in cursor.fetchall()]
    assert "cost" in cols

    # Simulate V2 -> V1 Rollback
    cursor.execute("CREATE TABLE items_backup (id INTEGER PRIMARY KEY, name TEXT)")
    cursor.execute("INSERT INTO items_backup (id, name) SELECT id, name FROM items")
    cursor.execute("DROP TABLE items")
    cursor.execute("ALTER TABLE items_backup RENAME TO items")
    cursor.execute("UPDATE schema_version SET version = 1")
    conn.commit()

    # Verify Rollback
    cursor.execute("PRAGMA table_info(items)")
    cols_after_rollback = [row[1] for row in cursor.fetchall()]
    assert "cost" not in cols_after_rollback
    conn.close()
