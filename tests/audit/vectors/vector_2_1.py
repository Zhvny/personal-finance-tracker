from decimal import Decimal

from harness import FinancialAuditVector


class AuditVector_2_1(FinancialAuditVector):
    """
    Failure Vector 2.1: Binary Floating Point Drift
    Verify that using float for IDR calculations causes drift, 
    whereas Decimal remains exact.
    """
    def setup(self):
        self.log("Setting up drift scenario with float vs Decimal.")
        self.values = [0.1, 0.2]
        self.decimal_values = [Decimal('0.1'), Decimal('0.2')]

    def reproduce(self):
        # Float math
        self.float_sum = sum(self.values)
        self.log(f"Float sum (0.1 + 0.2): {self.float_sum}")

        # Decimal math
        self.decimal_sum = sum(self.decimal_values)
        self.log(f"Decimal sum (0.1 + 0.2): {self.decimal_sum}")

    def validate(self) -> bool:
        # DoD: 0.1 + 0.2 must be EXACTLY 0.3 in financial context.
        expected = Decimal('0.3')

        float_correct = (self.float_sum == 0.3)
        decimal_correct = (self.decimal_sum == expected)

        self.log(f"Float correct? {float_correct}")
        self.log(f"Decimal correct? {decimal_correct}")

        # This vector passes if Decimal is correct and float is NOT (proving the drift exists)
        # However, for an audit, we want to ensure the SYSTEM uses Decimal.
        # Here we just verify that Decimal works as expected for 0.1 + 0.2.
        return decimal_correct and not float_correct

    def teardown(self):
        pass
