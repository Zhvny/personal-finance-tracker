# core/repository.py
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from packages.core.domain.models.investment import Investment, InvestmentStatus, SellTransaction

logger = logging.getLogger(__name__)


def _pg_password(host: str = "localhost") -> str:
    pw = os.environ.get("POSTGRES_PASSWORD")
    if pw:
        return pw
    if os.environ.get("DEV_MODE") == "1" or host in ("localhost", "127.0.0.1"):
        logger.warning("POSTGRES_PASSWORD unset, using dev default (localhost only)")
        return "postgres"
    raise RuntimeError("POSTGRES_PASSWORD is not set (required outside dev/localhost)")


# Try to use the unified DatabaseManager if available in the path
try:
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
except ImportError:
    # Fallback to local connection management if packages is not in path
    class DatabaseManager:
        @staticmethod
        def get_connection():
            return psycopg2.connect(
                dbname="finance_tracker",
                user="postgres",
                password=_pg_password("localhost"),
                host="localhost",
                port="5432"
            )

        @staticmethod
        def query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
            with DatabaseManager.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, params)
                    return [dict(row) for row in cur.fetchall()]

        @staticmethod
        def execute(sql: str, params: tuple = ()) -> Any:
            with DatabaseManager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    conn.commit()
                    if "RETURNING" in sql.upper():
                        row = cur.fetchone()
                        return row[0] if row else None
                    return cur.rowcount


# ─────────────────────── Abstract Interfaces ───────────────────────

class IInvestmentRepository(ABC):
    @abstractmethod
    def save(self, investment: Investment) -> int: pass

    @abstractmethod
    def get_all(self) -> List[Investment]: pass

    @abstractmethod
    def get_by_id(self, id: int) -> Optional[Investment]: pass

    @abstractmethod
    def delete(self, id: int) -> bool: pass


class IHistoricalRepository(ABC):
    @abstractmethod
    def save_weekly_snapshot(
        self, investment_id: int, date: datetime, price_usd: float, price_idr: float
    ): pass

    @abstractmethod
    def get_weekly_history(self, investment_id: int) -> List[Dict]: pass


# ────────────────────────── Implementation ─────────────────────────

class PostgresRepository(IInvestmentRepository, IHistoricalRepository):
    """PostgreSQL implementation of the Investment Repository."""

    def __init__(self, config: Any = None):
        # Config is ignored now as we use the unified DatabaseManager/Postgres connection
        pass

    # ── Investment CRUD ─────────────────────────────────────────────

    def save(self, investment: Investment) -> int:
        # Standardize to USD for storage
        buy_price = investment.buy_price
        currency  = investment.buy_currency.upper()
        buy_price_idr = investment.buy_price_idr

        if currency == "IDR":
            from packages.core.infrastructure.external.fx_service import FXService
            fx = FXService()
            rate = Decimal(str(fx.get_rate()))
            buy_price = buy_price / rate
            currency = "USD"
            if buy_price_idr is None:
                buy_price_idr = investment.buy_price
        elif buy_price_idr is None:
            # If bought in USD, we still want to capture the IDR cost basis AT THAT TIME
            from packages.core.infrastructure.external.fx_service import FXService
            fx = FXService()
            rate = Decimal(str(fx.get_rate()))
            buy_price_idr = buy_price * rate

        sql = """
            INSERT INTO investments
               (asset_type, ticker, quantity, buy_price, buy_currency,
                buy_date, status, remaining_quantity, is_favorite, buy_price_idr)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        params = (
            investment.asset_type,
            investment.ticker,
            investment.quantity,
            buy_price,
            currency,
            investment.buy_date.date(),
            investment.status.value,
            investment.remaining_quantity,
            investment.is_favorite,
            buy_price_idr
        )

        return DatabaseManager.execute(sql, params)

    def get_all(self) -> List[Investment]:
        sql = """
            SELECT id, asset_type, ticker, quantity, buy_price, buy_currency, 
                   buy_date, status, remaining_quantity, is_favorite, created_at, buy_price_idr
            FROM investments 
            ORDER BY is_favorite DESC, created_at DESC
        """
        try:
            rows = DatabaseManager.query(sql)
            return [self._row_to_investment(row) for row in rows]
        except Exception as e:
            logger.error(f"PostgreSQL error in get_all: {e}")
            return []

    def get_all_active(self) -> List[Investment]:
        """Return investments that still have remaining quantity (not fully sold)."""
        sql = """
            SELECT id, asset_type, ticker, quantity, buy_price, buy_currency, 
                   buy_date, status, remaining_quantity, is_favorite, created_at, buy_price_idr
            FROM investments 
            WHERE status != 'sold' 
            ORDER BY is_favorite DESC, created_at DESC
        """
        try:
            rows = DatabaseManager.query(sql)
            return [self._row_to_investment(row) for row in rows]
        except Exception as e:
            logger.error(f"PostgreSQL error in get_all_active: {e}")
            return []

    def get_active_tickers(self) -> List[Dict[str, Any]]:
        """Return a list of unique tickers that have active holdings."""
        sql = """
            SELECT ticker, asset_type, SUM(remaining_quantity) as total_qty 
            FROM investments 
            WHERE status != 'sold' 
            GROUP BY ticker, asset_type 
            ORDER BY ticker ASC
        """
        try:
            return DatabaseManager.query(sql)
        except Exception as e:
            logger.error(f"PostgreSQL error in get_active_tickers: {e}")
            return []

    def get_active_lots(self, ticker: str, asset_type: Optional[str] = None) -> List[Investment]:
        """Return all active investments for a specific ticker (and optionally asset_type), ordered by buy_date ASC (FIFO)."""
        sql = """
            SELECT id, asset_type, ticker, quantity, buy_price, buy_currency, 
                   buy_date, status, remaining_quantity, is_favorite, created_at, buy_price_idr
            FROM investments 
            WHERE ticker = %s AND status != 'sold'
        """
        params = [ticker.upper()]
        if asset_type:
            sql += " AND asset_type = %s"
            params.append(asset_type.lower())
        sql += " ORDER BY buy_date ASC"

        try:
            rows = DatabaseManager.query(sql, tuple(params))
            return [self._row_to_investment(row) for row in rows]
        except Exception as e:
            logger.error(f"PostgreSQL error in get_active_lots: {e}")
            return []

    def get_by_ticker(self, ticker: str) -> List[Investment]:
        """Return all active investments for a specific ticker, ordered by buy_date ASC (FIFO)."""
        sql = """
            SELECT id, asset_type, ticker, quantity, buy_price, buy_currency, 
                   buy_date, status, remaining_quantity, is_favorite, created_at, buy_price_idr
            FROM investments 
            WHERE ticker = %s AND status != 'sold' 
            ORDER BY buy_date ASC
        """
        try:
            rows = DatabaseManager.query(sql, (ticker.upper(),))
            return [self._row_to_investment(row) for row in rows]
        except Exception as e:
            logger.error(f"PostgreSQL error in get_by_ticker: {e}")
            return []

    def get_by_id(self, id: int) -> Optional[Investment]:
        sql = """
            SELECT id, asset_type, ticker, quantity, buy_price, buy_currency, 
                   buy_date, status, remaining_quantity, is_favorite, created_at, buy_price_idr
            FROM investments 
            WHERE id = %s
        """
        rows = DatabaseManager.query(sql, (id,))
        return self._row_to_investment(rows[0]) if rows else None

    def delete(self, id: int) -> bool:
        return DatabaseManager.execute("DELETE FROM investments WHERE id = %s", (id,)) > 0

    def toggle_favorite(self, investment_id: int) -> bool:
        """Toggle the is_favorite flag for an investment."""
        sql = "UPDATE investments SET is_favorite = NOT is_favorite WHERE id = %s"
        return DatabaseManager.execute(sql, (investment_id,)) > 0

    def get_reward_points(self) -> float:
        sql = "SELECT value FROM user_stats WHERE key = 'reward_points'"
        rows = DatabaseManager.query(sql)
        return float(rows[0]['value']) if rows else 100.0

    def update_reward_points(self, delta: float):
        sql = "UPDATE user_stats SET value = (CAST(value AS NUMERIC) + %s)::TEXT, updated_at = CURRENT_TIMESTAMP WHERE key = 'reward_points'"
        return DatabaseManager.execute(sql, (delta,)) > 0

    # ── Historical Prices ────────────────────────────────────────────

    def save_weekly_snapshot(
        self, investment_id: int, date: datetime, price_usd: float, price_idr: float
    ):
        sql = """
            INSERT INTO historical_prices 
               (investment_id, snapshot_date, price_usd, price_idr)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (investment_id, snapshot_date) DO UPDATE SET 
                price_usd = EXCLUDED.price_usd, 
                price_idr = EXCLUDED.price_idr
        """
        DatabaseManager.execute(sql, (investment_id, date.date(), price_usd, price_idr))

    def get_latest_price(self, investment_id: int) -> Optional[Dict]:
        """Get the absolute latest price snapshot from historical_prices."""
        sql = """
            SELECT investment_id, snapshot_date, price_usd, price_idr 
            FROM historical_prices 
            WHERE investment_id = %s 
            ORDER BY snapshot_date DESC LIMIT 1
        """
        try:
            rows = DatabaseManager.query(sql, (investment_id,))
            return rows[0] if rows else None
        except Exception:
            return None

    def get_weekly_history(self, investment_id: int) -> List[Dict]:
        sql = """
            SELECT investment_id, snapshot_date, price_usd, price_idr 
            FROM historical_prices 
            WHERE investment_id = %s 
            ORDER BY snapshot_date
        """
        return DatabaseManager.query(sql, (investment_id,))

    # ── Sell Transactions ────────────────────────────────────────────

    def save_sell_transaction(
        self, investment_id: int, investment: Investment, sell: SellTransaction
    ) -> int:
        """Persist a sell transaction and update the parent investment's status."""
        sql_sell = """
            INSERT INTO sell_transactions
               (investment_id, sell_date, quantity, sell_price_usd, sell_currency,
                fees, realized_pl_idr, realized_pl_pct, ticker)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        sell_price_usd = sell.sell_price
        if sell.sell_currency.upper() == "IDR":
            from packages.core.infrastructure.external.fx_service import FXService
            fx = FXService()
            rate = Decimal(str(fx.get_rate()))
            sell_price_usd = sell.sell_price / rate

        sell_id = DatabaseManager.execute(sql_sell, (
            investment_id,
            sell.sell_date.date(),
            sell.quantity,
            sell_price_usd,
            sell.sell_currency,
            sell.fees,
            sell.realized_pl,
            sell.realized_pl_pct,
            investment.ticker,
        ))

        DatabaseManager.execute(
            "UPDATE investments SET status = %s, remaining_quantity = %s WHERE id = %s",
            (investment.status.value, investment.remaining_quantity, investment_id),
        )
        return sell_id

    def get_realized_pl_summary(self, year: Optional[int] = None) -> dict:
        """Aggregate realized P/L stats, optionally filtered by year."""
        query = """
            SELECT
                SUM(realized_pl_idr)                                    AS total_realized_pl,
                COUNT(*)                                                 AS total_sells,
                SUM(CASE WHEN realized_pl_idr > 0 THEN 1 ELSE 0 END)   AS wins,
                SUM(CASE WHEN realized_pl_idr < 0 THEN 1 ELSE 0 END)   AS losses
            FROM sell_transactions
        """
        params = []
        if year:
            query += " WHERE EXTRACT(YEAR FROM sell_date) = %s"
            params.append(year)

        rows = DatabaseManager.query(query, tuple(params))
        row = rows[0]
        total_sells = row['total_sells'] or 0
        wins = row['wins'] or 0
        return {
            "total_realized_pl": float(row['total_realized_pl'] or 0),
            "total_sells": total_sells,
            "wins": wins,
            "losses": row['losses'] or 0,
            "win_rate": (wins / total_sells * 100) if total_sells else 0,
        }

    def get_all_sell_transactions(self) -> List[Dict]:
        """All sell transactions joined with their ticker symbol."""
        sql = """
            SELECT s.*, COALESCE(s.ticker, i.ticker, '---') as ticker
            FROM sell_transactions s
            LEFT JOIN investments i ON s.investment_id = i.id
            ORDER BY s.sell_date DESC
        """
        rows = DatabaseManager.query(sql)
        results = []
        for row in rows:
            r = dict(row)
            if hasattr(r['sell_date'], 'isoformat'):
                r['sell_date'] = r['sell_date'].isoformat()
            results.append(r)
        return results

    def prune_stale(self) -> dict:
        """
        Remove investments that are no longer useful (fully sold, zero quantity).
        """
        # Candidates: status=sold AND remaining_quantity == 0
        sql_select = "SELECT id FROM investments WHERE status = 'sold' AND (remaining_quantity = 0 OR remaining_quantity IS NULL)"
        deleted_ids = [row['id'] for row in DatabaseManager.query(sql_select)]
        deleted = 0

        if deleted_ids:
            placeholders = ",".join(["%s"] * len(deleted_ids))
            DatabaseManager.execute(
                f"DELETE FROM historical_prices WHERE investment_id IN ({placeholders})",
                tuple(deleted_ids),
            )
            DatabaseManager.execute(
                f"DELETE FROM investments WHERE id IN ({placeholders})",
                tuple(deleted_ids),
            )
        deleted = len(deleted_ids)

        kept_realized = DatabaseManager.query("SELECT COUNT(*) FROM investments WHERE status = 'sold' AND remaining_quantity > 0")[0]['count']
        kept_holding = DatabaseManager.query("SELECT COUNT(*) FROM investments WHERE status != 'sold'")[0]['count']

        return {"deleted": deleted, "kept_realized": kept_realized, "kept_holding": kept_holding}

    def _row_to_investment(self, row: Dict) -> Investment:
        inv = Investment(
            asset_type=row["asset_type"],
            ticker=row["ticker"],
            quantity=Decimal(str(row["quantity"])),
            buy_price=Decimal(str(row["buy_price"])),
            buy_currency=row["buy_currency"],
            buy_price_idr=Decimal(str(row["buy_price_idr"])) if row.get("buy_price_idr") is not None else None,
            buy_date=row["buy_date"],
            id=row["id"],
            is_favorite=bool(row["is_favorite"])
        )
        inv.status = InvestmentStatus(row["status"]) if row["status"] else InvestmentStatus.HOLDING
        inv.remaining_quantity = (
            Decimal(str(row["remaining_quantity"]))
            if row["remaining_quantity"] is not None
            else inv.quantity
        )
        return inv

# Standard naming for the repository used by the app
InvestmentRepository = PostgresRepository

