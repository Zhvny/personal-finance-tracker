from datetime import datetime, timedelta

import pandas as pd
import pytest

from apps.cli.stock_analyzer.domain.strategies.order_flow import OrderFlowEngine


@pytest.fixture
def sample_data():
    # Create 100 minutes of sample OHLCV data
    start_time = datetime(2023, 1, 1, 9, 30)
    data = []
    for i in range(100):
        # Create a trending price with some noise
        open_p = 100 + i * 0.1
        close_p = open_p + (0.2 if i % 2 == 0 else -0.1)
        high_p = max(open_p, close_p) + 0.05
        low_p = min(open_p, close_p) - 0.05
        vol = 1000 + i * 10
        data.append([open_p, high_p, low_p, close_p, vol])

    df = pd.DataFrame(data, columns=['Open', 'High', 'Low', 'Close', 'Volume'])
    df.index = [start_time + timedelta(minutes=i) for i in range(100)]
    return df

def test_calculate_synthetic_delta(sample_data):
    engine = OrderFlowEngine()
    df = engine.calculate_synthetic_delta(sample_data)

    assert 'buy_vol' in df.columns
    assert 'sell_vol' in df.columns
    assert 'delta' in df.columns
    assert 'cum_delta' in df.columns

    # Check a specific row where Close > Open
    row = df.iloc[0]
    if row['Close'] > row['Open']:
        assert row['buy_vol'] == row['Volume']
        assert row['sell_vol'] == 0
        assert row['delta'] == row['Volume']

def test_calculate_footprint(sample_data):
    engine = OrderFlowEngine()
    footprint = engine.calculate_footprint(sample_data, bin_size=0.1, window_minutes=15)

    assert len(footprint) > 0
    # Check if we have timestamps as keys
    first_ts = list(footprint.keys())[0]
    assert isinstance(footprint[first_ts], dict)

    # Check if bins have buy/sell vol
    some_bin = list(footprint[first_ts].keys())[0]
    assert 'buy_vol' in footprint[first_ts][some_bin]
    assert 'sell_vol' in footprint[first_ts][some_bin]

def test_detect_divergence(sample_data):
    engine = OrderFlowEngine()
    df = engine.calculate_synthetic_delta(sample_data)

    # Manually create a divergence in the data
    # Bearish: Price Higher High, Delta Lower High
    df.at[df.index[50], 'High'] = 120.0
    df.at[df.index[50], 'cum_delta'] = 50000

    df.at[df.index[70], 'High'] = 125.0
    df.at[df.index[70], 'cum_delta'] = 45000

    # Ensure they are peaks
    df.at[df.index[49], 'High'] = 119.0
    df.at[df.index[51], 'High'] = 119.0
    df.at[df.index[69], 'High'] = 124.0
    df.at[df.index[71], 'High'] = 124.0

    divergences = engine.detect_divergence(df, window=2)
    assert any(d['type'] == 'Bearish Divergence' for d in divergences)

def test_detect_imbalances():
    engine = OrderFlowEngine()
    footprint = {
        "2023-01-01T09:30:00": {
            100.0: {"buy_vol": 1000, "sell_vol": 100},
            100.1: {"buy_vol": 50, "sell_vol": 500}
        }
    }

    imbalances = engine.detect_imbalances(footprint, ratio=3.0)
    assert len(imbalances) == 2
    assert imbalances[0]['type'] == 'Buy Imbalance'
    assert imbalances[1]['type'] == 'Sell Imbalance'
