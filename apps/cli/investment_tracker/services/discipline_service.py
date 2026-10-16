from typing import List

from packages.core.domain.models import Investment, SellTransaction



class DisciplineService:
    def __init__(self, repo):
        self.repo = repo

    def evaluate_investment(self, inv: Investment, total_portfolio_value: float) -> List[tuple]:
        """Evaluate a new investment for discipline points."""
        events = []

        # Rule 1: Position Sizing
        inv_value = inv.quantity * inv.buy_price
        # Normalize to IDR for comparison if needed, but let's assume same currency for simplicity in MVP
        # Or just use percentage if we have total_portfolio_value
        if total_portfolio_value > 0:
            pct = (inv_value / total_portfolio_value) * 100
            if pct <= 10:
                events.append((5, f"Good Position Sizing ({pct:.1f}%)"))
            elif pct > 20:
                events.append((-10, f"Oversized Position ({pct:.1f}%)"))

        # Rule 2: Stop Loss (Mock check: we don't have a Stop Loss field yet,
        # but we can simulate based on user intent in future)
        # For now, let's just use sizing.

        for delta, reason in events:
            self.repo.update_reward_points(delta)

        return events

    def evaluate_sell(self, inv: Investment, sell: SellTransaction) -> List[tuple]:
        """Evaluate a sell action for discipline points."""
        events = []

        # Rule: No Revenge Trading
        # If sold at a loss, and the last trade was also a loss within 24 hours...
        # This requires more complex history tracking, but let's do a simple version.

        if sell.realized_pl < 0:
            # check recent history
            # (Stub for now)
            pass

        for delta, reason in events:
            self.repo.update_reward_points(delta)

        return events

    def get_status(self) -> dict:
        points = self.repo.get_reward_points()

        if points >= 120: rank = "Disciple of Zen"
        elif points >= 100: rank = "Steady Trader"
        elif points >= 80: rank = "Impulsive"
        else: rank = "Degenerate Gambler"

        return {
            "points": points,
            "rank": rank
        }
