import pandas as pd
import pytest

from apps.cli.stock_analyzer.adapters.advanced_indicators import AdvancedIndicatorEngine


@pytest.fixture
def intraday_data():
    # 50 bars at 100.0, 50 bars at 105.0
    prices = [100.0] * 50 + [105.0] * 50
    df = pd.DataFrame({
        'Open': prices,
        'High': [p + 0.1 for p in prices],
        'Low': [p - 0.1 for p in prices],
        'Close': [p + 0.05 for p in prices],
        'Volume': [1000.0] * 100
    }, index=pd.date_range('2023-01-01 09:30', periods=100, freq='min'))
    return df

def test_compute_advanced(intraday_data):
    engine = AdvancedIndicatorEngine()
    results = engine.compute_advanced("AAPL", None, intraday_data)

    # 1. VWAP
    assert results['vwap'] > 0
    assert 'trend_signal' in results['vwap_signals']
    assert 'mean_reversion_signal' in results['vwap_signals']

    # 2. Order Flow
    assert 'absorption' in results['order_flow_signals']
    assert 'exhaustion' in results['order_flow_signals']
    assert isinstance(results['order_flow_signals']['absorption'], list)
    assert isinstance(results['order_flow_signals']['exhaustion'], list)

    # 3. Volume Profile
    assert 'poc' in results
    assert 'vah' in results
    assert 'val' in results
    assert 'profile_shape' in results
    assert results['profile_shape'] in ['P-shape', 'b-shape', 'D-shape']

    # 4. Market Structure
    assert 'market_structure' in results
    assert 'fvg_present' in results
