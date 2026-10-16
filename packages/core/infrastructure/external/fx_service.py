import time
from datetime import date
from typing import Dict, Optional

from packages.core.domain.repositories.fx_repository import IFXRepository


class FXService:
    """
    Infrastructure service to fetch and store USD/IDR exchange rates.
    Supports both live rates (with caching) and historical rates (from DB).
    """

    _FX_CACHE: Dict[str, float] = {"rate": 16000.0, "last_fetch": 0.0}

    def __init__(self, repository: Optional[IFXRepository] = None):
        self.repository = repository

    def get_rate(self) -> float:
        """
        Fetch live USD/IDR rate with 1-hour cache. Fallback to repository or 16,000.
        Persists the fetched rate to the database if available.
        """
        now = time.time()
        # Cache for 1 hour
        if now - self._FX_CACHE["last_fetch"] < 3600:
            return self._FX_CACHE["rate"]

        try:
            from packages.core.utils.api_resilience import safe_requests_get

            url = "https://open.er-api.com/v6/latest/USD"
            success, data = safe_requests_get(url, timeout=5, max_retries=2)
            if success and data and "rates" in data and "IDR" in data["rates"]:
                rate = float(data["rates"]["IDR"])
                self._FX_CACHE["rate"] = rate
                self._FX_CACHE["last_fetch"] = now

                # Persist to DB for future historical lookups
                if self.repository:
                    self.repository.save_rate("USD/IDR", date.today(), rate)

                return rate
        except Exception:
            # Fallback to repository if API fails
            if self.repository:
                db_rate = self.repository.get_closest_rate("USD/IDR", date.today())
                if db_rate:
                    self._FX_CACHE["rate"] = db_rate
                    # Do not update last_fetch to allow retry on next call
                    return db_rate

        return self._FX_CACHE["rate"]

    def get_usd_idr(self) -> float:
        """Alias for get_rate for backward compatibility."""
        return self.get_rate()

    def get_rate_at(self, pair: str, rate_date: date) -> float:
        """
        Retrieves the exchange rate for a specific pair and date.
        Tries to find the closest historical rate in the database.
        Falls back to live rate (if today) or 16,000.
        """
        if rate_date == date.today():
            return self.get_rate()

        if self.repository:
            rate = self.repository.get_closest_rate(pair, rate_date)
            if rate:
                return rate

        # Fallback if no historical data found
        return 16000.0


# For backward compatibility with modules expecting the function
def get_live_fx_rate() -> float:
    # This remains for legacy but new code should use the service instance
    return FXService().get_rate()
