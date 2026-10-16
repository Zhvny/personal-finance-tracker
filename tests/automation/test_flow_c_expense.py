
def test_add_expense_and_verify(cli_driver):
    """
    Task 4: Flow C (Expense & Budget) Implementation
    - Add expense: 100, category "Food", description "Test Coffee"
    - View summary
    - Verify "Test Coffee" and 100 appear
    - Verify budget progress bar
    """
    # 2: EXPENSE
    # 1: ADD_EXPENSE, 1: FOOD, 1: CASH, Test Coffee, 100, "", n (Recur), y (Save), "" (Pause)
    # 3: MONTHLY_STATS, "" (Year), "" (Month), "" (Pause)
    # 5: BUDGET_CHECK, "" (Pause)
    # 0: BACK
    # 0: EXIT
    inputs = [
        "2",
        "1", "1", "1", "Test Coffee", "100", "", "n", "y", "",
        "3", "", "", "",
        "5", "",
        "0", "0"
    ]

    output = cli_driver.run(inputs)

    # 1. Verify success message
    assert "Record saved" in output

    # 2. Verify "Test Coffee" and 100 appear in summary
    assert "Test Coffee" in output
    # Format might be Rp100 or 100
    assert "100" in output

    # 3. Verify budget progress bar is displayed
    # If stubbed, it shows "not fully implemented"
    # If implemented, it shows bars like ━ or ·
    assert "━" in output or "·" in output
    assert "BUDGET" in output.upper()
