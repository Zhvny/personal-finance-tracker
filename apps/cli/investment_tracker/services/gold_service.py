from datetime import datetime

import logging

import yfinance as yf

from apps.cli.investment_tracker.core.interfaces import IFXService
from apps.cli.investment_tracker.services.base_price_service import BasePriceService

logger = logging.getLogger(__name__)

# Gold tickers tried in order — GC=F is the continuous front-month futures contract.
# MGC=F is the micro gold futures (1/10th size but same price per oz).
_GOLD_FUTURES_TICKERS = ["GC=F", "MGC=F"]
_TROY_OZ_TO_GRAM = 31.1034768


class GoldPriceService(BasePriceService):
    """
    Service untuk harga emas Indonesia (per gram, IDR).
    Standardized to use Yahoo Finance Gold Futures (GC=F) as the primary source.

    High Cohesion : only gold price logic here.
    Low Coupling  : depends only on IFXService; no direct DB access.
    DRY           : single _usd_oz_to_idr_gram() conversion used everywhere.
    """

    FALLBACK_IDR = 1_650_000.0  # Updated conservative estimate

    def __init__(self, fx_service: IFXService):
        super().__init__(fx_service)

    # ── Interface ─────────────────────────────────────────────────────

    def supports(self, asset_type: str) -> bool:
        return asset_type.lower() == "gold"

    def get_current_price_usd(self, ticker: str) -> float:
        """Return USD per gram (not per ounce — consistent with storage)."""
        idr_per_gram = self.get_current_price_idr_per_gram()
        usd_idr = self.fx_service.get_usd_idr()
        return idr_per_gram / usd_idr

    def get_prices(self, investment):
        current_idr = self.get_current_price_idr_per_gram()
        usd_idr = self.fx_service.get_usd_idr()

        buy_idr = (
            float(investment.buy_price)
            if investment.buy_currency.upper() == "IDR"
            else float(investment.buy_price) * usd_idr
        )

        print(f"   Your Buy: Rp{buy_idr:,.0f}/g")
        print(f"   Market:   Rp{current_idr:,.0f}/g")

        return {
            "usd": current_idr / usd_idr,
            "idr": current_idr,
            "buy_price_idr": buy_idr,
            "current_price_idr": current_idr,
            "usd_idr": usd_idr,
        }

    def get_historical_idr(self, ticker: str, start_date: datetime, end_date=None) -> list:
        """Weekly historical prices in IDR/gram via Yahoo Finance + live FX."""
        print("  ℹ  Historical: Yahoo Finance (Gold Futures) + current FX rate")
        usd_idr = self.fx_service.get_usd_idr()

        for yf_ticker in _GOLD_FUTURES_TICKERS:
            try:
                df = yf.download(
                    yf_ticker,
                    start=start_date.strftime("%Y-%m-%d"),
                    end=(end_date or datetime.now()).strftime("%Y-%m-%d"),
                    progress=False,
                )
                if not df.empty:
                    return self._df_to_idr_gram_history(df, usd_idr, oz_per_unit=1.0)
            except Exception as exc:
                logger.warning("Gold history fetch failed for %s: %s", yf_ticker, exc)
                continue

        return []

    # ── Core price fetch ──────────────────────────────────────────────

    def get_current_price_idr_per_gram(self) -> float:
        """
        Fetch current gold price in IDR/gram via Yahoo Futures.
        Returns FALLBACK_IDR with an explicit warning log when live fetch fails.
        """
        # 1. Yahoo Finance futures (GC=F)
        price = self._fetch_yahoo_futures()
        if price:
            return price

        # 2. Hard-coded sentinel
        logger.warning("Gold live price unavailable, using FALLBACK_IDR sentinel: %s/g", self.FALLBACK_IDR)
        print(f"    Yahoo Futures failed — using fallback: Rp{self.FALLBACK_IDR:,.0f}/g")
        return self.FALLBACK_IDR

    # ── Private fetchers ──────────────────────────────────────────────

    def _fetch_yahoo_futures(self) -> float:
        """Fetch gold price via futures tickers (GC=F → MGC=F)."""
        usd_idr = self.fx_service.get_usd_idr()
        for ticker in _GOLD_FUTURES_TICKERS:
            try:
                # Use period="5d" to ensure we get data even on weekends/holidays
                tk = yf.Ticker(ticker)
                # Try fast_info first for real-time
                try:
                    usd_per_oz = tk.fast_info["last_price"]
                except (KeyError, ValueError, TypeError) as exc:
                    logger.warning("Gold fast_info failed for %s: %s", ticker, exc)
                    data = tk.history(period="5d")
                    usd_per_oz = float(data["Close"].dropna().iloc[-1]) if not data.empty else 0

                if usd_per_oz > 100:  # sanity
                    idr = self._usd_oz_to_idr_gram(usd_per_oz, usd_idr)
                    print(f"   {ticker}: ${usd_per_oz:,.2f}/oz → Rp{idr:,.0f}/g")
                    return idr
            except Exception as exc:
                logger.warning("Gold futures fetch failed for %s: %s", ticker, exc)
                continue
        return 0.0

    # ── Shared helpers (DRY) ──────────────────────────────────────────

    @staticmethod
    def _usd_oz_to_idr_gram(usd_per_oz: float, usd_idr: float) -> float:
        """Convert USD/troy-oz → IDR/gram. Single conversion used everywhere."""
        return (usd_per_oz / _TROY_OZ_TO_GRAM) * usd_idr

    @staticmethod
    def _df_to_idr_gram_history(df, usd_idr: float, oz_per_unit: float) -> list:
        """Convert a yfinance DataFrame to weekly IDR/gram history list."""
        df_weekly = df.resample("W").last().dropna()
        history = []
        for date, row in df_weekly.iterrows():
            close = row["Close"]
            if hasattr(close, "item"):
                close = close.item()
            usd_per_oz = float(close) / oz_per_unit
            idr_per_gram = GoldPriceService._usd_oz_to_idr_gram(usd_per_oz, usd_idr)
            history.append({"date": date.to_pydatetime(), "close": idr_per_gram})
        return history
