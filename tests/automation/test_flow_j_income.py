
def test_flow_j_income(cli_driver):
    """
    Test Flow J: Income Management
    - Add income: 5000, source "Freelance", description "Project Alpha"
    - View history
    - Verify "Project Alpha" and 5000 appear
    """
    # 3: INCOME
    # 1: ADD_INCOME, 2: FREELANCE, Project Alpha, 5000, "", "", n (Taxed), y (Save)
    inputs = ["3", "1", "2", "Project Alpha", "5000", "", "", "n", "y"]
    cli_driver.run(inputs)

    # View History: 2: VIEW ALL
    output = cli_driver.run(["3", "2"])

    assert "Project Alpha" in output
    assert "5000" in output or "5,000" in output
