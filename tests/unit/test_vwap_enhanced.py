import pandas as pd

from apps.cli.stock_analyzer.domain.strategies.vwap import VWAPEngine


def test_get_signals_pullback():
    engine = VWAPEngine()
    df = pd.DataFrame({
        'High': [101.0, 102.0, 103.0],
        'Low': [99.0, 100.0, 101.0],
        'Close': [100.0, 101.0, 100.3],
        'Volume': [1000, 1000, 1000]
    }, index=pd.to_datetime(['2023-01-01 09:30', '2023-01-01 09:31', '2023-01-01 09:32']))

    vwap_series = pd.Series([100.0, 100.1, 100.2], index=df.index)

    signals = engine.get_signals(df, vwap_series)
    # 100.3 vs 100.2 is 0.1 difference, 0.1/100.2 ~ 0.00099 < 0.005
    assert signals['trend_signal'] == 'BULLISH_PULLBACK'

def test_get_signals_extended():
    engine = VWAPEngine()
    # Need some price movement for ATR
    prices = [100.0] * 20 + [120.0]
    df = pd.DataFrame({
        'High': [p + 0.5 for p in prices],
        'Low': [p - 0.5 for p in prices],
        'Close': prices,
        'Volume': [1000] * 21
    }, index=pd.date_range('2023-01-01 09:30', periods=21, freq='min'))

    vwap_series = pd.Series([100.0] * 21, index=df.index)

    signals = engine.get_signals(df, vwap_series)
    assert signals['mean_reversion_signal'] == 'EXTENDED_UP'

def test_get_signals_neutral():
    engine = VWAPEngine()
    df = pd.DataFrame({
        'High': [100.0],
        'Low': [100.0],
        'Close': [100.0],
        'Volume': [1000]
    }, index=pd.to_datetime(['2023-01-01 09:30']))

    vwap_series = pd.Series([100.0], index=df.index)

    signals = engine.get_signals(df, vwap_series)
    assert signals['trend_signal'] == 'NEUTRAL'
    assert signals['mean_reversion_signal'] == 'NEUTRAL'
