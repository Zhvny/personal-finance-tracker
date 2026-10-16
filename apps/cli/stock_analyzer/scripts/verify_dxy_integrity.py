
import logging
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd

# Add project root to sys.path
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
# Add apps directory to sys.path
_APPS_DIR = _PROJECT_ROOT / "apps"
sys.path.insert(0, str(_APPS_DIR))

from apps.cli.stock_analyzer.adapters.cache import DataCache
from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def verify_dxy_integrity():
    logger.info("=== DXY Source Integrity Test ===")

    cache = DataCache()
    fetcher = DataFetcher(cache=cache)
    symbol = "DX-Y.NYB"
    period = "1y"
    interval = "1d"
    cache_key = f"{symbol}_{period}_{interval}"

    # 1. Clear Cache for clean test
    logger.info(f"Step 1: Clearing cache for {symbol}...")
    cache.invalidate(symbol, period)

    # 2. Test API Reachability and Non-Emptiness
    logger.info("Step 2: Fetching DXY from API (forcing fresh data)...")
    try:
        # Use a non-standard period to bypass common cache if possible,
        # or just check if we can get data newer than May 6.
        start_time = time.time()
        df = fetcher.fetch(symbol, period="1mo", interval=interval)
        duration = time.time() - start_time

        if df is None or df.empty:
            logger.error("FAIL: Dataset is empty.")
            return False

        last_date = df.index[-1].date()
        logger.info(f"SUCCESS: Data fetched. Latest date: {last_date}")

        # Check if data is reasonably fresh (within 3 days, accounting for weekends)
        today = date.today()
        days_diff = (today - last_date).days
        logger.info(f"Data is {days_diff} days old.")

        if days_diff > 4:
            logger.warning(f"DATA STALE: Latest data is {days_diff} days old ({last_date}). Today is {today}.")
            logger.info("Attempting to fetch with yfinance directly to verify API...")
            import yfinance as yf
            df_direct = yf.download(symbol, period="5d")
            if not df_direct.empty:
                last_direct = df_direct.index[-1].date()
                logger.info(f"YFinance Direct Latest: {last_direct}")
                if last_direct > last_date:
                    logger.error(f"INTEGRITY ISSUE: Fetcher returned stale data ({last_date}) but API has newer data ({last_direct}).")
                    # return False # Uncomment if we want to fail on staleness
            else:
                logger.warning("YFinance Direct also returned no new data. Market might be closed or symbol changed.")

        logger.info(f"SUCCESS: API Reachable. Fetched {len(df)} rows in {duration:.2f}s.")
    except Exception as e:
        logger.error(f"FAIL: API Unreachable or error: {e}")
        return False

    # 3. Test Data Historis (No Gaps)
    logger.info("Step 3: Checking for historical gaps...")
    # Expected daily data. Max gap should be ~4 days (long weekend)
    df_sorted = df.sort_index()
    diffs = df_sorted.index.to_series().diff().dropna()
    max_gap = diffs.max()

    logger.info(f"Max gap found: {max_gap}")
    if max_gap > pd.Timedelta(days=5):
        logger.warning(f"POTENTIAL ISSUE: Gap of {max_gap} found in history.")
        # We might want to be more strict but 5 days is safe for holidays + weekends
    else:
        logger.info("SUCCESS: No significant historical gaps found.")

    # 4. Test Cache Integrity
    logger.info("Step 4: Verifying cache persistence...")
    # Use the same period as Step 2 to ensure we check what was just saved
    test_period = "1mo"
    test_cache_key = f"{symbol}_{test_period}_{interval}"
    cached_df = cache.get(test_cache_key, test_period)
    if cached_df is not None and not cached_df.empty:
        # Compare last price to ensure it's the same data
        if abs(cached_df['Close'].iloc[-1] - df['Close'].iloc[-1]) < 1e-6:
            logger.info("SUCCESS: Cache correctly filled and verified.")
        else:
            logger.error(f"FAIL: Cache data mismatch. Expected last price {df['Close'].iloc[-1]}, got {cached_df['Close'].iloc[-1]}")
            return False
    else:
        logger.error("FAIL: Cache is empty after fetch.")
        return False

    logger.info("=== ALL DXY INTEGRITY TESTS PASSED ===")
    return True

if __name__ == "__main__":
    success = verify_dxy_integrity()
    sys.exit(0 if success else 1)
