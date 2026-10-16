#!/usr/bin/env python3
"""
tests/run_sandbox_cli.py
========================
Helper script to start the Finance Tracker CLI in a fully isolated sandboxed
testing environment. It ensures no real user transaction data or active
profile settings are read, modified, or corrupted during manual testing.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def main():
    parser = argparse.ArgumentParser(description="Run Finance Tracker CLI in Sandbox Mode.")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Wipe the sandbox data directory before launching to start with a fresh database."
    )
    args = parser.parse_args()

    sandbox_root = PROJECT_ROOT / "tests" / "sandbox_env"

    if args.clean and sandbox_root.exists():
        print(f"[*] Wiping existing sandbox at: {sandbox_root}")
        # Retrying to handle lock issues in Windows
        for _ in range(3):
            try:
                shutil.rmtree(sandbox_root)
                break
            except Exception:
                import time
                time.sleep(0.5)
        else:
            print("[!] Warning: Could not clean some files in the sandbox directory (possibly locked).")

    # Create sandbox directories
    sandbox_root.mkdir(parents=True, exist_ok=True)
    (sandbox_root / "data").mkdir(exist_ok=True)
    (sandbox_root / "logs").mkdir(exist_ok=True)
    (sandbox_root / "apps" / "cli").mkdir(parents=True, exist_ok=True)

    # Copy base .env if present, so we have configuration settings
    real_env = PROJECT_ROOT / ".env"
    sandbox_env_file = sandbox_root / ".env"
    if real_env.exists() and not sandbox_env_file.exists():
        print("[*] Copying configuration schema from project root .env to sandbox...")
        shutil.copy2(real_env, sandbox_env_file)

    # Set environment variables for isolation
    env = os.environ.copy()
    env["FINANCE_ROOT_OVERRIDE"] = str(sandbox_root)
    # Clear FINANCE_DATA_ROOT to ensure we don't accidentally leak
    env.pop("FINANCE_DATA_ROOT", None)

    print("=" * 60)
    print("       FINANCE TRACKER - SANDBOX CLI TESTING ENVIRONMENT")
    print("=" * 60)
    print(f"  Sandbox Directory : {sandbox_root}")
    print("  Isolation Level   : FULL (All SQLite databases are redirected)")
    print("  Active Profile    : Stored under sandbox/data/active_profile.txt")
    print("  Status            : SAFE TO TEST (Real data remains untouched)")
    print("-" * 60)
    print("[*] Launching CLI...")

    cli_entry = PROJECT_ROOT / "apps" / "cli" / "main.py"

    try:
        import subprocess
        subprocess.run([sys.executable, str(cli_entry)], env=env, check=True)
    except KeyboardInterrupt:
        print("\n[*] Sandbox session closed by user.")
    except Exception as e:
        print(f"\n[!] Error running sandbox CLI: {e}")

if __name__ == "__main__":
    main()
