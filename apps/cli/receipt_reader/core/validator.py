from abc import ABC, abstractmethod
from typing import List, Tuple

from apps.cli.receipt_reader.core.interfaces import IReceiptValidator, ReceiptData


class ValidationResult:
    def __init__(self, is_valid: bool, errors: List[str], warnings: List[str]):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings

class BaseValidator(IReceiptValidator, ABC):
    """Base class untuk validators"""

    def __init__(self, next_validator: IReceiptValidator = None):
        self._next = next_validator

    def validate(self, receipt: ReceiptData) -> Tuple[bool, List[str]]:
        result = self._do_validate(receipt)

        if self._next:
            next_valid, next_errors = self._next.validate(receipt)
            result = (
                result[0] and next_valid,
                result[1] + next_errors
            )

        return result

    @abstractmethod
    def _do_validate(self, receipt: ReceiptData) -> Tuple[bool, List[str]]:
        pass

class AmountValidator(BaseValidator):
    """Validasi jumlah uang"""

    def _do_validate(self, receipt: ReceiptData) -> Tuple[bool, List[str]]:
        errors = []

        if receipt.total_amount.amount <= 0:
            errors.append("Total amount harus lebih dari 0")

        if receipt.total_amount.amount > 1_000_000_000:  # 1 Milyar
            errors.append("Total amount terlalu besar (>1M), periksa kembali")

        # Check apakah items sum match total
        if receipt.items:
            items_total = sum(item.total_price.amount for item in receipt.items)
            diff = abs(items_total - receipt.total_amount.amount)
            if diff > 1000:  # Tolerance 1000 rupiah
                errors.append(f"Total items (Rp{items_total:,.0f}) tidak match dengan total (Rp{receipt.total_amount.amount:,.0f})")

        return (len(errors) == 0, errors)

class DateValidator(BaseValidator):
    """Validasi tanggal"""

    def _do_validate(self, receipt: ReceiptData) -> Tuple[bool, List[str]]:
        from datetime import datetime, timedelta

        errors = []
        now = datetime.now()

        # Check future date
        if receipt.transaction_date > now + timedelta(days=1):
            errors.append("Tanggal transaksi di masa depan")

        # Check too old (more than 5 years)
        if receipt.transaction_date < now - timedelta(days=365*5):
            errors.append("Tanggal transaksi terlalu lama (>5 tahun)")

        return (len(errors) == 0, errors)

class MerchantValidator(BaseValidator):
    """Validasi merchant"""

    def _do_validate(self, receipt: ReceiptData) -> Tuple[bool, List[str]]:
        errors = []

        if not receipt.merchant_name or receipt.merchant_name.strip() == "":
            errors.append("Nama merchant kosong")
        elif len(receipt.merchant_name) < 2:
            errors.append("Nama merchant terlalu pendek")

        return (len(errors) == 0, errors)

class CompositeValidator(IReceiptValidator):
    """Composite validator yang gabungkan semua validators"""

    def __init__(self):
        self.validators = [
            AmountValidator(),
            DateValidator(),
            MerchantValidator()
        ]

    def validate(self, receipt: ReceiptData) -> Tuple[bool, List[str]]:
        all_errors = []

        for validator in self.validators:
            is_valid, errors = validator.validate(receipt)
            all_errors.extend(errors)

        return (len(all_errors) == 0, all_errors)
