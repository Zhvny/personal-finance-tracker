from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import packages.database.index as _db_module
from packages.core.domain.models import Income, IncomeType
from packages.core.domain.repositories.income_repository import IIncomeRepository


async def _db():
    """Lazy accessor — ensures we get the live Prisma client after connect()."""
    return await _db_module.get_db()


class PostgresIncomeRepository(IIncomeRepository):
    """
    PostgreSQL implementation of the Income Repository using Prisma.
    All public methods are native `async` to avoid event loop conflicts.
    """

    def __init__(self):
        pass

    async def save(self, income: Income, conn: Any = None) -> int:
        # Use mode="json" so enums (e.g. IncomeCategory) are serialised to their
        # string values instead of raw Python enum objects, which Prisma rejects.
        data = income.model_dump(mode="json", exclude={"id"})
        if isinstance(data["date"], str):
            data["date"] = datetime.fromisoformat(data["date"])
        if data["date"].tzinfo is None:
            data["date"] = data["date"].replace(tzinfo=timezone.utc)

        # Pydantic mode="json" serializes Decimal -> str; Prisma Decimal columns
        # take Decimal, so parse back exactly (float() would lose cents).
        data["amount"] = Decimal(str(data["amount"]))

        db = await _db()
        if income.id:
            updated = await db.income.update(where={"id": income.id}, data=data)
            return updated.id if updated else income.id
        else:
            created = await db.income.create(data=data)
            income.id = created.id
            return created.id

    async def get_all(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        income_type: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Income]:
        where = {}
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["gte"] = (
                    start_date.replace(tzinfo=timezone.utc) if start_date.tzinfo is None else start_date
                )
            if end_date:
                date_filter["lte"] = end_date.replace(tzinfo=timezone.utc) if end_date.tzinfo is None else end_date
            where["date"] = date_filter

        if income_type:
            where["income_type"] = income_type

        if search:
            where["OR"] = [
                {"source": {"contains": search, "mode": "insensitive"}},
                {"description": {"contains": search, "mode": "insensitive"}},
            ]

        db = await _db()
        rows = await db.income.find_many(where=where, order={"date": "desc"})
        return [Income.model_validate(row) for row in rows]

    async def get_by_id(self, income_id: int) -> Optional[Income]:
        db = await _db()
        row = await db.income.find_unique(where={"id": income_id})
        return Income.model_validate(row) if row else None

    async def get_monthly_summary(self, year: int, month: int) -> Dict:
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

        db = await _db()
        incomes = await db.income.find_many(where={"date": {"gte": start, "lt": end}})

        total_real = 0.0
        total_transfer = 0.0
        total_count = 0
        real_count = 0
        transfer_count = 0
        by_type = {}

        for i in incomes:
            amt = i.amount
            itype = i.income_type
            by_type[itype] = float(by_type.get(itype, 0.0) + amt)
            total_count += 1

            if itype == IncomeType.TRANSFER or str(itype).lower() == "transfer":
                total_transfer += amt
                transfer_count += 1
            else:
                total_real += amt
                real_count += 1

        return {
            "total": float(total_real),
            "real_income": float(total_real),
            "transfer_income": float(total_transfer),
            "gross_total": float(total_real + total_transfer),
            "count": total_count,
            "real_count": real_count,
            "transfer_count": transfer_count,
            "by_type": by_type,
            "average": float(total_real / real_count) if real_count > 0 else 0,
        }

    async def delete(self, income_id: int) -> bool:
        import logging

        db = await _db()
        existing = await db.income.find_unique(where={"id": income_id})
        if existing is None:
            return False
        try:
            await db.income.delete(where={"id": income_id})
            return True
        except Exception as exc:
            logging.getLogger(__name__).error("Failed to delete income id=%s: %s", income_id, exc, exc_info=True)
            raise

    async def get_by_type(self, income_type: str) -> List[Income]:
        db = await _db()
        rows = await db.income.find_many(where={"income_type": income_type}, order={"date": "desc"})
        return [Income.model_validate(row) for row in rows]

    async def get_summary_by_month(self, year: int, month: int) -> Dict:
        return await self.get_monthly_summary(year, month)
