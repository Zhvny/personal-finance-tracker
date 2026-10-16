import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from harness import AuditHarness, BaseAuditVector


class AuditVector_1_9(BaseAuditVector):
    """
    Failure Vector 1.9: Permission Integrity
    Verify that check_perms.py correctly identifies missing write permissions.
    """
    def setup(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.script_path = AuditHarness.resolve_script_path("scripts/check_perms.py")

        # Create a mock structure inside temp_dir
        self.mock_root = self.temp_dir / "mock_root"
        self.mock_root.mkdir()
        (self.mock_root / "apps").mkdir()
        (self.mock_root / "data").mkdir()
        (self.mock_root / "logs").mkdir()

        # Place a copy of the script in mock_root/scripts/
        (self.mock_root / "scripts").mkdir()
        self.mock_script = self.mock_root / "scripts" / "check_perms.py"
        shutil.copy(self.script_path, self.mock_script)

    def reproduce(self):
        # 1. Test Success
        self.log("Testing success case...")
        res_success = self.run_command([sys.executable, str(self.mock_script)])
        self.success_passed = (res_success.returncode == 0)
        self.log(f"Success output: {res_success.stdout.strip()}")

        # 2. Test Failure (restricted permission)
        self.log("Testing failure case (read-only dir)...")
        data_dir = self.mock_root / "data"

        # On Windows, we use icacls to deny write.
        # We use the current username to be sure it applies to us.
        username = os.environ.get('USERNAME', 'Everyone')
        if sys.platform == 'win32':
            subprocess.run(['icacls', str(data_dir), '/deny', f'{username}:(W)'], capture_output=True)
        else:
            os.chmod(data_dir, 0o555)

        res_failure = self.run_command([sys.executable, str(self.mock_script)])
        self.failure_detected = (res_failure.returncode != 0)
        self.failure_msg = res_failure.stdout.strip()

        # Cleanup permissions so we can delete the temp dir
        if sys.platform == 'win32':
            subprocess.run(['icacls', str(data_dir), '/grant', f'{username}:(F)'], capture_output=True)
            # Sometimes icacls /remove is better to get rid of denys
            subprocess.run(['icacls', str(data_dir), '/remove:d', username], capture_output=True)
        else:
            os.chmod(data_dir, 0o777)

    def validate(self) -> bool:
        self.log(f"Success passed: {self.success_passed}")
        self.log(f"Failure detected: {self.failure_detected}")
        if self.failure_detected:
            self.log(f"Failure message: {self.failure_msg}")

        # Note: icacls might fail depending on environment, so if failure_detected is false,
        # we still count as "pass" if Success passed on a real system,
        # but for the audit we want strict verification.
        return self.success_passed and self.failure_detected

    def teardown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
