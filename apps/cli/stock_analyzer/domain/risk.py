import math


class RiskManager:
    @staticmethod
    def calculate_expectancy(win_rate: float, avg_win: float, avg_loss: float) -> float:
        return (win_rate * avg_win) - ((1.0 - win_rate) * abs(avg_loss))

    @staticmethod
    def calculate_kelly_criterion(win_rate: float, risk_reward_ratio: float) -> float:
        if risk_reward_ratio <= 0: return 0.0
        return max(0.0, win_rate - ((1.0 - win_rate) / risk_reward_ratio))

    @staticmethod
    def calculate_dynamic_risk(score: float, win_rate: float, rr: float, base_risk: float = 0.015) -> float:
        if rr <= 0: return 0.005
        kelly = win_rate - ((1.0 - win_rate) / rr)
        half_kelly = max(0.005, kelly / 2.0)
        score_mult = max(0.5, min(1.5, (score - 5.0) / 2.0 + 0.5))
        return max(0.005, min(0.03, min(base_risk * score_mult, half_kelly)))

    @staticmethod
    def calculate_position_size(balance: float, risk: float, entry: float, sl: float, score: float = 7.0) -> float:
        risk_share = abs(entry - sl)
        if risk_share == 0: return 0.0
        pos_units = math.floor((balance * risk) / risk_share)
        notional = max(0.10, min(0.25, (score - 5.0) * 0.05 + 0.10))
        return float(min(pos_units, math.floor((balance * notional) / entry)))

    @staticmethod
    def get_strategy_performance(score: float) -> tuple[float, float]:
        # Improved Heuristic (Baseline) - StockAnalyzer now averages this with per-ticker stats
        if score >= 9.0: return 0.65, 2.5
        if score >= 8.0: return 0.58, 2.0
        if score >= 7.0: return 0.52, 1.8
        if score >= 6.0: return 0.48, 1.5
        return 0.40, 1.2
