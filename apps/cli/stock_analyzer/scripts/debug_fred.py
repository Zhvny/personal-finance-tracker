
import sys
from pathlib import Path

# Add apps directory to sys.path
_HERE = Path(__file__).resolve()
_APPS_DIR = _HERE.parent.parent.parent
sys.path.insert(0, str(_APPS_DIR))

import logging

from apps.cli.stock_analyzer.adapters.fred_fetcher import FREDFetcher
from apps.cli.stock_analyzer.domain.config import AppConfig

logging.basicConfig(level=logging.INFO)

def test_fred():
    print("--- Testing FRED Fetcher ---")
    config = AppConfig.load()
    if not config.fred_api_key:
        print("Error: No FRED API Key found in config.yaml")
        return

    fetcher = FREDFetcher(config)

    print(f"Using API Key: {config.fred_api_key[:5]}...")

    # Test individual series
    for sid in ["FEDFUNDS", "UMCSENT", "DGS10"]:
        print(f"Fetching {sid}...")
        s = fetcher.fetch_series(sid, limit=5)
        if not s.empty:
            print(f"SUCCESS: {sid} latest value: {s.iloc[-1]} on {s.index[-1].date()}")
        else:
            print(f"FAILED: {sid} is empty")

    # Test macro context
    print("\nFetching Macro Context...")
    from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher
    fetcher_y = DataFetcher()
    try:
        dxy_df = fetcher_y.fetch("DX-Y.NYB", period="1y")
        if not dxy_df.empty:
            print(f"SUCCESS: DXY latest value: {dxy_df['Close'].iloc[-1]} on {dxy_df.index[-1].date()}")
        else:
            print("FAILED: DXY is empty")
    except Exception as e:
        print(f"ERROR: DXY fetch failed: {e}")

    ctx = fetcher.get_macro_context()
    print(f"Regime: {ctx['regime']}")
    print(f"RRM: {ctx['rrm']}")
    print(f"YCMO: {ctx['ycmo']}")
    print(f"LPI: {ctx['lpi']}")
    print(f"ICM: {ctx['icm']}")
    print(f"CSI: {ctx['csi']}")
    print(f"Signals: {ctx['signals']}")

if __name__ == "__main__":
    test_fred()
