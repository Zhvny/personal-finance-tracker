from abc import ABC, abstractmethod
from typing import Dict

from apps.cli.investment_tracker.core.interfaces import IFXService, IPriceService
from packages.core.domain.models import Investment


class BasePriceService(IPriceService, ABC):
    """
    Base class untuk semua price service.
    Mengimplementasikan common logic (konversi mata uang).
    """

    def __init__(self, fx_service: IFXService):
        self.fx_service = fx_service  # Dependency Injection untuk Low Coupling

    def _normalize_to_idr(self, price, currency: str) -> float:
        """Convert price ke IDR jika perlu. Accepts Decimal or float."""
        price = float(price)
        if currency.upper() == "USD":
            return price * self.fx_service.get_usd_idr()
        return price

    @abstractmethod
    def get_current_price_usd(self, ticker: str) -> float:
        """Ambil harga terkini dalam USD"""
        pass

    def get_prices(self, investment: Investment) -> Dict[str, float]:
        # Template Method Pattern
        current_usd = self.get_current_price_usd(investment.ticker)
        usd_idr = self.fx_service.get_usd_idr()

        current_idr = current_usd * usd_idr
        buy_price_idr = self._normalize_to_idr(
            investment.buy_price,
            investment.buy_currency
        )

        return {
            "usd": current_usd,
            "idr": current_idr,
            "buy_price_idr": buy_price_idr,
            "current_price_idr": current_idr
        }
