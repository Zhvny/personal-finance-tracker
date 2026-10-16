
def test_flow_a_isolation(cli_driver):
    """
    Test Flow A: Profile Isolation
    - Switch to QA_PERSONAL
    - Add unique income entry
    - Switch to QA_BUSINESS
    - Verify isolation (personal data not visible)
    - Add unique business income
    - Switch back to QA_PERSONAL
    - Verify isolation (business data not visible, personal data present)
    """
    # 1. Switch to QA_PERSONAL
    # 8: PROFILE, 1: SWITCH, 3: QA_PERSONAL
    cli_driver.run(["8", "1", "3"])

    # 2. Add personal income
    # 3: INCOME, 1: ADD, 1: SALARY, IsolationTest_P, 7777, "", "", n, y
    cli_driver.run(["3", "1", "1", "IsolationTest_P", "7777", "", "", "n", "y"])

    # 3. Switch to QA_BUSINESS
    # 8: PROFILE, 1: SWITCH, 4: QA_BUSINESS
    cli_driver.run(["8", "1", "4"])

    # 4. Verify isolation
    # 3: INCOME, 2: VIEW ALL
    out_b = cli_driver.run(["3", "2"])
    assert "IsolationTest_P" not in out_b
    assert "7,777" not in out_b

    # 5. Add business income
    # 3: INCOME, 1: ADD, 1: SALARY, IsolationTest_B, 8888, "", "", n, y
    cli_driver.run(["3", "1", "1", "IsolationTest_B", "8888", "", "", "n", "y"])

    # 6. Switch back to QA_PERSONAL
    cli_driver.run(["8", "1", "3"])

    # 7. Final verification
    out_p = cli_driver.run(["3", "2"])
    assert "IsolationTest_P" in out_p
    assert "7,777" in out_p
    assert "IsolationTest_B" not in out_p
    assert "8,888" not in out_p
