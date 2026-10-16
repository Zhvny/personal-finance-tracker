from typing import List

from packages.core.domain.models import Expense


class ExpenseCalculator:

    @staticmethod
    def total_expenses(expenses: List[Expense]) -> float:
        return sum(e.amount for e in expenses)

    @staticmethod
    def average_daily(expenses: List[Expense], days: int = 30) -> float:
        if not expenses or days <= 0:
            return 0
        return sum(e.amount for e in expenses) / days

    @staticmethod
    def top_spending_categories(expenses: List[Expense], limit: int = 3) -> List[tuple]:
        totals = {}
        for e in expenses:
            c = e.category.value
            totals[c] = totals.get(c, 0) + e.amount

        sorted_items = sorted(totals.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:limit]
