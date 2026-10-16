import concurrent.futures
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

# Setup logging
logger = logging.getLogger(__name__)

# Setup paths
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
if str(_HERE) not in sys.path: sys.path.insert(0, str(_HERE))
if str(_ROOT) not in sys.path: sys.path.insert(0, str(_ROOT))

from packages.core.utils.symbol_utils import SymbolFormatter

try:
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
    from packages.core.infrastructure.persistence.postgres_ohlcv_repository import PostgresOHLCVRepository
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

ROOT = _ROOT
RAW_DIR = ROOT / "data" / "raw"

# Initialize Postgres Repo
REPO = None
if HAS_POSTGRES:
    try:
        DatabaseManager.initialize()
        REPO = PostgresOHLCVRepository()
    except Exception as e:
        print(f"Warning: Could not initialize Postgres: {e}")

# ... (TICKERS_CORE and load_tickers_from_list unchanged)
TICKERS: list[str] = []

def sync_one(ticker):
    try:
        cache_key = f"{ticker}_2y_1d"

        # 1. Fetch Latest Data (7d for incremental sync)
        df_new = yf.download(ticker, period="7d", interval="1d", auto_adjust=True, progress=False)
        if df_new is None or df_new.empty:
            return False

        if df_new.index.tz is not None: df_new.index = df_new.index.tz_localize(None)
        if isinstance(df_new.columns, pd.MultiIndex): df_new.columns = df_new.columns.get_level_values(0)

        # 2. Get Existing Data (Prefer Postgres, Fallback to CSV)
        df_old = None
        if REPO:
            df_old = REPO.get(cache_key, "2y")

        if df_old is None:
            market = SymbolFormatter.get_market(ticker)
            cat = market.lower()
            fpath = RAW_DIR / cat / f"{ticker}.csv"
            if fpath.exists():
                df_old = pd.read_csv(fpath, index_col=0, parse_dates=True)
            else:
                # Full download if no existing data
                df_old = yf.download(ticker, start="2017-01-01", auto_adjust=True, progress=False)
                if df_old.index.tz is not None: df_old.index = df_old.index.tz_localize(None)
                if isinstance(df_old.columns, pd.MultiIndex): df_old.columns = df_old.columns.get_level_values(0)

        # 3. Merge
        combined = pd.concat([df_old, df_new])
        combined = combined[~combined.index.duplicated(keep='last')].sort_index()

        # Keep only last 2 years
        cutoff = datetime.now() - timedelta(days=740)
        combined = combined[combined.index >= cutoff]

        # 4. Save (Postgres + CSV backup)
        if REPO:
            REPO.save(cache_key, "2y", combined)

        market = SymbolFormatter.get_market(ticker)
        cat = market.lower()
        fpath = RAW_DIR / cat / f"{ticker}.csv"
        fpath.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(fpath)

        return True
    except Exception as e:
        print(f"Error syncing {ticker}: {e}")
    return False


def main():
    lock_path = ROOT / "data" / "market_sync.lock"
    if lock_path.exists():
        if time.time() - lock_path.stat().st_mtime > 1800:
            print("Warning: Stale lock file found, removing.")
            lock_path.unlink()
        else:
            print("Aborting: Market sync already in progress (lock file exists).")
            return

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch()
    try:
        # Assuming TICKERS is defined elsewhere or should be loaded
        # Since this file seems to be a partial template, we keep the usage but fix the structure
        try:
            print(f"Live Sync v1.0: Updating {len(TICKERS)} assets...")
        except NameError:
            print("Error: TICKERS not defined. Skipping sync.")
            return

        start_time = datetime.now()

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(sync_one, TICKERS))

        elapsed = datetime.now() - start_time
        print(f"COMPLETED: {sum(1 for r in results if r)} OK | Time: {elapsed.total_seconds():.1f}s")
    finally:
        if lock_path.exists():
            try:
                lock_path.unlink()
            except Exception:
                logger.exception("Failed to remove lock file: %s", lock_path)


if __name__ == '__main__':
    main()
