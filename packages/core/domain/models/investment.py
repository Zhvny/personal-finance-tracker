from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssetType(str, Enum):
    STOCK = "stock"
    CRYPTO = "crypto"
    FOREX = "forex"
    COMMODITY = "commodity"
    OTHER = "other"

class InvestmentStatus(str, Enum):
    HOLDING = "holding"
    SOLD = "sold"
    PARTIAL_SOLD = "partial"

class SellTransaction(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    sell_date: datetime
    quantity: Decimal
    sell_price: Decimal
    sell_currency: str = "IDR"
    fees: Decimal = Decimal("0.0")
    fx_rate: Decimal = Decimal("1.0")
    realized_pl: Decimal = Decimal("0.0")
    realized_pl_idr: Decimal = Decimal("0.0")
    realized_pl_pct: Decimal = Decimal("0.0")
    ticker: Optional[str] = None
    investment_id: Optional[int] = None

class Investment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    asset_type: str
    ticker: str
    quantity: Decimal
    buy_price: Decimal
    buy_currency: str
    buy_price_idr: Optional[Decimal] = None
    buy_date: datetime = Field(default_factory=datetime.now)
    status: InvestmentStatus = InvestmentStatus.HOLDING
    remaining_quantity: Optional[Decimal] = None
    is_favorite: bool = False
    sells: List[SellTransaction] = Field(default_factory=list)

    # Enrichment fields
    current_price_idr: Optional[Decimal] = None
    current_price_date: Optional[Union[datetime, date, str]] = None
    pl: Optional[Decimal] = None
    pl_pct: Optional[Decimal] = None
    cap_gain: Optional[Decimal] = None
    fx_gain: Optional[Decimal] = None
    is_stale: bool = False
    fx_buy: Optional[Decimal] = None
    fx_live: Optional[Decimal] = None

    @field_validator("sells", mode="before")
    @classmethod
    def allow_none_for_sells(cls, v):
        if v is None:
            return []
        return v

    @model_validator(mode="after")
    def set_remaining_quantity(self) -> "Investment":
        if self.remaining_quantity is None:
            self.remaining_quantity = self.quantity
        return self
