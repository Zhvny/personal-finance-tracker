import logging
import sqlite3
from typing import Dict, List, Optional

from apps.cli.receipt_reader.core.interfaces import IDataExporter, ReceiptData

logger = logging.getLogger(__name__)


class ExportResult:
    def __init__(self, success: bool, message: str, export_id: Optional[int] = None):
        self.success = success
        self.message = message
        self.export_id = export_id


class UnifiedExporter:
    """
    Service layer untuk export dengan:
    - Multiple exporter support
    - Retry mechanism
    - Transaction logging
    - Error recovery
    """

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.exporters: List[IDataExporter] = []
        self._init_exporters()

        # Setup logging database
        self.log_db_path = f"{base_path}/receipt_reader/data/export_log.db"
        self._init_log_db()

    def _init_exporters(self):
        """Initialize semua available exporters"""
        from apps.cli.receipt_reader.core.exporters.expense_exporter import ExpenseExporter
        from apps.cli.receipt_reader.core.exporters.income_exporter import IncomeExporter
        from apps.cli.receipt_reader.core.exporters.json_exporter import JSONExporter

        self.exporters = [
            ExpenseExporter(self.base_path),
            IncomeExporter(self.base_path),
            JSONExporter(f"{self.base_path}/receipt_reader/exports"),
        ]

    def _init_log_db(self):
        """Initialize logging database"""
        import os

        os.makedirs(os.path.dirname(self.log_db_path), exist_ok=True)

        conn = sqlite3.connect(self.log_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS export_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_merchant TEXT,
                receipt_amount REAL,
                receipt_date TEXT,
                target_system TEXT,
                success BOOLEAN,
                message TEXT,
                exported_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def export(self, receipt: ReceiptData, preferred_system: Optional[str] = None) -> ExportResult:
        """
        Export receipt ke appropriate system

        Args:
            receipt: ReceiptData yang mau di-export
            preferred_system: 'expense', 'income', 'json', atau None untuk auto-detect
        """
        # Determine target system
        if preferred_system:
            target = preferred_system
        else:
            target = "expense" if receipt.transaction_type.value == "expense" else "income"

        # Find appropriate exporter
        for exporter in self.exporters:
            if not exporter.can_export(receipt):
                continue

            # Check kalau match dengan target
            exporter_name = exporter.__class__.__name__.lower()
            if target in exporter_name:
                try:
                    success = exporter.export(receipt)

                    # Log result
                    self._log_export(receipt, target, success, "OK" if success else "Failed")

                    if success:
                        return ExportResult(
                            success=True,
                            message=f"Berhasil export ke {target}",
                            export_id=None,  # Bisa di-enhance untuk return ID
                        )

                except Exception as e:
                    self._log_export(receipt, target, False, str(e))
                    return ExportResult(success=False, message=f"Error: {str(e)}")

        # Fallback: coba semua exporter yang bisa
        for exporter in self.exporters:
            if exporter.can_export(receipt):
                try:
                    success = exporter.export(receipt)
                    if success:
                        self._log_export(receipt, "fallback", True, "Fallback success")
                        return ExportResult(success=True, message="Berhasil export (fallback)")
                except Exception as exc:
                    logger.warning("Fallback exporter %s failed: %s", type(exporter).__name__, exc)
                    continue

        return ExportResult(success=False, message="Tidak ada exporter yang berhasil")

    def _log_export(self, receipt: ReceiptData, target: str, success: bool, message: str):
        """Log export attempt"""
        conn = sqlite3.connect(self.log_db_path)
        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO export_log (receipt_merchant, receipt_amount, receipt_date, target_system, success, message)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    receipt.merchant_name,
                    receipt.total_amount.amount,
                    receipt.transaction_date.isoformat(),
                    target,
                    success,
                    message,
                ),
            )

            conn.commit()
        except (sqlite3.Error, AttributeError, ValueError) as exc:
            logger.warning("Export log write failed: %s", exc)
        finally:
            conn.close()

    def get_export_history(self, limit: int = 10) -> List[Dict]:
        """Get recent export history"""
        try:
            conn = sqlite3.connect(self.log_db_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT * FROM export_log
                    ORDER BY exported_at DESC
                    LIMIT ?
                """,
                    (limit,),
                )

                rows = cursor.fetchall()

                return [dict(row) for row in rows]
            finally:
                conn.close()

        except sqlite3.Error as exc:
            logger.warning("Export history read failed: %s", exc)
            return []
