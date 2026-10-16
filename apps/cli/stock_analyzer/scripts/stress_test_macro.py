
import os
import sys

import pandas as pd

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from apps.cli.stock_analyzer.domain.scoring import ScoringEngine


def run_stress_test():
    engine = ScoringEngine()

    # Mock technical data for a "Perfect Setup"
    # Tech Score would be high (e.g., 9.0)
    mock_indicators = pd.Series({
        'Close': 150.0,
        'ema50': 140.0,
        'ema200': 130.0,
        'rsi': 55.0,
        'macd_hist': 0.5,
        'macd_line': 1.0,
        'macd_signal': 0.5,
        'Volume': 2000000,
        'vol_ma20': 1000000,
        'obv_slope': 100,
        'sr_support': 145.0,
        'sr_resistance': 160.0,
        'atr': 3.0
    })

    # --- Scenario 1: GOLDILOCKS (Market Bliss) ---
    goldilocks_ctx = {
        'rrm': -0.5,      # Falling real rates
        'ycmo': 0.1,      # Improving yield curve
        'lpi': 0.8,       # High liquidity
        'icm': 0.0,
        'errf_mult': 1.3, # 30% Boost
        'regime': 'GOLDILOCKS'
    }

    # --- Scenario 2: LIQUIDITY DROUGHT (Bear Market / QT Extremes) ---
    bear_market_ctx = {
        'rrm': 1.0,       # Rising real rates (Tightening)
        'ycmo': -0.2,     # Inverted/Flattening curve
        'lpi': 0.15,      # QT (Liquidity drying up)
        'icm': 0.8,       # High Inflation
        'errf_mult': 0.6, # 40% Penalty
        'regime': 'LIQUIDITY_DROUGHT'
    }

    print("=== SCORING ENGINE STRESS TEST ===")
    print("Technical Setup: 'Bullish Perfect Confluence' (Base Tech Score ~9.0)\n")

    for name, ctx in [("GOLDILOCKS", goldilocks_ctx), ("BEAR_MARKET", bear_market_ctx)]:
        tech_score, breakdown = engine.calculate_composite_score(mock_indicators)
        css, tier = engine.calculate_css(tech_score, ctx)
        signal = engine.generate_signal(tech_score, mock_indicators, ml_sig="BULLISH", ml_prob=0.85, css_tier=tier)

        print(f"--- Scenario: {name} ---")
        print(f"Macro Regime   : {ctx['regime']}")
        print(f"Base Tech Score: {tech_score:.2f}")
        print(f"Multiplier     : {ctx['errf_mult']}x")
        print(f"CSS Final Score: {css:.1f}")
        print(f"Trade Tier     : {tier}")
        print(f"Final Signal   : {signal}")
        print("-" * 30)

if __name__ == "__main__":
    run_stress_test()
