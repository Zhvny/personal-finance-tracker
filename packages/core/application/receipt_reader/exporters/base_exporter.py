import logging

logger = logging.getLogger(__name__)

from abc import ABC, abstractmethod

from packages.core.application.receipt_reader.interfaces import IDataExporter, ReceiptData


class BaseExporter(IDataExporter, ABC):
    """Template untuk semua exporters"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    @abstractmethod
    def _get_table_schema(self) -> str:
        pass

    @abstractmethod
    def _prepare_data(self, receipt: ReceiptData) -> tuple:
        """Return tuple untuk SQL INSERT"""
        pass

    def can_export(self, receipt: ReceiptData) -> bool:
        """Check apakah bisa handle receipt ini"""
        return True

    def export(self, receipt: ReceiptData) -> bool:
        """Template method untuk export"""
        try:
            import os
            import sqlite3

            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create table
            cursor.execute(self._get_table_schema())

            # Insert data
            data = self._prepare_data(receipt)
            cursor.execute(self._get_insert_query(), data)

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.warning("Failed to exporting receipt data", exc_info=True)
            print(f"Export error: {e}")
            return False

    @abstractmethod
    def _get_insert_query(self) -> str:
        pass
