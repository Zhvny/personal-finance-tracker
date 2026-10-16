import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Set paths
_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))

# Load .env
load_dotenv(_HERE / ".env")
load_dotenv(_HERE / "packages" / "api" / ".env")

print("DATABASE_URL:", os.environ.get("DATABASE_URL"))

from packages.core.infrastructure.config import Config
from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager

Config.initialize()
DatabaseManager.initialize()

try:
    print("Active profile:", Config.get_active_profile())

    # List all schemas
    schemas = DatabaseManager.query("SELECT schema_name FROM information_schema.schemata")
    print("\n--- SCHEMAS ---")
    for s in schemas:
        print(s['schema_name'])

    # List all tables in all schemas (filter to active profile, public, etc.)
    tables = DatabaseManager.query(
        "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog', 'information_schema')"
    )
    print("\n--- TABLES ---")
    for t in tables:
        print(f"{t['table_schema']}.{t['table_name']}")
except Exception as e:
    print("Error:", e)
