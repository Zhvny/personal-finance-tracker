
import sys
from pathlib import Path

_PROJECT_ROOT = Path(r"..")
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "packages"))

from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager


def inspect_database():
    try:
        DatabaseManager.initialize()
        sql = """
            SELECT n.nspname as schema_name,
                   c.relname as table_name,
                   reltuples::bigint as estimated_rows
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND c.relkind = 'r'
            ORDER BY n.nspname, c.relname;
        """
        rows = DatabaseManager.query(sql)
        print("--- DATABASE SCHEMA INSPECTION ---")
        for row in rows:
            print(f"[{row['schema_name']}] {row['table_name']}: ~{row['estimated_rows']} rows")

        print("\n--- SEARCH PATH ---")
        res = DatabaseManager.query("SHOW search_path;")
        print(res)

    except Exception as e:
        print(f"Inspection failed: {e}")

if __name__ == "__main__":
    inspect_database()
