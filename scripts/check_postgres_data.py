import sys
from pathlib import Path

# Add root to sys.path
MONOREPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(MONOREPO_ROOT))

try:
    from packages.core.infrastructure.config import Config
    Config.initialize()

    import psycopg2
    from psycopg2.extras import RealDictCursor

    try:
        conn = psycopg2.connect(
            dbname=Config.POSTGRES_DB,
            user=Config.POSTGRES_USER,
            password=Config.POSTGRES_PASSWORD,
            host=Config.POSTGRES_HOST,
            port=Config.POSTGRES_PORT,
            connect_timeout=3
        )
        cur = conn.cursor()
        # Search all schemas
        cur.execute("SELECT nspname FROM pg_catalog.pg_namespace")
        schemas = [r[0] for r in cur.fetchall()]
        print("Schemas:", schemas)

        # Find where market_data is
        cur.execute("SELECT table_schema, table_name FROM information_schema.tables WHERE table_name = 'market_data'")
        tables = cur.fetchall()
        print("Found market_data in:", tables)

        for schema, table in tables:
            try:
                cur.execute(f'SELECT count(DISTINCT ticker) FROM "{schema}"."{table}"')
                print(f"Unique tickers in {schema}.{table}:", cur.fetchone()[0])
            except Exception as e:
                print(f"Query failed for {schema}.{table}: {e}")
                conn.rollback()

        conn.close()
    except Exception as e:
        print(f"Postgres Connection Failed: {e}")

except ImportError as e:
    print(f"Import Error: {e}")
except Exception as e:
    print(f"Error: {e}")
