from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MarketData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    price: float
    timestamp: datetime
    currency: str = "IDR"
    id: Optional[int] = None
    change_pct: Optional[float] = None
    volume: Optional[int] = None
    metadata: Optional[str] = None
