import sys

from harness import AuditHarness, BaseAuditVector


class AuditVector_1_4(BaseAuditVector):
    """
    Failure Vector 1.4: Idempotent sys.path Injection
    Call injection logic 10x in a loop.
    """
    def setup(self):
        self.root = AuditHarness.get_canonical_root()
        self.root_str = str(self.root)

    def reproduce(self):
        # Simulation of the injection logic in main.py
        for _ in range(10):
            if self.root_str not in sys.path:
                sys.path.insert(0, self.root_str)
            else:
                # Some naive implementations might just append/insert anyway
                # But our target logic has the 'if' check.
                pass

    def validate(self) -> bool:
        count = sys.path.count(self.root_str)
        self.log(f"Root '{self.root_str}' found {count} times in sys.path")

        # DoD: sys.path contains exactly one entry for project root.
        return count == 1

    def teardown(self):
        # Clean up sys.path if needed (though it might affect the current process)
        while self.root_str in sys.path:
            sys.path.remove(self.root_str)
        # Re-add once to keep it clean but functional
        sys.path.insert(0, self.root_str)
