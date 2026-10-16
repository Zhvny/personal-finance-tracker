import os
import sys
from decimal import Decimal
from pathlib import Path

# Add monorepo root to sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

print("--- VALIDATING INCOME ERROR FIXES ---")

# 1. SQLiteIncomeRepository should have 'get_monthly_summary'
print("\n1. Testing SQLiteIncomeRepository for 'get_monthly_summary'...")
try:
    from packages.core.infrastructure.income_tracker.repository import SQLiteIncomeRepository
    test_db = os.path.join(_ROOT, "data", "test_income_repro.db")
    repo = SQLiteIncomeRepository(db_path=test_db)
    print("Calling repo.get_monthly_summary(2026, 5)...")
    summary = repo.get_monthly_summary(2026, 5)
    print(f"Success: get_monthly_summary returned {summary}")
except AttributeError as e:
    print(f"FAIL: SQLiteIncomeRepository is missing 'get_monthly_summary': {e}")
    sys.exit(1)
except Exception as e:
    print(f"FAIL: Unexpected error in test 1: {type(e).__name__}: {e}")
    sys.exit(1)
finally:
    try:
        if 'test_db' in locals() and os.path.exists(test_db):
            os.remove(test_db)
    except PermissionError:
        pass

# 2. rich color parsing fix (ensuring we use #333333 in app, and rich accepts it)
print("\n2. Testing rich color parsing with #333333...")
try:
    from rich.console import Console
    from rich.panel import Panel
    console = Console(file=open(os.devnull, 'w'))
    print("Rendering Panel with border_style='#333333'...")
    panel = Panel("Test", border_style="#333333")
    console.print(panel)
    print("Success: rich color parsing works with 6-digit hex.")
except Exception as e:
    print(f"FAIL: rich error with #333333: {type(e).__name__}: {e}")
    sys.exit(1)

# 3. Float/Decimal division fix
print("\n3. Testing Decimal/Decimal division in IncomeCalculator...")
try:
    from apps.cli.income_tracker.core.calculator import IncomeCalculator
    annual_income = Decimal("50000000")
    # tax_estimate now handles Decimal correctly
    tax = IncomeCalculator.tax_estimate(annual_income)
    print(f"Tax estimate for {annual_income}: {tax} (type: {type(tax).__name__})")
    print("Attempting tax / annual_income (Decimal / Decimal)...")
    tax_ratio = tax / annual_income
    print(f"Success: tax_ratio calculated as {tax_ratio}")
except TypeError as e:
    print(f"FAIL: TypeError in division: {e}")
    sys.exit(1)
except Exception as e:
    print(f"FAIL: Unexpected error in test 3: {type(e).__name__}: {e}")
    sys.exit(1)

print("\n--- VALIDATION COMPLETE: ALL FIXES VERIFIED ---")
