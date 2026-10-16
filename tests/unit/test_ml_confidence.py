from unittest.mock import patch

import numpy as np
import pandas as pd

from apps.cli.prediction_service import PredictionService


def test_small_returns_confidence():
    """
    Verify confidence is not near-zero (e.g., > 0.015) when pred_return is very small 
    (e.g., 0.001) and volatility is normal (e.g., 0.02).
    Tanh(0.35 * 0.001/0.02) = Tanh(0.0175) ~ 0.0175.
    """
    pred_return = 0.001
    volatility = 0.02
    confidence = PredictionService.calculate_confidence(pred_return, volatility)

    assert confidence > 0.015, f"Confidence {confidence} too low for small return"

def test_extreme_volatility_confidence():
    """
    Verify confidence decreases as volatility increases but does not hard 
    collapse to zero unless volatility is truly extreme.
    """
    pred_return = 0.01
    vol_normal = 0.02
    vol_high = 0.10
    vol_extreme = 0.50

    conf_normal = PredictionService.calculate_confidence(pred_return, vol_normal)
    conf_high = PredictionService.calculate_confidence(pred_return, vol_high)
    conf_extreme = PredictionService.calculate_confidence(pred_return, vol_extreme)

    # Must be monotonic decreasing
    assert conf_normal > conf_high > conf_extreme

    # Tanh(0.35 * 0.01/0.10) = Tanh(0.035) ~ 0.0349
    # Tanh(0.35 * 0.01/0.50) = Tanh(0.007) ~ 0.0069
    assert conf_high > 0.03, f"Confidence {conf_high} collapsed too early for high volatility"
    assert conf_extreme > 0.005, f"Confidence {conf_extreme} collapsed too early for extreme volatility"
    assert conf_extreme > 0.0, "Confidence should not be exactly zero"

def test_confidence_bounds():
    """
    Verify confidence is ALWAYS within [0.0, 1.0] across various edge cases 
    (negative returns, zero volatility, extreme returns).
    """
    edge_cases = [
        (0.001, 0.02),    # Standard
        (0.0, 0.02),      # Zero return
        (0.05, 0.0),      # Zero volatility (Division by zero risk)
        (-0.02, 0.02),    # Negative return (Should use absolute)
        (0.50, 0.01),     # Extreme return (Should be clipped at 1.0)
        (0.01, 5.0),      # Extreme volatility
    ]

    for r, v in edge_cases:
        conf = PredictionService.calculate_confidence(r, v)
        assert 0.0 <= conf <= 1.0, f"Confidence {conf} out of bounds for return={r}, vol={v}"

def test_confidence_is_float():
    """
    Ensure the output is a standard float, not a numpy object, for serialization.
    """
    conf = PredictionService.calculate_confidence(0.01, 0.02)
    assert isinstance(conf, float)

def test_insufficient_data_handling():
    """
    Verify get_prediction returns an explicit status for missing or insufficient data.
    """
    # Mock pathlib.Path.exists and pandas.read_csv
    # We patch them where they are USED (apps.cli.prediction_service)
    with patch("apps.cli.prediction_service.Path.exists") as mock_exists, \
         patch("apps.cli.prediction_service.pd.read_csv") as mock_read:

        # Case 1: Missing raw data file
        mock_exists.return_value = False
        res = PredictionService.get_prediction("AAPL", "us")
        assert res == {"status": "insufficient_data", "ticker": "AAPL", "data": None}

        # Case 2: Data file exists but has < 60 rows (Insufficient)
        mock_exists.return_value = True
        mock_read.return_value = pd.DataFrame({"Close": [100]*10}) # 10 rows < 60
        res = PredictionService.get_prediction("AAPL", "us")
        assert res == {"status": "insufficient_data", "ticker": "AAPL", "data": None}


def test_confidence_distribution_spread():
    """
    Verify that confidence scores are well-distributed across a range of 
    inputs and do not cluster excessively in the 5%-15% range (REQ-5).
    """
    samples = []
    # Generate 400 samples (20x20 grid)
    returns = np.linspace(-0.1, 0.1, 20)
    volatilities = np.linspace(0.01, 0.05, 20)

    for r in returns:
        for v in volatilities:
            conf = PredictionService.calculate_confidence(r, v)
            samples.append(conf)

    samples = np.array(samples)
    total = len(samples)

    # Count samples in [0.05, 0.15]
    cluster_count = np.sum((samples >= 0.05) & (samples <= 0.15))
    cluster_ratio = cluster_count / total

    # Assert that clustering is < 30%
    # With k=5.1 and the sigmoid, the distribution should be more spread out
    assert cluster_ratio < 0.30, f"Confidence clustering in 5-15% range is too high: {cluster_ratio:.2%}"

    # Also verify we have higher confidence values present
    high_conf_count = np.sum(samples > 0.50)
    assert high_conf_count > 0, "No high confidence values (>50%) generated in sample range"
