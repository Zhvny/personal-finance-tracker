import os
import sqlite3

db_path = r"../finance-tracker-gui/data/market.db"
if not os.path.exists(db_path):
    print(f"DB not found: {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print("Tables:", [r[0] for r in cur.fetchall()])

    # Also check if market_data exists and count tickers
    try:
        cur.execute("SELECT count(DISTINCT ticker) FROM market_data")
        print("Unique tickers in market_data:", cur.fetchone()[0])
    except Exception as e:
        print("Error querying market_data:", e)

    conn.close()
