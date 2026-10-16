import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from psycopg2.extras import RealDictCursor

import packages.database.index as _db_module
from packages.core.domain.models import Expense
from packages.core.domain.repositories.expense_repository import IExpenseRepository
from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager


async def _db():
    """Lazy accessor — ensures we get the live Prisma client after connect()."""
    return await _db_module.get_db()


# ──────────────────────────────────────────────────────────
# Legacy DB value normalizers
# ──────────────────────────────────────────────────────────
_CAT_LEGACY: dict[str, str] = {
    "food & drink": "food",
    "food and drink": "food",
    "transportation": "transport",
    "groceries": "food",
    "utility": "housing",
    "utilities": "housing",
    "medical": "health",
}
_PM_LEGACY: dict[str, str] = {
    "debit card": "debit-card",
    "credit card": "credit-card",
    "e wallet": "e-wallet",
    "ewallet": "e-wallet",
    "bank transfer": "bank-transfer",
}
_VALID_CATS = {
    "food",
    "transport",
    "housing",
    "entertainment",
    "health",
    "shopping",
    "education",
    "investment",
    "other",
}
_VALID_PMS = {"cash", "debit-card", "credit-card", "e-wallet", "bank-transfer", "ovo", "gopay", "shopeepay", "qris"}


def _normalize_cat(v: str) -> str:
    n = v.lower().strip()
    canon = _CAT_LEGACY.get(n, n)
    return canon if canon in _VALID_CATS else "other"


def _normalize_pm(v: str) -> str:
    n = v.lower().strip().replace(" ", "-")
    canon = _PM_LEGACY.get(n, n)
    return canon if canon in _VALID_PMS else "cash"


def _row_to_expense(row) -> "Expense":
    """Convert a Prisma ORM row to an Expense, normalizing legacy enum strings."""
    data = {k: getattr(row, k) for k in row.__fields__ if hasattr(row, k)} if hasattr(row, "__fields__") else dict(row)
    if isinstance(data.get("category"), str):
        data["category"] = _normalize_cat(data["category"])
    if isinstance(data.get("payment_method"), str):
        data["payment_method"] = _normalize_pm(data["payment_method"])
    return Expense.model_validate(data)


class PostgresExpenseRepository(IExpenseRepository):
    """
    PostgreSQL implementation of the Expense Repository using Prisma.

    All public methods are native `async` to avoid any asyncio.run() nesting
    inside an already-running uvicorn event loop. Route handlers must `await`
    these directly; the sync IExpenseRepository interface is satisfied by
    the async overrides being called only from async FastAPI routes.
    """

    def __init__(self):
        pass

    async def save(self, expense: Expense) -> int:
        data = expense.model_dump(exclude={"id"})
        # Prisma Decimal columns: keep Decimal exact (float() would lose cents).
        for k, v in data.items():
            if isinstance(v, Decimal):
                data[k] = Decimal(str(v))
            elif isinstance(v, Enum):
                data[k] = v.value
        if data["date"].tzinfo is None:
            data["date"] = data["date"].replace(tzinfo=timezone.utc)
        db = await _db()
        created = await db.expense.create(data=data)
        expense.id = created.id
        return created.id

    async def apply_recurring_expenses(self, as_of: Optional[datetime] = None) -> Dict:
        """Create this month's recurring expenses exactly once per template.

        This uses one PostgreSQL transaction and an advisory lock scoped to the
        active schema. The lock serializes competing scheduler/API requests
        without imposing a uniqueness constraint that would reject legitimate
        non-recurring expenses with the same description.
        """
        target_date = as_of or datetime.now(timezone.utc)
        return await asyncio.to_thread(self._apply_recurring_expenses_sync, target_date)

    @staticmethod
    def _apply_recurring_expenses_sync(target_date: datetime) -> Dict:
        month_start = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        applied, skipped, entries = 0, 0, []

        with DatabaseManager.transaction() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
                    ("alpha-recurring-expenses", "active-profile"),
                )
                cursor.execute("SELECT * FROM expenses WHERE is_recurring = TRUE")
                templates = cursor.fetchall()

                for template in templates:
                    cursor.execute(
                        """
                        SELECT id FROM expenses
                        WHERE description = %s AND category = %s
                          AND date >= %s AND date < %s
                          AND is_recurring = FALSE
                        LIMIT 1
                        """,
                        (template["description"], template["category"], month_start.date(), month_end.date()),
                    )
                    if cursor.fetchone() is not None:
                        skipped += 1
                        continue

                    cursor.execute(
                        """
                        INSERT INTO expenses
                            (amount, description, category, payment_method, date, is_recurring)
                        VALUES (%s, %s, %s, %s, %s, FALSE)
                        RETURNING id
                        """,
                        (
                            template["amount"],
                            template["description"],
                            template["category"],
                            template["payment_method"],
                            target_date,
                        ),
                    )
                    row = cursor.fetchone()
                    applied += 1
                    entries.append(
                        {
                            "id": row["id"],
                            "description": template["description"],
                            "amount": float(template["amount"]),
                        }
                    )

        return {"applied": applied, "skipped": skipped, "entries": entries}

    async def get_all(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Expense]:
        where = {}
        if start_date and end_date:
            where["date"] = {
                "gte": start_date.replace(tzinfo=timezone.utc) if start_date.tzinfo is None else start_date,
                "lte": end_date.replace(tzinfo=timezone.utc) if end_date.tzinfo is None else end_date,
            }
        if category:
            where["category"] = category
        if search:
            where["OR"] = [
                {"description": {"contains": search, "mode": "insensitive"}},
                {"category": {"contains": search, "mode": "insensitive"}},
            ]

        db = await _db()
        rows = await db.expense.find_many(where=where, take=limit, skip=offset, order={"date": "desc"})
        return [_row_to_expense(row) for row in rows]

    async def count(self, category: Optional[str] = None, search: Optional[str] = None) -> int:
        where = {}
        if category:
            where["category"] = category
        if search:
            where["OR"] = [
                {"description": {"contains": search, "mode": "insensitive"}},
                {"category": {"contains": search, "mode": "insensitive"}},
            ]
        db = await _db()
        return await db.expense.count(where=where)

    async def get_by_id(self, expense_id: int) -> Optional[Expense]:
        db = await _db()
        row = await db.expense.find_unique(where={"id": expense_id})
        return _row_to_expense(row) if row else None

    async def get_monthly_summary(self, year: int, month: int) -> Dict:
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = (
            datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            if month == 12
            else datetime(year, month + 1, 1, tzinfo=timezone.utc)
        )

        db = await _db()
        expenses = await db.expense.find_many(where={"date": {"gte": start, "lt": end}})

        total_amt = 0.0
        by_category: dict = {}
        by_payment: dict = {}
        for e in expenses:
            amt = float(e.amount)
            total_amt += amt
            by_category[e.category] = by_category.get(e.category, 0.0) + amt
            by_payment[e.payment_method] = by_payment.get(e.payment_method, 0.0) + amt

        total_count = len(expenses)
        return {
            "total": total_amt,
            "count": total_count,
            "by_category": by_category,
            "by_payment": by_payment,
            "average_per_day": total_amt / 30 if total_count > 0 else 0,
        }

    async def delete(self, expense_id: int) -> bool:
        try:
            db = await _db()
            await db.expense.delete(where={"id": expense_id})
            return True
        except Exception:
            return False

    async def get_by_category(self, category: str) -> List[Expense]:
        return await self.get_all(category=category)

    async def get_category_breakdown(self, year: int, month: int) -> Dict[str, float]:
        summary = await self.get_monthly_summary(year, month)
        return summary["by_category"]

    # Budget-related methods
    async def get_budgets(self, year: int, month: int) -> Dict[str, float]:
        db = await _db()
        rows = await db.budget.find_many(where={"year": year, "month": month})
        return {row.category: float(row.limit_amt) for row in rows}

    async def set_budget(self, category: str, year: int, month: int, limit_amt: float) -> bool:
        try:
            db = await _db()
            amt = Decimal(str(limit_amt))
            await db.budget.upsert(
                where={"category_year_month": {"category": category, "year": year, "month": month}},
                data={
                    "create": {"category": category, "year": year, "month": month, "limit_amt": amt},
                    "update": {"limit_amt": amt},
                },
            )
            return True
        except Exception:
            return False
