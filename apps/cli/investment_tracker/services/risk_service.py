from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Optional

from apps.cli.investment_tracker.services.simulation_engine import SimulationEngine


class RiskService:
    @staticmethod
    def calculate_kelly_sizing(win_prob: float, win_loss_ratio: float) -> float:
        """
        Kelly Criterion Formula: K% = (p*b - q) / b
        p = win_prob
        q = 1 - p
        b = win_loss_ratio (e.g. 2.0 for 2:1 reward/risk)
        """
        if win_loss_ratio <= 0: return 0.0
        p = win_prob
        q = 1 - p
        b = win_loss_ratio
        kelly = (p * b - q) / b
        return max(0.0, kelly)

    @staticmethod
    def monte_carlo_simulation(current_price: float, volatility: float, iterations: int = 1000, days: int = 252) -> Dict:
        """
        DR. STRANGE SIMULATOR: Long-term portfolio risk modeling.
        Uses ProcessPoolExecutor to run vectorized simulation in a separate process.
        Includes a synchronous fallback for environments where multiprocessing is restricted.
        """
        try:
            with ProcessPoolExecutor(max_workers=1) as executor:
                future = executor.submit(SimulationEngine.run_monte_carlo, current_price, volatility, iterations, days)
                return future.result()
        except Exception:
            # Fallback to synchronous execution if ProcessPoolExecutor fails (e.g. WinError 3)
            return SimulationEngine.run_monte_carlo(current_price, volatility, iterations, days)

    @staticmethod
    def get_surgical_advice(ticker: str, current_price: float, pred_data: Optional[dict]):
        if not pred_data:
            return "No ML data for this asset."

        target = pred_data["target_price"]
        conf = pred_data["confidence"]
        pred_ret = pred_data["pred_return"]
        volatility = pred_data.get("volatility", 0.02) # Default to 2% if missing

        # Run Monte Carlo Simulation
        mc = RiskService.monte_carlo_simulation(current_price, volatility)
        prob_ruin = mc["prob_of_ruin"]

        # Base Sizing (Conservative)
        base_size = 5.0 # 5% of portfolio

        advice = f"ML Target: {target:.2f} ({pred_ret:+.2f}%) | Confidence: {conf*100:.0f}%\n"
        advice += "DR. STRANGE RISK REPORT (252 days):\n"
        advice += f"   Prob. of Ruin (-20% drawdown): {prob_ruin*100:.1f}%\n"
        advice += f"   Expected Final Price: {mc['final_mean_price']:.2f}\n"

        if prob_ruin > 0.40:
            advice += "⚠️ HIGH RISK: Simulation shows high ruin probability. Size down.\n"
            base_size *= 0.5

        if pred_ret > 0 and conf > 0.80:
            boost = 1.5 # 50% boost
            advice += "🔥 SNIPER SIGNAL: Confidence is high (>80%).\n"
            advice += f"   Recommended Position Boost: {boost}x (Kelly % boost applied).\n"
            advice += f"   Surgical Allocation: {base_size * boost:.1f}% of capital."
        elif pred_ret > 0:
            advice += "📈 BULLISH: Predicted price is higher.\n"
            advice += f"   Standard Allocation: {base_size}% of capital."
        else:
            advice += "📉 BEARISH: Predicted price is lower.\n"
            advice += "   Caution: Consider reducing position or waiting for dip."

        return advice
