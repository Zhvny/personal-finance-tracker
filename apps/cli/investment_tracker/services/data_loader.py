import logging

import numpy as np

from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher


class DataLoader:
    def __init__(self, fetcher: DataFetcher = None):
        self.fetcher = fetcher or DataFetcher()

    def get_returns(self, ticker: str, timeframe: str = '2y') -> np.ndarray:
        """
        Fetch historical returns for a ticker and return as a normalized NumPy array.
        Used by Genetic Optimizer for real-world risk/reward modeling.
        """
        try:
            returns_series = self.fetcher.get_returns(ticker, period=timeframe)
            if returns_series.empty:
                logging.warning(f"[DataLoader] No returns found for {ticker}")
                return np.array([])

            # Convert to numpy and handle any NaNs/Infs that might have slipped through
            returns = returns_series.values
            returns = returns[np.isfinite(returns)]

            return returns
        except Exception as e:
            logging.error(f"[DataLoader] Error fetching returns for {ticker}: {e}")
            return np.array([])
