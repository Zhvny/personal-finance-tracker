from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, computed_field


class AccountType(str, Enum):
    CASH = "cash"
    BANK = "bank"
    E_WALLET = "e-wallet"
    INVESTMENT = "investment"
    OTHER = "other"

class VirtualAccount(BaseModel):
    id: str
    name: str
    balance: Decimal
    target_amount: Decimal = Decimal("0.0")   # FIX #4: was missing, referenced in dashboard_service
    cashflow_velocity: Decimal = Decimal("0.0")
    sankey_node_id: Optional[str] = None

    @computed_field  # type: ignore[misc]
    @property
    def progress_pct(self) -> float:
        """Percentage of target_amount reached. Returns 0 if no target set."""
        if self.target_amount and self.target_amount > 0:
            return float(self.balance / self.target_amount * 100)
        return 0.0

# Alias for backward compatibility
Account = VirtualAccount

