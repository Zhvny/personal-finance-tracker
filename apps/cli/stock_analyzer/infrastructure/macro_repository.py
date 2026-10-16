import logging
from typing import Any, Dict

import pandas as pd

from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher
from apps.cli.stock_analyzer.adapters.fred_fetcher import FREDFetcher

logger = logging.getLogger(__name__)

class MacroRepository:
    """Central hub for macro data (DXY, Brent, FRED)."""

    def __init__(self, fred_fetcher: FREDFetcher, data_fetcher: DataFetcher):
        self.fred = fred_fetcher
        self.fetcher = data_fetcher
        self._cache: Dict[str, Any] = {}
        self._initialized = False

    def initialize(self):
        """Startup initialization for macro datasets."""
        logger.info("[MacroRepo] Initializing macro datasets concurrently...")
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=3) as executor:
                f_dxy = executor.submit(self.get_dxy)
                f_brent = executor.submit(self.get_brent)
                f_fred = executor.submit(self.get_fred_context)
                f_dxy.result()
                f_brent.result()
                ctx = f_fred.result()

            if ctx and ctx.get('regime'):
                self._initialized = True
                logger.info("[MacroRepo] Macro datasets initialized successfully.")
            else:
                logger.warning("[MacroRepo] Initialization completed but macro regime is missing.")
        except Exception as e:
            logger.error(f"[MacroRepo] Initialization failed: {e}")

    def get_dxy(self, force_refresh: bool = False) -> pd.DataFrame:
        """Fetch DXY (US Dollar Index) data."""
        try:
            if force_refresh:
                symbol = self.fetcher.normalize("DX-Y.NYB")
                # Invalidate both yfinance cache and Repo cache
                self.fetcher.cache.invalidate(f"{symbol}_2y_1d", period="2y")

            # force_cache=False allows population if missing
            df = self.fetcher.fetch("DX-Y.NYB", period="2y", force_cache=False)
            self._cache['dxy'] = df
            return df
        except Exception as e:
            logger.error(f"[MacroRepo] DXY fetch failed: {e}")
            return pd.DataFrame()

    def get_brent(self, force_refresh: bool = False) -> pd.DataFrame:
        """Fetch Brent Crude Oil data."""
        try:
            if force_refresh:
                symbol = self.fetcher.normalize("BZ=F")
                self.fetcher.cache.invalidate(f"{symbol}_2y_1d", period="2y")

            df = self.fetcher.fetch("BZ=F", period="2y", force_cache=False)
            self._cache['brent'] = df
            return df
        except Exception as e:
            logger.error(f"[MacroRepo] Brent fetch failed: {e}")
            return pd.DataFrame()

    def get_fred_context(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetch FRED macro context (regime, signals, etc)."""
        try:
            brent_df = self._cache.get('brent')
            if brent_df is None or brent_df.empty or force_refresh:
                brent_df = self.get_brent(force_refresh=force_refresh)

            context = self.fred.get_macro_context(brent_df=brent_df, force_refresh=force_refresh)
            self._cache['fred_context'] = context
            return context
        except Exception as e:
            logger.error(f"[MacroRepo] FRED context fetch failed: {e}")
            return self._cache.get('fred_context', {})

    def invalidate_cache(self):
        """Clear the local repository cache and trigger full refreshes."""
        self._cache.clear()
        logger.info("[MacroRepo] Cache invalidated. Triggering background refresh...")
        # Trigger forced refreshes
        self.get_dxy(force_refresh=True)
        self.get_brent(force_refresh=True)
        self.get_fred_context(force_refresh=True)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
