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

class ExpenseExporter:
    """
    Export ReceiptData ke expense_tracker SQLite DB with transparent Postgres redirection.
    Schema matches Finance Tracker expense_tracker/core/repository.py exactly:
      id, amount, description, category, payment_method, date, is_recurring, recurring_period
    """

    def __init__(self, base_path: str):
        self.db_path = os.path.join(base_path, "expense_tracker", "data", "expense.db")

    def can_export(self, receipt: ReceiptData) -> bool:
        return receipt.transaction_type == TransactionType.EXPENSE

    # Map QRIS → e-wallet (Finance Tracker tidak punya QRIS)
    _PAYMENT_MAP = {
        "qris":          "e-wallet",
        "cash":          "cash",
        "debit-card":    "debit-card",
        "credit-card":   "credit-card",
        "e-wallet":      "e-wallet",
        "bank-transfer": "bank-transfer",
    }

    def export(self, receipt: ReceiptData) -> bool:
        try:
            # Guard: skip receipts with invalid amounts
            raw_amount = receipt.total_amount.amount if receipt.total_amount else 0
            if not raw_amount or float(raw_amount) <= 0:
                logger.warning(
                    f"ExpenseExporter: skipping receipt with invalid amount "
                    f"({raw_amount}) for '{receipt.merchant_name}'"
                )
                return False

            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            category = (
                receipt.category.value
                if hasattr(receipt.category, "value")
                else str(receipt.category)
            )
            pay_raw  = receipt.payment_method.value if receipt.payment_method else "cash"
            pay_val  = self._PAYMENT_MAP.get(pay_raw, "cash")

            script = """
                CREATE TABLE IF NOT EXISTS expenses (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount           REAL    NOT NULL,
                    description      TEXT    NOT NULL,
                    category         TEXT    NOT NULL,
                    payment_method   TEXT    NOT NULL,
                    date             TEXT    NOT NULL,
                    is_recurring     BOOLEAN DEFAULT 0,
                    recurring_period TEXT,
                    created_at       TEXT    DEFAULT CURRENT_TIMESTAMP
                )
            """
            Database.execute_script(self.db_path, script)

            sql = """INSERT INTO expenses
                       (amount, description, category, payment_method, date)
                       VALUES (?, ?, ?, ?, ?)"""
            params = (
                raw_amount,
                receipt.merchant_name or "",
                category,
                pay_val,
                receipt.transaction_date.isoformat(),
            )

            Database.execute(self.db_path, sql, params)
            return True
        except Exception as e:
            logger.error(f"ExpenseExporter error: {e}")
            return False

