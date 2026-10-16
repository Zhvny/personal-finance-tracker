
import sys
from pathlib import Path

_PROJECT_ROOT = Path(r"..")
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "packages"))
sys.path.insert(0, str(_PROJECT_ROOT / "apps"))

from stock_analyzer.adapters.cleaner import DataCleaner
from stock_analyzer.adapters.fetcher import DataFetcher
from stock_analyzer.adapters.indicators import IndicatorEngine
from stock_analyzer.domain.scoring import ScoringEngine
from stock_analyzer.use_cases.analyzer import StockAnalyzer

from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager


def check_analytics():
    try:
        DatabaseManager.initialize()

        # 1. Check DXY in cache
        print("--- CHECKING DXY CACHE ---")
        sql = "SELECT ticker, period, fetched_at FROM market.ohlcv_cache WHERE ticker IN ('DX-Y.NYB', 'DXY', 'DX=F')"
        rows = DatabaseManager.query(sql)
        for row in rows:
            print(f"Found {row['ticker']} ({row['period']}) fetched at {row['fetched_at']}")

        # 2. Check Macro Context
        print("\n--- CHECKING MACRO CONTEXT ---")
        # Simulate what StockRepository does
        from stock_analyzer.adapters.fred_fetcher import FREDFetcher
        from stock_analyzer.domain.config import AppConfig

        config = AppConfig.load(str(_PROJECT_ROOT / "apps" / "stock_analyzer" / "config.yaml"))
        fetcher = DataFetcher()
        fred_fetcher = FREDFetcher(config)

        # Manually fetch DXY to populate cache and get data
        print("Fetching DXY (DX-Y.NYB)...")
        dxy_df = fetcher.fetch("DX-Y.NYB", "3mo")
        print(f"DXY fetch complete: {len(dxy_df)} rows")

        brent_df = fetcher.fetch("CL=F", "1mo")
        macro_data = fred_fetcher.get_macro_context(brent_df)
        print(f"Regime: {macro_data['regime']}")

        # 3. Check DXY in cache AGAIN
        print("\n--- CHECKING DXY CACHE AFTER FETCH ---")
        sql = "SELECT ticker, period, fetched_at FROM market.ohlcv_cache WHERE ticker IN ('DX-Y.NYB', 'DXY', 'DX=F')"
        rows = DatabaseManager.query(sql)
        for row in rows:
            print(f"Found {row['ticker']} ({row['period']}) fetched at {row['fetched_at']}")

        # 4. Test Analyzer
        print("\n--- TESTING ANALYZER ---")
        cleaner = DataCleaner()
        indicators = IndicatorEngine()
        scoring = ScoringEngine()
        analyzer = StockAnalyzer(fetcher, cleaner, indicators, scoring, config, macro_data)

        res = analyzer.analyze_ticker("BTC-USD", dxy_df=dxy_df)
        if res is None:
            print("Result is None (Likely skipped or failed)")
        else:
            print(f"Analysis successful for BTC-USD: Signal={res.signal}, DCDS={res.dcds}, MRZG={res.mrzg}")

    except Exception as e:
        print(f"Check failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_analytics()
