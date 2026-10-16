import os

import psycopg2
from psycopg2.extras import RealDictCursor


def count_rows():
    conn = psycopg2.connect(
        dbname=os.environ.get("POSTGRES_DB", "finance_tracker"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        host=os.environ.get("POSTGRES_HOST", "localhost")
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)

    schemas = ["financials", "personal", "business"]
    tables = ["expenses", "incomes"]

    for schema in schemas:
        print(f"\n--- Schema: {schema} ---")
        for table in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
                count = cur.fetchone()['count']
                print(f"{table}: {count} rows")
            except Exception as e:
                print(f"{table}: Table not found or error: {e}")
                conn.rollback()

    conn.close()

if __name__ == "__main__":
    count_rows()
