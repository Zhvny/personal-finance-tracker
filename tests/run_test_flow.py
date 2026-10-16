import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# Finance Tracker QA Automation Utility (Phase 2)
# ---------------------------------------------
# This script automates interaction with apps/cli/main.py using integer-based inputs.
# Specifically designed for exhaustive QA of core financial flows.

MONOREPO_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = MONOREPO_ROOT / "apps" / "cli" / "main.py"
LOG_DIR = MONOREPO_ROOT / "tests" / "logs"

def run_flow(name, inputs, timeout=60):
    print(f"\n[QA] Running Flow: {name}")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{name.replace(' ', '_').lower()}.log"

    cmd = f'python -u "{CLI_PATH}"'

    # Environment Setup
    env = {
        **os.environ,
        "PYTHONPATH": str(MONOREPO_ROOT),
        "PYTHONIOENCODING": "utf-8",
        "TERM": "xterm-256color"
    }

    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
        shell=True,
        env=env
    )

    # We append '0' twice to ensure we exit any sub-menus and then the main menu
    full_input = "\n".join(inputs) + "\n0\n0\n0\n"
    stdout, stderr = "", ""

    try:
        stdout, stderr = process.communicate(input=full_input, timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        print(f"[QA] Flow {name} TIMEOUT after {timeout}s")

    # Save full output to log file
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("--- STDOUT ---\n")
        f.write(stdout)
        f.write("\n--- STDERR ---\n")
        f.write(stderr)

    lines = stdout.splitlines()
    print(f"[QA] Captured {len(lines)} output lines. Full log: {log_file.name}")

    if stderr and "Error" in stderr:
        print("[QA] ERRORS captured in stderr")

    return stdout, stderr

def verify_success(stdout, patterns):
    """Checks if specified patterns (regex) are present in stdout."""
    results = []
    for p in patterns:
        match = re.search(p, stdout, re.IGNORECASE | re.DOTALL)
        results.append(bool(match))
        if not match:
            print(f"[QA] VERIFICATION FAILED: Pattern '{p}' not found.")
        else:
            print(f"[QA] VERIFIED: '{p}'")
    return all(results)

def setup_profile(profile_name):
    """Ensure the profile is set correctly before running flows."""
    print(f"[QA] Setting profile to {profile_name}...")
    cmd = [sys.executable, str(CLI_PATH), "profile", "set", profile_name]
    subprocess.run(cmd, check=True, env={**os.environ, "PYTHONPATH": str(MONOREPO_ROOT)})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--flow", help="Flows to run (A,B,C,J)", default="A,B,C,J")
    parser.add_argument("--profile", help="Profile to use", default="QA_FINANCIAL")
    args = parser.parse_args()

    target_flows = [f.strip().upper() for f in args.flow.split(",")]

    # Ensure starting from a clean target profile
    setup_profile(args.profile)

    # -------------------------------------------------------------------------
    # Flow A: Profile Creation & Isolation
    # -------------------------------------------------------------------------
    if "A" in target_flows:
        # A.1 Check available profiles (8)
        # A.2 Switch to personal (8 -> 1)
        # A.3 Switch back to QA_FINANCIAL (8 -> 3) - assuming QA_FINANCIAL is 3rd
        inputs = [
            "8", "1", # Switch to Personal
            "8", "3", # Switch to QA_FINANCIAL
        ]
        res_a, _ = run_flow("Flow A", inputs)
        verify_success(res_a, [
            "Switched to PERSONAL",
            "Switched to QA_FINANCIAL",
            "QA_FINANCIAL OVERVIEW"
        ])

    # -------------------------------------------------------------------------
    # Flow B: Investment (Buy, Sync, FIFO Sell)
    # -------------------------------------------------------------------------
    if "B" in target_flows:
        # B.1 Buy AAPL Lot 1 (1 -> 1 -> AAPL -> us -> 150 -> 10 -> [Enter for today] -> [Desc] -> n -> y)
        # Note: input for date is Enter, description is Enter, chart preview is n, save is y
        # B.2 Buy AAPL Lot 2 (1 -> 1 -> AAPL -> us -> 170 -> 10 -> [Enter] -> [Enter] -> n -> y)
        # B.3 Portfolio View (1 -> 3) - triggers price sync simulation
        # B.4 FIFO Sell (1 -> 7 -> 1 (assuming AAPL is 1st) -> 15 -> 200 -> [Enter] -> [Enter] -> y)
        # B.5 Check Realized P/L (1 -> 8)
        inputs = [
            "1", "1", "AAPL", "us", "150", "10", "", "", "n", "y", # Buy 1
            "1", "1", "AAPL", "us", "170", "10", "", "", "n", "y", # Buy 2
            "1", "3", # View Portfolio (Sync)
            "1", "7", "1", "15", "200", "", "", "y", # Sell 15 units
            "1", "8"  # View Realized
        ]
        res_b, _ = run_flow("Flow B", inputs)
        verify_success(res_b, [
            "Saved! ID:",
            "Fetching latest market prices",
            "Realized P/L",
            "AAPL",
            "FIFO SELL CONFIRMATION"
        ])

    # -------------------------------------------------------------------------
    # Flow C: Expense & Filter
    # -------------------------------------------------------------------------
    if "C" in target_flows:
        # C.1 Add Expense 1 (2 -> 1 -> 100000 -> Lunch (QA) (test) -> 2 (Makan) -> 1 (Cash) -> [Enter] -> n -> y)
        # C.2 Add Expense 2 (2 -> 1 -> 50000 -> Coffee (QA) (test) -> 1 (Lifestyle) -> 1 (Cash) -> [Enter] -> n -> y)
        # C.3 Filter by Category (2 -> 4 -> 2)
        inputs = [
            "2", "1", "100000", "Lunch (QA) (test)", "2", "1", "", "n", "y",
            "2", "1", "50000", "Coffee (QA) (test)", "1", "1", "", "n", "y",
            "2", "4", "2" # Filter Category 2 (Makan/Food)
        ]
        res_c, _ = run_flow("Flow C", inputs)
        verify_success(res_c, [
            "Record saved",
            "LUNCH (QA) (test)",
            "CATEGORY_VIEW",
            "MAKAN"
        ])

    # -------------------------------------------------------------------------
    # Flow J: Income & Smart Saving
    # -------------------------------------------------------------------------
    if "J" in target_flows:
        # J.1 Record Income (3 -> 1 -> 1 (Salary) -> Gaji Utama (QA) (test) -> 10000000 -> [Enter] -> [Enter] -> n -> y)
        # J.2 Check Dashboard for Savings (Automatic after exit sub-menu)
        inputs = [
            "3", "1", "1", "Gaji Utama (QA) (test)", "10,000,000", "", "", "n", "y",
            "0" # Back to dashboard
        ]
        res_j, _ = run_flow("Flow J", inputs)

        # Smart Saving for 10M (30% bank_savings + 10% emergency_fund = 40% = 4M)
        verify_success(res_j, [
            "Record saved",
            "ALLOCATION_COMPLETE",
            "SAV.*4.0M" # Verify Savings total on dashboard (40% of 10M)
        ])

    print("\n[QA] ALL SELECTED FLOWS COMPLETED.")

if __name__ == "__main__":
    main()
