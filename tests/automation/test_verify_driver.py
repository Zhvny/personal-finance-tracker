def test_cli_exit(cli_driver):
    # Input 0 to exit CLI
    output = cli_driver.run(["0"])
    assert "Exiting" in output or "Goodbye" in output or "0" in output
