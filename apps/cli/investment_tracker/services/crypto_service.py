from apps.cli.investment_tracker.core.interfaces import IFXService
from apps.cli.investment_tracker.services.base_price_service import BasePriceService


class CryptoPriceService(BasePriceService):
    def __init__(self, fx_service: IFXService):
        super().__init__(fx_service)
        self.base_url = "https://api.coingecko.com/api/v3"

    def supports(self, asset_type: str) -> bool:
        return asset_type.lower() == "crypto"

    def get_current_price_usd(self, ticker: str) -> float:
        # Normalize ticker for CoinGecko
        symbol_map = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana',
            'BNB': 'binancecoin', 'ADA': 'cardano', 'DOT': 'polkadot',
            'DOGE': 'dogecoin', 'XRP': 'ripple', 'AVAX': 'avalanche-2',
            'POL': 'matic-network', 'MATIC': 'matic-network',  # MATIC rebranded to POL
            'USDT': 'tether', 'USDC': 'usd-coin'
        }
        coin_id = symbol_map.get(ticker.upper(), ticker.lower())

        # 1. Try CoinGecko with safe request verification & retries
        try:
            from packages.core.utils.api_resilience import safe_requests_get
            url = f"{self.base_url}/simple/price"
            params = {'ids': coin_id, 'vs_currencies': 'usd'}
            success, data = safe_requests_get(url, params=params, timeout=8, max_retries=2)
            if success and data and coin_id in data and 'usd' in data[coin_id]:
                return float(data[coin_id]['usd'])
        except Exception:
            pass

        # 2. Fallback to yfinance
        try:
            import yfinance as yf
            yf_ticker = f"{ticker.upper()}-USD"
            stock = yf.Ticker(yf_ticker)
            data = stock.history(period="5d")
            if not data.empty:
                return float(data["Close"].dropna().iloc[-1])
        except Exception:
            pass

        raise ValueError(f"Crypto price for '{ticker}' not found in CoinGecko or yfinance")

    def get_prices(self, investment):
        # Implement abstract method
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
