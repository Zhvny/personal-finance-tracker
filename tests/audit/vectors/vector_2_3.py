from decimal import Decimal

from harness import FinancialAuditVector


class AuditVector_2_3(FinancialAuditVector):
    """
    Failure Vector 2.3: Negative Cost Basis
    Verify that trade reversals cannot result in a negative cost basis.
    """
    def setup(self):
        self.log("Initial state: 10 shares @ 100 IDR each.")
        self.shares = 10
        self.cost_per_share = Decimal('100')
        self.total_cost = self.shares * self.cost_per_share

        self.log("Reversal event: Refund of 1100 IDR (more than initial cost).")
        self.refund_amount = Decimal('1100')

    def reproduce(self):
        # Simulation of bug: direct subtraction without floor
        self.new_cost = self.total_cost - self.refund_amount
        self.log(f"New cost basis after reversal: {self.new_cost}")

    def validate(self) -> bool:
        # DoD: Cost basis must NEVER be negative.
        is_negative = self.new_cost < 0
        self.log(f"Is cost basis negative? {is_negative}")

        # This vector "detects" the failure if is_negative is True.
        # For the audit to "pass" (meaning it correctly identifies the bug),
        # we might want to return False if the bug is present.
        # But usually these vectors are used to verify the FIX.
        # For now, let's assume we are testing if the system ALLOWS it (which it shouldn't).
        return self.new_cost >= 0

    def teardown(self):
        pass
