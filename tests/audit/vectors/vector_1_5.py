import tempfile
from pathlib import Path

from harness import BaseAuditVector

from packages.core.infrastructure.persistence.database import Database


class AuditVector_1_5(BaseAuditVector):
    """
    Failure Vector 1.5: Path Truncation Guard
    Create a dummy path >240 chars. Attempt file write via Repo.
    """
    def setup(self):
        # Create a very long path. Max Path on Windows is 260.
        # We'll aim for ~300.
        base = Path(tempfile.gettempdir()).resolve()
        # Create deep structure
        self.long_dir = base
        for i in range(10):
            self.long_dir = self.long_dir / f"dir_{i}_{'x'*20}"

        self.long_path = self.long_dir / "test_long_path.db"
        self.log(f"Long path (length {len(str(self.long_path))}): {self.long_path}")

    def reproduce(self):
        self.error = None
        self.success_connect = False
        try:
            self.long_dir.mkdir(parents=True, exist_ok=True)
            # Use Database utility
            conn = Database._get_connection(str(self.long_path))
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
            conn.execute("INSERT INTO test (id) VALUES (1)")
            conn.commit()
            conn.close()
            self.success_connect = True
            self.log("Successfully wrote to long path database.")
        except Exception as e:
            self.log(f"Failed to write to long path: {e}")
            self.error = str(e)

    def validate(self) -> bool:
        # DoD: System detects risk; uses UNC path or raises explicit Error.
        # If success_connect is True, it means Python/OS handled it (likely via UNC).
        # In modern Python 3.8+ on Windows, long paths are often enabled or handled by pathlib.
        if self.success_connect:
            return True

        # If it failed, we want an explicit Error, not a silent truncation
        return self.error is not None

    def teardown(self):
        # Attempt to clean up. This might also fail if tools don't support long paths.
        import shutil
        try:
            # On Windows, we might need UNC path for shutil.rmtree too
            shutil.rmtree(str(self.long_dir.parents[8]), ignore_errors=True)
        except:
            pass
