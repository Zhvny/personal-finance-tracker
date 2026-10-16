
def test_probe_income_output(cli_driver):
    inputs = [
        "3", "1", "2", "Freelance", "5000", "", "Project Alpha", "n", "y", "", "2", "", "0", "", "0"
    ]
    output = cli_driver.run(inputs)
    print("\n--- OUTPUT START ---")
    print(output)
    print("--- OUTPUT END ---")
    assert "5,000" in output
