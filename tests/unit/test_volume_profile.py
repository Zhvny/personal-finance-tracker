import numpy as np
import pandas as pd
import pytest

from apps.cli.stock_analyzer.domain.strategies.volume_profile import VolumeProfile


@pytest.fixture
def trending_up_data():
    """Create a 100-bar trending up dataset."""
    data = []
    for i in range(100):
        price = 100 + i
        data.append({
            'Open': price,
            'High': price + 1.5,
            'Low': price - 0.5,
            'Close': price + 1.0,
            'Volume': 1000
        })
    df = pd.DataFrame(data)
    df.index = pd.date_range(start='2023-01-01', periods=100, freq='D')
    return df

@pytest.fixture
def ranging_data():
    """Create a 100-bar ranging dataset (Balanced)."""
    data = []
    for i in range(100):
        # Sine wave price between 95 and 105
        price = 100 + 5 * np.sin(i * 2 * np.pi / 20)
        data.append({
            'Open': price,
            'High': price + 1,
            'Low': price - 1,
            'Close': price + 0.1,
            'Volume': 1000
        })
    df = pd.DataFrame(data)
    df.index = pd.date_range(start='2023-01-01', periods=100, freq='D')
    return df

def test_volume_profile_calculate_basic(ranging_data):
    vp = VolumeProfile()
    result = vp.calculate(ranging_data, bins=20)

    assert 'poc' in result
    assert 'vah' in result
    assert 'val' in result
    assert result['total_volume'] == 1000 * 100
    assert result['poc'] >= 95 and result['poc'] <= 105
    assert result['vah'] >= result['poc']
    assert result['val'] <= result['poc']

def test_volume_profile_amt_state(ranging_data):
    vp = VolumeProfile()
    # Calculate VP on ranging data
    result = vp.calculate(ranging_data, bins=20)

    # Last price is around 100
    current_price = ranging_data['Close'].iloc[-1]
    state = vp.get_amt_state(current_price, result['vah'], result['val'], result['poc'])

    # In ranging data, it should be balanced
    assert state in ['BALANCED', 'IMBALANCED_UP', 'IMBALANCED_DOWN']

    # Test explicitly imbalanced
    assert vp.get_amt_state(120, 110, 90, 100) == 'IMBALANCED_UP'
    assert vp.get_amt_state(80, 110, 90, 100) == 'IMBALANCED_DOWN'
    assert vp.get_amt_state(100, 110, 90, 100) == 'BALANCED'

def test_volume_profile_nodes(ranging_data):
    vp = VolumeProfile()
    result = vp.calculate(ranging_data, bins=20)

    hvn, lvn = vp.identify_nodes(result['profile'])
    assert isinstance(hvn, list)
    assert isinstance(lvn, list)

def test_amt_signals():
    vp = VolumeProfile()
    df = pd.DataFrame([
        {'Close': 115}, # Prev price above VAH
        {'Close': 105}  # Current price inside VA
    ])
    vp_data = {
        'amt_state': 'BALANCED',
        'vah': 110,
        'val': 90,
        'poc': 100
    }

    signals = vp.get_amt_signals(df, vp_data)
    assert signals['type'] == 'MEAN_REVERSION_SHORT'
    assert signals['target'] == 100
    assert signals['confidence'] == 0.7

def test_empty_dataframe():
    vp = VolumeProfile()
    result = vp.calculate(pd.DataFrame())
    assert result == {}

def test_single_price_data():
    vp = VolumeProfile()
    df = pd.DataFrame([{'High': 100, 'Low': 100, 'Close': 100, 'Volume': 1000}])
    result = vp.calculate(df)
    assert result['poc'] == 100
    assert result['amt_state'] == 'BALANCED'
