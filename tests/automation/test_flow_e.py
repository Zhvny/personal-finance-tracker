import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tests.automation.cli_driver import CLIDriver


def test_flow_e():
    driver = CLIDriver()

    # E.1: Sniper Advice
    # E.2: Agent Senate
    # E.3: Butterfly Map
    # Sequence: 1 (Invest) -> 5 (Sniper) -> BTCUSD -> crypto -> [Enter] ->
    #          10 (Senate) -> AAPL -> us -> [Enter] ->
    #          11 (Butterfly) -> TSLA -> us -> [Enter] -> 0 (Back) -> 0 (Exit)
    inputs = [
        "1", "5", "BTCUSD", "crypto", "",
        "10", "AAPL", "us", "",
        "11", "TSLA", "us", "",
        "0", "0"
    ]

    print("Running Flow E Automation (ML Sniper, Senate, Butterfly)...")
    output, error = driver.run_scenario(inputs, wait_after_input=1.2, timeout=15)

    passed = True
    output_upper = output.upper()

    # Verify Sniper
    if "NO ML MODEL" in output_upper:
        print("Sniper: SKIPPED (No Model)")
    elif "TARGET" in output_upper or "CONFIDENCE" in output_upper or "SNIPER" in output_upper:
        print("Sniper: PASS")
    else:
        print("FAIL: ML Sniper section not detected properly")
        passed = False

    # Verify Senate
    if "SENATE" in output_upper or "CONSENSUS" in output_upper or "VOTING" in output_upper:
        print("Senate: PASS")
    else:
        print("FAIL: Agent Senate keywords not found in output")
        passed = False

    # Verify Butterfly
    if "BUTTERFLY" in output_upper or "CORRELATION" in output_upper or "RISK" in output_upper:
        print("Butterfly: PASS")
    else:
        print("FAIL: Butterfly Analysis keywords not found in output")
        passed = False

    if passed:
        print("Flow E: PASS")
    else:
        sys.exit(1)

if __name__ == "__main__":
    try:
        test_flow_e()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Flow E: ERROR - {e}")
        sys.exit(1)
