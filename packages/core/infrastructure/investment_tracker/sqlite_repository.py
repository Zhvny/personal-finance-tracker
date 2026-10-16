import logging
import os
import sqlite3
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from packages.core.domain.models.investment import Investment, InvestmentStatus, SellTransaction

from .interfaces import IInvestmentRepository

try:
    from packages.core.infrastructure.persistence.database import Database
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
    from psycopg2.extras import RealDictCursor
except ImportError:

    class Database:
        @staticmethod
        def query(db_path, sql, params=()):
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                return [dict(r) for r in conn.execute(sql, params).fetchall()]

        @staticmethod
        def execute(db_path, sql, params=()):
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute(sql, params)
                return cursor.lastrowid if "INSERT" in sql.upper() else cursor.rowcount

        @staticmethod
        def execute_script(db_path, script):
            with sqlite3.connect(db_path) as conn:
                conn.executescript(script)

        @staticmethod
        def _is_postgres_target(db_path):
            return False

        @staticmethod
        def _get_schema(db_path):
            return None

    DatabaseManager = None

logger = logging.getLogger(__name__)


class SQLiteInvestmentRepository(IInvestmentRepository):
    """
    Investment Repository implementation supporting both local SQLite storage
    and canonical PostgreSQL persistence via Database redirection.
    """

    def __init__(self, db_path: str = "data/portfolio.db"):
        if not os.path.isabs(db_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, db_path)
        else:
            self.db_path = db_path

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        script = """
            CREATE TABLE IF NOT EXISTS investments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_type TEXT NOT NULL,
                ticker TEXT NOT NULL,
                quantity NUMERIC NOT NULL,
                buy_price NUMERIC NOT NULL,
                buy_currency TEXT NOT NULL,
                buy_date TEXT NOT NULL,
                status TEXT NOT NULL,
                remaining_quantity NUMERIC,
                is_favorite BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sell_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investment_id INTEGER NOT NULL,
                sell_date TEXT NOT NULL,
                quantity NUMERIC NOT NULL,
                sell_price NUMERIC NOT NULL,
                sell_currency TEXT DEFAULT 'IDR',
                fees NUMERIC DEFAULT 0,
                realized_pl NUMERIC,
                realized_pl_pct NUMERIC,
                FOREIGN KEY (investment_id) REFERENCES investments (id)
            );
            CREATE TABLE IF NOT EXISTS user_stats (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS price_snapshots (
                investment_id INTEGER,
                date TEXT,
                price_usd NUMERIC,
                price_idr NUMERIC,
                FOREIGN KEY (investment_id) REFERENCES investments (id)
            );
            INSERT OR IGNORE INTO user_stats (key, value) VALUES ('reward_points', '100');
        """
        Database.execute_script(self.db_path, script)

    def get_reward_points(self) -> float:
        rows = Database.query(self.db_path, "SELECT value FROM user_stats WHERE key = 'reward_points'")
        if rows and rows[0].get("value") is not None:
            try:
                return float(rows[0]["value"])
            except (ValueError, TypeError):
                pass
        return 100.0

    def update_reward_points(self, delta: float):
        current = self.get_reward_points()
        new_val = current + delta
        Database.execute(
            self.db_path,
            "UPDATE user_stats SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'reward_points'",
            (str(new_val),),
        )

    def save(self, inv: Investment) -> int:
        sql = """INSERT INTO investments 
                 (asset_type, ticker, quantity, buy_price, buy_currency, buy_date, status, remaining_quantity, is_favorite)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        if hasattr(Database, "_is_postgres_target") and Database._is_postgres_target(self.db_path):
            sql += " RETURNING id"

        params = (
            inv.asset_type,
            inv.ticker,
            str(inv.quantity),
            str(inv.buy_price),
            inv.buy_currency,
            inv.buy_date.isoformat(),
            inv.status.value,
            str(inv.remaining_quantity) if inv.remaining_quantity is not None else str(inv.quantity),
            bool(inv.is_favorite),
        )
        res = Database.execute(self.db_path, sql, params)
        inv.id = int(res) if res else 0
        return inv.id

    def get_all(self) -> List[Investment]:
        rows = Database.query(self.db_path, "SELECT * FROM investments ORDER BY buy_date DESC")
        return [self._map_row_to_investment(row) for row in rows]

    def get_all_active(self) -> List[Investment]:
        rows = Database.query(self.db_path, "SELECT * FROM investments WHERE status != 'sold' ORDER BY buy_date ASC")
        return [self._map_row_to_investment(row) for row in rows]

    def get_active_tickers(self) -> List[Dict[str, Any]]:
        sql = """
            SELECT ticker, asset_type, SUM(remaining_quantity) as total_qty
            FROM investments 
            WHERE status != 'sold' 
            GROUP BY ticker, asset_type
        """
        rows = Database.query(self.db_path, sql)
        results = []
        for row in rows:
            d = dict(row)
            d["total_qty"] = Decimal(str(d["total_qty"]))
            results.append(d)
        return results

    def get_active_lots(self, ticker: str, asset_type: Optional[str] = None) -> List[Investment]:
        sql = "SELECT * FROM investments WHERE ticker = ? AND status != 'sold'"
        params = [ticker.upper()]
        if asset_type:
            sql += " AND asset_type = ?"
            params.append(asset_type.lower())
        sql += " ORDER BY buy_date ASC"

        rows = Database.query(self.db_path, sql, tuple(params))
        return [self._map_row_to_investment(row) for row in rows]

    def save_sell_transaction(self, investment_id: int, investment: Investment, sell: SellTransaction):
        """Atomically update investment and record sell transaction."""
        if hasattr(Database, "_is_postgres_target") and Database._is_postgres_target(self.db_path) and DatabaseManager:
            schema = Database._get_schema(self.db_path)
            with DatabaseManager.transaction(schema=schema) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE investments SET remaining_quantity = %s, status = %s WHERE id = %s",
                        (str(investment.remaining_quantity), investment.status.value, investment_id),
                    )
                    sql_sell = """
                        INSERT INTO sell_transactions 
                        (investment_id, ticker, sell_date, quantity, sell_price_usd, sell_currency, fees, realized_pl_idr, realized_pl_pct)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cur.execute(
                        sql_sell,
                        (
                            investment_id,
                            investment.ticker,
                            sell.sell_date.isoformat(),
                            str(sell.quantity),
                            str(sell.sell_price),
                            sell.sell_currency,
                            str(sell.fees),
                            str(sell.realized_pl_idr),
                            str(sell.realized_pl_pct),
                        ),
                    )
        else:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("BEGIN")
                try:
                    conn.execute(
                        "UPDATE investments SET remaining_quantity = ?, status = ? WHERE id = ?",
                        (str(investment.remaining_quantity), investment.status.value, investment_id),
                    )
                    sql_sell = """
                        INSERT INTO sell_transactions 
                        (investment_id, sell_date, quantity, sell_price, sell_currency, fees, realized_pl, realized_pl_pct)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    conn.execute(
                        sql_sell,
                        (
                            investment_id,
                            sell.sell_date.isoformat(),
                            str(sell.quantity),
                            str(sell.sell_price),
                            sell.sell_currency,
                            str(sell.fees),
                            str(sell.realized_pl),
                            str(sell.realized_pl_pct),
                        ),
                    )
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    raise e

    def get_realized_pl(self) -> List[SellTransaction]:
        sql = """
            SELECT s.*, i.ticker, i.asset_type
            FROM sell_transactions s
            JOIN investments i ON s.investment_id = i.id
            ORDER BY s.sell_date DESC
        """
        rows = Database.query(self.db_path, sql)
        return [self._map_row_to_sell_transaction(row) for row in rows]

    def delete(self, investment_id: int) -> bool:
        if hasattr(Database, "_is_postgres_target") and Database._is_postgres_target(self.db_path) and DatabaseManager:
            schema = Database._get_schema(self.db_path)
            with DatabaseManager.transaction(schema=schema) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM investments WHERE id = %s", (investment_id,))
                    inv = cur.fetchone()
                    if not inv:
                        return False
                    ticker = inv["ticker"]
                    status = inv["status"]
                    if status in ["partial_sold", "sold"]:
                        return False

                    cur.execute(
                        "SELECT SUM(quantity) as sum_qty FROM investments WHERE ticker = %s AND id != %s",
                        (ticker, investment_id),
                    )
                    r1 = cur.fetchone()
                    total_buy_qty = Decimal(str(r1["sum_qty"] if r1 and r1.get("sum_qty") is not None else 0))

                    cur.execute(
                        """
                        SELECT SUM(s.quantity) as sum_qty
                        FROM sell_transactions s
                        JOIN investments i ON s.investment_id = i.id
                        WHERE i.ticker = %s
                    """,
                        (ticker,),
                    )
                    r2 = cur.fetchone()
                    total_sell_qty = Decimal(str(r2["sum_qty"] if r2 and r2.get("sum_qty") is not None else 0))

                    if total_buy_qty < total_sell_qty:
                        return False

                    cur.execute("DELETE FROM sell_transactions WHERE investment_id = %s", (investment_id,))
                    cur.execute("DELETE FROM price_snapshots WHERE investment_id = %s", (investment_id,))
                    cur.execute("DELETE FROM investments WHERE id = %s", (investment_id,))
                    return cur.rowcount > 0
        else:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("BEGIN")
                try:
                    conn.row_factory = sqlite3.Row
                    inv = conn.execute("SELECT * FROM investments WHERE id = ?", (investment_id,)).fetchone()
                    if not inv:
                        return False
                    ticker = inv["ticker"]
                    status = inv["status"]
                    if status in ["partial_sold", "sold"]:
                        return False

                    total_buy_res = conn.execute(
                        "SELECT SUM(quantity) FROM investments WHERE ticker = ? AND id != ?", (ticker, investment_id)
                    ).fetchone()
                    total_buy_qty = Decimal(str(total_buy_res[0] or 0))

                    total_sell_res = conn.execute(
                        "SELECT SUM(s.quantity) FROM sell_transactions s JOIN investments i ON s.investment_id = i.id WHERE i.ticker = ?",
                        (ticker,),
                    ).fetchone()
                    total_sell_qty = Decimal(str(total_sell_res[0] or 0))

                    if total_buy_qty < total_sell_qty:
                        return False

                    conn.execute("DELETE FROM sell_transactions WHERE investment_id = ?", (investment_id,))
                    conn.execute("DELETE FROM price_snapshots WHERE investment_id = ?", (investment_id,))
                    res = conn.execute("DELETE FROM investments WHERE id = ?", (investment_id,))
                    conn.commit()
                    return res.rowcount > 0
                except Exception:
                    conn.rollback()
                    return False

    def prune_sold_lots(self) -> Dict[str, int]:
        res = Database.execute(self.db_path, "DELETE FROM investments WHERE status = 'sold'")
        return {"deleted": int(res) if res is not None else 0}

    def get_by_id(self, id: int) -> Optional[Investment]:
        rows = Database.query(self.db_path, "SELECT * FROM investments WHERE id = ?", (id,))
        return self._map_row_to_investment(rows[0]) if rows else None

    def add_sell_transaction(self, sell: SellTransaction) -> int:
        sql = """
            INSERT INTO sell_transactions 
            (investment_id, sell_date, quantity, sell_price, sell_currency, fees, realized_pl, realized_pl_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        if hasattr(Database, "_is_postgres_target") and Database._is_postgres_target(self.db_path):
            sql += " RETURNING id"

        params = (
            sell.investment_id,
            sell.sell_date.isoformat(),
            str(sell.quantity),
            str(sell.sell_price),
            sell.sell_currency,
            str(sell.fees),
            str(sell.realized_pl),
            str(sell.realized_pl_pct),
        )
        res = Database.execute(self.db_path, sql, params)
        return int(res) if res else 0

    def update_status(self, investment_id: int, status: str, remaining_qty: Decimal) -> bool:
        sql = "UPDATE investments SET status = ?, remaining_quantity = ? WHERE id = ?"
        res = Database.execute(self.db_path, sql, (status, str(remaining_qty), investment_id))
        return bool(res)

    def toggle_favorite(self, investment_id: int) -> bool:
        sql = "UPDATE investments SET is_favorite = NOT is_favorite WHERE id = ?"
        Database.execute(self.db_path, sql, (investment_id,))
        return True

    def save_price_snapshot(self, investment_id: int, date: datetime, price_usd: Decimal, price_idr: Decimal) -> bool:
        sql = "INSERT INTO price_snapshots (investment_id, date, price_usd, price_idr) VALUES (?, ?, ?, ?)"
        Database.execute(self.db_path, sql, (investment_id, date.isoformat(), str(price_usd), str(price_idr)))
        return True

    def get_latest_snapshot(self, investment_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM price_snapshots WHERE investment_id = ? ORDER BY date DESC LIMIT 1"
        rows = Database.query(self.db_path, sql, (investment_id,))
        if rows:
            d = dict(rows[0])
            d["price_usd"] = Decimal(str(d["price_usd"]))
            d["price_idr"] = Decimal(str(d["price_idr"]))
            return d
        return None

    def get_all_snapshots(self, investment_id: int) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM price_snapshots WHERE investment_id = ? ORDER BY date DESC"
        rows = Database.query(self.db_path, sql, (investment_id,))
        results = []
        for row in rows:
            d = dict(row)
            d["price_usd"] = Decimal(str(d["price_usd"]))
            d["price_idr"] = Decimal(str(d["price_idr"]))
            results.append(d)
        return results

    def get_all_lots_by_ticker(self, ticker: str) -> List[Investment]:
        sql = "SELECT * FROM investments WHERE ticker = ? ORDER BY buy_date ASC"
        rows = Database.query(self.db_path, sql, (ticker,))
        return [self._map_row_to_investment(row) for row in rows]

    def get_all_sell_transactions_by_ticker(self, ticker: str) -> List[SellTransaction]:
        sql = """
            SELECT s.*, i.ticker, i.asset_type
            FROM sell_transactions s
            JOIN investments i ON s.investment_id = i.id
            WHERE i.ticker = ?
            ORDER BY s.sell_date DESC
        """
        rows = Database.query(self.db_path, sql, (ticker,))
        return [self._map_row_to_sell_transaction(row) for row in rows]

    def _map_row_to_investment(self, row) -> Investment:
        row_dict = dict(row) if hasattr(row, "keys") or isinstance(row, dict) else row

        def _parse_date(d):
            if not d:
                raise ValueError("missing date value in investment row")
            if isinstance(d, datetime):
                return d
            if isinstance(d, str):
                try:
                    return datetime.fromisoformat(d.replace(" ", "T"))
                except ValueError as exc:
                    raise ValueError(f"invalid ISO date {d!r} in investment row: {exc}") from exc
            raise ValueError(f"unsupported date type {type(d).__name__} in investment row")

        buy_currency = row_dict["buy_currency"]
        buy_price = Decimal(str(row_dict["buy_price"]))

        buy_price_idr = None
        if row_dict.get("buy_price_idr") is not None:
            buy_price_idr = Decimal(str(row_dict["buy_price_idr"]))

        if buy_price_idr is None:
            buy_price_idr = buy_price
            if buy_currency == "USD":
                buy_price_idr = buy_price * Decimal("16000")

        status_val = row_dict["status"]
        if isinstance(status_val, InvestmentStatus):
            status_enum = status_val
        else:
            status_enum = InvestmentStatus(str(status_val))

        return Investment(
            id=row_dict["id"],
            asset_type=row_dict["asset_type"],
            ticker=row_dict["ticker"],
            quantity=Decimal(str(row_dict["quantity"])),
            buy_price=buy_price,
            buy_currency=buy_currency,
            buy_price_idr=buy_price_idr,
            buy_date=_parse_date(row_dict["buy_date"]),
            status=status_enum,
            remaining_quantity=Decimal(str(row_dict["remaining_quantity"]))
            if row_dict.get("remaining_quantity") is not None
            else None,
            is_favorite=bool(row_dict.get("is_favorite", False)),
        )

    def _map_row_to_sell_transaction(self, row) -> SellTransaction:
        row_dict = dict(row) if hasattr(row, "keys") or isinstance(row, dict) else row

        def _parse_date(d):
            if not d:
                raise ValueError("missing date value in sell-transaction row")
            if isinstance(d, datetime):
                return d
            if isinstance(d, str):
                try:
                    return datetime.fromisoformat(d.replace(" ", "T"))
                except ValueError as exc:
                    raise ValueError(f"invalid ISO date {d!r} in sell-transaction row: {exc}") from exc
            raise ValueError(f"unsupported date type {type(d).__name__} in sell-transaction row")

        # Postgres schema uses *_usd/*_idr columns; SQLite/legacy rows use
        # sell_price/realized_pl. Accept either, preferring the canonical one.
        def _dec(*keys):
            for k in keys:
                if row_dict.get(k) is not None:
                    return Decimal(str(row_dict[k]))
            return Decimal("0")

        return SellTransaction(
            id=row_dict["id"],
            investment_id=row_dict["investment_id"],
            sell_date=_parse_date(row_dict["sell_date"]),
            quantity=Decimal(str(row_dict["quantity"])),
            sell_price=_dec("sell_price_usd", "sell_price"),
            sell_currency=row_dict.get("sell_currency", "IDR"),
            fees=_dec("fees"),
            realized_pl=_dec("realized_pl_idr", "realized_pl"),
            realized_pl_idr=_dec("realized_pl_idr", "realized_pl"),
            realized_pl_pct=_dec("realized_pl_pct"),
            ticker=row_dict.get("ticker"),
        )
