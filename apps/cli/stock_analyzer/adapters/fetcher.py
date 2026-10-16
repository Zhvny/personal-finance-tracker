import logging
import threading
import time

import pandas as pd
import yfinance as yf
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from apps.cli.stock_analyzer.adapters.cache import DataCache
from packages.core.utils.symbol_utils import SymbolFormatter


class DataFetcher:
    def __init__(self, cache: DataCache = None):
        self.cache = cache or DataCache()

    @staticmethod
    def get_category(ticker: str) -> str:
        return SymbolFormatter.get_market(ticker)

    def normalize(self, symbol: str, category: str = None) -> str:
        return SymbolFormatter.normalize(symbol, market=category)

    def _normalize(self, symbol: str, category: str = None) -> str:
        norm = self.normalize(symbol, category)
        return norm

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_not_exception_type(ValueError),
        reraise=True,
    )
    def fetch(self, symbol: str, period: str = '2y', interval: str = '1d', category: str = None, force_cache: bool = False) -> pd.DataFrame:
        start_time = time.time()
        symbol_orig = str(symbol).replace('$', '')
        symbol = self._normalize(symbol_orig, category)
        cache_key = f'{symbol}_{period}_{interval}'

        is_dxy = "DX-Y.NYB" in symbol or symbol_orig.upper() == "DXY"

        # Use the pure symbol for Postgres cache mapping, cache_key for SQLite if needed
        # But DataCache.get/set currently takes (ticker, period)
        cached = self.cache.get(symbol, period)
        if cached is not None:
            if is_dxy:
                logging.info(f'[DXY] cache hit | rows: {len(cached)}')
            if hasattr(cached.index, 'tz') and cached.index.tz is not None:
                cached.index = cached.index.tz_localize(None)
            return cached

        if is_dxy:
            logging.info('[DXY] cache miss')

        if force_cache: return pd.DataFrame()

        logging.info(f'[Fetcher] Requesting {symbol}...')
        result = [None]
        def _download():
            try:
                if '=' in symbol or '^' in symbol:
                    df = yf.download(symbol, period=period, interval=interval, progress=False, threads=False)
                else:
                    tk = yf.Ticker(symbol)
                    df = tk.history(period=period, interval=interval, auto_adjust=True)
                    if df is None or df.empty:
                        df = yf.download(symbol, period=period, interval=interval, progress=False, threads=False)
                if df is not None and not df.empty:
                    if hasattr(df.index, 'tz') and df.index.tz is not None:
                        df.index = df.index.tz_localize(None)
                result[0] = df
            except Exception:
                logging.exception("Failed to download data for symbol: %s", symbol)

        t = threading.Thread(target=_download, daemon=True)
        t.start()
        t.join(timeout=30)

        df = result[0]
        duration = time.time() - start_time

        if df is None or df.empty:
            if is_dxy:
                logging.error(f'[DXY] fetch failed | duration: {duration:.2f}s')
            stale = self.cache.get(symbol, period, allow_stale=True)
            if stale is not None: return stale
            raise ValueError(f'No data for {symbol}')

        # Standard normalization & ordering
        if not df.index.is_monotonic_increasing:
            df = df.sort_index()

        if hasattr(df.index, 'tz') and df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        if is_dxy:
            logging.info(f'[DXY] fetch success | rows loaded: {len(df)} | duration: {duration:.2f}s')

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.loc[:, ~df.columns.duplicated()]

        self.cache.set(symbol, period, df)
        return df.copy()

    def get_returns(self, symbol: str, period: str = '2y', interval: str = '1d') -> pd.Series:
        """Fetch data and calculate percentage returns."""
        df = self.fetch(symbol, period=period, interval=interval)
        # Use 'Close' or the first available column if Close is missing
        col = 'Close' if 'Close' in df.columns else df.columns[0]
        return df[col].pct_change().dropna()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_not_exception_type(ValueError),
        reraise=True,
    )
    def fetch_intraday(self, ticker: str, period: str = '7d', interval: str = '1m', category: str = None) -> pd.DataFrame:
        """Fetch high-resolution intraday data. 
        Limits: 1m (last 7-9d), 5m (last 60d)."""
        start_time = time.time()
        ticker_orig = str(ticker).replace('$', '')
        ticker = self._normalize(ticker_orig, category)

        cache_key = f"intraday_{period}_{interval}"
        cached = self.cache.get(ticker, cache_key)
        if cached is not None:
            logging.info(f'[Fetcher] Intraday cache hit for {ticker} ({period}/{interval})')
            if hasattr(cached.index, 'tz') and cached.index.tz is not None:
                cached.index = cached.index.tz_localize(None)
            return cached

        # Validation based on yfinance limits
        if interval == '1m' and period not in ['1d', '5d', '7d']:
            logging.warning(f'[Fetcher] 1m interval usually limited to 7d. Requested: {period}')
        if interval == '5m' and 'd' in period and int(period.replace('d', '')) > 60:
            logging.warning(f'[Fetcher] 5m interval usually limited to 60d. Requested: {period}')

        logging.info(f'[Fetcher] Requesting intraday {ticker} ({period}/{interval})...')

        result = [None]
        def _download():
            try:
                # Intraday usually works better with download() for specific intervals
                df = yf.download(ticker, period=period, interval=interval, progress=False, threads=False)
                if df is not None and not df.empty:
                    if hasattr(df.index, 'tz') and df.index.tz is not None:
                        df.index = df.index.tz_localize(None)
                result[0] = df
            except Exception as e:
                logging.error(f'[Fetcher] Intraday error for {ticker}: {e}')

        t = threading.Thread(target=_download, daemon=True)
        t.start()
        t.join(timeout=30)

        df = result[0]
        duration = time.time() - start_time

        if df is None or df.empty:
            logging.error(f'[Fetcher] Intraday fetch failed for {ticker} | duration: {duration:.2f}s')
            stale = self.cache.get(ticker, cache_key, allow_stale=True)
            if stale is not None: return stale
            raise ValueError(f'No intraday data for {ticker}')

        if not df.index.is_monotonic_increasing:
            df = df.sort_index()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.loc[:, ~df.columns.duplicated()]

        self.cache.set(ticker, cache_key, df)
        return df.copy()
