import pandas as pd
import pytest

from apps.cli.stock_analyzer.domain.strategies.price_action import PriceActionDetector


@pytest.fixture
def structure_data():
    """Create data with HH, HL, LH, LL."""
    data = [
        {'High': 100, 'Low': 90, 'Close': 95},   # Base
        {'High': 110, 'Low': 100, 'Close': 105}, # HH
        {'High': 105, 'Low': 95, 'Close': 100},  # HL
        {'High': 120, 'Low': 110, 'Close': 115}, # HH
        {'High': 115, 'Low': 105, 'Close': 110}, # HL
        {'High': 100, 'Low': 90, 'Close': 95},   # LL
        {'High': 95, 'Low': 85, 'Close': 90},    # LL
        {'High': 97, 'Low': 87, 'Close': 92},    # LH
    ]
    # Repeat to fill window requirements (window=2 for testing)
    expanded_data = []
    for item in data:
        for _ in range(5): # Each point lasts 5 bars
            expanded_data.append(item.copy())

    df = pd.DataFrame(expanded_data)
    df.index = pd.date_range(start='2023-01-01', periods=len(df), freq='h')
    return df
def test_detect_structure(structure_data):
    detector = PriceActionDetector()
    df = detector.detect_structure(structure_data, window=2)

    assert 'Structure' in df.columns
    assert 'TrendState' in df.columns

    # Check if we have some signals
    assert any(df['Structure'] != "")
    assert "HH" in df['Structure'].values
    assert "LL" in df['Structure'].values

def test_detect_patterns():
    detector = PriceActionDetector()

    # Create specific patterns
    data = [
        {'Open': 100, 'High': 105, 'Low': 95, 'Close': 100.1, 'Volume': 1000}, # Doji
        {'Open': 100, 'High': 102, 'Low': 90, 'Close': 101, 'Volume': 1000},   # Hammer
        {'Open': 100, 'High': 110, 'Low': 98, 'Close': 99, 'Volume': 1000},    # Shooting Star
        {'Open': 100, 'High': 105, 'Low': 95, 'Close': 98, 'Volume': 1000},    # Bearish candle for engulfing
        {'Open': 97, 'High': 106, 'Low': 96, 'Close': 106, 'Volume': 1000},   # Bullish Engulfing
    ]
    df = pd.DataFrame(data)
    df = detector.detect_patterns(df)

    assert df.at[0, 'Pattern'] == "Doji"
    assert df.at[1, 'Pattern'] == "Hammer"
    assert df.at[2, 'Pattern'] == "Shooting Star"
    assert df.at[4, 'Pattern'] == "Bullish Engulfing"

def test_detect_fvg():
    detector = PriceActionDetector()

    data = [
        {'High': 100, 'Low': 90, 'Close': 95}, # Bar 0
        {'High': 110, 'Low': 101, 'Close': 105}, # Bar 1 (Gap Up)
        {'High': 120, 'Low': 111, 'Close': 115}, # Bar 2 (Gap Up)
    ]
    # Bullish FVG exists if Low(2) > High(0) -> 111 > 100. Yes.

    df = pd.DataFrame(data)
    df = detector.detect_fvg(df)

    assert "Bullish FVG" in df.at[1, 'FVG']
