
import os
import sys

# Add project root and packages to sys.path
project_root = r".."
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, "packages"))

# Mock environment variables for Config
os.environ["POSTGRES_DB"] = "finance_tracker"
os.environ["POSTGRES_USER"] = "postgres"
os.environ["POSTGRES_PASSWORD"] = "postgres" # Assuming default from other scripts
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"

try:
    from core.infrastructure.persistence.postgres_manager import DatabaseManager

    # Initialize pool
    DatabaseManager.initialize()

    # Check system schema and tables
    tables = DatabaseManager.query("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'system'
    """)
    print("Tables in 'system' schema:")
    for t in tables:
        print(f"- {t['table_name']}")

    schemas = DatabaseManager.query("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'system'")
    if not schemas:
        print("'system' schema does not exist.")
    else:
        print("'system' schema exists.")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
