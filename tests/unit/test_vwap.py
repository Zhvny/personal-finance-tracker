from datetime import datetime, timedelta

import pandas as pd
import pytest

from apps.cli.stock_analyzer.domain.strategies.vwap import VWAPEngine


@pytest.fixture
def session_data():
    """Create data spanning two days."""
    dates = []
    # Day 1
    start1 = datetime(2023, 1, 1, 9, 30)
    for i in range(100):
        dates.append(start1 + timedelta(minutes=i))
    # Day 2
    start2 = datetime(2023, 1, 2, 9, 30)
    for i in range(100):
        dates.append(start2 + timedelta(minutes=i))

    df = pd.DataFrame(index=dates)
    df['High'] = 100.0
    df['Low'] = 100.0
    df['Close'] = 100.0
    df['Volume'] = 100
    return df

def test_calculate_standard_resets(session_data):
    engine = VWAPEngine()
    vwap = engine.calculate_standard(session_data)

    assert len(vwap) == len(session_data)
    # Since prices are constant, VWAP should be constant 100
    assert (vwap == 100.0).all()

    # Modify prices to check reset
    session_data.iloc[0:100, session_data.columns.get_loc('High')] = 110
    session_data.iloc[0:100, session_data.columns.get_loc('Low')] = 110
    session_data.iloc[0:100, session_data.columns.get_loc('Close')] = 110

    vwap = engine.calculate_standard(session_data)
    assert vwap.iloc[99] == 110.0
    assert vwap.iloc[100] == 100.0 # Resets on second day

def test_calculate_anchored(session_data):
    engine = VWAPEngine()
    # Anchor at the start of day 2
    anchor_date = "2023-01-02 09:30:00"

    # Day 1: 110, Day 2: 100
    session_data.iloc[0:100, session_data.columns.get_loc('High')] = 110
    session_data.iloc[0:100, session_data.columns.get_loc('Low')] = 110
    session_data.iloc[0:100, session_data.columns.get_loc('Close')] = 110

    anchored = engine.calculate_anchored(session_data, anchor_date)

    assert pd.isna(anchored.iloc[0])
    assert anchored.iloc[100] == 100.0

def test_get_signals_trend_bullish(session_data):
    engine = VWAPEngine()
    vwap = engine.calculate_standard(session_data)

    # Setup bullish trend with pullback
    # Price > VWAP (100)
    # Pullback to 0.3% of VWAP (100.3)
    session_data.iloc[-1, session_data.columns.get_loc('Close')] = 100.3
    session_data.iloc[-1, session_data.columns.get_loc('High')] = 100.5
    session_data.iloc[-1, session_data.columns.get_loc('Low')] = 100.1

    signals = engine.get_signals(session_data, vwap)
    assert signals['trend_signal'] == 'BULLISH_PULLBACK'

def test_get_signals_mean_reversion_extended_up(session_data):
    engine = VWAPEngine()
    vwap = engine.calculate_standard(session_data)

    # Setup extended price
    # Default ATR will be low if constant. Let's force a high price.
    session_data.iloc[-1, session_data.columns.get_loc('Close')] = 120.0

    signals = engine.get_signals(session_data, vwap)
    assert signals['mean_reversion_signal'] == 'EXTENDED_UP'
