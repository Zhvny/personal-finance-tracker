from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class IncomeCategory(str, Enum):
    SALARY = "salary"
    FREELANCE = "freelance"
    INVESTMENT = "investment"
    SIDE_HUSTLE = "side-hustle"
    TRANSFER = "transfer"
    OTHER = "other"

    @classmethod
    def from_str(cls, value: Any):
        if not value:
            return cls.OTHER

        # If it's already an instance of the class, return it
        if isinstance(value, cls):
            return value

        # Handle case-insensitive and normalization
        clean_val = str(value).lower().strip().replace("_", "-").replace(" ", "-")

        # Try direct value match first (performance)
        for member in cls:
            if member.value == clean_val:
                return member

        # Fallback for common variants
        if clean_val in ["transfer", "trf", "bank-transfer", "pindah-buku", "remit"]:
            return cls.TRANSFER
        if clean_val in ["salary", "gaji", "payroll"]:
            return cls.SALARY
        if clean_val in ["investment", "dividend", "bunga", "interest"]:
            return cls.INVESTMENT
        if clean_val in ["freelance", "side-hustle", "project", "side-job"]:
            return cls.SIDE_HUSTLE

        try:
            # Try direct constructor as last resort
            return cls(clean_val)
        except (ValueError, Exception):
            # Fallback to OTHER instead of crashing
            return cls.OTHER

# Alias for backward compatibility
IncomeType = IncomeCategory

class Income(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    amount: Decimal
    source: str
    income_type: IncomeCategory
    date: datetime
    description: Optional[str] = None
    is_taxed: bool = False

    @field_validator("income_type", mode="before")
    @classmethod
    def validate_income_type(cls, v: Any) -> IncomeCategory:
        if isinstance(v, IncomeCategory):
            return v
        return IncomeCategory.from_str(v)
