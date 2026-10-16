import asyncio
import logging
import time
from typing import Any, Dict, Optional

import pandas as pd

from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher
from apps.cli.stock_analyzer.adapters.fred_fetcher import FREDFetcher
from apps.cli.stock_analyzer.domain.config import AppConfig

logger = logging.getLogger("api.repository.stock")

from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager


class StockRepository:
    def __init__(self, config: AppConfig):
        self.config = config
        self.fetcher = DataFetcher()
        self.fred_fetcher = FREDFetcher(config)
        self._macro_cache = {"data": None, "timestamp": 0, "dxy": None}
        self._cache_ttl = 300 # 5 minutes
        self._macro_lock = asyncio.Lock()
        self._dxy_max_retries = 3
        self._dxy_retry_delay = 5 # seconds

    async def get_favorites(self) -> list[str]:
        """Fetch all favorite tickers from the database."""
        try:
            sql = "SELECT ticker FROM market.favorites ORDER BY created_at DESC"
            rows = DatabaseManager.query(sql)
            return [r['ticker'] for r in rows]
        except Exception as e:
            logger.error(f"Error fetching favorites: {e}")
            return []

    async def add_favorite(self, ticker: str) -> bool:
        """Add a ticker to the favorites list."""
        try:
            sql = "INSERT INTO market.favorites (ticker) VALUES (%s) ON CONFLICT (ticker) DO NOTHING"
            DatabaseManager.execute(sql, (ticker.upper(),))
            return True
        except Exception as e:
            logger.error(f"Error adding favorite {ticker}: {e}")
            return False

    async def remove_favorite(self, ticker: str) -> bool:
        """Remove a ticker from the favorites list."""
        try:
            sql = "DELETE FROM market.favorites WHERE ticker = %s"
            DatabaseManager.execute(sql, (ticker.upper(),))
            return True
        except Exception as e:
            logger.error(f"Error removing favorite {ticker}: {e}")
            return False

    async def fetch_ticker_data(self, ticker: str, period: str = "2y") -> Optional[pd.DataFrame]:
        """Fetch historical data for a ticker with timeout and retry logic."""
        start_time = time.time()
        logger.info(f"Fetching data for {ticker} (period={period})")

        try:
            # Wrap synchronous fetcher in thread to keep loop non-blocking
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(None, self.fetcher.fetch, ticker, period)

            elapsed = time.time() - start_time
            if df is not None and not df.empty:
                logger.info(f"Successfully fetched {ticker} in {elapsed:.2f}s ({len(df)} rows)")
                return df
            else:
                logger.warning(f"No data returned for {ticker} in {elapsed:.2f}s")
                return None
        except Exception as e:
            logger.error(f"Error fetching {ticker}: {str(e)}")
            return None

    async def get_macro_context(self) -> Dict[str, Any]:
        """Get cached macro context or fetch fresh data."""
        now = time.time()
        if self._macro_cache["data"] and (now - self._macro_cache["timestamp"]) < self._cache_ttl:
            return self._macro_cache["data"]

        async with self._macro_lock:
            # Re-check cache inside lock
            now = time.time()
            if self._macro_cache["data"] and (now - self._macro_cache["timestamp"]) < self._cache_ttl:
                return self._macro_cache["data"]

            logger.info("Macro cache expired or empty, fetching fresh macro context")
            try:
                loop = asyncio.get_event_loop()
                # Fetch Brent immediately for core macro context
                brent_df = await loop.run_in_executor(None, self.fetcher.fetch, "CL=F", "1mo")
                macro_data = await loop.run_in_executor(None, self.fred_fetcher.get_macro_context, brent_df)

                self._macro_cache["data"] = macro_data
                self._macro_cache["timestamp"] = now

                # Start DXY fetch in background if not already fetching
                if not self._macro_cache.get("is_syncing_dxy"):
                    asyncio.create_task(self._sync_dxy_background())

                return macro_data
            except Exception as e:
                logger.error(f"Failed to fetch macro context: {e}")

                # Still try to start DXY sync even if FRED fails
                if not self._macro_cache.get("is_syncing_dxy"):
                    asyncio.create_task(self._sync_dxy_background())

                if self._macro_cache["data"]:
                    return self._macro_cache["data"]
                # Fallback structure with nulls to prevent frontend crashes (Task 8 Audit)
                return {
                    "status": "unavailable",
                    "regime": "SYNCING",
                    "lpi": None,
                    "ycmo": None,
                    "csi": None
                }

    async def _sync_dxy_background(self):
        """Fetch DXY data in background with retry logic and 3mo window."""
        self._macro_cache["is_syncing_dxy"] = True
        max_retries = self._dxy_max_retries
        retry_delay = self._dxy_retry_delay

        for attempt in range(max_retries):
            try:
                logger.info(f"[DXY] Starting background sync (3mo window), attempt {attempt+1}/{max_retries}...")
                loop = asyncio.get_event_loop()

                # Use 3mo window for better statistical baseline
                dxy_df = await loop.run_in_executor(None, self.fetcher.fetch, "DX-Y.NYB", "3mo")

                if dxy_df is not None and not dxy_df.empty:
                    self._macro_cache["dxy"] = dxy_df
                    logger.info(f"[DXY] Background sync complete ({len(dxy_df)} rows)")
                    break
                else:
                    logger.warning(f"[DXY] Fetch returned empty dataframe on attempt {attempt+1}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
            except Exception as e:
                logger.error(f"[DXY] Background sync failed on attempt {attempt+1}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)

        self._macro_cache["is_syncing_dxy"] = False

    async def get_dxy_status(self) -> Dict[str, Any]:
        """Get current status of DXY sync."""
        return {
            "is_ready": self._macro_cache["dxy"] is not None and not self._macro_cache["dxy"].empty,
            "is_syncing": self._macro_cache.get("is_syncing_dxy", False)
        }

    async def get_dxy_data(self) -> Optional[pd.DataFrame]:
        """Get cached or fresh DXY data."""
        return self._macro_cache["dxy"]
