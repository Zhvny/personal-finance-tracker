from decimal import Decimal
from typing import List

from packages.core.domain.models import Income


class IncomeCalculator:

    @staticmethod
    def total_income(incomes: List[Income]) -> Decimal:
        return sum((Decimal(str(i.amount)) for i in incomes), Decimal('0'))

    @staticmethod
    def average_monthly(incomes: List[Income]) -> Decimal:
        if not incomes:
            return Decimal('0')
        return sum((Decimal(str(i.amount)) for i in incomes), Decimal('0')) / Decimal(len(incomes))

    @staticmethod
    def tax_estimate(annual_income: Decimal) -> Decimal:
        """
        Simplified PPh 21 estimation (Indonesia).
        """
        # PTKP (Penghasilan Tidak Kena Pajak) - K/0 = 58.5 juta
        ptkp = Decimal('58500000')

        taxable = max(Decimal('0'), annual_income - ptkp)

        # Progressive tax
        if taxable <= Decimal('60000000'):
            tax = taxable * Decimal('0.05')
        elif taxable <= Decimal('250000000'):
            tax = Decimal('3000000') + (taxable - Decimal('60000000')) * Decimal('0.15')
        elif taxable <= Decimal('500000000'):
            tax = Decimal('31500000') + (taxable - Decimal('250000000')) * Decimal('0.25')
        elif taxable <= Decimal('5000000000'):
            tax = Decimal('94000000') + (taxable - Decimal('500000000')) * Decimal('0.30')
        else:
            tax = Decimal('1444000000') + (taxable - Decimal('5000000000')) * Decimal('0.35')

        return tax
