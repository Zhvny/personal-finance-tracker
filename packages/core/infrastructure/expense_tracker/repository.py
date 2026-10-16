import sys
from pathlib import Path

# Add monorepo root to sys.path to access shared packages
_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, List

from .interfaces import IExpenseRepository
from .models import Expense, ExpenseCategory, PaymentMethod

# Try to import shared Database utility for Postgres redirection
try:
    from packages.core.infrastructure.persistence.database import Database
except ImportError:
    # Fallback for local development if packages is not in path
    import sqlite3
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

logger = logging.getLogger(__name__)

class SQLiteExpenseRepository(IExpenseRepository):
    def __init__(self, db_path: str = "data/expense.db"):
        # Use absolute path relative to this file to ensure consistency
        if not os.path.isabs(db_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, db_path)
        else:
            self.db_path = db_path

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        script = """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                date TEXT NOT NULL,
                is_recurring BOOLEAN DEFAULT 0,
                recurring_period TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
            CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);
        """
        Database.execute_script(self.db_path, script)

    def save(self, expense: Expense) -> int:
        sql = """INSERT INTO expenses (amount, description, category, payment_method, 
                   date, is_recurring, recurring_period)
                   VALUES (?, ?, ?, ?, ?, ?, ?)"""
        params = (
            expense.amount, expense.description, expense.category.value,
            expense.payment_method.value, expense.date.isoformat(),
            expense.is_recurring, expense.recurring_period
        )

        result = Database.execute(self.db_path, sql, params)
        if result is not False:
            return result
        return 0

    def get_all(self, start_date=None, end_date=None, category=None) -> List[Expense]:
        query = """
            SELECT id, amount, description, category, payment_method, 
                   date, is_recurring, recurring_period, created_at
            FROM expenses 
            WHERE 1=1
        """
        params = []

        if start_date and end_date:
            query += " AND date BETWEEN ? AND ?"
            params.extend([start_date.isoformat(), end_date.isoformat()])

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY date DESC"

        rows = Database.query(self.db_path, query, tuple(params))
        return [self._row_to_expense(row) for row in rows]

    def get_by_category(self, category: str) -> List[Expense]:
        return self.get_all(category=category)

    def get_monthly_summary(self, year: int, month: int) -> Dict:
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)

        expenses = self.get_all(start, end)

        total = sum(e.amount for e in expenses)
        by_category = {}
        by_payment = {}

        for e in expenses:
            c = e.category.value
            by_category[c] = by_category.get(c, 0) + e.amount
            p = e.payment_method.value
            by_payment[p] = by_payment.get(p, 0) + e.amount

        return {
            "total": total,
            "count": len(expenses),
            "by_category": by_category,
            "by_payment": by_payment,
            "average_per_day": total / 30 if expenses else 0
        }

    def get_category_breakdown(self, year: int, month: int) -> Dict[str, float]:
        summary = self.get_monthly_summary(year, month)
        return summary["by_category"]

    def delete(self, id: int) -> bool:
        sql = "DELETE FROM expenses WHERE id = ?"
        result = Database.execute(self.db_path, sql, (id,))
        return bool(result)


    # ── Canonical aliases: maps any legacy/variant value → valid PaymentMethod
    # DRY: single source of truth for all payment-method normalisation.
    # Open/Closed: add new aliases here without touching any other method.
    _PAYMENT_ALIASES: dict = {
        # QRIS variants (receipt_reader writes "qris"; no hyphen in model)
        # QR-based
        "qris":          "qris",
        # OVO
        "ovo":           "ovo",
        # GoPay
        "gopay":         "gopay",
        "go-pay":        "gopay",
        "go_pay":        "gopay",
        # ShopeePay
        "shopeepay":     "shopeepay",
        "shopee_pay":    "shopeepay",
        "shopee-pay":    "shopeepay",
        "spay":          "shopeepay",
        # Legacy e-wallet fallback (old data)
        "e_wallet":      "e-wallet",
        # underscore variants (old import scripts)
        "debit_card":    "debit-card",
        "credit_card":   "credit-card",
        "e_wallet":      "e-wallet",
        "bank_transfer": "bank-transfer",
        # plain aliases
        "debit":         "debit-card",
        "credit":        "credit-card",
        "transfer":      "bank-transfer",
        "atm":           "debit-card",
        "gopay":         "e-wallet",
        "ovo":           "e-wallet",
        "dana":          "e-wallet",
        "shopeepay":     "e-wallet",
        "linkaja":       "e-wallet",
    }

    @classmethod
    def _resolve_payment_method(cls, raw: str) -> PaymentMethod:
        """
        Abstraction layer: safely coerce any raw payment_method string
        (from DB, receipts, or legacy imports) into a valid PaymentMethod.
        Falls back to CASH — never raises.
        """
        normalised = raw.strip().lower()
        # Direct match first (happy path — O(1))
        try:
            return PaymentMethod(normalised)
        except ValueError:
            pass
        # Alias lookup
        canonical = cls._PAYMENT_ALIASES.get(normalised)
        if canonical:
            try:
                return PaymentMethod(canonical)
            except ValueError:
                pass
        return PaymentMethod.CASH  # safe sentinel

    # ── Category aliases: maps any legacy/variant value → valid ExpenseCategory
    _CATEGORY_ALIASES: dict = {
        "food & drink": "food",
        "makan":        "food",
        "transportasi": "transport",
        "kendaraan":    "transport",
        "belanja":      "shopping",
        "hiburan":      "entertainment",
        "kesehatan":    "health",
        "pendidikan":   "education",
        "investasi":    "investment",
        "rumah":        "housing",
    }

    @classmethod
    def _resolve_category(cls, raw: str) -> ExpenseCategory:
        """Coerce raw category string into a valid ExpenseCategory enum."""
        normalised = raw.strip().lower()
        try:
            return ExpenseCategory(normalised)
        except ValueError:
            pass

        canonical = cls._CATEGORY_ALIASES.get(normalised)
        if canonical:
            try:
                return ExpenseCategory(canonical)
            except ValueError:
                pass
        return ExpenseCategory.OTHER

    def _row_to_expense(self, row) -> Expense:
        """
        Map a SQLite row → Expense dataclass.
        Separation of Concerns: all type-coercion lives here, nowhere else.
        """
        # Convert sqlite3.Row to dict so .get() with defaults works correctly
        row = dict(row)
        date_val = row.get('date')
        if not date_val:
            dt = datetime.now()
        elif isinstance(date_val, datetime):
            dt = date_val
        elif isinstance(date_val, str):
            try:
                # Handle potential space/timezone issues
                dt = datetime.fromisoformat(date_val.replace(" ", "T"))
            except ValueError:
                dt = datetime.now()
        else:
            dt = datetime.now()

        return Expense(
            id=row['id'],
            amount=Decimal(str(row['amount'])),
            description=row['description'],
            category=self._resolve_category(row['category']),
            payment_method=self._resolve_payment_method(row['payment_method']),
            date=dt,
            is_recurring=bool(row['is_recurring']),
            recurring_period=row['recurring_period'],
        )
