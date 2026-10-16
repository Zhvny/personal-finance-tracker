import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

import packages.database.index as _db_module
from packages.core.domain.models import Investment, InvestmentStatus, SellTransaction
from packages.core.domain.repositories.investment_repository import IInvestmentRepository
from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager


async def _db():
    """Lazy accessor — ensures we get the live Prisma client after connect()."""
    return await _db_module.get_db()


class ConcurrentSaleError(RuntimeError):
    """The holding changed while a sale was being recorded."""


class PostgresInvestmentRepository(IInvestmentRepository):
    """
    PostgreSQL implementation of the Investment Repository using Prisma.
    """

    def __init__(self):
        pass

    async def save(self, investment: Investment) -> int:
        # Exclude enrichment fields that are not in the database schema
        exclude_fields = {
            "id",
            "sells",
            "current_price_idr",
            "current_price_date",
            "pl",
            "pl_pct",
            "cap_gain",
            "fx_gain",
            "is_stale",
            "fx_buy",
            "fx_live",
        }
        data = investment.model_dump(exclude=exclude_fields)
        # Prisma Decimal columns: keep Decimal exact (float() would lose precision).
        for k, v in data.items():
            if isinstance(v, Decimal):
                data[k] = Decimal(str(v))
            elif isinstance(v, Enum):
                data[k] = v.value
        if data["buy_date"].tzinfo is None:
            data["buy_date"] = data["buy_date"].replace(tzinfo=timezone.utc)

        db = await _db()
        created = await db.investment.create(data=data)
        investment.id = created.id
        return created.id

    async def get_all_active(self) -> List[Investment]:
        """Fetch active investments directly from PostgreSQL (bypasses Prisma SQLite)."""
        sql = """
            SELECT id, asset_type, ticker, quantity, buy_price, buy_currency,
                   buy_date, status, remaining_quantity, is_favorite, created_at, buy_price_idr
            FROM investments
            WHERE status != 'sold' AND remaining_quantity > 0
            ORDER BY is_favorite DESC, created_at DESC
        """
        fallback_sql = """
            SELECT id, asset_type, ticker, quantity, buy_price, buy_currency,
                   buy_date, status, remaining_quantity, FALSE as is_favorite, created_at, buy_price_idr
            FROM investments
            WHERE status != 'sold' AND remaining_quantity > 0
            ORDER BY created_at DESC
        """
        try:
            try:
                rows = await asyncio.to_thread(DatabaseManager.query, sql)
            except Exception as e:
                if "is_favorite" in str(e):
                    rows = await asyncio.to_thread(DatabaseManager.query, fallback_sql)
                else:
                    rows = DatabaseManager.query(sql)
        except Exception as e:
            if "is_favorite" in str(e):
                rows = DatabaseManager.query(fallback_sql)
            else:
                raise

        investments = []
        for row in rows:
            try:
                inv = Investment.model_validate(dict(row))
            except Exception:
                inv = self._row_to_investment(row)
            investments.append(inv)
        return investments

    def _row_to_investment(self, row: dict) -> Investment:
        """Fallback mapper from raw DB row to Investment domain model."""
        inv = Investment(
            asset_type=row["asset_type"],
            ticker=row["ticker"],
            quantity=Decimal(str(row["quantity"])),
            buy_price=Decimal(str(row["buy_price"])),
            buy_currency=row["buy_currency"],
            buy_price_idr=Decimal(str(row["buy_price_idr"])) if row.get("buy_price_idr") is not None else None,
            buy_date=row["buy_date"]
            if isinstance(row["buy_date"], datetime)
            else datetime.fromisoformat(str(row["buy_date"])),
            id=row["id"],
            is_favorite=bool(row.get("is_favorite", False)),
        )
        inv.status = InvestmentStatus(row["status"]) if row.get("status") else InvestmentStatus.HOLDING
        inv.remaining_quantity = (
            Decimal(str(row["remaining_quantity"])) if row.get("remaining_quantity") is not None else inv.quantity
        )
        return inv

    async def get_by_id(self, investment_id: int) -> Optional[Investment]:
        db = await _db()
        row = await db.investment.find_unique(where={"id": investment_id})
        return Investment.model_validate(row) if row else None

    async def delete(self, investment_id: int) -> bool:
        import logging as _logging

        try:
            db = await _db()
            await db.investment.delete(where={"id": investment_id})
            return True
        except Exception as exc:
            _logging.getLogger(__name__).error(
                "Failed to delete investment id=%s: %s", investment_id, exc, exc_info=True
            )
            return False

    async def update_status(self, investment_id: int, status: str, remaining_qty: Decimal) -> bool:
        import logging as _logging

        try:
            db = await _db()
            await db.investment.update(
                where={"id": investment_id}, data={"status": status, "remaining_quantity": Decimal(str(remaining_qty))}
            )
            return True
        except Exception as exc:
            _logging.getLogger(__name__).error(
                "Failed to update_status investment id=%s: %s", investment_id, exc, exc_info=True
            )
            return False

    async def add_sell_transaction(self, sell: SellTransaction) -> int:
        data = sell.model_dump(exclude={"id"})
        if data["sell_date"].tzinfo is None:
            data["sell_date"] = data["sell_date"].replace(tzinfo=timezone.utc)

        # Map Pydantic field names to Prisma schema if they differ
        # Based on previous SQL, sell_price_usd was used
        prisma_data = {
            "investmentId": sell.investment_id,
            "ticker": sell.ticker,
            "sell_date": data["sell_date"],
            "quantity": Decimal(str(sell.quantity)),
            "sell_price_usd": Decimal(str(sell.sell_price)),
            "sell_currency": sell.sell_currency,
            "fees": Decimal(str(sell.fees)),
            "realized_pl_idr": Decimal(str(sell.realized_pl_idr)),
            "realized_pl_pct": Decimal(str(sell.realized_pl_pct)),
        }
        db = await _db()
        created = await db.selltransaction.create(data=prisma_data)
        sell.id = created.id
        return created.id

    async def sell_and_record_income(
        self,
        sell: SellTransaction,
        *,
        income_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist a sale and its derived income as one PostgreSQL transaction.

        The conditional decrement is intentionally performed in the database so
        concurrent sale requests cannot oversell a lot between an application
        read and its subsequent update.
        """
        db = await _db()
        quantity = Decimal(str(sell.quantity))

        async with db.tx() as transaction:
            updated_count = await transaction.investment.update_many(
                where={
                    "id": sell.investment_id,
                    "status": {"not": "sold"},
                    "remaining_quantity": {"gte": quantity},
                },
                data={"remaining_quantity": {"decrement": quantity}},
            )
            if updated_count != 1:
                raise ConcurrentSaleError("Investment holding changed or no longer has sufficient quantity")

            updated_investment = await transaction.investment.find_unique(where={"id": sell.investment_id})
            if updated_investment is None:
                raise ConcurrentSaleError("Investment holding disappeared during sale")

            remaining = Decimal(str(updated_investment.remaining_quantity))
            status = "sold" if remaining <= Decimal("0") else InvestmentStatus.PARTIAL_SOLD.value
            updated_investment = await transaction.investment.update(
                where={"id": sell.investment_id},
                data={"status": status},
            )

            sell_date = sell.sell_date
            if sell_date.tzinfo is None:
                sell_date = sell_date.replace(tzinfo=timezone.utc)
            created_sell = await transaction.selltransaction.create(
                data={
                    "investmentId": sell.investment_id,
                    "ticker": sell.ticker,
                    "sell_date": sell_date,
                    "quantity": quantity,
                    "sell_price_usd": Decimal(str(sell.sell_price)),
                    "sell_currency": sell.sell_currency,
                    "fees": Decimal(str(sell.fees)),
                    "realized_pl_idr": Decimal(str(sell.realized_pl_idr)),
                    "realized_pl_pct": Decimal(str(sell.realized_pl_pct)),
                }
            )

            income_id = None
            if income_data is not None:
                income_date = income_data["date"]
                if income_date.tzinfo is None:
                    income_date = income_date.replace(tzinfo=timezone.utc)
                created_income = await transaction.income.create(
                    data={
                        "amount": Decimal(str(income_data["amount"])),
                        "source": income_data["source"],
                        "income_type": income_data["income_type"],
                        "date": income_date,
                        "description": income_data.get("description"),
                        "is_taxed": bool(income_data.get("is_taxed", False)),
                    }
                )
                income_id = created_income.id

        sell.id = created_sell.id
        return {
            "sell_id": created_sell.id,
            "income_id": income_id,
            "new_remaining": remaining,
            "new_status": updated_investment.status,
        }

    async def get_realized_pl(self) -> List[SellTransaction]:
        db = await _db()
        rows = await db.selltransaction.find_many(order={"sell_date": "desc"})
        return [
            SellTransaction(
                id=r.id,
                investment_id=r.investmentId,
                sell_date=r.sell_date,
                quantity=Decimal(str(r.quantity)),
                sell_price=Decimal(str(r.sell_price_usd)),
                sell_currency=r.sell_currency,
                fees=Decimal(str(r.fees)),
                realized_pl=Decimal(str(r.realized_pl_idr)),
                realized_pl_idr=Decimal(str(r.realized_pl_idr)),
                realized_pl_pct=Decimal(str(r.realized_pl_pct)),
                ticker=r.ticker,
            )
            for r in rows
        ]

    async def get_all_lots_by_ticker(self, ticker: str) -> List[Investment]:
        db = await _db()
        rows = await db.investment.find_many(where={"ticker": ticker.upper()}, order={"buy_date": "asc"})
        return [Investment.model_validate(row) for row in rows]

    async def get_all_sell_transactions_by_ticker(self, ticker: str) -> List[SellTransaction]:
        db = await _db()
        rows = await db.selltransaction.find_many(where={"ticker": ticker.upper()}, order={"sell_date": "asc"})
        return [
            SellTransaction(
                id=r.id,
                investment_id=r.investmentId,
                sell_date=r.sell_date,
                quantity=Decimal(str(r.quantity)),
                sell_price=Decimal(str(r.sell_price_usd)),
                sell_currency=r.sell_currency,
                fees=Decimal(str(r.fees)),
                realized_pl=Decimal(str(r.realized_pl_idr)),
                realized_pl_idr=Decimal(str(r.realized_pl_idr)),
                realized_pl_pct=Decimal(str(r.realized_pl_pct)),
                ticker=r.ticker,
            )
            for r in rows
        ]

    async def save_price_snapshot(self, investment_id: int, date: datetime, price_usd: float, price_idr: float) -> bool:
        sql = """
            INSERT INTO historical_prices (investment_id, snapshot_date, price_usd, price_idr)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (investment_id, snapshot_date) DO UPDATE SET
                price_usd = EXCLUDED.price_usd,
                price_idr = EXCLUDED.price_idr
        """
        snapshot_date = date.date() if isinstance(date, datetime) else date
        import logging as _logging

        try:
            await asyncio.to_thread(
                DatabaseManager.execute, sql, (investment_id, snapshot_date, float(price_usd), float(price_idr))
            )
            return True
        except Exception as exc:
            _logging.getLogger(__name__).error(f"save_price_snapshot error for {investment_id}: {exc}")
            return False

    async def get_latest_snapshot(self, investment_id: int) -> Optional[Dict[str, Any]]:
        """Get latest price snapshot from PostgreSQL historical_prices."""
        sql = """
            SELECT hp.investment_id, hp.snapshot_date, hp.price_usd, hp.price_idr
            FROM historical_prices hp
            WHERE hp.investment_id = %s
            ORDER BY hp.snapshot_date DESC
            LIMIT 1
        """
        import logging as _logging

        try:
            rows = await asyncio.to_thread(DatabaseManager.query, sql, (investment_id,))
            if not rows:
                # Fallback: check by ticker if lot has no direct snapshot yet
                sql_by_ticker = """
                    SELECT hp.investment_id, hp.snapshot_date, hp.price_usd, hp.price_idr
                    FROM historical_prices hp
                    JOIN investments i ON hp.investment_id = i.id
                    WHERE i.ticker = (SELECT ticker FROM investments WHERE id = %s)
                    ORDER BY hp.snapshot_date DESC
                    LIMIT 1
                """
                rows = await asyncio.to_thread(DatabaseManager.query, sql_by_ticker, (investment_id,))
            if rows:
                return {
                    "investment_id": rows[0]["investment_id"],
                    "snapshot_date": rows[0]["snapshot_date"],
                    "price_usd": rows[0]["price_usd"],
                    "price_idr": rows[0]["price_idr"],
                }
        except Exception as exc:
            _logging.getLogger(__name__).warning(
                "get_latest_snapshot failed for investment_id=%s: %s", investment_id, exc
            )
        return None

    async def get_all_snapshots(self, investment_id: int) -> List[Dict[str, Any]]:
        """Get all price snapshots from PostgreSQL historical_prices.

        Single asyncio.to_thread path — no sync fallback.  Read failures return
        an empty list so callers gracefully degrade to no chart data.
        """
        sql = """
            SELECT snapshot_date, price_usd, price_idr
            FROM historical_prices
            WHERE investment_id = %s
            ORDER BY snapshot_date ASC
        """
        import logging as _logging

        try:
            rows = await asyncio.to_thread(DatabaseManager.query, sql, (investment_id,))
            return [
                {"snapshot_date": r["snapshot_date"], "price_usd": r["price_usd"], "price_idr": r["price_idr"]}
                for r in rows
            ]
        except Exception as exc:
            _logging.getLogger(__name__).warning(
                "get_all_snapshots failed for investment_id=%s: %s", investment_id, exc
            )
            return []

    async def toggle_favorite(self, investment_id: int) -> bool:
        db = await _db()
        inv = await db.investment.find_unique(where={"id": investment_id})
        if inv:
            await db.investment.update(where={"id": investment_id}, data={"is_favorite": not inv.is_favorite})
            return True
        return False

    async def prune_sold_lots(self) -> Dict[str, int]:
        db = await _db()
        # This is a bit more complex in Prisma for bulk delete with condition
        stale = await db.investment.find_many(
            where={"status": "sold", "OR": [{"remaining_quantity": 0}, {"remaining_quantity": None}]}
        )
        deleted = 0
        for inv in stale:
            await db.historicalprice.delete_many(where={"investmentId": inv.id})
            await db.investment.delete(where={"id": inv.id})
            deleted += 1

        kept_holding = await db.investment.count(where={"status": {"not": "sold"}})
        kept_realized = await db.investment.count(where={"status": "sold", "remaining_quantity": {"gt": 0}})

        return {"deleted": deleted, "kept_holding": kept_holding, "kept_realized": kept_realized}

    async def get_active_tickers(self) -> List[Dict[str, Any]]:
        db = await _db()
        # Prisma group by
        results = await db.investment.group_by(
            by=["ticker", "asset_type"], where={"status": {"not": "sold"}}, sum={"remaining_quantity": True}
        )
        return [
            {"ticker": r["ticker"], "asset_type": r["asset_type"], "total_qty": r["_sum"]["remaining_quantity"]}
            for r in results
        ]

    async def get_active_lots(self, ticker: str, asset_type: Optional[str] = None) -> List[Investment]:
        where = {"ticker": ticker.upper(), "status": {"not": "sold"}}
        if asset_type:
            where["asset_type"] = asset_type.lower()

        db = await _db()
        rows = await db.investment.find_many(where=where, order={"buy_date": "asc"})
        return [Investment.model_validate(row) for row in rows]

    async def get_by_ticker(self, ticker: str) -> List[Investment]:
        return await self.get_active_lots(ticker)

    async def get_reward_points(self) -> float:
        db = await _db()
        row = await db.userstat.find_unique(where={"key": "reward_points"})
        return float(row.value) if row else 100.0

    async def update_reward_points(self, delta: float) -> bool:
        current = await self.get_reward_points()
        new_val = str(current + delta)
        db = await _db()
        await db.userstat.upsert(
            where={"key": "reward_points"},
            data={"create": {"key": "reward_points", "value": new_val}, "update": {"value": new_val}},
        )
        return True

    async def get_realized_pl_summary(self, year: Optional[int] = None) -> Dict[str, Any]:
        where = {}
        if year:
            start = datetime(year, 1, 1, tzinfo=timezone.utc)
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            where["sell_date"] = {"gte": start, "lt": end}

        db = await _db()
        sells = await db.selltransaction.find_many(where=where)
        total_realized_pl = sum(s.realized_pl_idr for s in sells)
        total_sells = len(sells)
        wins = sum(1 for s in sells if s.realized_pl_idr > 0)
        losses = sum(1 for s in sells if s.realized_pl_idr < 0)

        return {
            "total_realized_pl": float(total_realized_pl),
            "total_sells": total_sells,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / total_sells * 100) if total_sells else 0,
        }

    async def get_all_sell_transactions(self) -> List[Dict[str, Any]]:
        db = await _db()
        rows = await db.selltransaction.find_many(include={"investment": True}, order={"sell_date": "desc"})
        results = []
        for r in rows:
            res = {
                "id": r.id,
                "investment_id": r.investmentId,
                "sell_date": r.sell_date.isoformat(),
                "quantity": r.quantity,
                "sell_price_usd": r.sell_price_usd,
                "sell_currency": r.sell_currency,
                "fees": r.fees,
                "realized_pl_idr": r.realized_pl_idr,
                "realized_pl_pct": r.realized_pl_pct,
                "ticker": r.ticker or (r.investment.ticker if r.investment else "---"),
            }
            results.append(res)
        return results
