import sys
from datetime import datetime

# Setup path to find the modules
project_root = r'C:\Users\Zhvn\Documents\Zhvny\Project\finance-tracker'
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from apps.cli.receipt_reader.core.categorizer import UniversalCategorizer
from apps.cli.receipt_reader.core.interfaces import IncomeCategory, Money, ReceiptData, TransactionType


def test_income_other_no_crash():
    categorizer = UniversalCategorizer()

    # Text that triggers income detection in _detect_transaction_type
    # but has no specific income category keywords in _classify_income
    raw_text = 'Diterima Berhasil'

    receipt = ReceiptData(
        merchant_name='Unknown Source',
        raw_ocr_text=raw_text,
        total_amount=Money(100000),
        transaction_date=datetime.now()
    )

    # Ensure it's detected as income first
    tx_type = categorizer._detect_transaction_type(receipt)
    assert tx_type == TransactionType.INCOME

    # Classify income - this is where the KeyError was happening
    result = categorizer._classify_income(receipt)

    print(f'Category: {result.category}')
    print(f'Reasoning: {result.reasoning}')

    assert result.category == IncomeCategory.OTHER
    assert 'Income detected: other' in result.reasoning

if __name__ == '__main__':
    try:
        test_income_other_no_crash()
        print('Test Passed!')
    except Exception as e:
        print(f'Test Failed: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
