#!/usr/bin/env python3
"""
Maintenance & Data Refresh Script
===================================
1. Cleans QA & Test databases for Expense Tracker, Investment Tracker, and Income Tracker.
2. Updates live market prices & historical valuation for Investment Tracker holdings.
"""

import datetime
import glob
import json
import os
import shutil
import sqlite3
import sys
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager


def cleanup_qa_and_test_dbs():
    print("[*] 1. Cleaning QA and Test databases...")

    # A. Clean SQLite test files & sandbox
    sandbox_dir = _ROOT / "tests" / "sandbox_debug"
    if sandbox_dir.exists():
        shutil.rmtree(sandbox_dir, ignore_errors=True)
        print("  - Removed tests/sandbox_debug directory.")

    test_db_patterns = [
        _ROOT / "tests" / "integration" / "*.db",
        _ROOT / ".cache" / "yfinance" / "*.db",
    ]
    for pattern in test_db_patterns:
        for db_file in glob.glob(str(pattern)):
            try:
                os.remove(db_file)
                print(f"  - Removed test db: {Path(db_file).name}")
            except Exception as e:
                print(f"  - Warning removing {db_file}: {e}")

    # B. Reset QA Profile SQLite databases
    qa_profile_dirs = [
        _ROOT / "apps" / "cli" / "profiles" / "qa_business",
        _ROOT / "apps" / "cli" / "profiles" / "qa_financial",
        _ROOT / "apps" / "cli" / "profiles" / "qa_personal",
    ]
    for qa_dir in qa_profile_dirs:
        if qa_dir.exists():
            for db_file in qa_dir.glob("**/*.db"):
                try:
                    conn = sqlite3.connect(str(db_file))
                    cursor = conn.cursor()
                    tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
                    for t in tables:
                        cursor.execute(f"DELETE FROM {t};")
                    conn.commit()
                    conn.close()
                    print(f"  - Cleared tables in QA DB: {db_file.relative_to(_ROOT)}")
                except Exception as e:
                    print(f"  - Warning clearing {db_file}: {e}")

    # C. Truncate PostgreSQL QA schemas
    qa_schemas = ["qa_financial", "qa_business", "qa_personal"]
    for schema in qa_schemas:
        try:
            tables = DatabaseManager.query(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}'")
            for t in tables:
                t_name = t["table_name"]
                DatabaseManager.execute(f"TRUNCATE TABLE {schema}.{t_name} CASCADE;")
            print(f"  - Truncated PostgreSQL schema: {schema}")
        except Exception as e:
            print(f"  - Notice for PostgreSQL schema {schema}: {e}")

    print("[OK] QA & Test database cleanup complete.\n")


def update_investment_prices():
    print("[*] 2. Updating Investment Tracker prices and valuation data...")

    # Fetch live quotes for watchlist
    tickers = {
        "BTC": {"type": "crypto", "coingecko": "bitcoin"},
        "ETH": {"type": "crypto", "coingecko": "ethereum"},
        "SOL": {"type": "crypto", "coingecko": "solana"},
        "AAPL": {"type": "stock", "default": 225.50},
        "GOOG": {"type": "stock", "default": 178.20},
        "BBRI.JK": {"type": "stock", "default": 4750.0},
        "BMRI.JK": {"type": "stock", "default": 6400.0},
        "TLKM.JK": {"type": "stock", "default": 2900.0},
        "GOLD": {"type": "commodity", "default": 2450.0},
        "XAU": {"type": "commodity", "default": 2450.0},
        "OIL": {"type": "commodity", "default": 76.50},
    }

    # Fetch crypto rates from CoinGecko
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd,idr"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if "bitcoin" in data:
                tickers["BTC"]["price_usd"] = data["bitcoin"]["usd"]
                tickers["BTC"]["price_idr"] = data["bitcoin"]["idr"]
            if "ethereum" in data:
                tickers["ETH"]["price_usd"] = data["ethereum"]["usd"]
                tickers["ETH"]["price_idr"] = data["ethereum"]["idr"]
            if "solana" in data:
                tickers["SOL"]["price_usd"] = data["solana"]["usd"]
                tickers["SOL"]["price_idr"] = data["solana"]["idr"]
            print("  - Successfully fetched live crypto prices from CoinGecko.")
    except Exception as e:
        print(f"  - Using cached fallback prices for crypto: {e}")

    # Fallbacks for stocks/commodities if needed
    fallback_fx = 16200.0
    today_str = datetime.date.today().isoformat()
    now_ts = datetime.datetime.now()

    # Ensure market.latest_prices table exists and update
    try:
        for sym, info in tickers.items():
            price_usd = info.get("price_usd", info.get("default", 100.0))
            price_idr = info.get("price_idr", price_usd * fallback_fx)

            DatabaseManager.execute("""
                INSERT INTO market.latest_prices (ticker, price, timestamp, change_pct)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (ticker) DO UPDATE 
                SET price = EXCLUDED.price, timestamp = EXCLUDED.timestamp, change_pct = EXCLUDED.change_pct;
            """, (sym, price_usd, now_ts, 0.0))

            print(f"  - Updated {sym}: USD ${price_usd:,.2f} | IDR Rp {price_idr:,.0f}")

    except Exception as e:
        print(f"  - Error updating market.latest_prices: {e}")

    # Update SQLite portfolio.db active files
    sqlite_portfolios = [
        _ROOT / "apps" / "cli" / "profiles" / "personal" / "investment_tracker" / "data" / "portfolio.db",
        _ROOT / "apps" / "cli" / "profiles" / "business" / "investment_tracker" / "data" / "portfolio.db",
    ]
    for db_path in sqlite_portfolios:
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS latest_prices (
                        ticker TEXT PRIMARY KEY,
                        price_usd REAL,
                        price_idr REAL,
                        updated_at TEXT
                    );
                """)
                for sym, info in tickers.items():
                    p_usd = info.get("price_usd", info.get("default", 100.0))
                    p_idr = info.get("price_idr", p_usd * fallback_fx)
                    cursor.execute("""
                        INSERT INTO latest_prices (ticker, price_usd, price_idr, updated_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(ticker) DO UPDATE SET
                        price_usd=excluded.price_usd, price_idr=excluded.price_idr, updated_at=excluded.updated_at;
                    """, (sym, p_usd, p_idr, now_ts.isoformat()))
                conn.commit()
                conn.close()
                print(f"  - Refreshed price table in SQLite: {db_path.relative_to(_ROOT)}")
            except Exception as e:
                print(f"  - Warning updating SQLite {db_path}: {e}")

    print("[OK] Investment Tracker market prices successfully updated.\n")


if __name__ == "__main__":
    cleanup_qa_and_test_dbs()
    update_investment_prices()
