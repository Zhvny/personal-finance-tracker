from datetime import datetime
from decimal import Decimal

from apps.cli.income_tracker.core.calculator import IncomeCalculator
from packages.core.domain.models import Income, IncomeCategory


def test_total_income_decimal_precision():
    incomes = [
        Income(amount=Decimal("1000.50"), source="A", income_type=IncomeCategory.SALARY, date=datetime.now()),
        Income(amount=Decimal("2000.75"), source="B", income_type=IncomeCategory.FREELANCE, date=datetime.now()),
        Income(amount=Decimal("0.01"), source="C", income_type=IncomeCategory.OTHER, date=datetime.now()),
    ]
    total = IncomeCalculator.total_income(incomes)
    assert total == Decimal("3001.26")
    assert isinstance(total, Decimal)

def test_average_monthly_decimal_precision():
    incomes = [
        Income(amount=Decimal("1000"), source="A", income_type=IncomeCategory.SALARY, date=datetime.now()),
        Income(amount=Decimal("2000"), source="B", income_type=IncomeCategory.SALARY, date=datetime.now()),
        Income(amount=Decimal("3000"), source="C", income_type=IncomeCategory.SALARY, date=datetime.now()),
    ]
    avg = IncomeCalculator.average_monthly(incomes)
    assert avg == Decimal("2000")
    assert isinstance(avg, Decimal)

def test_average_monthly_empty():
    avg = IncomeCalculator.average_monthly([])
    assert avg == Decimal("0")

def test_tax_estimate_below_ptkp():
    # PTKP = 58.5M
    income = Decimal("50000000")
    tax = IncomeCalculator.tax_estimate(income)
    assert tax == Decimal("0")

def test_tax_estimate_bracket_1():
    # Taxable income <= 60M (5%)
    # Total income = 58.5M + 10M = 68.5M
    income = Decimal("68500000")
    tax = IncomeCalculator.tax_estimate(income)
    # Taxable = 10M. Tax = 10M * 0.05 = 500k
    assert tax == Decimal("500000")

def test_tax_estimate_bracket_2():
    # Taxable income > 60M and <= 250M (15%)
    # Total income = 58.5M + 100M = 158.5M
    income = Decimal("158500000")
    tax = IncomeCalculator.tax_estimate(income)
    # Taxable = 100M.
    # Bracket 1 (60M): 3M
    # Bracket 2 (40M): 40M * 0.15 = 6M
    # Total = 9M
    assert tax == Decimal("9000000")

def test_tax_estimate_bracket_3():
    # Taxable income > 250M and <= 500M (25%)
    # Total income = 58.5M + 400M = 458.5M
    income = Decimal("458500000")
    tax = IncomeCalculator.tax_estimate(income)
    # Taxable = 400M
    # Bracket 1 (60M): 3M
    # Bracket 2 (190M): 190M * 0.15 = 28.5M
    # Bracket 3 (150M): 150M * 0.25 = 37.5M
    # Total = 3M + 28.5M + 37.5M = 69M
    assert tax == Decimal("69000000")
