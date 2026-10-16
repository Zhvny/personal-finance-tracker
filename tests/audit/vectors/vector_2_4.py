from decimal import Decimal

from harness import FinancialAuditVector


class AuditVector_2_4(FinancialAuditVector):
    """
    Failure Vector 2.4: Tax Bracket "Cliff" Error
    Verify PPh 21 calculation at the 60,000,000 IDR boundary.
    Bracket 1: 0 - 60M (5%)
    Bracket 2: 60M - 250M (15%)
    """
    def setup(self):
        self.boundary = Decimal('60000000')
        self.test_value_low = self.boundary - Decimal('1')
        self.test_value_exact = self.boundary
        self.test_value_high = self.boundary + Decimal('1')

    def calculate_tax(self, income: Decimal) -> Decimal:
        tax = Decimal('0')
        if income <= Decimal('60000000'):
            tax = income * Decimal('0.05')
        else:
            tax = Decimal('60000000') * Decimal('0.05')
            tax += (income - Decimal('60000000')) * Decimal('0.15')
        return tax

    def reproduce(self):
        self.tax_low = self.calculate_tax(self.test_value_low)
        self.tax_exact = self.calculate_tax(self.test_value_exact)
        self.tax_high = self.calculate_tax(self.test_value_high)

        self.log(f"Tax for {self.test_value_low}: {self.tax_low}")
        self.log(f"Tax for {self.test_value_exact}: {self.tax_exact}")
        self.log(f"Tax for {self.test_value_high}: {self.tax_high}")

    def validate(self) -> bool:
        # 60M * 0.05 = 3,000,000
        expected_exact = Decimal('3000000')
        expected_high = Decimal('3000000') + Decimal('0.15')

        valid_exact = (self.tax_exact == expected_exact)
        valid_high = (self.tax_high == expected_high)

        self.log(f"Valid at boundary? {valid_exact}")
        self.log(f"Valid above boundary? {valid_high}")

        return valid_exact and valid_high

    def teardown(self):
        pass
