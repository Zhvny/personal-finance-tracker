import unittest
from pathlib import Path

from packages.core.infrastructure.config import Config


class TestConfig(unittest.TestCase):
    def test_base_dir_exists(self):
        self.assertTrue(Config.BASE_DIR.exists())
        self.assertTrue(Config.BASE_DIR.is_dir())

    def test_get_active_profile(self):
        profile = Config.get_active_profile()
        self.assertIn(profile, ["personal", "business"])

    def test_get_cli_data_root(self):
        root = Config.get_cli_data_root()
        self.assertTrue("profiles" in str(root))
        self.assertIn(Config.get_active_profile(), str(root))

    def test_get_db_paths(self):
        paths = Config.get_db_paths()
        self.assertIn("expense", paths)
        self.assertIn("income", paths)
        self.assertIsInstance(paths["expense"], Path)

if __name__ == "__main__":
    unittest.main()
