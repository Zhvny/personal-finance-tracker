from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from packages.core.domain.models import Expense


class IExpenseRepository(ABC):
    @abstractmethod
    def save(self, expense: Expense) -> int: pass

    @abstractmethod
    def get_all(self, start_date=None, end_date=None, category=None) -> List[Expense]: pass

    @abstractmethod
    def get_by_id(self, expense_id: int) -> Optional[Expense]: pass

    @abstractmethod
    def get_monthly_summary(self, year: int, month: int) -> Dict: pass

    @abstractmethod
    def delete(self, expense_id: int) -> bool: pass

    @abstractmethod
    def get_budgets(self, year: int, month: int) -> Dict[str, float]: pass

    @abstractmethod
    def set_budget(self, category: str, year: int, month: int, limit_amt: float) -> bool: pass
