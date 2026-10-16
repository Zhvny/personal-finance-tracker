import logging

import yfinance as yf

from apps.cli.investment_tracker.core.interfaces import IFXService
from apps.cli.investment_tracker.services.base_price_service import BasePriceService

logger = logging.getLogger(__name__)
try:
    from packages.core.utils.symbol_utils import SymbolFormatter
except ImportError:
    SymbolFormatter = None
class StockPriceService(BasePriceService):
    def __init__(self, fx_service: IFXService):
        super().__init__(fx_service)
    def supports(self, asset_type: str) -> bool:
        return asset_type.lower() == "stock"
    def get_current_price_usd(self, ticker: str) -> float:
        norm = ticker
        if SymbolFormatter: norm = SymbolFormatter.normalize(ticker)
        s = yf.Ticker(norm)
        try:
            i = getattr(s, "basic_info", getattr(s, "fast_info", s.info))
            p = i.get("last_price") or i.get("currentPrice") or i.get("regularMarketPrice")
            if p: return float(p)
        except Exception:
            logger.exception(f"YFinance basic_info fetch failed for {norm}")
        h = s.history(period="5d")
        if not h.empty: return float(h["Close"].dropna().iloc[-1])
        raise ValueError(f"No price for {norm}")
    def get_prices(self, investment):
        norm = SymbolFormatter.normalize(investment.ticker) if SymbolFormatter else investment.ticker
        raw = self.get_current_price_usd(investment.ticker)
        r = self.fx_service.get_usd_idr()
        if norm.upper().endswith(".JK"):
            idr = float(raw); usd = idr / r
        else:
            usd = float(raw); idr = usd * r
        bidr = self._normalize_to_idr(investment.buy_price, investment.buy_currency)
        return {"usd": usd, "idr": idr, "buy_price_idr": bidr, "current_price_idr": idr}
