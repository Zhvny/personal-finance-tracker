from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, model_validator


class ExpenseCategory(str, Enum):
    FOOD = "food"
    TRANSPORT = "transport"
    HOUSING = "housing"
    ENTERTAINMENT = "entertainment"
    HEALTH = "health"
    SHOPPING = "shopping"
    EDUCATION = "education"
    INVESTMENT = "investment"
    OTHER = "other"

    @classmethod
    def _missing_(cls, value):
        """Handle legacy / variant string values from DB."""
        if not isinstance(value, str):
            return None
        normalized = value.lower().strip()
        # Legacy label → canonical value map
        _LEGACY_MAP = {
            "food & drink": "food",
            "food and drink": "food",
            "transportation": "transport",
            "groceries": "food",
            "utility": "housing",
            "utilities": "housing",
            "medical": "health",
        }
        canonical = _LEGACY_MAP.get(normalized, normalized)
        for member in cls:
            if member.value == canonical:
                return member
        return cls.OTHER  # fallback to 'other' for fully unknown values

class PaymentMethod(str, Enum):
    CASH = "cash"
    DEBIT_CARD = "debit-card"
    CREDIT_CARD = "credit-card"
    E_WALLET = "e-wallet"
    BANK_TRANSFER = "bank-transfer"
    OVO = "ovo"
    GOPAY = "gopay"
    SHOPEEPAY = "shopeepay"
    QRIS = "qris"

    @classmethod
    def _missing_(cls, value):
        """Handle uppercase and legacy payment method strings from DB."""
        if not isinstance(value, str):
            return None
        normalized = value.lower().strip().replace(" ", "-")
        _LEGACY_MAP = {
            "debit card": "debit-card",
            "credit card": "credit-card",
            "e wallet": "e-wallet",
            "ewallet": "e-wallet",
            "bank transfer": "bank-transfer",
        }
        canonical = _LEGACY_MAP.get(normalized, normalized)
        for member in cls:
            if member.value == canonical:
                return member
        return cls.CASH  # fallback

class Expense(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=False)

    id: Optional[int] = None
    amount: Decimal
    description: str
    category: ExpenseCategory
    payment_method: PaymentMethod
    date: datetime
    is_recurring: bool = False
    recurring_period: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_fields(cls, data: Any) -> Any:
        """Pre-process raw DB rows to coerce legacy enum strings."""
        if not isinstance(data, dict):
            # from_attributes mode — let _missing_ handle it
            return data
        cat = data.get("category")
        pm = data.get("payment_method")
        if isinstance(cat, str):
            resolved = ExpenseCategory._missing_(cat)
            if resolved is not None:
                data["category"] = resolved.value
        if isinstance(pm, str):
            resolved = PaymentMethod._missing_(pm)
            if resolved is not None:
                data["payment_method"] = resolved.value
        return data
