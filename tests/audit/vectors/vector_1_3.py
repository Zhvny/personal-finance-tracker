import sys

from harness import AuditHarness, BaseAuditVector


class AuditVector_1_3(BaseAuditVector):
    """
    Failure Vector 1.3: Monorepo Boundary Linter
    Inject violation into core utility and run linter.
    """
    def setup(self):
        self.root = AuditHarness.get_canonical_root()
        self.target_file = self.root / "packages" / "core" / "utils" / "boundary_test.py"
        self.target_file.parent.mkdir(parents=True, exist_ok=True)
        self.log(f"Creating violation in {self.target_file}")

        with open(self.target_file, 'w') as f:
            f.write("from apps.cli.main import X\n")

    def reproduce(self):
        linter_script = AuditHarness.resolve_script_path("scripts/boundary_linter.py")
        self.log(f"Running linter: {linter_script}")

        self.result = self.run_command(
            [sys.executable, str(linter_script)]
        )
        self.log(f"Linter exit code: {self.result.returncode}")
        self.log(f"Linter output: {self.result.stdout}")

    def validate(self) -> bool:
        # DoD: Script exits Code 1; points to exact line of violation.
        success = self.result.returncode == 1 and "boundary_test.py:1: from apps.cli.main import X" in self.result.stdout
        return success

    def teardown(self):
        if self.target_file.exists():
            self.target_file.unlink()
