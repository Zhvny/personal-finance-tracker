import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
# Find the directory that contains 'stock_analyzer'
_P = _HERE.parent
while _P.name != "stock_analyzer" and _P.parent != _P:
    _P = _P.parent
_PROJECT_ROOT = str(_P.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pickle
import sqlite3


def inspect():
    conn = sqlite3.connect('cache.db')
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, period, fetched_at FROM ohlcv_cache")
    rows = cursor.fetchall()
    print("=== Cache Entries ===")
    for r in rows:
        print(f"Ticker: {r[0]}, Period: {r[1]}, Fetched At: {r[2]}")

    # Inspect USDIDR=X
    cursor.execute("SELECT data FROM ohlcv_cache WHERE ticker LIKE '%USDIDR%'")
    row = cursor.fetchone()
    if row:
        df = pickle.loads(row[0])
        print("\n=== USDIDR=X Tail ===")
        print(df.tail())
        print("\nColumns:", df.columns)
    else:
        print("\nUSDIDR=X not found in cache")
    conn.close()

if __name__ == "__main__":
    inspect()
