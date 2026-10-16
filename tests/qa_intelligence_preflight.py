"""
QA Intelligence Pre-flight Network Validation
Ensures external dependencies (yfinance, crypto APIs) are reachable before running deep audits.
"""

import logging
import os
import sys

# Add project root to path to resolve packages
sys.path.append(os.getcwd())

from packages.core.infrastructure.external.fx_service import FXService
from packages.core.infrastructure.external.yfinance_fetcher import YFinanceFetcher

# Setup minimal logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def check_yfinance():
    """Validates connectivity to Yahoo Finance via yfinance."""
    ticker = "AAPL"
    logging.info(f"Checking yfinance connectivity (Symbol: {ticker})...")
    try:
        data = YFinanceFetcher.fetch_latest_price(ticker)
        if data and data.price > 0:
            logging.info(f"Successfully fetched {ticker} price: {data.price}")
            return True
        else:
            logging.error(f"yfinance returned invalid data for {ticker}")
            return False
    except Exception as e:
        logging.error(f"yfinance connectivity check failed: {e}")
        return False

def check_crypto():
    """Validates connectivity to a crypto price source (via yfinance as per project convention)."""
    # Project uses yfinance for crypto too (e.g. BTC-USD)
    ticker = "BTC-USD"
    logging.info(f"Checking crypto connectivity (Symbol: {ticker})...")
    try:
        data = YFinanceFetcher.fetch_latest_price(ticker)
        if data and data.price > 0:
            logging.info(f"Successfully fetched {ticker} price: {data.price}")
            return True
        else:
            logging.error(f"Crypto fetch returned invalid data for {ticker}")
            return False
    except Exception as e:
        logging.error(f"Crypto connectivity check failed: {e}")
        return False

def check_fx_api():
    """Validates connectivity to the FX API (Exchange Rate API)."""
    logging.info("Checking FX API connectivity (USD/IDR)...")
    try:
        service = FXService()
        rate = service.get_rate()
        # Default fallback is 16000.0, if we get exactly 16000.0 AND the fetch failed, it might be a silent failure.
        # But FXService.get_rate() caches and catches exceptions silently.

        # Check if cache was updated (last_fetch > 0)
        if service._FX_CACHE["last_fetch"] > 0:
            logging.info(f"Successfully fetched FX rate: {rate}")
            return True
        else:
            logging.error("FX API fetch failed (using fallback/default)")
            return False
    except Exception as e:
        logging.error(f"FX API connectivity check failed: {e}")
        return False

def main():
    logging.info("Starting QA Intelligence Pre-flight Validation...")

    results = {
        "yfinance": check_yfinance(),
        "crypto": check_crypto(),
        "fx_api": check_fx_api()
    }

    failed = [k for k, v in results.items() if not v]

    if failed:
        logging.error(f"PRE-FLIGHT FAILED. Unreachable endpoints: {', '.join(failed)}")
        sys.exit(1)

    logging.info("PRE-FLIGHT SUCCESS. All external endpoints are reachable.")
    sys.exit(0)

if __name__ == "__main__":
    main()
