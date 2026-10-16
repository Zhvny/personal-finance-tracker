from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class ExpenseCategory(Enum):
    FOOD = "food"
    TRANSPORT = "transport"
    HOUSING = "housing"
    ENTERTAINMENT = "entertainment"
    HEALTH = "health"
    SHOPPING = "shopping"
    EDUCATION = "education"
    INVESTMENT = "investment"
    OTHER = "other"

class PaymentMethod(Enum):
    CASH = "cash"
    DEBIT_CARD = "debit-card"
    CREDIT_CARD = "credit-card"
    E_WALLET = "e-wallet"
    BANK_TRANSFER = "bank-transfer"
    OVO = "ovo"
    GOPAY = "gopay"
    SHOPEEPAY = "shopeepay"
    QRIS = "qris"

@dataclass
class Expense:
    amount: Decimal
    description: str
    category: ExpenseCategory
    payment_method: PaymentMethod
    date: datetime
    is_recurring: bool = False       # Langganan bulanan?
    recurring_period: Optional[str] = None  # "monthly", "yearly"
    id: Optional[int] = None

    def __post_init__(self):
        """Automatically validate upon creation."""
        self.validate()

    def validate(self):
        """
        Business Rule Validation: Ensure data integrity before persistence.
        Raises ValueError if any rule is violated.
        """
        if self.amount <= 0:
            raise ValueError("Amount must be greater than 0.")

        if len(self.description) > 500:
            raise ValueError("Description is too long (max 500 chars).")

        if len(self.description.strip()) == 0:
            raise ValueError("Description cannot be empty.")

        # Future date check: allow any time today, reject tomorrow+
        if self.date.date() > datetime.now().date():
            raise ValueError("Transaction date cannot be in the future.")

        # Too old check (sanity check: older than 1900?)
        if self.date.year < 1900:
            raise ValueError("Transaction date is invalid (too far in the past).")
