import shutil
import unittest
from pathlib import Path

from packages.core.application.profile_service import ProfileService


class TestProfileService(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for tests
        self.test_dir = Path("tests/fixtures/temp_profile_test")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.service = ProfileService(self.test_dir)

    def tearDown(self):
        # Clean up
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_default_profile(self):
        self.assertEqual(self.service.get_active_profile(), "personal")

    def test_set_active_profile(self):
        self.service.set_active_profile("business")
        self.assertEqual(self.service.get_active_profile(), "business")

        # Check file content
        profile_file = self.test_dir / "data" / "active_profile.txt"
        self.assertTrue(profile_file.exists())
        self.assertEqual(profile_file.read_text(), "business")

    def test_invalid_profile(self):
        with self.assertRaises(ValueError):
            self.service.set_active_profile("hacker")

    def test_get_available_profiles(self):
        self.assertEqual(self.service.get_available_profiles(), ["personal", "business"])

if __name__ == "__main__":
    unittest.main()
