import logging
from typing import Any, Dict

import yfinance as yf


class WhaleVolumeProfiler:
    """
    Task 6.2: Whale/Smart Money Volume Profiler
    Objective: Detect institutional accumulation (Absorption).
    
    Criteria:
    1. Track Volume / Average_Volume_20D.
    2. Identify "Large Order" spikes where price movement is < 0.5% (Absorption logic).
    3. Relationship between Volume and Price Action (Anti-Cheat).
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def analyze_ticker(self, ticker: str, asset_type: str = "stock") -> Dict[str, Any]:
        """
        Analyzes the volume and price action of a ticker to detect 'Smart Money' activity.
        """
        try:
            # Normalize ticker for yfinance
            yf_ticker = self._map_ticker(ticker, asset_type)

            # Fetch at least 60 days of daily data to calculate 20-day SMA reliably
            stock = yf.Ticker(yf_ticker)
            df = stock.history(period="60d", interval="1d")

            if df.empty:
                return {"error": f"No data found for {yf_ticker}"}

            if 'Volume' not in df.columns or len(df) < 20:
                return {"error": f"Insufficient volume data for {yf_ticker}"}

            # 1. Track Volume / Average_Volume_20D
            df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
            df['Vol_Ratio'] = df['Volume'] / df['Vol_SMA20']

            # 2. Identify "Large Order" spikes where price movement is < 0.5% (Absorption logic)
            # Price Movement: We use (High - Low) / Low to measure total intraday range.
            # Absorption is when high volume fails to move the price significantly.
            df['Price_Range_Pct'] = ((df['High'] - df['Low']) / df['Low']) * 100

            # Body movement: abs(Close - Open) / Open
            df['Body_Move_Pct'] = (abs(df['Close'] - df['Open']) / df['Open']) * 100

            # Fill NaN with 0 for safety
            df['Price_Range_Pct'] = df['Price_Range_Pct'].fillna(0)
            df['Body_Move_Pct'] = df['Body_Move_Pct'].fillna(0)
            df['Vol_Ratio'] = df['Vol_Ratio'].fillna(0)

            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest

            vol_ratio = latest['Vol_Ratio']
            price_range = latest['Price_Range_Pct']
            body_move = latest['Body_Move_Pct']

            # Thresholds
            # Volume Spike: > 1.5x average (typical institutional entry)
            # Tight Price: < 0.5% movement
            is_volume_spike = vol_ratio > 1.5
            is_tight_price = price_range < 0.5 or body_move < 0.3

            # Ensure price_range is not 0 (which might happen on missing data)
            if price_range == 0 and body_move == 0 and latest['Volume'] == 0:
                is_tight_price = False # Not absorption, just no data/no trade

            # 3. Anti-Cheat: Relationship check
            # We don't just flag volume spikes. We flag volume spikes that LACK price movement.
            is_absorption = is_volume_spike and is_tight_price

            signal = "NORMAL"
            if is_absorption:
                # Decide if it's Accumulation or Distribution based on Close vs Prev Close
                # or Close vs Open
                if latest['Close'] >= prev['Close']:
                    signal = "WHALE_ACCUMULATION"
                else:
                    signal = "WHALE_DISTRIBUTION"
            elif is_volume_spike:
                signal = "HIGH_VOLATILITY_VOLUME"

            result = {
                "ticker": ticker,
                "yf_ticker": yf_ticker,
                "date": df.index[-1].strftime('%Y-%m-%d'),
                "volume": int(latest['Volume']),
                "avg_volume_20d": float(latest['Vol_SMA20']),
                "vol_ratio": float(vol_ratio),
                "price_range_pct": float(price_range),
                "body_move_pct": float(body_move),
                "signal": signal,
                "is_whale_activity": bool(is_absorption),
                "description": self._get_description(vol_ratio, price_range, body_move, signal)
            }

            return result

        except Exception as e:
            return {"error": str(e)}

    def _get_description(self, vol_ratio: float, price_range: float, body_move: float, signal: str) -> str:
        if signal == "NORMAL":
            return "Normal market activity. No institutional signatures detected."

        if signal == "HIGH_VOLATILITY_VOLUME":
            return f"High volume spike ({vol_ratio:.1f}x) detected, but accompanied by high volatility ({price_range:.1f}%). This is likely retail FOMO or news-driven volatility, not quiet institutional absorption."

        desc = "⚠️ [bold cyan]WHALE SIGNATURE DETECTED[/bold cyan] ⚠️\n"
        desc += f"Signal: {signal}\n"
        desc += f"Reasoning: Volume is [green]{vol_ratio:.2f}x[/green] higher than the 20-day average, yet the price range was restricted to [yellow]{price_range:.2f}%[/yellow].\n"

        if signal == "WHALE_ACCUMULATION":
            desc += "Interpretation: Institutional buyers are absorbing all sell orders at this level without letting the price break out yet. This often precedes a bullish move."
        else:
            desc += "Interpretation: Institutional sellers are offloading large positions into buy orders without crashing the price yet. This often precedes a bearish breakdown."

        return desc

    def _map_ticker(self, ticker: str, asset_type: str) -> str:
        # Simplified mapping for yfinance
        if asset_type == 'crypto':
            if '-' not in ticker:
                return f"{ticker}-USD"
        elif asset_type == 'idx' or ticker.isdigit(): # Indonesia Stock Exchange
            if not ticker.endswith(".JK"):
                return f"{ticker}.JK"
        return ticker
