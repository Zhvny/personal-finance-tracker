import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class CLIRunner:
    """
    Wraps subprocess.Popen to interact with the Finance Tracker CLI.
    Handles sending inputs, capturing output, and logging.
    """
    def __init__(self, monorepo_root: Path, cli_path: Path, scenario_name: str,
                 env_overrides: Optional[Dict[str, str]] = None):
        self.monorepo_root = monorepo_root
        self.cli_path = cli_path
        self.scenario_name = scenario_name
        # Extra env vars applied on top of os.environ when spawning the CLI.
        # Used by e2e flow tests to pin FINANCE_ROOT_OVERRIDE to the real repo
        # root: tests/conftest.py injects a per-test sandbox override whose
        # data/ dir has no active_profile.txt, so the CLI would silently fall
        # back to the 'personal' Postgres schema (real user data) instead of
        # the profile under test.
        self.env_overrides = env_overrides or {}
        self.log_dir = monorepo_root / "tests" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"{scenario_name.replace(' ', '_').lower()}.log"

        self.stdout = ""
        self.stderr = ""

        # Setup logging for this runner instance
        self.logger = logging.getLogger(f"CLIRunner.{scenario_name}")
        self.logger.setLevel(logging.DEBUG)
        # Clear existing handlers
        self.logger.handlers = []
        fh = logging.FileHandler(self.log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(fh)

    def run(self, inputs: List[str], timeout: int = 60) -> Tuple[str, str]:
        """
        Executes the CLI with the provided inputs.
        """
        self.logger.info(f"Starting CLI Flow: {self.scenario_name}")
        self.logger.info(f"Inputs: {inputs}")

        # Use sys.executable to run with the active interpreter
        python_exe = sys.executable
        cmd = [python_exe, "-u", str(self.cli_path)]

        env = {
            **os.environ,
            "PYTHONPATH": str(self.monorepo_root),
            "PYTHONIOENCODING": "utf-8",
            "TERM": "xterm-256color"
        }
        if self.env_overrides:
            env.update(self.env_overrides)

        # Join inputs with newlines and add exit sequence
        # CLI often needs multiple '0's to exit nested menus
        full_input = "\n".join(inputs) + "\n0\n0\n0\n0\n"

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
            shell=False
        )

        try:
            self.stdout, self.stderr = process.communicate(input=full_input, timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            self.stdout, self.stderr = process.communicate()
            self.logger.error(f"Flow TIMEOUT after {timeout}s")
            print(f"[ERROR] Flow {self.scenario_name} TIMEOUT after {timeout}s")

        def safe_log(text):
            if text:
                return text.encode('ascii', errors='replace').decode('ascii')
            return ""

        self.logger.debug("--- STDOUT ---")
        self.logger.debug(safe_log(self.stdout))
        self.logger.debug("--- STDERR ---")
        self.logger.debug(safe_log(self.stderr))

        if self.stderr and "Error" in self.stderr:
            self.logger.warning("Errors found in STDERR")

        return self.stdout, self.stderr

    def verify_output(self, patterns: List[str]) -> bool:
        """
        Verifies if the provided regex patterns are found in the captured STDOUT.
        """
        success = True
        for pattern in patterns:
            match = re.search(pattern, self.stdout, re.IGNORECASE | re.DOTALL)
            if match:
                self.logger.info(f"VERIFIED: Pattern '{pattern}' found.")
                print(f"[OK] Verified: '{pattern}'")
            else:
                self.logger.error(f"FAILED: Pattern '{pattern}' not found.")
                print(f"[FAIL] Pattern '{pattern}' not found.")
                success = False
        return success

def ensure_profile(profile_name: str, monorepo_root: Path, cli_path: Path) -> bool:
    """
    Ensures a QA profile exists in profiles.json and sets it as the active profile.

    Strategy:
    1. Try ``profile set <name>`` — succeeds if the profile already exists.
    2. If stdout contains '[red]Error[/red]' (profile unknown), run ``profile add <name>``
       to register it, then ``profile set <name>`` again.
    3. Validate by checking stdout for 'Success'.
    """
    print(f"[INFO] Ensuring profile '{profile_name}'...")
    python_exe = sys.executable
    env = {**os.environ, "PYTHONPATH": str(monorepo_root)}

    def _run(action: str, name: str) -> subprocess.CompletedProcess:
        cmd = [python_exe, str(cli_path), "profile", action, name]
        return subprocess.run(cmd, capture_output=True, text=True, env=env, shell=False)

    # --- Step 1: try to set the active profile ---
    res_set = _run("set", profile_name)
    combined = (res_set.stdout + res_set.stderr).upper()

    if "SUCCESS" in combined and "ERROR" not in combined:
        print(f"[OK] Profile '{profile_name}' is now active.")
        return True

    # --- Step 2: profile likely doesn't exist — add it ---
    print(f"[INFO] Profile '{profile_name}' not found. Creating via 'profile add'...")
    res_add = _run("add", profile_name)
    combined_add = (res_add.stdout + res_add.stderr).upper()

    # 'already exists' is acceptable (profile was created by a previous run)
    if "ERROR" in combined_add and "ALREADY EXISTS" not in combined_add:
        print(f"[ERROR] Failed to add profile '{profile_name}': {res_add.stdout.strip()}")
        return False

    # --- Step 3: set it again now that it exists ---
    res_set2 = _run("set", profile_name)
    combined2 = (res_set2.stdout + res_set2.stderr).upper()

    if "SUCCESS" in combined2 and "ERROR" not in combined2:
        print(f"[OK] Profile '{profile_name}' created and is now active.")
        return True

    print(f"[ERROR] Failed to ensure profile '{profile_name}': {res_set2.stdout.strip()}")
    return False

def reset_profile_tables(profile_name: str, monorepo_root: Path) -> bool:
    """
    Purge transactional rows from the profile's Postgres schema so e2e flow
    tests are idempotent across runs (expense/income totals accumulate otherwise).
    Only touches tables inside schema ``<profile_name>`` — never other profiles.
    Missing tables are skipped; failures are logged, never raised.
    """
    if not re.match(r"^[a-zA-Z0-9_]+$", profile_name):
        print(f"[ERROR] Invalid profile name for reset: {profile_name!r}")
        return False

    print(f"[INFO] Purging transactional data from schema '{profile_name}'...")
    try:
        repo_root = str(monorepo_root)
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager

        # Child tables first (FK-safe order): sell_transactions -> investments
        ordered_tables = ["sell_transactions", "investments", "expenses", "incomes"]

        with DatabaseManager.get_connection(schema=profile_name) as conn:
            with conn.cursor() as cur:
                # Resolve actual table names in THIS schema; skip anything absent
                cur.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
                    (profile_name,),
                )
                existing = {row[0] for row in cur.fetchall()}
                targets = [t for t in ordered_tables if t in existing]
                for t in targets:
                    cur.execute(f"DELETE FROM {profile_name}.{t}")
                    print(f"[OK] Purged {profile_name}.{t} ({cur.rowcount} rows)")
            conn.commit()
        return True
    except Exception as exc:
        print(f"[WARN] Skipped data purge for '{profile_name}': {exc}")
        return False


if __name__ == "__main__":
    # Self-test if run directly
    ROOT = Path(__file__).resolve().parent.parent.parent
    CLI = ROOT / "apps" / "cli" / "main.py"

    print(f"Monorepo Root: {ROOT}")
    print(f"CLI Path: {CLI}")

    if not CLI.exists():
        print("ERROR: CLI path not found.")
        sys.exit(1)

    # Test version/help
    python_exe = sys.executable
    res = subprocess.run([python_exe, str(CLI), "--help"], capture_output=True, text=True, shell=False)
    if res.returncode == 0:
        print("[OK] CLI is executable.")
    else:
        print(f"[FAIL] CLI execution failed: {res.stderr}")
