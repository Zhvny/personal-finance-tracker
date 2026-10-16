"""Flow C: Expense & Budgeting (isolated SQLite).

Runs on the disposable SQLite path via the shared ``cli_driver`` fixture
(FINANCE_DATA_ROOT=<tmp> + ALPHA_FORCE_SQLITE=1). No ensure_profile /
reset_profile_tables / REAL-root pinning.
"""


def test_flow_c_expense_isolated(cli_driver):
    # 1. Add Expense: 200,000 to Food (2=EXPENSE, 1=ADD, 1=FOOD, 1=CASH)
    out_add = cli_driver.run(["2", "1", "1", "1", "Lunch", "200000", "", "n", "y"])
    assert "Record saved" in out_add

    # 2. View All to verify
    out_view = cli_driver.run(["2", "2"])
    assert "Lunch" in out_view
    assert "200,000" in out_view

    # 3. Monthly summary
    out_sum = cli_driver.run(["2", "3", "", ""])
    assert "TOTAL_SPENT" in out_sum.upper()
    assert "200,000" in out_sum


def test_flow_c_budget_isolated(cli_driver):
    out = cli_driver.run(["2", "5"])
    assert "Budget" in out
