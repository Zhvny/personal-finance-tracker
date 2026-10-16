from apps.cli.investment_tracker.core.interfaces import IFXService


class FXService(IFXService):
    """Service untuk foreign exchange rate"""

    def __init__(self, fallback_rate: float = 16500):  # Update fallback
        self.fallback_rate = fallback_rate
        self._cache = None

    def get_usd_idr(self) -> float:
        if self._cache is not None:
            return self._cache

        try:
            from packages.core.utils.api_resilience import safe_requests_get
            url = "https://open.er-api.com/v6/latest/USD"
            success, data = safe_requests_get(url, timeout=5, max_retries=2)

            if success and data and "rates" in data and "IDR" in data["rates"]:
                self._cache = float(data["rates"]["IDR"])
                print(f"   FX Rate: 1 USD = Rp{self._cache:,.0f}")
                return self._cache

        except Exception as e:
            from packages.core.infrastructure.logging import get_logger
            get_logger("fx_service").exception(f"FX Service Error: {e}")
            print(f"   FX Service Error: {e}")

        print(f"   Using fallback rate: Rp{self.fallback_rate:,.0f}/USD")
        return self.fallback_rate

class MockFXService(IFXService):
    def __init__(self, rate: float = 16500):
        self.rate = rate

    def get_usd_idr(self) -> float:
        return self.rate
