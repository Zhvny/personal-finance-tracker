import io
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from .postgres_manager import DatabaseManager


class PostgresOHLCVRepository:
    """
    PostgreSQL implementation of the OHLCV Cache Repository.
    Synchronizes stock/crypto market data across all analysis agents.
    """

    def __init__(self):
        # Initialized by migration script
        pass

    def save(self, ticker: str, period: str, df: pd.DataFrame):
        sql = """
            INSERT INTO market.ohlcv_cache (ticker, period, fetched_at, data)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (ticker, period) DO UPDATE SET
                fetched_at = EXCLUDED.fetched_at,
                data = EXCLUDED.data
        """
        params = (ticker, period, datetime.now(timezone.utc), df.to_json(orient="split", date_format="iso").encode("utf-8"))
        DatabaseManager.execute(sql, params)

    def save_ohlcv(self, ticker: str, timestamp: datetime, open: float, high: float, low: float, close: float, volume: int, period: str = "1d"):
        """
        Append a single OHLCV point to the cached DataFrame for a given ticker and period.
        """
        existing = self.get(ticker, period)
        if existing:
            df, _ = existing
            # Ensure index is datetime for consistent matching
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            new_row = pd.DataFrame([{
                "Open": float(open),
                "High": float(high),
                "Low": float(low),
                "Close": float(close),
                "Volume": int(volume)
            }], index=[timestamp])

            # Combine and remove duplicates, keeping newest
            df = pd.concat([df, new_row])
            df = df[~df.index.duplicated(keep='last')]
            df = df.sort_index()
        else:
            df = pd.DataFrame([{
                "Open": float(open),
                "High": float(high),
                "Low": float(low),
                "Close": float(close),
                "Volume": int(volume)
            }], index=[timestamp])
            df.index.name = "Date"

        self.save(ticker, period, df)

    def get(self, ticker: str, period: str) -> Optional[tuple]:
        sql = "SELECT data, fetched_at FROM market.ohlcv_cache WHERE ticker = %s AND period = %s"
        rows = DatabaseManager.query(sql, (ticker, period))
        if rows:
            raw = rows[0]["data"]
            if isinstance(raw, memoryview):
                raw = raw.tobytes()
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return pd.read_json(io.StringIO(raw), orient="split"), rows[0]["fetched_at"]
        return None
