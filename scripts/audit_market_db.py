
import logging
import os
import time

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


def audit_db():
    pw = os.environ.get("POSTGRES_PASSWORD")
    if not pw:
        if os.environ.get("DEV_MODE") == "1":
            logger.warning("POSTGRES_PASSWORD unset, using dev default")
        else:
            logger.warning("POSTGRES_PASSWORD unset, using localhost dev default")
        pw = "postgres"
    try:
        conn = psycopg2.connect(dbname="finance_tracker", user="postgres", password=pw, host="localhost", port="5432")
        cur = conn.cursor(cursor_factory=RealDictCursor)

        print("--- Database Audit: market.ohlcv_cache ---")

        # 1. Table existence and structure
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'market' AND table_name = 'ohlcv_cache'
        """)
        columns = cur.fetchall()
        print("\nColumns:")
        for col in columns:
            print(f"  {col['column_name']} ({col['data_type']})")

        # 2. Row count
        cur.execute("SELECT COUNT(*) FROM market.ohlcv_cache")
        count = cur.fetchone()['count']
        print(f"\nTotal Rows: {count}")

        # 3. Duplicate check (ticker, period)
        cur.execute("""
            SELECT ticker, period, COUNT(*) 
            FROM market.ohlcv_cache 
            GROUP BY ticker, period 
            HAVING COUNT(*) > 1
        """)
        dupes = cur.fetchall()
        if dupes:
            print(f"\n[!] WARNING: Found {len(dupes)} duplicate (ticker, period) pairs!")
            for d in dupes[:5]:
                print(f"  {d['ticker']} ({d['period']}): {d['count']} times")
        else:
            print("\n[OK] No duplicate (ticker, period) pairs found.")

        # 4. Stale data check
        cur.execute("""
            SELECT ticker, period, fetched_at 
            FROM market.ohlcv_cache 
            ORDER BY fetched_at ASC 
            LIMIT 5
        """)
        oldest = cur.fetchall()
        print("\nOldest entries:")
        for o in oldest:
            print(f"  {o['ticker']} ({o['period']}): {o['fetched_at']}")

        # 5. Null check
        cur.execute("""
            SELECT COUNT(*) FROM market.ohlcv_cache 
            WHERE data IS NULL OR ticker IS NULL OR period IS NULL OR fetched_at IS NULL
        """)
        nulls = cur.fetchone()['count']
        if nulls > 0:
            print(f"\n[!] WARNING: Found {nulls} rows with NULL values!")
        else:
            print("\n[OK] No NULL values found in core columns.")

        # 6. Slow query check (simulated)
        start = time.time()
        cur.execute("SELECT ticker, period, fetched_at FROM market.ohlcv_cache WHERE ticker LIKE 'AAPL%'")
        cur.fetchall()
        print(f"\nQuery latency (AAPL%): {(time.time() - start)*1000:.2f}ms")

        conn.close()
    except Exception as e:
        print(f"Audit failed: {e}")

if __name__ == "__main__":
    audit_db()
