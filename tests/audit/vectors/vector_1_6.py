import os
import sys

from harness import AuditHarness, BaseAuditVector


class AuditVector_1_6(BaseAuditVector):
    """
    Failure Vector 1.6: Atomic PID Management
    Verify that scheduler detects and overwrites stale PID files.
    """
    def setup(self):
        self.root = AuditHarness.get_canonical_root()
        self.scheduler_py = AuditHarness.resolve_script_path("apps/cli/scheduler.py")

        # Inject root into sys.path to get Config
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))

        from packages.core.infrastructure.config import Config
        self.pid_file = (Config.BASE_DIR / "logs" / "scheduler.pid").resolve()
        self.log(f"Target PID file: {self.pid_file}")

    def reproduce(self):
        # 1. Create a stale PID file with a non-existent PID
        # We'll use a very high PID that is unlikely to exist or just pick one and verify is_running is false
        stale_pid = 99999
        try:
            os.kill(stale_pid, 0)
            # If it exists, try another one
            stale_pid = 99998
        except OSError:
            pass

        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.pid_file, 'w') as f:
            f.write(str(stale_pid))
        self.log(f"Created stale PID file with PID {stale_pid}")

        # 2. Run scheduler
        self.log("Running scheduler with stale PID file...")
        result = self.run_command(
            [sys.executable, str(self.scheduler_py)]
        )
        self.stdout = result.stdout
        self.returncode = result.returncode
        self.log(f"Output: {self.stdout}")

    def validate(self) -> bool:
        # DoD: Scheduler detects stale PID/Lock; overwrites and starts.
        return "Detected stale PID file" in self.stdout and self.returncode == 0

    def teardown(self):
        if hasattr(self, 'pid_file') and self.pid_file.exists():
            try: self.pid_file.unlink()
            except: pass
