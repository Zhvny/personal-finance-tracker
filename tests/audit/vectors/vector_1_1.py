import os
import shutil
import tempfile
from pathlib import Path

from harness import BaseAuditVector

from packages.core.infrastructure.config import Config


class AuditVector_1_1(BaseAuditVector):
    """
    Failure Vector 1.1: Marker-Chain Root Detection
    Verify that find_root returns canonical root even when called from deep symlinks.
    """
    def setup(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.log(f"Temp dir: {self.temp_dir}")

        # Create a mock project structure
        self.root = self.temp_dir / "project"
        self.root.mkdir()
        (self.root / ".setup_done").touch()
        (self.root / "package.json").touch()

        # Create deep structure
        self.deep_path = self.root / "node_modules" / "a" / "b" / "c" / "d" / "e"
        self.deep_path.mkdir(parents=True)

        # Create symlink
        self.symlink_path = self.temp_dir / "link_to_deep"
        # os.symlink(src, dst)
        try:
            os.symlink(str(self.deep_path), str(self.symlink_path), target_is_directory=True)
            self.log(f"Created symlink: {self.symlink_path} -> {self.deep_path}")
        except Exception as e:
            self.log(f"Failed to create symlink: {e}")
            # Fallback for Windows if symlink fails due to permissions
            self.symlink_path = self.deep_path

    def reproduce(self):
        self.log(f"Calling Config.get_root from {self.symlink_path}")
        # Note: Config.get_root uses Path(__file__) by default, we need to pass the start_path
        self.detected_root = Config.get_root(self.symlink_path)
        self.log(f"Detected root: {self.detected_root}")

    def validate(self) -> bool:
        expected = self.root.resolve()
        actual = self.detected_root.resolve()
        self.log(f"Expected: {expected}")
        self.log(f"Actual:   {actual}")

        # DoD: Returns absolute canonical root, not symlink path.
        return expected == actual

    def teardown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
