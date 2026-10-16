import pandas as pd

from apps.cli.stock_analyzer.domain.strategies.order_flow import OrderFlowEngine


def test_detect_absorption():
    engine = OrderFlowEngine()
    # Need 20+ rows for MA
    data = []
    for i in range(25):
        data.append({'Open': 100.0, 'High': 101.0, 'Low': 99.0, 'Close': 100.5, 'Volume': 1000.0})

    # Absorption row: High volume (3000 > 1000*1.5), low range (0.2 < 2.0*0.5)
    data[-1] = {'Open': 100.0, 'High': 100.1, 'Low': 99.9, 'Close': 100.0, 'Volume': 3000.0}

    df = pd.DataFrame(data)
    df.index = pd.date_range('2023-01-01 09:30', periods=len(df), freq='min')

    absorptions = engine.detect_absorption(df)
    assert len(absorptions) > 0
    assert absorptions[0]['type'] == 'Absorption'
    assert absorptions[0]['volume'] == 3000.0

def test_detect_exhaustion():
    engine = OrderFlowEngine()
    data = []
    for i in range(15):
        data.append({'Open': 100.0+i, 'High': 101.0+i, 'Low': 99.0+i, 'Close': 100.5+i, 'Volume': 1000.0})

    df = pd.DataFrame(data)
    df.index = pd.date_range('2023-01-01 09:30', periods=len(df), freq='min')
    df = engine.calculate_synthetic_delta(df)

    # Exhaustion at high: High price, negative delta
    last_idx = df.index[-1]
    df.at[last_idx, 'High'] = 150.0
    df.at[last_idx, 'Close'] = 149.0
    df.at[last_idx, 'Open'] = 150.0 # Open >= Close means delta <= 0

    # Recalculate delta for the last row
    df = engine.calculate_synthetic_delta(df)

    exhaustions = engine.detect_exhaustion(df)
    assert any(e['type'] == 'Bearish Exhaustion' for e in exhaustions)

def test_detect_absorption_empty():
    engine = OrderFlowEngine()
    assert engine.detect_absorption(pd.DataFrame()) == []

def test_detect_exhaustion_empty():
    engine = OrderFlowEngine()
    assert engine.detect_exhaustion(pd.DataFrame()) == []
