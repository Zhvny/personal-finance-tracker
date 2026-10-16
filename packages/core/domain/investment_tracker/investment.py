# models/investment.py
# Canonical domain model for investment_tracker.
# Imported by: core/interfaces.py, core/repository.py, core/calculator.py,
#              services/, ui/cli_view.py, main.py
# DO NOT duplicate: a stale stub previously existed at core/models.py and has been removed.
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class InvestmentStatus(Enum):
    HOLDING = "holding"
    SOLD = "sold"
    PARTIAL_SOLD = "partial"

@dataclass
class SellTransaction:
    sell_date: datetime
    quantity: float
    sell_price: float
    sell_currency: str = "IDR"
    fees: float = 0.0
    realized_pl: float = field(init=False, default=0.0)
    realized_pl_pct: float = field(init=False, default=0.0)

    def __post_init__(self):
        self.sell_currency = str(self.sell_currency).upper()

@dataclass
class Investment:
    asset_type: str
    ticker: str
    quantity: float
    buy_price: float
    buy_currency: str
    buy_price_idr: Optional[float] = None
    buy_date: Optional[datetime] = None
    id: Optional[int] = None
    status: InvestmentStatus = InvestmentStatus.HOLDING
    is_favorite: bool = False
    remaining_quantity: float = field(init=False)
    sells: List[SellTransaction] = field(default_factory=list)

    def __post_init__(self):
        if self.buy_date is None:
            self.buy_date = datetime.now()
        self.buy_currency = str(self.buy_currency).upper()
        self.asset_type = str(self.asset_type).lower()
        self.ticker = str(self.ticker).upper()
        self.remaining_quantity = self.quantity
        if self.buy_price_idr is None and self.buy_currency == "IDR":
            self.buy_price_idr = self.buy_price
