import time
from decimal import Decimal

from harness import FinancialAuditVector


class AuditVector_2_5(FinancialAuditVector):
    """
    Failure Vector 2.5: FX Rate Staleness
    Verify that the system detects and rejects rates older than 2 hours.
    """
    def setup(self):
        self.log("Defining rate timestamps.")
        self.now = int(time.time())
        self.fresh_rate = {"rate": Decimal('15000'), "timestamp": self.now}
        self.stale_rate = {"rate": Decimal('14000'), "timestamp": self.now - (25 * 3600)} # 25 hours old

    def is_rate_valid(self, rate_obj: dict) -> bool:
        # Business Rule: Rates older than 2 hours are stale.
        MAX_AGE = 2 * 3600
        age = self.now - rate_obj["timestamp"]
        return age <= MAX_AGE

    def reproduce(self):
        self.fresh_valid = self.is_rate_valid(self.fresh_rate)
        self.stale_valid = self.is_rate_valid(self.stale_rate)

        self.log(f"Fresh rate valid? {self.fresh_valid}")
        self.log(f"Stale rate valid? {self.stale_valid}")

    def validate(self) -> bool:
        # DoD: Fresh is valid, Stale is NOT.
        return self.fresh_valid == True and self.stale_valid == False

    def teardown(self):
        pass
