import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path("C:/Users/Zhvn/Documents/Zhvny/Project/finance-tracker")
sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.infrastructure.config import Config

Config.initialize()

import psycopg2
from psycopg2.extras import RealDictCursor


def check_reconciliation():
    try:
        conn = psycopg2.connect(
            dbname=Config.POSTGRES_DB,
            user=Config.POSTGRES_USER,
            password=Config.POSTGRES_PASSWORD,
            host=Config.POSTGRES_HOST,
            port=Config.POSTGRES_PORT,
            connect_timeout=3
        )
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Set search path to personal
        cur.execute("SET search_path TO personal")

        print("\n--- Sell Transactions (Realized P/L) ---")
        cur.execute("""
            SELECT *
            FROM sell_transactions 
            WHERE sell_date >= '2026-05-30'
            ORDER BY sell_date DESC
        """)
        sells = cur.fetchall()
        for s in sells:
            print(s)

        print("\n--- Active Holdings Check ---")
        # Check target assets
        tickers = ['AAPL', 'AMZN', 'NVDA', 'GOOG', 'GOLD']
        for ticker in tickers:
            cur.execute("""
                SELECT *
                FROM investments 
                WHERE ticker = %s AND (quantity > 0 OR status != 'sold')
            """, (ticker,))
            holdings = cur.fetchall()
            print(f"Ticker: {ticker}")
            if not holdings:
                print("  No active holdings.")
            for h in holdings:
                print(f"  Qty: {h['quantity']}, Status: {h['status']}")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_reconciliation()
