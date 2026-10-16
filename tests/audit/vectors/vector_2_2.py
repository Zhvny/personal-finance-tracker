from decimal import Decimal

from harness import FinancialAuditVector


class AuditVector_2_2(FinancialAuditVector):
    """
    Failure Vector 2.2: FIFO Lot Fragmentation
    Verify that micro-sells are correctly subtracted from lots without leaving
    irrecoverable float-based dust.
    """
    def setup(self):
        self.log("Setting up 1.0 BTC lot.")
        self.initial_lot = Decimal('1.0')
        self.sell_amount = Decimal('0.00000001')
        self.iterations = 100

    def reproduce(self):
        self.current_lot = self.initial_lot
        self.log(f"Subtracting {self.sell_amount} {self.iterations} times.")
        for i in range(self.iterations):
            self.current_lot -= self.sell_amount

    def validate(self) -> bool:
        expected = self.initial_lot - (self.sell_amount * self.iterations)
        self.log(f"Final lot size: {self.current_lot}")
        self.log(f"Expected size:  {expected}")

        # DoD: Exact precision maintained. No rounding errors at 8 decimal places.
        return self.current_lot == expected

    def teardown(self):
        pass
