import numpy as np
import pandas as pd

from apps.cli.stock_analyzer.domain.strategies.volume_profile import VolumeProfile


def test_detect_shape_p():
    vp = VolumeProfile()
    # High volume at top
    prices = np.linspace(100, 110, 20)
    # Lower half (10 bins) low volume, Upper half (10 bins) high volume
    volumes = np.concatenate([np.full(10, 100.0), np.full(10, 1000.0)])
    profile = pd.Series(volumes, index=prices)

    # POC in upper half (109 is > 106)
    shape = vp.detect_shape(profile, poc=109.0, vah=110.0, val=105.0)
    assert shape == "P-shape"

def test_detect_shape_b():
    vp = VolumeProfile()
    # High volume at bottom
    prices = np.linspace(100, 110, 20)
    # Lower half (10 bins) high volume, Upper half (10 bins) low volume
    volumes = np.concatenate([np.full(10, 1000.0), np.full(10, 100.0)])
    profile = pd.Series(volumes, index=prices)

    # POC in lower half (101 is < 104)
    shape = vp.detect_shape(profile, poc=101.0, vah=105.0, val=100.0)
    assert shape == "b-shape"

def test_calculate_includes_shape():
    vp = VolumeProfile()
    data = []
    # Create a 'P' shape distribution: price trending up then staying high with more volume
    for i in range(50):
        data.append({'High': 100.0+i*0.1, 'Low': 100.0+i*0.1-0.05, 'Close': 100.0+i*0.1, 'Volume': 100.0})
    for i in range(50):
        data.append({'High': 105.0, 'Low': 104.95, 'Close': 105.0, 'Volume': 1000.0})

    df = pd.DataFrame(data)
    result = vp.calculate(df)
    assert 'profile_shape' in result
    assert result['profile_shape'] == 'P-shape'

def test_detect_shape_d():
    vp = VolumeProfile()
    # Balanced volume around center
    prices = np.linspace(100, 110, 21)
    volumes = [100.0]*8 + [1000.0]*5 + [100.0]*8
    profile = pd.Series(volumes, index=prices)

    shape = vp.detect_shape(profile, poc=105.0, vah=107.0, val=103.0)
    assert shape == "D-shape"

def test_detect_absorption():
    vp = VolumeProfile()
    # Create synthetic data with an absorption bar
    # High volume (2000), low range (100.1 - 100.0 = 0.1)
    # Compared to average volume (1000) and average range (1.0)
    data = []
    for i in range(10):
        data.append({'High': 100.0+i, 'Low': 99.0+i, 'Close': 100.0+i, 'Volume': 1000.0})

    # The absorption bar
    data.append({'High': 105.1, 'Low': 105.0, 'Close': 105.05, 'Volume': 5000.0})

    df = pd.DataFrame(data)
    result = vp.calculate(df)

    assert 'absorption_zones' in result
    # Price 105.05 should be near one of the absorption zones
    assert len(result['absorption_zones']) > 0
    # Check if 105 is close to any flagged zone
    assert any(abs(z - 105) < 2.0 for z in result['absorption_zones'])
