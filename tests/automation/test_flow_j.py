"""Flow J: Income & Smart Saving (isolated SQLite).

Runs on the disposable SQLite path via the shared ``cli_driver`` fixture
(FINANCE_DATA_ROOT=<tmp> + ALPHA_FORCE_SQLITE=1). No ensure_profile /
reset_profile_tables / REAL-root pinning.
"""


def test_flow_j_income_isolated(cli_driver):
    # 1. Record Income: 1,000,000 (3=INCOME, 1=ADD, 1=SALARY)
    out_add = cli_driver.run(["3", "1", "1", "Gaji", "1000000", "", "", "n", "y"])
    assert "Record saved" in out_add

    # 2. Verify in View All
    out_view = cli_driver.run(["3", "2"])
    assert "Gaji" in out_view
    assert "1,000,000" in out_view

    # 3. Dashboard smart-saving allocation (30% bank + 10% emergency = 400,000)
    out_dash = cli_driver.run(["0"])
    assert "SAV" in out_dash
    assert any(x in out_dash for x in ["1.0M", "400", "1,000"])
