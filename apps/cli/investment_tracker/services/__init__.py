from typing import Dict, Type

from apps.cli.investment_tracker.core.interfaces import IFXService, IPriceService
from apps.cli.investment_tracker.services.crypto_service import CryptoPriceService
from apps.cli.investment_tracker.services.fx_service import FXService
from apps.cli.investment_tracker.services.gold_service import GoldPriceService
from apps.cli.investment_tracker.services.stock_service import StockPriceService


class PriceServiceFactory:
    """
    Factory Pattern untuk membuat price service berdasarkan asset type.
    Memudahkan penambahan asset type baru tanpa mengubah client code.
    """

    def __init__(self, fx_service: IFXService = None):
        self.fx_service = fx_service or FXService()
        self._services: Dict[str, IPriceService] = {}
        self._register_default_services()

    def _register_default_services(self):
        """Register semua available services"""
        services = [
            StockPriceService(self.fx_service),
            CryptoPriceService(self.fx_service),
            GoldPriceService(self.fx_service),
        ]

        for service in services:
            self.register(service)

    def register(self, service: IPriceService):
        """Register service baru"""
        # Register by supported asset types
        if hasattr(service, 'supports'):
            # Register dengan dummy check untuk dapatkan supported types
            asset_types = ['stock', 'crypto', 'gold']
            for asset_type in asset_types:
                if service.supports(asset_type):
                    self._services[asset_type] = service

    def get_service(self, asset_type: str) -> IPriceService:
        """Get service untuk asset type tertentu"""
        asset_type = asset_type.lower()

        if asset_type not in self._services:
            raise ValueError(f"No service found for asset type: {asset_type}")

        return self._services[asset_type]

# Singleton instance
_factory = None

def get_price_service_factory() -> PriceServiceFactory:
    global _factory
    if _factory is None:
        _factory = PriceServiceFactory()
    return _factory
