from abc import ABC, abstractmethod
from typing import List, Optional

from .models import Income


class IIncomeRepository(ABC):
    @abstractmethod
    def save(self, income: Income) -> int: pass

    @abstractmethod
    def get_all(self, start_date=None, end_date=None, income_type: Optional[str] = None, search: Optional[str] = None) -> List[Income]: pass

    @abstractmethod
    def get_by_type(self, income_type: str) -> List[Income]: pass

    @abstractmethod
    def get_monthly_summary(self, year: int, month: int) -> dict: pass

    @abstractmethod
    def delete(self, id: int) -> bool: pass
