import os

import psycopg2

# --- Configuration ---
POSTGRES_DB = os.environ.get("POSTGRES_DB", "finance_tracker")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")

def check_tables():
    try:
        conn = psycopg2.connect(
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT
        )
        cur = conn.cursor()

        schemas = ["financials", "investment", "personal", "business"]
        for schema in schemas:
            print(f"\n--- Schema: {schema} ---")
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s;", (schema,))
            rows = cur.fetchall()
            for row in rows:
                print(row[0])

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_tables()
