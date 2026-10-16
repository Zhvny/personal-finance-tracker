from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from packages.core.domain.models import Investment, SellTransaction


class IInvestmentRepository(ABC):
    @abstractmethod
    def save(self, investment: Investment) -> int: pass

    @abstractmethod
    def get_all_active(self) -> List[Investment]: pass

    @abstractmethod
    def get_by_id(self, investment_id: int) -> Optional[Investment]: pass

    @abstractmethod
    def add_sell_transaction(self, sell: SellTransaction) -> int: pass

    @abstractmethod
    def get_realized_pl(self) -> List[SellTransaction]: pass

    @abstractmethod
    def delete(self, investment_id: int) -> bool: pass

    @abstractmethod
    def update_status(self, investment_id: int, status: str, remaining_qty: Decimal) -> bool: pass

    @abstractmethod
    def save_price_snapshot(self, investment_id: int, date: datetime, price_usd: float, price_idr: float) -> bool: pass

    @abstractmethod
    def get_latest_snapshot(self, investment_id: int) -> Optional[Dict[str, Any]]: pass

    @abstractmethod
    def get_all_snapshots(self, investment_id: int) -> List[Dict[str, Any]]: pass

    @abstractmethod
    def toggle_favorite(self, investment_id: int) -> bool: pass

    @abstractmethod
    def get_all_lots_by_ticker(self, ticker: str) -> List[Investment]: pass

    @abstractmethod
    def get_all_sell_transactions_by_ticker(self, ticker: str) -> List[SellTransaction]: pass

    @abstractmethod
    def prune_sold_lots(self) -> Dict[str, int]:
        """
        Remove fully-sold investment rows and their historical snapshots.
        Returns a dictionary with 'deleted', 'kept_holding', and 'kept_realized' counts.
        """
        pass
