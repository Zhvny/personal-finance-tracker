from abc import ABC, abstractmethod
from typing import Dict

from packages.core.domain.models.investment import Investment
from packages.core.domain.repositories.investment_repository import IInvestmentRepository  # noqa: F401 (re-export)


class IPriceService(ABC):
    """Abstract Base Class untuk semua price service"""

    @abstractmethod
    def get_prices(self, investment: Investment) -> Dict[str, float]:
        """Return dict dengan keys: usd, idr, buy_price_idr, current_price_idr"""
        pass

    @abstractmethod
    def supports(self, asset_type: str) -> bool:
        """Cek apakah service ini support asset type tertentu"""
        pass


class IFXService(ABC):
    """Abstract Base Class untuk foreign exchange service"""

    @abstractmethod
    def get_usd_idr(self) -> float:
        """Get current USD to IDR rate"""
        pass
