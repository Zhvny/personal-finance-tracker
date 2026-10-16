from typing import List

from packages.cli.income_tracker.core.models import Income


class IncomeCalculator:

    @staticmethod
    def total_income(incomes: List[Income]) -> float:
        return sum(i.amount for i in incomes)

    @staticmethod
    def average_monthly(incomes: List[Income]) -> float:
        if not incomes:
            return 0
        return sum(i.amount for i in incomes) / len(incomes)

    @staticmethod
    def tax_estimate(annual_income: float) -> float:
        """
        Simplified PPh 21 estimation (Indonesia).
        """
        # PTKP (Penghasilan Tidak Kena Pajak) - K/0 = 58.5 juta
        ptkp = 58_500_000

        taxable = max(0, annual_income - ptkp)

        # Progressive tax
        if taxable <= 60_000_000:
            tax = taxable * 0.05
        elif taxable <= 250_000_000:
            tax = 3_000_000 + (taxable - 60_000_000) * 0.15
        elif taxable <= 500_000_000:
            tax = 31_500_000 + (taxable - 250_000_000) * 0.25
        elif taxable <= 5_000_000_000:
            tax = 94_000_000 + (taxable - 500_000_000) * 0.30
        else:
            tax = 1_444_000_000 + (taxable - 5_000_000_000) * 0.35

        return tax
