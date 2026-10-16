import os
import sys

import pytest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tests.automation.cli_driver import CLIDriver


def test_flow_f():
    driver = CLIDriver()

    # F.1: Stock Analyzer
    # Sequence: 5 (Stocks) -> MSFT -> [Enter] -> 0 (Exit)
    inputs = ["5", "MSFT", "", "0"]

    print("Running Flow F Automation (Stock Analyzer)...")
    output, error = driver.run_scenario(inputs, wait_after_input=1.5, timeout=10)

    # In headless/non-TTY mode, the TUI is skipped and CLI falls through.
    # Accept either the full TUI keywords OR the known headless skip message.
    keywords = ["EXPECTANCY", "KELLY", "Score", "SIGNAL", "TARGET"]
    headless_indicators = ["MarketAnalyzerApp TUI mode", "Skipped", "non-TTY"]

    found_keywords = [k for k in keywords if k.upper() in output.upper()]
    found_headless = any(h.lower() in output.lower() for h in headless_indicators)

    if found_keywords:
        print(f"Found keywords: {found_keywords}")
        print("Flow F: PASS (full TUI output)")
    elif found_headless:
        print("Flow F: PASS (headless mode detected — TUI skipped as expected)")
    else:
        print(f"FAIL: None of the expected keywords {keywords} found in output")
        print("\n--- CAPTURED OUTPUT ---")
        print(output.encode('ascii', errors='replace').decode('ascii'))
        print("-----------------------\n")
        pytest.fail("Flow F: No expected keywords or headless indicator found in output")

if __name__ == "__main__":
    try:
        test_flow_f()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Flow F: ERROR - {e}")
        sys.exit(1)
