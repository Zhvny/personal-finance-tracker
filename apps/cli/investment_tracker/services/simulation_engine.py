from typing import Dict

import numpy as np


def run_monte_carlo(current_price: float, volatility: float, iterations: int = 1000, days: int = 252) -> Dict:
    """
    Vectorized Monte Carlo Simulation.
    Calculates Probability of Ruin based on -20% drawdown.
    Top-level function for picklability (required for Windows multiprocessing).
    """
    if iterations < 1000:
        iterations = 1000

    # Daily returns simulation using numpy vectorization
    # volatility = ATR_R (Average True Range Relative)
    daily_returns = np.random.normal(0, volatility, (iterations, days))

    # Calculate cumulative price paths
    price_paths = current_price * np.cumprod(1 + daily_returns, axis=1)

    # Vectorized Drawdown Calculation
    running_max = np.maximum.accumulate(price_paths, axis=1)
    running_max = np.maximum(running_max, current_price)
    drawdowns = (price_paths / running_max) - 1

    # Probability of Ruin (-20% drawdown)
    ruined_paths = np.any(drawdowns <= -0.20, axis=1)
    prob_of_ruin = np.mean(ruined_paths)

    return {
        "iterations": iterations,
        "days": days,
        "prob_of_ruin": float(prob_of_ruin),
        "final_mean_price": float(np.mean(price_paths[:, -1])),
        "worst_drawdown": float(np.min(drawdowns))
    }

class SimulationEngine:
    @staticmethod
    def run_monte_carlo(current_price: float, volatility: float, iterations: int = 1000, days: int = 252) -> Dict:
        """Wrapper for top-level simulation function."""
        return run_monte_carlo(current_price, volatility, iterations, days)
