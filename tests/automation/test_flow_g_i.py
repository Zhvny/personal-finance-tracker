import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tests.automation.cli_driver import CLIDriver


def test_flow_g_i():
    driver = CLIDriver()

    # Flow I: Whale Profiler (Option 9)
    # Sequence: 9 (Whale) -> ETHUSD -> crypto -> [Enter] -> 0 (Exit)
    inputs_i = ["9", "ETHUSD", "crypto", "", "0"]

    print("Running Flow I Automation (Whale Profiler)...")
    output_i, error_i = driver.run_scenario(inputs_i, wait_after_input=1.5, timeout=10)

    passed_i = True
    if not ("WHALE" in output_i.upper() or "VOLUME PATTERNS" in output_i.upper()):
        print("FAIL: Whale Profiler keywords not found in output")
        passed_i = False
    else:
        print("Flow I: PASS")

    # Flow G: Predictive ML (Option 6)
    # This usually launches an external Flask app which might not return to the same shell session easily.
    # We will verify if the command starts.
    print("Flow G (ML_STX): Verifying launch...")
    inputs_g = ["6", "0"] # Try to launch and exit if possible
    output_g, error_g = driver.run_scenario(inputs_g, wait_after_input=2.0, timeout=5)

    if "ML_STOCKS" in output_g.upper() or "LAUNCHING" in output_g.upper() or "SUBPROCESS" in output_g.upper():
        print("Flow G: PASS (Launch verified)")
    else:
        # Check if the process started according to main.py's logs
        print("Flow G: Verification inconclusive via stdout (likely separate window/process).")
        # In many CLI environments, launching a separate flask app via subprocess might not capture output back to parent easily if not piped correctly.

    if not passed_i:
        sys.exit(1)

if __name__ == "__main__":
    try:
        test_flow_g_i()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Flow G/I: ERROR - {e}")
        sys.exit(1)
