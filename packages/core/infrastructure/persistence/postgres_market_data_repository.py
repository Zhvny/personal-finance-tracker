from typing import List, Optional

from packages.core.domain.models import MarketData
from packages.core.domain.repositories.market_data_repository import IMarketDataRepository

from .postgres_manager import DatabaseManager


class PostgresMarketDataRepository(IMarketDataRepository):
    """
    PostgreSQL implementation of the Market Data Repository.
    Handles persistence of latest prices in the 'market.latest_prices' table.
    """

    def save(self, data: MarketData) -> bool:
        """
        Upsert latest price for a ticker.
        """
        sql = """
            INSERT INTO market.latest_prices (ticker, price, timestamp, change_pct, volume, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker) DO UPDATE SET
                price = EXCLUDED.price,
                timestamp = EXCLUDED.timestamp,
                change_pct = EXCLUDED.change_pct,
                volume = EXCLUDED.volume,
                metadata = EXCLUDED.metadata
        """
        params = (
            data.ticker,
            data.price,
            data.timestamp,
            data.change_pct,
            data.volume,
            data.metadata
        )
        try:
            DatabaseManager.execute(sql, params)
            return True
        except Exception:
            return False

    def get_latest(self, ticker: str) -> Optional[MarketData]:
        """
        Fetch the latest price for a ticker.
        """
        sql = """
            SELECT ticker, price, timestamp, change_pct, volume, metadata 
            FROM market.latest_prices 
            WHERE ticker = %s
        """
        rows = DatabaseManager.query(sql, (ticker,))
        if rows:
            row = rows[0]
            # Ensure price and change_pct are floats as decimal.Decimal might be returned from psycopg2
            return MarketData(
                ticker=row["ticker"],
                price=float(row["price"]),
                timestamp=row["timestamp"],
                change_pct=float(row["change_pct"]) if row["change_pct"] is not None else None,
                volume=row["volume"],
                metadata=row["metadata"]
            )
        return None

    def get_history(self, ticker: str, limit: int = 24) -> List[MarketData]:
        """
        Return history (currently just returns the latest price in a list as per objective).
        """
        latest = self.get_latest(ticker)
        return [latest] if latest else []
