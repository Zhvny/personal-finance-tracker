from dataclasses import dataclass
from typing import List

import pandas as pd
import yfinance as yf


@dataclass
class ButterflyNode:
    ticker: str
    correlation: float
    impact_level: str
    description: str

class ButterflyService:
    """
    Synchronous implementation of Butterfly Effect Service for CLI.
    """
    def __init__(self):
        self.macros = {
            "^TNX": "US 10Y Treasury Yield",
            "DX-Y.NYB": "US Dollar Index (DXY)",
            "CL=F": "Crude Oil prices (WTI)",
            "GC=F": "Gold (Safe Haven Asset)",
            "SPY": "US Equity Market (S&P 500)",
            "QQQ": "Nasdaq 100 (Tech Growth)",
            "^VIX": "Market Volatility (Fear Index)",
            "USDIDR=X": "US Dollar strength vs IDR",
            "BTC-USD": "Bitcoin (Crypto Sentiment)",
            "HG=F": "Copper (Economic Doctor)",
            "^JKSE": "IHSG (Indonesian Stock Market)"
        }

    def get_risk_map(self, target_ticker: str, category: str = "us") -> List[ButterflyNode]:
        """
        Calculates simple correlation between target and macros.
        """
        nodes = []
        try:
            # Normalize target ticker
            if category == "crypto" and not target_ticker.endswith("-USD"):
                yf_target = f"{target_ticker}-USD" if "USD" in target_ticker else f"{target_ticker}-USD"
                # Handle cases like BTCUSD -> BTC-USD
                if target_ticker.endswith("USD"):
                    yf_target = target_ticker.replace("USD", "-USD")
            else:
                yf_target = target_ticker

            # Fetch data for target and macros (last 60 days)
            all_tickers = [yf_target] + list(self.macros.keys())
            try:
                data = yf.download(all_tickers, period="60d", interval="1d", progress=False)['Close']
            except Exception as e:
                print(f"Butterfly Download Error: {e}")
                return []

            if data is None or (isinstance(data, pd.DataFrame) and data.empty):
                return []

            # Ensure data is a DataFrame even if only one ticker requested (unlikely here)
            if isinstance(data, pd.Series):
                data = data.to_frame()

            if yf_target not in data.columns:
                return []

            returns = data.pct_change().dropna()
            corr_matrix = returns.corr()

            for macro, desc in self.macros.items():
                if macro not in corr_matrix.columns or yf_target == macro:
                    continue

                corr = corr_matrix.loc[yf_target, macro]
                if pd.isna(corr): continue

                abs_corr = abs(corr)
                if abs_corr > 0.6: impact = "High"
                elif abs_corr > 0.3: impact = "Medium"
                else: impact = "Low"

                nodes.append(ButterflyNode(
                    ticker=macro,
                    correlation=float(corr),
                    impact_level=impact,
                    description=desc
                ))

            # Sort by absolute correlation
            nodes.sort(key=lambda x: abs(x.correlation), reverse=True)
            return nodes

        except Exception as e:
            print(f"Butterfly Error: {e}")
            return []
