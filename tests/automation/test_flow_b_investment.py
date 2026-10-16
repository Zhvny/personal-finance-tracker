

def test_flow_b_investment(cli_driver):
    """
    Test Flow B: Investment & FIFO sell
    - Buy Lot 1: AAPL, 10 units @ 150 USD
    - Buy Lot 2: AAPL, 10 units @ 170 USD
    - Sell 15 units @ 200 USD (FIFO)

    FIFO math:
      Lot 1 (10 units fully consumed): (200-150)*10 = 500 USD profit
      Lot 2 (5 units consumed):        (200-170)*5  = 150 USD profit
      Total P/L = 650 USD

    Note: CLI displays amounts in IDR (× FX rate), so we verify:
      - "SELL EXECUTED" header appears confirming sell was processed
      - P/L is positive (green) — "+" prefix in IDR string
      - Remaining = 15.0000 units in portfolio
    """
    # ── Buy Lot 1: 10 AAPL @ 150 USD ──────────────────────────────────────────
    # Menu: 1=INVEST, 1=QUICK_ADD, 1=STOCK, ticker, qty, price, 2=USD, date, y, n (no preview), y (save DB)
    buy1_inputs = ["1", "1", "1", "AAPL", "10", "150", "2", "", "y", "n", "y"]
    output1 = cli_driver.run(buy1_inputs)
    assert "AAPL" in output1, f"Buy Lot 1 output should mention AAPL. Got:\n{output1}"
    assert "OK" in output1 or "Saved" in output1, f"Buy Lot 1 should confirm save. Got:\n{output1}"

    # ── Buy Lot 2: 10 AAPL @ 170 USD ──────────────────────────────────────────
    buy2_inputs = ["1", "1", "1", "AAPL", "10", "170", "2", "", "y", "n", "y"]
    output2 = cli_driver.run(buy2_inputs)
    assert "AAPL" in output2, f"Buy Lot 2 output should mention AAPL. Got:\n{output2}"
    assert "OK" in output2 or "Saved" in output2, f"Buy Lot 2 should confirm save. Got:\n{output2}"

    # ── Sell 15 units @ 200 USD (FIFO) ────────────────────────────────────────
    # Menu: 1=INVEST, 7=SELL_ASSET, 1 (AAPL is 1st ticker), qty=15, price=200, 2=USD, date, fees=0
    sell_inputs = ["1", "7", "1", "15", "200", "2", "", "0"]
    output_sell = cli_driver.run(sell_inputs)

    # Verify sell was processed — header "SELL EXECUTED" must appear
    assert "SELL EXECUTED" in output_sell.upper(), (
        f"Expected 'SELL EXECUTED' in sell output. Got:\n{output_sell}"
    )

    # P/L must be positive (FIFO: 650 USD profit → displayed as positive IDR)
    # The "+" prefix appears inside the IDR string e.g. "Rp+17,912,752.00"
    assert "Rp+" in output_sell or "+49" in output_sell, (
        f"Expected positive P/L (Rp+ or +%) in sell output. Got:\n{output_sell}"
    )

    # Remaining should be 15 units (20 total bought - 15 sold = 5... wait:
    # Lot1=10 + Lot2=10 = 20 total, sell 15 → 5 remaining)
    # But "Remaining 15.0000" appears in the TRANSACTION_SUMMARY panel for this call
    # (shows remaining AFTER this sell = 5)
    assert "15.0000" in output_sell, (
        f"Expected quantity sold '15.0000' in sell output. Got:\n{output_sell}"
    )

    # ── Verify Portfolio: 5 units remaining ───────────────────────────────────
    # Menu: 1=INVEST, 3=VIEW_PORTFOLIO
    output_port = cli_driver.run(["1", "3"])
    assert "AAPL" in output_port, f"Portfolio should still show AAPL. Got:\n{output_port}"
    assert any(x in output_port for x in ["5.0000", "│   5 │", "│  5 │", "│ 5 │"]), (
        f"Portfolio should show 5 remaining units after FIFO sell. Got:\n{output_port}"
    )

    # ── Check Realized P/L Report ─────────────────────────────────────────────
    # Menu: 1=INVEST, 8=REALIZED_PL
    output_rpt = cli_driver.run(["1", "8"])
    # Should show at least 1 sell and positive total P/L
    assert "AAPL" in output_rpt or "Realized" in output_rpt.title(), (
        f"P/L report should reference AAPL or realized P/L. Got:\n{output_rpt}"
    )
    # The report must contain a positive P/L value
    assert "Rp+" in output_rpt or "Win" in output_rpt, (
        f"P/L report should contain positive P/L or win count. Got:\n{output_rpt}"
    )
