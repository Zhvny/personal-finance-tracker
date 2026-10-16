import os
import sqlite3

db_path = r"../apps/stock_analyzer/cache.db"
if not os.path.exists(db_path):
    print(f"DB not found: {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print("Tables:", [r[0] for r in cur.fetchall()])

    # Try common table names for market data
    for table in ['market_data', 'ohlcv_cache', 'stock_cache']:
        try:
            cur.execute(f"SELECT count(DISTINCT ticker) FROM {table}")
            print(f"Unique tickers in {table}:", cur.fetchone()[0])
        except Exception:
            pass

    conn.close()
