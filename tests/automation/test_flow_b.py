"""Flow B: Investment FIFO (isolated SQLite).

Runs on the disposable SQLite path via the shared ``cli_driver`` fixture
(FINANCE_DATA_ROOT=<tmp> + ALPHA_FORCE_SQLITE=1). No ensure_profile /
reset_profile_tables / REAL-root pinning.
"""


def test_flow_b_fifo_isolated(cli_driver):
    # ── Buy Lot 1: 10 TEST_B @ 100 USD (1=INVEST, 1=QUICK_ADD, 2=CRYPTO) ──
    out1 = cli_driver.run(["1", "1", "2", "TEST_B", "10", "100", "2", "", "y", "n", "y"])
    assert "TEST_B" in out1

    # ── Buy Lot 2: 10 TEST_B @ 120 USD ──
    out2 = cli_driver.run(["1", "1", "2", "TEST_B", "10", "120", "2", "", "y", "n", "y"])
    assert "TEST_B" in out2

    # ── View Portfolio to verify both lots ──
    out_port = cli_driver.run(["1", "3"])
    assert "TEST_B" in out_port

    # ── Sell 15 units @ 150 USD (FIFO) ──
    out_sell = cli_driver.run(["1", "7", "1", "15", "150", "2", "", "0"])
    assert "SELL EXECUTED" in out_sell.upper()
    # SQLite path renders positive P/L as "Rp+..." (same as live path).
    assert "Rp+" in out_sell

    # ── Realized P/L report ──
    out_rpt = cli_driver.run(["1", "8"])
    assert "TEST_B" in out_rpt
    assert "Rp+" in out_rpt

    # ── Remaining position (5 units @ 120) ──
    out_final = cli_driver.run(["1", "3"])
    assert any(x in out_final for x in ["5.0000", "│   5 │", "│  5 │", "│ 5 │"])
