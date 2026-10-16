from abc import ABC, abstractmethod
from typing import List, Optional

from packages.core.domain.models import MarketData


class IMarketDataRepository(ABC):
    @abstractmethod
    def save(self, data: MarketData) -> bool: pass

    @abstractmethod
    def get_latest(self, ticker: str) -> Optional[MarketData]: pass

    @abstractmethod
    def get_history(self, ticker: str, limit: int = 24) -> List[MarketData]: pass
