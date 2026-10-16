from abc import ABC, abstractmethod
from typing import Dict, List

from packages.core.domain.models import Expense


class IExpenseRepository(ABC):
    @abstractmethod
    def save(self, expense: Expense) -> int: pass

    @abstractmethod
    def get_all(self, start_date=None, end_date=None, category=None) -> List[Expense]: pass

    @abstractmethod
    def get_by_category(self, category: str) -> List[Expense]: pass

    @abstractmethod
    def get_monthly_summary(self, year: int, month: int) -> Dict: pass

    @abstractmethod
    def get_category_breakdown(self, year: int, month: int) -> Dict[str, float]: pass

    @abstractmethod
    def delete(self, id: int) -> bool: pass
