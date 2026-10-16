from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class Transaction(BaseModel):
    id: Optional[str] = None
    date: datetime
    description: str
    amount: float
    category: Optional[str] = None
    tags: list[str] = []
    metadata: Dict[str, Any] = {}
