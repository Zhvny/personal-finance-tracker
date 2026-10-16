import os
import subprocess
import sys
import unittest
from pathlib import Path

from test_infrastructure import CLIRunner, ensure_profile


def _set_profile(profile_name: str, root: Path, cli: Path) -> bool:
    """Switch the active profile using the reliable CLI subcommand."""
    env = {**os.environ, "PYTHONPATH": str(root)}
    res = subprocess.run(
        [sys.executable, str(cli), "profile", "set", profile_name],
        capture_output=True, text=True, env=env, shell=False
    )
    combined = (res.stdout + res.stderr).upper()
    if "SUCCESS" in combined and "ERROR" not in combined:
        print(f"[OK] Profile '{profile_name}' is now active.")
        return True
    print(f"[FAIL] Could not switch to profile '{profile_name}': {res.stdout.strip()}")
    return False


class TestFlowA(unittest.TestCase):
    """
    Flow A: Profile & Isolation
    Verifies that data added to one profile is not visible in another.
    """

    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent.parent.parent
        cls.cli = cls.root / "apps" / "cli" / "main.py"

        if not ensure_profile("qa_personal", cls.root, cls.cli):
            raise RuntimeError("Failed to setup qa_personal profile")
        if not ensure_profile("qa_business", cls.root, cls.cli):
            raise RuntimeError("Failed to setup qa_business profile")
        if not ensure_profile("qa_financial", cls.root, cls.cli):
            raise RuntimeError("Failed to setup qa_financial profile")

    def test_profile_isolation(self):
        # 1. Switch to 'qa_personal' via reliable CLI subcommand
        self.assertTrue(
            _set_profile("qa_personal", self.root, self.cli),
            "Failed to switch to qa_personal profile"
        )

        # 2. Add unique income record to Personal
        unique_amount = "7777"
        unique_source = "A_ISOLATION_TEST"
        runner_add = CLIRunner(self.root, self.cli, "flow_a_step2_add_personal_data")
        runner_add.run(["3", "1", "1", unique_source, unique_amount, "", "", "n", "y"])
        self.assertTrue(runner_add.verify_output(["Record saved"]))

        # 3. Switch to 'qa_business' via reliable CLI subcommand
        self.assertTrue(
            _set_profile("qa_business", self.root, self.cli),
            "Failed to switch to qa_business profile"
        )

        # 4. Verify record NOT visible in Business income list
        runner_list_b = CLIRunner(self.root, self.cli, "flow_a_step4_verify_business_isolation")
        runner_list_b.run(["3", "2"])
        self.assertNotIn(unique_source, runner_list_b.stdout)
        self.assertNotIn(unique_amount, runner_list_b.stdout)

        # 5. Switch back to 'qa_personal' and verify the record still exists
        self.assertTrue(
            _set_profile("qa_personal", self.root, self.cli),
            "Failed to switch back to qa_personal profile"
        )

        runner_list_p = CLIRunner(self.root, self.cli, "flow_a_step6_personal_list_check")
        runner_list_p.run(["3", "2"])
        self.assertIn(unique_source, runner_list_p.stdout)
        self.assertIn("7,777", runner_list_p.stdout)


if __name__ == "__main__":
    unittest.main()

