from typing import Dict


class BudgetService:
    """
    Budget vs Actual tracking.
    """

    def __init__(self):
        # Default budgets (bisa di-load dari config/db)
        self.default_budgets = {
            "food": 2_000_000,
            "transport": 1_000_000,
            "housing": 3_000_000,
            "entertainment": 500_000,
            "health": 500_000,
            "shopping": 1_000_000,
            "education": 500_000,
            "other": 300_000,
        }

    def set_budget(self, category: str, amount: float):
        self.default_budgets[category] = amount

    def check_budget(self, actual_spending: Dict[str, float]) -> Dict:
        """
        Compare actual vs budget.
        Returns dict dengan status: 'under', 'over', 'warning' (80%+)
        """
        results = {}

        for category, budget in self.default_budgets.items():
            actual = actual_spending.get(category, 0)
            remaining = budget - actual
            pct_used = (actual / budget * 100) if budget > 0 else 0

            if pct_used >= 100:
                status = "over"
            elif pct_used >= 80:
                status = "warning"
            else:
                status = "under"

            results[category] = {
                "budget": budget,
                "actual": actual,
                "remaining": remaining,
                "pct_used": pct_used,
                "status": status
            }

        return results
