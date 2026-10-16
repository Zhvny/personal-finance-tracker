import os
import shutil
import tempfile
from pathlib import Path

from harness import BaseAuditVector


class AuditVector_1_8(BaseAuditVector):
    """
    Failure Vector 1.8: BOM-Aware .env Parser
    Verify that .env with UTF-16 BOM is parsed correctly.
    """
    def setup(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.env_file = self.temp_dir / ".env"

        # Key-Value pair to test
        self.test_key = "BOM_TEST_KEY"
        self.test_value = "BOM_SUCCESS_VALUE"

        content = f"{self.test_key}={self.test_value}"
        # Write with UTF-16 and BOM
        # In Python, 'utf-16' encoding writes the BOM automatically at the start.
        with open(self.env_file, 'w', encoding='utf-16') as f:
            f.write(content)

        self.log(f"Created UTF-16 .env at {self.env_file}")

    def reproduce(self):
        # Clear existing env var if any
        if self.test_key in os.environ:
            del os.environ[self.test_key]

        self.log("Calling Config.load_with_encoding with UTF-16 file")
        from packages.core.infrastructure.config import Config
        Config.load_with_encoding(self.env_file)

        self.result_value = os.environ.get(self.test_key)
        self.log(f"Detected value: {self.result_value}")

    def validate(self) -> bool:
        # DoD: Keys/Values parsed correctly without junk characters.
        # If it returns None or garbage, it fails.
        return self.result_value == self.test_value

    def teardown(self):
        if self.test_key in os.environ:
            del os.environ[self.test_key]
        shutil.rmtree(self.temp_dir, ignore_errors=True)
