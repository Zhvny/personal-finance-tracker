import pytest

pytestmark = pytest.mark.xfail(
    reason="Integration tests need full backend setup; tracked separately (tracking: gate-split)", strict=False
)
import sqlite3

import numpy as np
import pandas as pd


from apps.cli.genetic_optimizer import AUDIT_DB, GeneticOptimizer
from apps.cli.investment_tracker.services.data_loader import DataLoader
from apps.cli.investment_tracker.services.risk_service import RiskService
from apps.cli.stock_analyzer.domain.strategies.volume_profile import VolumeProfile


class MockFetcher:
    def get_returns(self, ticker, period="2y"):
        # Generate 500 days of returns
        np.random.seed(42)
        dates = pd.date_range(end="2024-01-01", periods=500)
        returns = np.random.normal(0.0005, 0.01, 500)
        return pd.Series(returns, index=dates)

    def get_ohlcv(self, ticker, period="1y"):
        np.random.seed(42)
        dates = pd.date_range(end="2024-01-01", periods=100)
        df = pd.DataFrame(
            {
                "Open": np.random.uniform(100, 110, 100),
                "High": np.random.uniform(110, 120, 100),
                "Low": np.random.uniform(90, 100, 100),
                "Close": np.random.uniform(100, 110, 100),
                "Volume": np.random.uniform(1000, 5000, 100),
            },
            index=dates,
        )

        # Inject absorption zones (High Vol, Low Range)
        df.iloc[50:55, 4] = 10000  # High Volume
        df.iloc[50:55, 1] = 105.1  # High
        df.iloc[50:55, 2] = 104.9  # Low
        df.iloc[50:55, 3] = 105.0  # Close

        return df


@pytest.fixture
def integration_context():
    fetcher = MockFetcher()
    data_loader = DataLoader(fetcher=fetcher)
    vp = VolumeProfile()
    # Mocking GeneticOptimizer to use our data_loader
    optimizer = GeneticOptimizer(iterations=2, pop_size=5)
    optimizer.data_loader = data_loader
    return {"fetcher": fetcher, "data_loader": data_loader, "optimizer": optimizer, "vp": vp}


def test_full_advanced_flow(integration_context):
    ctx = integration_context
    ticker = "INTEGRATION_TEST_TICKER"

    # 1. Data Loading
    returns = ctx["data_loader"].get_returns(ticker)
    assert len(returns) == 500
    assert isinstance(returns, np.ndarray)

    # 2. Genetic Optimization (XGBoost)
    # This evolves params based on features generated from returns
    # We use small iterations for speed in test
    best_mae = ctx["optimizer"].evolve(ticker, "test_category")
    assert best_mae is not None
    assert best_mae >= 0

    # Verify Audit Log
    with sqlite3.connect(str(AUDIT_DB)) as conn:
        res = conn.execute("SELECT COUNT(*) FROM evolution_logs WHERE ticker = ?", (ticker,)).fetchone()
        assert res[0] > 0

    # 3. Volume Profile & Absorption
    ohlcv = ctx["fetcher"].get_ohlcv(ticker)
    vp_data = ctx["vp"].calculate(ohlcv)

    assert "poc" in vp_data
    assert "absorption_zones" in vp_data
    assert len(vp_data["absorption_zones"]) > 0

    # 4. Risk Service (Monte Carlo)
    # We'll use the volatility from returns and a current price of 100
    vol = returns.std()
    mc_result = RiskService.monte_carlo_simulation(100.0, vol, iterations=2000)

    assert "prob_of_ruin" in mc_result
    assert "final_mean_price" in mc_result
    assert mc_result["iterations"] == 2000

    # 5. Surgical Advice Integration
    pred_data = {"target_price": 115.0, "confidence": 0.85, "pred_return": 15.0, "volatility": vol}
    advice = RiskService.get_surgical_advice(ticker, 100.0, pred_data)
    assert "DR. STRANGE RISK REPORT" in advice
    assert "SNIPER SIGNAL" in advice or "BULLISH" in advice

    print(f"\nIntegration Success: {ticker}")
    print(f"Best MAE: {best_mae}")
    print(f"Absorption Zones: {vp_data['absorption_zones']}")
    print(f"Prob of Ruin: {mc_result['prob_of_ruin']:.4f}")


if __name__ == "__main__":
    # Allow manual run
    pytest.main([__file__])
