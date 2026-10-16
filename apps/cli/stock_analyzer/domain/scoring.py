import logging

import numpy as np
import pandas as pd

from apps.cli.stock_analyzer.adapters.cache import TTL_TECHNICALS, ticker_cache
from apps.cli.stock_analyzer.domain.config import AppConfig
from apps.cli.stock_analyzer.domain.models import TradingSignal

logger = logging.getLogger(__name__)

class ScoringEngine:
    """Core domain logic for scoring stocks based on technical indicators."""

    @staticmethod
    @ticker_cache(ttl=TTL_TECHNICALS, cache_type="scoring")
    def calculate_composite_score(indicators_row: pd.Series, ticker: str = None, config: AppConfig = None) -> tuple[float, dict]:
        # Helper to safely compare values even with NaNs
        def safe_score(val, threshold, weight=1.0, operator='>'):
            try:
                v = float(val)
                t = float(threshold)
                if np.isnan(v) or np.isnan(t): return 0.0
                if operator == '>' : return weight if v > t else 0.0
                if operator == '<' : return weight if v < t else 0.0
            except Exception:
                logger.debug("safe_score conversion error")
            return 0.0

        # --- CONFLUENCE CATEGORIES (Max: 10.0) ---
        price = indicators_row.get('Close', 0)

        # 1. Trend: EMA 50 / 200 (Weight: 3.0)
        # Fallback logic: If EMA200 is missing, use EMA100/50 or current Price as baseline
        ema200 = indicators_row.get('ema200', indicators_row.get('ma50', price))
        ema50  = indicators_row.get('ema50', price)

        trend_score = 0.0
        trend_score += safe_score(price, ema200, 1.0)
        trend_score += safe_score(price, ema50, 1.0)
        trend_score += safe_score(ema50, ema200, 1.0)

        # 2. Momentum: RSI / MACD (Weight: 3.0)
        momentum_score = 0.0
        rsi = indicators_row.get('rsi', 50)
        macd_h = indicators_row.get('macd_hist', 0)
        macd_l = indicators_row.get('macd_line', 0)
        macd_s = indicators_row.get('macd_signal', 0)

        momentum_score += safe_score(rsi, 50, 1.0)
        momentum_score += safe_score(macd_h, 0, 1.0)
        momentum_score += safe_score(macd_l, macd_s, 1.0)

        # 3. Volume: Volume spike / OBV (Weight: 2.0)
        volume_score = 0.0
        vol = indicators_row.get('Volume', 0)
        vol_ma = indicators_row.get('vol_ma20', vol)
        obv_s = indicators_row.get('obv_slope', 0)

        volume_score += safe_score(vol, vol_ma, 1.0)
        volume_score += safe_score(obv_s, 0, 1.0)

        # 4. Structure: Support & Resistance (Weight: 2.0)
        structure_score = 0.0
        support = indicators_row.get('sr_support', indicators_row.get('bb_lower', price * 0.95))
        resistance = indicators_row.get('sr_resistance', indicators_row.get('bb_upper', price * 1.05))

        if not np.isnan(support) and not np.isnan(resistance) and resistance > support:
            # Proportional score: 2.0 at support, 0.0 at resistance
            # This provides a granular "Edge" instead of binary 0/2
            total_range = resistance - support
            relative_pos = (resistance - price) / total_range
            # Clamp to [0, 1] then scale to [0, 2]
            structure_score = max(0.0, min(1.0, relative_pos)) * 2.0

        total_score = min(10.0, trend_score + momentum_score + volume_score + structure_score)

        return float(total_score), {
            "trend": float(trend_score),
            "momentum": float(momentum_score),
            "volume": float(volume_score),
            "structure": float(structure_score)
        }

    @staticmethod
    def calculate_macro_bonus(macro_context: dict, is_commodity: bool = False, dcds: float = 0.0) -> float:
        bonus = 0.0
        lpi = float(macro_context.get('lpi', 0.5))
        icm = float(macro_context.get('icm', 0.0))
        smfd = float(macro_context.get('smfd_5d', 0))
        csi = float(macro_context.get('csi', 70.0))

        if lpi > 0.65: bonus += 0.5
        if lpi < 0.35: bonus -= 0.5
        if is_commodity and icm > 0.4: bonus += 0.5
        if smfd >= 3: bonus += 0.5
        if smfd <= -3: bonus -= 0.5

        # Divergence Bonus: Strong commodity strength vs USD strength
        if is_commodity and dcds > 1.5: bonus += 0.5

        # Consumer Sentiment Bonus/Penalty
        if csi > 80: bonus += 0.3
        if csi < 60: bonus -= 0.3

        return max(-1.0, min(2.0, bonus))


    @staticmethod
    def calculate_css(tech_score: float, macro_context: dict, is_commodity: bool = False, dcds: float = 0.0) -> tuple[float, str]:
        errf_mult = float(macro_context.get('errf_mult', 1.0))
        bonus = ScoringEngine.calculate_macro_bonus(macro_context, is_commodity, dcds=dcds)

        adj_score = (tech_score * errf_mult) + bonus
        css = max(0.0, min(10.0, adj_score)) * 10.0

        if css >= 80: tier = "HIGH"
        elif css >= 65: tier = "MEDIUM"
        elif css >= 50: tier = "LOW"
        else: tier = "NO_TRADE"

        return round(float(css), 1), tier

    @staticmethod
    def generate_signal(score: float, indicators_row: pd.Series, config: AppConfig = None,
                        ml_sig: str = "NEUTRAL", ml_prob: float = 0.5, css_tier: str = "MEDIUM") -> TradingSignal:

        # --- MACRO GATE: If CSS Tier is NO_TRADE, we avoid everything ---
        if css_tier == "NO_TRADE":
            return TradingSignal.AVOID

        # --- MACRO HARD-GATE (STRESS TEST FIX) ---
        # If macro risk is HIGH (Tier LOW), we FORBID Strong Buy / Buy signals.
        # Capital preservation is priority.
        is_macro_high_risk = (css_tier == "LOW")

        buy_threshold = 8.0
        strong_buy_threshold = 9.0

        if config and hasattr(config, 'buy_threshold'):
            buy_threshold = config.buy_threshold - 0.5
            strong_buy_threshold = config.buy_threshold + 0.5

        atr = float(indicators_row.get('atr', 0))
        price = float(indicators_row.get('Close', 0))
        atr_ratio = atr / (price + 1e-9)

        ema200 = float(indicators_row.get('ema200', price))
        ema50 = float(indicators_row.get('ema50', price))

        is_bullish = price > ema200
        is_strong_trend = is_bullish and (price > ema50)

        is_ml_bull = (ml_sig == "BULLISH")
        is_ml_bear = (ml_sig == "BEARISH")

        if score < 4.0 and is_ml_bear and ml_prob > 0.7:
            return TradingSignal.STRONG_SELL
        if score < 5.0 and (is_ml_bear or float(indicators_row.get('rsi', 50)) > 75):
            return TradingSignal.SELL

        if atr_ratio > 0.12 and not is_strong_trend and not (is_ml_bull and ml_prob > 0.8):
            return TradingSignal.AVOID

        # Check Buy signals with Macro High-Risk restriction
        if not is_macro_high_risk:
            if score >= strong_buy_threshold or (score >= buy_threshold and is_ml_bull and ml_prob > 0.7):
                return TradingSignal.STRONG_BUY

            if score >= buy_threshold or (score >= (buy_threshold - 1.5) and is_ml_bull and ml_prob > 0.6):
                return TradingSignal.BUY

        # If Macro is high risk, or tech score is lower, allow only defensive signals
        if score >= 6.5 or (is_ml_bull and ml_prob > 0.8):
            return TradingSignal.ACCUMULATE

        if score >= 5.0 or is_strong_trend or is_ml_bull:
            return TradingSignal.WAIT

        return TradingSignal.AVOID

    @staticmethod
    def mrzg_signal(last_row: pd.Series, ycmo: float, rrm: float) -> str:
        try:
            zp_raw = last_row.get('z_price', np.nan)
            zr_raw = last_row.get('z_rsi', np.nan)

            # Handle missing data
            if pd.isna(zp_raw) or pd.isna(zr_raw):
                return "NONE"

            zp = float(zp_raw)
            zr = float(zr_raw)

            # Core logic with macro confirmation
            if zp < -2.2 and zr < -1.8:
                if ycmo > 0: return "MR_LONG"
                if ycmo is None or ycmo == 0: return "MR_OVERSOLD"
                return "MR_POTENTIAL_LONG"

            if zp > 2.2 and zr > 1.8:
                if rrm > 0: return "MR_SHORT"
                if rrm is None or rrm == 0: return "MR_OVERBOUGHT"
                return "MR_POTENTIAL_SHORT"
        except Exception as e:
            logging.error(f"[Scoring] MRZG calculation error: {e}")
            return "ERROR"

        return "NONE"
