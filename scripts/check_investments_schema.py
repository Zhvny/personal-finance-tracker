
import os
import sys

project_root = r".."
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, "packages"))

os.environ["POSTGRES_DB"] = "finance_tracker"
os.environ["POSTGRES_USER"] = "postgres"
os.environ["POSTGRES_PASSWORD"] = "postgres"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"

try:
    from core.infrastructure.persistence.postgres_manager import DatabaseManager
    DatabaseManager.initialize()

    columns = DatabaseManager.query("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'system' AND table_name = 'investments'
    """)
    print("Columns in 'system.investments':")
    for c in columns:
        print(f"- {c['column_name']} ({c['data_type']})")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
