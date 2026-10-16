import concurrent.futures
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

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
RAW_LIST: list[str] = []

def download_one(ticker):
    try:
        # Categorization based on normalized ticker
        market = SymbolFormatter.get_market(ticker)
        cat = market.lower()

        # Validation before fetch
        if not SymbolFormatter.validate(ticker):
            print(f"Skipping invalid symbol: {ticker}")
            return False

        df = yf.download(ticker, start="2017-01-01", auto_adjust=True, progress=False)
        if df is not None and not df.empty:
            # Strip timezone info to prevent 'Cannot compare dtypes' errors
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if len(df) >= 100:
                # Save to Postgres
                if REPO:
                    cache_key = f"{ticker}_2y_1d"
                    REPO.save(cache_key, "2y", df)

                # Secondary backup to CSV
                d = RAW_DIR / cat
                d.mkdir(parents=True, exist_ok=True)
                fpath = d / f"{ticker}.csv"
                df.to_csv(fpath)
                return True
        else:
            if df is not None and len(df) < 100:
                print(f"Insufficient data for {ticker}: {len(df)} rows.")
    except Exception as e:
        print(f"Error downloading {ticker}: {e}")
    return False

def main():
    print(f"Parallel Sync v4.5: Target {len(TICKERS)} Tickers (Normalized).")
    # Deduplication check
    print(f"Deduplicated from {len(RAW_LIST)} raw entries.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(download_one, TICKERS))

    print(f"COMPLETED: {sum(1 for r in results if r)} assets OK.")

if __name__ == "__main__":
    main()
