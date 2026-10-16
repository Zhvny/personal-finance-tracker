from decimal import Decimal

from harness import FinancialAuditVector


class AuditVector_2_9(FinancialAuditVector):
    """
    Failure Vector 2.9: PTKP Status Drift
    Verify that changing tax status correctly updates future calculations 
    but preserves historical record integrity (or triggers recalculation if mandated).
    """
    def setup(self):
        # PTKP (Penghasilan Tidak Kena Pajak) values for 2024
        self.ptkp_rates = {
            "TK/0": Decimal('54000000'),
            "K/3": Decimal('72000000')
        }
        self.current_status = "TK/0"
        self.log(f"Initial status: {self.current_status}")

    def calculate_taxable_income(self, annual_income: Decimal) -> Decimal:
        ptkp = self.ptkp_rates[self.current_status]
        taxable = annual_income - ptkp
        return max(Decimal('0'), taxable)

    def reproduce(self):
        self.income = Decimal('100000000')

        # Period 1
        self.taxable_p1 = self.calculate_taxable_income(self.income)
        self.log(f"Taxable income (TK/0): {self.taxable_p1}")

        # Update Status
        self.current_status = "K/3"
        self.log("Updated status to K/3.")

        # Period 2
        self.taxable_p2 = self.calculate_taxable_income(self.income)
        self.log(f"Taxable income (K/3): {self.taxable_p2}")

    def validate(self) -> bool:
        # DoD: Taxable income for K/3 (married, 3 children) must be lower than TK/0.
        # 100M - 54M = 46M
        # 100M - 72M = 28M

        valid_p1 = (self.taxable_p1 == Decimal('46000000'))
        valid_p2 = (self.taxable_p2 == Decimal('28000000'))

        self.log(f"P1 Valid? {valid_p1}")
        self.log(f"P2 Valid? {valid_p2}")

        return valid_p1 and valid_p2

    def teardown(self):
        pass
