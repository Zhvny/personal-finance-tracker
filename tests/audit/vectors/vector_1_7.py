import sys

from harness import BaseAuditVector


class AuditVector_1_7(BaseAuditVector):
    """
    Failure Vector 1.7: Circular Import Break
    Verify that importing Config does not trigger circular dependency errors.
    """
    def setup(self):
        self.stdout = ""
        self.stderr = ""

    def reproduce(self):
        # We run it in a separate process to ensure a clean state
        # We use -c to just import it
        cmd = [sys.executable, "-c", "from packages.core.infrastructure.config import Config; print('SUCCESS')"]

        self.log(f"Running command: {' '.join(cmd)}")
        try:
            result = self.run_command(cmd)
            self.stdout = result.stdout
            self.stderr = result.stderr
            self.log(f"Stdout: {self.stdout.strip()}")
            if self.stderr:
                self.log(f"Stderr: {self.stderr.strip()}")
        except Exception as e:
            self.log(f"Execution failed: {e}")

    def validate(self) -> bool:
        # DoD: Zero ImportError or AttributeError during init.
        return "SUCCESS" in self.stdout and ("ImportError" not in self.stderr and "AttributeError" not in self.stderr)

    def teardown(self):
        pass
