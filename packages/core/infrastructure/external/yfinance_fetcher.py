import logging
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from packages.core.domain.models.market_data import MarketData
from packages.core.utils.symbol_utils import SymbolFormatter


class YFinanceFetcher:
    @staticmethod
    def fetch_latest_price(ticker: str) -> Optional[MarketData]:
        try:
            # Aggressively strip '$' just in case
            ticker = str(ticker).replace("$", "")

            # Normalize ticker before fetch
            norm_ticker = SymbolFormatter.normalize(ticker)

            tk = yf.Ticker(norm_ticker)

            # Use fast_info if available or history
            info = tk.fast_info
            price = None

            if info and "last_price" in info:
                price = info["last_price"]

            # If fast_info failed or returned None, try history
            if price is None or pd.isna(price):
                # Fallback to history with 5d period for robustness (especially IDX)
                df = tk.history(period="5d")
                if not df.empty and "Close" in df.columns:
                    price = df["Close"].dropna().iloc[-1]

            if price is None or pd.isna(price):
                return None

            # Standardize timestamp to UTC
            now = datetime.utcnow()

            return MarketData(
                ticker=ticker, # Store original ticker for lookups
                price=float(price),
                timestamp=now,
                metadata=f"Yahoo Symbol: {norm_ticker}"
            )
        except Exception as e:
            logging.error(f"Error fetching {ticker} (norm: {norm_ticker if 'norm_ticker' in locals() else 'N/A'}) from yfinance: {e}")
            return None

    @staticmethod
    def fetch_history(ticker: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Fetches historical price data for a specific ticker and range.
        Returns a pandas DataFrame with 'Close' prices.
        """
        try:
            ticker = str(ticker).replace("$", "")
            norm_ticker = SymbolFormatter.normalize(ticker)
            tk = yf.Ticker(norm_ticker)

            # Use daily interval for history
            df = tk.history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval="1d"
            )
            return df
        except Exception as e:
            logging.error(f"Error fetching history for {ticker}: {e}")
            return pd.DataFrame()

    @staticmethod
    def fetch_batch_latest(tickers: List[str]) -> Dict[str, MarketData]:
        # yfinance.download is faster for batches
        results = {}
        if not tickers:
            return results

        try:
            # Map original tickers to normalized ones and strip '$' just in case
            tickers = [t.replace("$", "") for t in tickers]
            ticker_map = {SymbolFormatter.normalize(t): t for t in tickers}
            norm_tickers = list(ticker_map.keys())

            # Use 5d period for more reliability (handles weekend/holiday gaps better)
            # interval='1m' is good for intraday, but fallback to '1d' if needed
            df = yf.download(norm_tickers, period="5d", interval="1m", progress=False, group_by="ticker", auto_adjust=True)

            # Fallback if 1m data is missing (e.g. for some futures or indices)
            if df.empty:
                df = yf.download(norm_tickers, period="5d", interval="1d", progress=False, group_by="ticker", auto_adjust=True)

            now = datetime.utcnow()

            for norm_t in norm_tickers:
                try:
                    orig_t = ticker_map[norm_t]

                    if len(norm_tickers) == 1:
                        ticker_df = df
                    else:
                        ticker_df = df[norm_t]

                    if not ticker_df.empty:
                        # Get last valid price
                        last_price = ticker_df["Close"].dropna().iloc[-1]
                        results[orig_t] = MarketData(
                            ticker=orig_t,
                            price=float(last_price),
                            timestamp=now,
                            metadata=f"Yahoo Symbol: {norm_t}"
                        )
                except Exception:
                    continue
        except Exception as e:
            logging.error(f"Batch fetch error: {e}")

        return results
