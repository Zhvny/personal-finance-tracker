from decimal import ROUND_HALF_UP, Decimal

from harness import FinancialAuditVector


class AuditVector_2_7(FinancialAuditVector):
    """
    Failure Vector 2.7: Rounding Accumulation
    Verify that summing rounded items vs rounding the total leads to variance.
    """
    def setup(self):
        self.log("Setting up 10,000 transactions of 0.004 IDR.")
        self.item_value = Decimal('0.004')
        self.count = 10000

    def reproduce(self):
        # Method 1: Round each item, then sum
        self.sum_rounded_items = sum([self.item_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) for _ in range(self.count)])

        # Method 2: Sum all, then round total
        self.rounded_total = (self.item_value * self.count).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        self.log(f"Sum of rounded items: {self.sum_rounded_items}")
        self.log(f"Rounded total sum:    {self.rounded_total}")

    def validate(self) -> bool:
        # DoD: Financial reports MUST round at the total level for accuracy.
        # 0.004 rounds to 0.00. 0.00 * 10,000 = 0.
        # 0.004 * 10,000 = 40. 40 rounds to 40.
        # There should be a 40 IDR difference.
        variance = abs(self.sum_rounded_items - self.rounded_total)
        self.log(f"Variance: {variance}")

        return variance > 0 and self.rounded_total == Decimal('40.00')

    def teardown(self):
        pass
