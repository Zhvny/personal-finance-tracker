from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union


# ENUMS - EXACT MATCH dengan Finance Tracker yang sudah ada
class TransactionType(Enum):
    EXPENSE = "expense"
    INCOME = "income"

class PaymentMethod(Enum):
    """EXACT sama dengan expense_tracker/core/models.py"""
    CASH = "cash"
    DEBIT_CARD = "debit-card"      # hyphen, bukan underscore!
    CREDIT_CARD = "credit-card"    # hyphen!
    E_WALLET = "e-wallet"          # e-wallet, bukan terpisah!
    BANK_TRANSFER = "bank-transfer"  # hyphen!

    # QRIS bisa masuk ke E_WALLET atau tambahin di sini kalau mau
    QRIS = "qris"

class ExpenseCategory(Enum):
    """EXACT sama dengan expense_tracker/core/models.py"""
    FOOD = "food"
    TRANSPORT = "transport"
    HOUSING = "housing"
    ENTERTAINMENT = "entertainment"
    HEALTH = "health"              # health, bukan healthcare!
    SHOPPING = "shopping"
    EDUCATION = "education"
    INVESTMENT = "investment"
    OTHER = "other"

class IncomeCategory(Enum):
    """EXACT sama dengan income_tracker/core/models.py"""
    SALARY = "salary"
    FREELANCE = "freelance"
    INVESTMENT = "investment"      # Dividend, interest
    SIDE_HUSTLE = "side-hustle"    # side-hustle, bukan freelance doang!
    TRANSFER = "transfer"
    OTHER = "other"

# EXTENDED ENUMS - Untuk internal use (mapping ke yang di atas)
class DetailedExpenseCategory(Enum):
    """
    Extended categories untuk receipt classification.
    Nanti di-map ke ExpenseCategory yang sederhana saat export.
    """
    # FOOD subcategories
    FOOD_RESTAURANT = "food_restaurant"
    FOOD_FAST_FOOD = "food_fast_food"
    FOOD_GROCERY = "food_grocery"
    FOOD_BEVERAGE = "food_beverage"

    # TRANSPORT subcategories
    TRANSPORT_FUEL = "transport_fuel"
    TRANSPORT_PARKING = "transport_parking"
    TRANSPORT_TOLL = "transport_toll"
    TRANSPORT_PUBLIC = "transport_public"
    TRANSPORT_RIDE_HAILING = "transport_ride_hailing"

    # HOUSING subcategories
    HOUSING_RENT = "housing_rent"
    HOUSING_MORTGAGE = "housing_mortgage"
    HOUSING_MAINTENANCE = "housing_maintenance"
    HOUSING_UTILITIES = "housing_utilities"

    # HEALTH subcategories (akan di-map ke HEALTH)
    HEALTHCARE_HOSPITAL = "healthcare_hospital"
    HEALTHCARE_PHARMACY = "healthcare_pharmacy"
    HEALTHCARE_INSURANCE = "healthcare_insurance"
    HEALTHCARE_CHECKUP = "healthcare_checkup"

    # Dan seterusnya...

DETAILED_TO_SIMPLE_MAP = {
    # FOOD
    DetailedExpenseCategory.FOOD_RESTAURANT: ExpenseCategory.FOOD,
    DetailedExpenseCategory.FOOD_FAST_FOOD: ExpenseCategory.FOOD,
    DetailedExpenseCategory.FOOD_GROCERY: ExpenseCategory.FOOD,
    DetailedExpenseCategory.FOOD_BEVERAGE: ExpenseCategory.FOOD,

    # TRANSPORT
    DetailedExpenseCategory.TRANSPORT_FUEL: ExpenseCategory.TRANSPORT,
    DetailedExpenseCategory.TRANSPORT_PARKING: ExpenseCategory.TRANSPORT,
    DetailedExpenseCategory.TRANSPORT_TOLL: ExpenseCategory.TRANSPORT,
    DetailedExpenseCategory.TRANSPORT_PUBLIC: ExpenseCategory.TRANSPORT,
    DetailedExpenseCategory.TRANSPORT_RIDE_HAILING: ExpenseCategory.TRANSPORT,

    # HOUSING
    DetailedExpenseCategory.HOUSING_RENT: ExpenseCategory.HOUSING,
    DetailedExpenseCategory.HOUSING_MORTGAGE: ExpenseCategory.HOUSING,
    DetailedExpenseCategory.HOUSING_MAINTENANCE: ExpenseCategory.HOUSING,
    DetailedExpenseCategory.HOUSING_UTILITIES: ExpenseCategory.HOUSING,

    # HEALTH
    DetailedExpenseCategory.HEALTHCARE_HOSPITAL: ExpenseCategory.HEALTH,
    DetailedExpenseCategory.HEALTHCARE_PHARMACY: ExpenseCategory.HEALTH,
    DetailedExpenseCategory.HEALTHCARE_INSURANCE: ExpenseCategory.HEALTH,
    DetailedExpenseCategory.HEALTHCARE_CHECKUP: ExpenseCategory.HEALTH,
}

# PAYMENT METHOD DETECTION - Map dari teks ke enum
PAYMENT_METHOD_KEYWORDS = {
    PaymentMethod.CASH: ['cash', 'tunai', 'uang'],
    PaymentMethod.DEBIT_CARD: ['debit', 'kartu debit', 'atm'],
    PaymentMethod.CREDIT_CARD: ['credit', 'kartu kredit', 'cc', 'visa', 'mastercard'],
    PaymentMethod.E_WALLET: ['gopay', 'ovo', 'dana', 'shopeepay', 'linkaja', 'e-wallet', 'ewallet', 'dompet digital'],
    PaymentMethod.BANK_TRANSFER: ['transfer', 'bank', 'va', 'virtual account'],
    PaymentMethod.QRIS: ['qris', 'qr', 'qr code', 'scan'],
}

# VALUE OBJECTS & ENTITIES
@dataclass(frozen=True)
class Money:
    """Value Object untuk uang - immutable"""
    amount: float
    currency: str = "IDR"

    def add(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(self.amount + other.amount, self.currency)

    def format(self) -> str:
        if self.currency == "IDR":
            return f"Rp{self.amount:,.0f}"
        return f"{self.currency} {self.amount:,.2f}"

@dataclass
class LineItem:
    """Entity untuk item line dalam receipt"""
    name: str
    quantity: float = 1.0
    unit_price: Money = field(default_factory=lambda: Money(0))
    total_price: Money = field(default_factory=lambda: Money(0))
    category: Optional[ExpenseCategory] = None

    def __post_init__(self):
        if self.total_price.amount == 0 and self.unit_price.amount > 0:
            self.total_price = Money(
                self.unit_price.amount * self.quantity,
                self.unit_price.currency
            )

@dataclass
class ReceiptData:
    """Aggregate Root untuk receipt"""
    merchant_name: str = ""
    transaction_date: datetime = field(default_factory=datetime.now)
    total_amount: Money = field(default_factory=lambda: Money(0))
    payment_method: PaymentMethod = PaymentMethod.E_WALLET  # Default ke e-wallet untuk QRIS
    transaction_type: TransactionType = TransactionType.EXPENSE
    category: Union[ExpenseCategory, IncomeCategory, str] = ExpenseCategory.OTHER
    items: List[LineItem] = field(default_factory=list)
    tax_amount: Optional[Money] = None
    discount_amount: Optional[Money] = None
    raw_ocr_text: str = ""
    confidence_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_expense_dict(self) -> Dict[str, Any]:
        """
        Convert ke format expense_tracker yang sudah ada.
        PASTIKAN field names sama persis!
        """
        # Handle category mapping
        if isinstance(self.category, DetailedExpenseCategory):
            simple_category = DETAILED_TO_SIMPLE_MAP.get(self.category, ExpenseCategory.OTHER)
            category_value = simple_category.value
        elif isinstance(self.category, ExpenseCategory):
            category_value = self.category.value
        else:
            category_value = str(self.category)

        return {
            "amount": self.total_amount.amount,
            "category": category_value,  # "food", "transport", etc (bukan "FOOD")
            "description": self.merchant_name,
            "date": self.transaction_date.strftime("%Y-%m-%d"),
            "payment_method": self.payment_method.value  # "e-wallet", "debit-card", etc
        }

    def to_income_dict(self) -> Dict[str, Any]:
        """
        Convert ke format income_tracker yang sudah ada.
        """
        if isinstance(self.category, IncomeCategory):
            category_value = self.category.value
        else:
            category_value = str(self.category)

        return {
            "amount": self.total_amount.amount,
            "income_type": category_value,  # "salary", "freelance", "side-hustle", etc
            "description": self.merchant_name,
            "date": self.transaction_date.strftime("%Y-%m-%d")
        }

# ABSTRACT INTERFACES
class IOCREngine(ABC):
    @abstractmethod
    def extract_text(self, image_path: str) -> str:
        pass

    @abstractmethod
    def get_confidence_score(self, image_path: str) -> float:
        pass

    @property
    @abstractmethod
    def engine_name(self) -> str:
        pass

class ITextParser(ABC):
    @abstractmethod
    def parse(self, raw_text: str) -> ReceiptData:
        pass

class ICategoryClassifier(ABC):
    @abstractmethod
    def classify(self, receipt: ReceiptData) -> Any:
        pass

    @abstractmethod
    def classify_item(self, item_name: str) -> Optional[ExpenseCategory]:
        pass

class IDataExporter(ABC):
    @abstractmethod
    def export(self, receipt: ReceiptData) -> bool:
        pass

    @abstractmethod
    def can_export(self, receipt: ReceiptData) -> bool:
        pass

class IUserInterface(ABC):
    @abstractmethod
    def display_receipt(self, receipt: ReceiptData) -> None:
        pass

    @abstractmethod
    def edit_receipt(self, receipt: ReceiptData) -> ReceiptData:
        pass

    @abstractmethod
    def confirm_action(self, message: str) -> bool:
        pass

    @abstractmethod
    def get_input(self, prompt: str) -> str:
        pass

    @abstractmethod
    def show_success(self, message: str) -> None:
        pass

    @abstractmethod
    def show_error(self, message: str) -> None:
        pass

class IReceiptValidator(ABC):
    @abstractmethod
    def validate(self, receipt: ReceiptData) -> tuple[bool, List[str]]:
        pass

class IImagePreprocessor(ABC):
    @abstractmethod
    def preprocess(self, image_path: str) -> str:
        pass
