from dataclasses import dataclass


@dataclass
class ProfitResult:
    """Data class untuk hasil kalkulasi"""
    buy_value: float
    current_value: float
    profit: float
    percent: float

class ProfitCalculator:
    @staticmethod
    def calculate(buy_price_idr: float, current_price_idr: float, quantity: float) -> ProfitResult:
        buy_value = buy_price_idr * quantity
        current_value = current_price_idr * quantity
        profit = current_value - buy_value

        percent = (profit / buy_value * 100) if buy_value != 0 else 0.0

        return ProfitResult(
            buy_value=float(buy_value),
            current_value=float(current_value),
            profit=float(profit),
            percent=float(percent)
        )
