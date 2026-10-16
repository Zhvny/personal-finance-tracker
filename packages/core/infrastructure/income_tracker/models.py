from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class IncomeType(Enum):
    SALARY = "salary"
    FREELANCE = "freelance"
    INVESTMENT = "investment"  # Dividend, interest
    SIDE_HUSTLE = "side-hustle"
    TRANSFER = "transfer"
    OTHER = "other"

    @classmethod
    def from_str(cls, value: str):
        try:
            return cls(value.lower().replace("_", "-"))
        except ValueError:
            return cls.OTHER

@dataclass
class Income:
    amount: Decimal                  # Dalam IDR
    source: str                      # "Gaji Bulanan", "Project A", dll
    income_type: IncomeType
    date: datetime
    description: Optional[str] = None
    is_taxed: bool = False           # Sudah dipotong pajak?
    id: Optional[int] = None

    def __post_init__(self):
        self.validate()

    def validate(self):
        if self.amount <= 0:
            raise ValueError("Amount must be greater than 0.")
        if len(self.source) > 100:
            raise ValueError("Source name is too long.")
        if self.description and len(self.description) > 500:
            raise ValueError("Description is too long.")
        # Future date check: allow any time today, reject tomorrow+
        if self.date.date() > datetime.now().date():
            raise ValueError("Transaction date cannot be in the future.")
