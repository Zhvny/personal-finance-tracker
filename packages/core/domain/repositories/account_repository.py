from abc import ABC, abstractmethod
from typing import List, Optional

from packages.core.domain.models.account import VirtualAccount


class IVirtualAccountRepository(ABC):
    @abstractmethod
    def save(self, account: VirtualAccount) -> int:
        pass

    @abstractmethod
    def get_all(self, profile_id: str) -> List[VirtualAccount]:
        pass

    @abstractmethod
    def get_by_id(self, account_id: int, profile_id: str) -> Optional[VirtualAccount]:
        pass

    @abstractmethod
    def delete(self, account_id: int, profile_id: str) -> bool:
        pass

    @abstractmethod
    def update_balance(self, account_id: int, profile_id: str, new_balance: float) -> bool:
        pass
