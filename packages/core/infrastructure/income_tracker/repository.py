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
from typing import List, Optional

from .interfaces import IIncomeRepository
from .models import Income, IncomeType

# Try to import shared Database utility for Postgres redirection
try:
    from packages.core.infrastructure.persistence.database import Database
except ImportError:
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

class SQLiteIncomeRepository(IIncomeRepository):
    def __init__(self, db_path: str = "data/income.db"):
        if not os.path.isabs(db_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, db_path)
        else:
            self.db_path = db_path

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        script = """
            CREATE TABLE IF NOT EXISTS incomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                source TEXT NOT NULL,
                income_type TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                is_taxed BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        Database.execute_script(self.db_path, script)

    def save(self, income: Income) -> int:
        sql = """INSERT INTO incomes (amount, source, income_type, date, description, is_taxed)
                   VALUES (?, ?, ?, ?, ?, ?)"""
        params = (income.amount, income.source, income.income_type.value,
                 income.date.isoformat(), income.description, income.is_taxed)

        result = Database.execute(self.db_path, sql, params)
        if result is not False:
            return result
        return 0

    def get_all(self, start_date=None, end_date=None, income_type: Optional[str] = None, search: Optional[str] = None) -> List[Income]:
        query = """
            SELECT id, amount, source, income_type, date, description, is_taxed, created_at 
            FROM incomes 
            WHERE 1=1
        """
        params = []

        if start_date and end_date:
            query += " AND date BETWEEN ? AND ?"
            params.extend([start_date.isoformat(), end_date.isoformat()])
        elif start_date:
            query += " AND date >= ?"
            params.append(start_date.isoformat())
        elif end_date:
            query += " AND date <= ?"
            params.append(end_date.isoformat())

        if income_type:
            query += " AND income_type = ?"
            params.append(income_type)

        if search:
            query += " AND (source LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY date DESC"

        rows = Database.query(self.db_path, query, tuple(params))
        return [self._row_to_income(row) for row in rows]

    def get_by_type(self, income_type: str) -> List[Income]:
        query = """
            SELECT id, amount, source, income_type, date, description, is_taxed, created_at 
            FROM incomes 
            WHERE income_type = ? 
            ORDER BY date DESC
        """
        rows = Database.query(self.db_path, query, (income_type,))
        return [self._row_to_income(row) for row in rows]

    def get_monthly_summary(self, year: int, month: int) -> dict:
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)

        incomes = self.get_all(start, end)

        total = sum(i.amount for i in incomes) if incomes else Decimal('0')
        by_type = {}
        for i in incomes:
            t = i.income_type.value
            by_type[t] = by_type.get(t, Decimal('0')) + i.amount

        return {
            "total": total,
            "count": len(incomes),
            "by_type": by_type,
            "average": total / len(incomes) if incomes else Decimal('0')
        }

    def delete(self, id: int) -> bool:
        sql = "DELETE FROM incomes WHERE id = ?"
        result = Database.execute(self.db_path, sql, (id,))
        return bool(result)


    def _row_to_income(self, row) -> Income:
        # Convert sqlite3.Row to dict so .get() with defaults works correctly
        row = dict(row)
        date_val = row.get('date')
        if not date_val:
            dt = datetime.now()
        elif isinstance(date_val, datetime):
            dt = date_val
        elif isinstance(date_val, str):
            try:
                dt = datetime.fromisoformat(date_val.replace(" ", "T"))
            except ValueError:
                dt = datetime.now()
        else:
            dt = datetime.now()

        return Income(
            id=row['id'],
            amount=Decimal(str(row['amount'])),
            source=row['source'],
            income_type=IncomeType.from_str(row['income_type']),
            date=dt,
            description=row['description'],
            is_taxed=bool(row['is_taxed'])
        )
