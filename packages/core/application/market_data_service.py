import logging
from typing import List, Optional

from packages.core.domain.repositories.market_data_repository import IMarketDataRepository
from packages.core.infrastructure.external.yfinance_fetcher import YFinanceFetcher
from packages.core.infrastructure.persistence.postgres_ohlcv_repository import PostgresOHLCVRepository


class MarketDataService:
    def __init__(self, repository: IMarketDataRepository, ohlcv_repo: PostgresOHLCVRepository = None):
        self.repository = repository
        self.ohlcv_repo = ohlcv_repo or PostgresOHLCVRepository()

    def update_all_tickers(self, watchlist_path: str):
        """
        Refactored to implement update logic directly, as the external UseCase is missing.
        Fetch jaringan diparalelkan (bounded); penulisan DB tetap di thread utama.
        """
        tickers = self._load_watchlist(watchlist_path)
        logging.info(f"Starting market data update for {len(tickers)} tickers...")
        if not tickers:
            return

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _fetch(tkr: str):
            try:
                return tkr, YFinanceFetcher.fetch_latest_price(tkr)
            except Exception as e:
                logging.error(f"Failed to update {tkr}: {e}")
                return tkr, None

        with ThreadPoolExecutor(max_workers=min(8, len(tickers))) as pool:
            futures = [pool.submit(_fetch, t) for t in tickers]
            for fut in as_completed(futures):
                ticker, data = fut.result()
                if not data:
                    continue
                try:
                    # Persist to OHLCV cache
                    self.ohlcv_repo.save_ohlcv(
                        ticker=ticker,
                        timestamp=data.timestamp,
                        open=data.price,
                        high=data.price,
                        low=data.price,
                        close=data.price,
                        volume=0
                    )
                    # Persist to latest prices repository
                    self.repository.save(data)
                    logging.info(f"Updated {ticker}: {data.price}")
                except Exception as e:
                    logging.error(f"Failed to persist {ticker}: {e}")

    def get_price(self, ticker: str) -> Optional[float]:
        data = self.repository.get_latest(ticker)
        if data:
            return data.price
        return None

    def _load_watchlist(self, path: str) -> List[str]:
        import os

        from ..utils.symbol_utils import SymbolFormatter

        if not os.path.exists(path):
            return []

        tickers = []
        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or line.endswith(":"):
                        continue

                    # Centralized Normalization
                    norm_ticker = SymbolFormatter.normalize(line)
                    tickers.append(norm_ticker)
        except Exception as e:
            logging.error(f"Error loading watchlist {path}: {e}")

        return list(set(tickers))
