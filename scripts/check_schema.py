import sys

import psycopg2

sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv

load_dotenv()

dsn = "postgresql://postgres:postgres@localhost:5432/finance_tracker"
conn = psycopg2.connect(dsn)
cur = conn.cursor()

schema = "qa_financial"
tables = ["transactions", "expenses", "incomes", "budgets", "goals",
          "investments", "sell_transactions", "networth_snapshots",
          "manual_balances", "user_stats", "virtual_accounts"]

print(f"=== Schema: {schema} ===")
for table in tables:
    try:
        cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
        count = cur.fetchone()[0]
        status = "HAS DATA" if count > 0 else "EMPTY"
        print(f"  {table}: {count} rows [{status}]")
    except Exception as e:
        print(f"  {table}: ERROR - {e}")

print()
# Also check personal for comparison
print("=== Schema: personal (untuk perbandingan) ===")
for table in tables:
    try:
        cur.execute(f'SELECT COUNT(*) FROM personal."{table}"')
        count = cur.fetchone()[0]
        status = "HAS DATA" if count > 0 else "EMPTY"
        print(f"  {table}: {count} rows [{status}]")
    except Exception as e:
        print(f"  {table}: ERROR - {e}")

conn.close()
