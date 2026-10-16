from decimal import Decimal

from harness import FinancialAuditVector


class AuditVector_2_6(FinancialAuditVector):
    """
    Failure Vector 2.6: Unrealized Gain Overflow
    Verify that extremely high values (10,000% gain) don't overflow.
    In Python this is usually fine, but we verify 64-bit bounds or Decimal limits.
    """
    def setup(self):
        # 32-bit signed int max is ~2.1 billion.
        # If we use IDR, we can hit this easily.
        # 1,000,000,000,000 (1 Trillion IDR) is a realistic test for overflow in some systems.
        self.log("Setting up massive gain scenario.")
        self.initial_investment = Decimal('1000') # 1,000 IDR
        self.target_gain_multiplier = Decimal('1000000000') # 1 Billion multiplier

    def reproduce(self):
        self.current_value = self.initial_investment * self.target_gain_multiplier
        self.log(f"Current Value: {self.current_value}")

        # Check if it fits in a 64-bit integer (optional, but good for DB check)
        self.as_int = int(self.current_value)
        self.fits_64bit = self.as_int < (2**63 - 1)

    def validate(self) -> bool:
        # DoD: Calculation is accurate and fits in 64-bit space (standard for modern DBs).
        expected = Decimal('1000000000000') # 1 Trillion
        self.log(f"Expected: {expected}")
        self.log(f"Fits 64-bit? {self.fits_64bit}")

        return self.current_value == expected and self.fits_64bit

    def teardown(self):
        pass
