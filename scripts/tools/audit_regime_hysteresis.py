import os
import sys

# Setup paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(base_path)
sys.path.append(os.path.join(base_path, "apps", "cli"))
sys.path.append(os.path.join(base_path, "apps", "cli", "investment_tracker"))
sys.path.append(os.path.join(base_path, "apps", "cli", "investment_tracker", "services"))
sys.path.append(os.path.join(base_path, "packages", "core", "src", "application"))

from unittest.mock import MagicMock

import pandas as pd

# Mock services that cause import loops/failures in audit env
sys.modules['services.butterfly_service'] = MagicMock()
sys.modules['services.sentiment_service'] = MagicMock()
sys.modules['prediction_service'] = MagicMock()
sys.modules['core.repository'] = MagicMock()

from services.senate_service import AgentOpinion, SenateService, Vote


def run_hysteresis_test():
    print("=== Vector 4.1: Regime Hysteresis Test ===")

    # Create baseline DF (Bull regime: MA50 > MA200)
    # Price is 150. MA50=140, MA200=100.
    dates = pd.date_range(end='2026-05-25', periods=200)
    df = pd.DataFrame({
        'Open': 150.0, 'High': 155.0, 'Low': 145.0, 'Close': 151.0, 'Volume': 1000000
    }, index=dates)
    df.ticker = "TEST_HYST"

    svc = SenateService(category="audit")

    # Manually override agents that use mocked services to return neutral
    for agent in svc.agents:
        if "Sentiment" in agent.name or "Macro" in agent.name or "Quant" in agent.name:
            agent.vote = MagicMock(return_value=AgentOpinion(agent.name, Vote.HOLD, 0.5, "Audit neutral"))

    results = []
    # Noise range: RSI 54-56 (Threshold 55)
    for rsi_val in [54.0, 55.0, 56.0, 54.0, 56.0]:
        MomentumAgent_orig = svc.agents[0]._calculate_rsi
        svc.agents[0]._calculate_rsi = MagicMock(return_value=pd.Series([rsi_val]*200))

        res = svc.get_senate_decision("TEST_HYST", df)
        results.append((rsi_val, res.consensus.value, f"{res.confidence:.2f}"))
        svc.agents[0]._calculate_rsi = MomentumAgent_orig

    for val, con, conf in results:
        print(f"RSI: {val} -> Consensus: {con} (Conf: {conf})")

    # Check for flipping
    consensuses = [r[1] for r in results]
    if len(set(consensuses)) > 1:
        print("WARNING: Regime Hysteresis detected. Minor RSI noise flips consensus.")
    else:
        print("PASS: Consensus stable despite noise.")

if __name__ == "__main__":
    run_hysteresis_test()
