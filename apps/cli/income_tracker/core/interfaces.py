from abc import ABC, abstractmethod
from typing import List

from packages.core.domain.models import Income


class IIncomeRepository(ABC):
    @abstractmethod
    def save(self, income: Income) -> int: pass

    @abstractmethod
    def get_all(self, start_date=None, end_date=None) -> List[Income]: pass

    @abstractmethod
    def get_by_type(self, income_type: str) -> List[Income]: pass

    @abstractmethod
    def get_summary_by_month(self, year: int, month: int) -> dict: pass

    @abstractmethod
    def delete(self, id: int) -> bool: pass
