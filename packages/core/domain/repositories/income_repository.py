from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from packages.core.domain.models import Income


class IIncomeRepository(ABC):
    @abstractmethod
    def save(self, income: Income) -> int: pass

    @abstractmethod
    def get_all(self, start_date=None, end_date=None, income_type=None, search=None) -> List[Income]: pass

    @abstractmethod
    def get_by_id(self, income_id: int) -> Optional[Income]: pass

    @abstractmethod
    def get_monthly_summary(self, year: int, month: int) -> Dict: pass

    @abstractmethod
    def delete(self, income_id: int) -> bool: pass
