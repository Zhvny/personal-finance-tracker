import logging
import os

from packages.core.application.receipt_reader.interfaces import ReceiptData, TransactionType

# Try to import shared Database utility for Postgres redirection
try:
    from packages.core.infrastructure.persistence.database import Database
except ImportError:
    import sqlite3
    class Database:
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

class IncomeExporter:
    """
    Export ReceiptData ke income_tracker SQLite DB with transparent Postgres redirection.
    Schema matches Finance Tracker income_tracker/core/repository.py exactly:
      id, amount, source, income_type, date, description, is_taxed
    """

    def __init__(self, base_path: str):
        self.db_path = os.path.join(base_path, "income_tracker", "data", "income.db")

    def can_export(self, receipt: ReceiptData) -> bool:
        return receipt.transaction_type == TransactionType.INCOME

    # Map receipt category → income_type (Finance Tracker IncomeType enum values)
    _INCOME_TYPE_MAP = {
        "salary":     "salary",
        "freelance":  "freelance",
        "investment": "investment",
        "side-hustle":"side-hustle",
        "transfer":   "transfer",
        "other":      "other",
        # receipt_reader categories → closest income_type
        "food":       "other",
        "transport":  "other",
        "housing":    "other",
        "entertainment": "other",
        "health":     "other",
        "shopping":   "other",
        "education":  "other",
    }

    def export(self, receipt: ReceiptData) -> bool:
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            cat_raw    = (
                receipt.category.value
                if hasattr(receipt.category, "value")
                else str(receipt.category)
            )
            income_type = self._INCOME_TYPE_MAP.get(cat_raw, "other")

            script = """
                CREATE TABLE IF NOT EXISTS incomes (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount      REAL    NOT NULL,
                    source      TEXT    NOT NULL,
                    income_type TEXT    NOT NULL,
                    date        TEXT    NOT NULL,
                    description TEXT,
                    is_taxed    BOOLEAN DEFAULT 0,
                    created_at  TEXT    DEFAULT CURRENT_TIMESTAMP
                )
            """
            Database.execute_script(self.db_path, script)

            sql = """INSERT INTO incomes
                       (amount, source, income_type, date, description)
                       VALUES (?, ?, ?, ?, ?)"""
            params = (
                receipt.total_amount.amount,
                receipt.merchant_name or "",   # source = who sent money
                income_type,
                receipt.transaction_date.isoformat(),
                receipt.merchant_name or "",   # description = same as source for now
            )

            Database.execute(self.db_path, sql, params)
            return True
        except Exception as e:
            logger.error(f"IncomeExporter error: {e}")
            return False

