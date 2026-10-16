from abc import ABC, abstractmethod
from datetime import date
from typing import Optional


class IFXRepository(ABC):
    """
    Abstract interface for foreign exchange rate persistence.
    """
    @abstractmethod
    def save_rate(self, pair: str, rate_date: date, rate: float) -> None:
        """
        Save an exchange rate for a specific pair and date.
        """
        pass

    @abstractmethod
    def get_closest_rate(self, pair: str, rate_date: date) -> Optional[float]:
        """
        Retrieve the closest exchange rate for a pair on or before the given date.
        """
        pass
