from datetime import datetime
from decimal import Decimal

from packages.core.domain.models.expense import Expense, ExpenseCategory, PaymentMethod
from packages.core.domain.models.income import Income, IncomeType
from packages.core.domain.models.investment import Investment, SellTransaction


def test_decimal_precision_preservation():
    """
    Test if financial models can handle high-precision Decimals without silent float conversion.
    This test serves as a RED baseline to detect float usage in Pydantic models.
    """
    # 1. Expense
    amount = Decimal("123.456789")
    expense = Expense(
        amount=amount,
        description="Precision Test",
        category=ExpenseCategory.OTHER,
        payment_method=PaymentMethod.CASH,
        date=datetime.now()
    )
    # If the model uses float internally, this will fail or lose precision
    assert isinstance(expense.amount, Decimal), f"Expense amount should be Decimal, got {type(expense.amount)}"
    assert expense.amount == amount

    # 2. Income
    income = Income(
        amount=amount,
        source="Precision Test",
        income_type=IncomeType.OTHER,
        date=datetime.now()
    )
    assert isinstance(income.amount, Decimal), f"Income amount should be Decimal, got {type(income.amount)}"
    assert income.amount == amount

    # 3. Investment
    buy_price = Decimal("1500.85")
    quantity = Decimal("10.12345678")
    investment = Investment(
        asset_type="STOCK",
        ticker="AAPL",
        quantity=quantity,
        buy_price=buy_price,
        buy_currency="USD",
        buy_date=datetime.now()
    )
    assert isinstance(investment.quantity, Decimal), f"Investment quantity should be Decimal, got {type(investment.quantity)}"
    assert isinstance(investment.buy_price, Decimal), f"Investment buy_price should be Decimal, got {type(investment.buy_price)}"
    assert investment.quantity == quantity
    assert investment.buy_price == buy_price

def test_sell_transaction_precision():
    # 4. SellTransaction
    sell_price = Decimal("175.50")
    quantity = Decimal("5.5")
    fees = Decimal("0.25")
    sell = SellTransaction(
        sell_date=datetime.now(),
        quantity=quantity,
        sell_price=sell_price,
        fees=fees
    )
    assert isinstance(sell.quantity, Decimal)
    assert isinstance(sell.sell_price, Decimal)
    assert isinstance(sell.fees, Decimal)
