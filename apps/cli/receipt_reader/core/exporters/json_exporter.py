import json
import os
from datetime import datetime
from typing import Any, Dict

from apps.cli.receipt_reader.core.interfaces import IDataExporter, ReceiptData


class JSONExporter(IDataExporter):
    """Export receipt ke file JSON"""

    def __init__(self, output_dir: str = "exports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def can_export(self, receipt: ReceiptData) -> bool:
        """Selalu bisa export ke JSON"""
        return True

    def export(self, receipt: ReceiptData) -> bool:
        """Export receipt ke file JSON"""
        try:
            filename = self._generate_filename(receipt)
            filepath = os.path.join(self.output_dir, filename)

            data = self._receipt_to_dict(receipt)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            return True

        except Exception as e:
            print(f"JSON Export error: {e}")
            return False

    def _generate_filename(self, receipt: ReceiptData) -> str:
        """Generate filename dari merchant dan tanggal"""
        merchant = receipt.merchant_name.replace(' ', '_')[:20]
        date_str = receipt.transaction_date.strftime("%Y%m%d")
        timestamp = datetime.now().strftime("%H%M%S")
        return f"receipt_{merchant}_{date_str}_{timestamp}.json"

    def _receipt_to_dict(self, receipt: ReceiptData) -> Dict[str, Any]:
        """Convert ReceiptData ke dictionary"""
        return {
            "merchant_name": receipt.merchant_name,
            "transaction_date": receipt.transaction_date.isoformat(),
            "total_amount": {
                "amount": receipt.total_amount.amount,
                "currency": receipt.total_amount.currency
            },
            "payment_method": receipt.payment_method.value,
            "transaction_type": receipt.transaction_type.value,
            "category": str(receipt.category),
            "items": [
                {
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit_price": {
                        "amount": item.unit_price.amount,
                        "currency": item.unit_price.currency
                    },
                    "total_price": {
                        "amount": item.total_price.amount,
                        "currency": item.total_price.currency
                    }
                }
                for item in receipt.items
            ],
            "tax_amount": {
                "amount": receipt.tax_amount.amount,
                "currency": receipt.tax_amount.currency
            } if receipt.tax_amount else None,
            "discount_amount": {
                "amount": receipt.discount_amount.amount,
                "currency": receipt.discount_amount.currency
            } if receipt.discount_amount else None,
            "raw_ocr_text": receipt.raw_ocr_text,
            "confidence_score": receipt.confidence_score,
            "metadata": receipt.metadata,
            "exported_at": datetime.now().isoformat()
        }
