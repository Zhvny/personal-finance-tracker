import os
import sys
import unittest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tests.automation.cli_driver import CLIDriver


class TestCLIDriver(unittest.TestCase):
    def test_import(self):
        driver = CLIDriver()
        self.assertIsNotNone(driver)

    def test_start_and_exit(self):
        driver = CLIDriver()
        driver.start()
        # Assume CLI has an 'exit' command or we just terminate
        driver.stop()
        self.assertFalse(driver.is_running())

    def test_send_command(self):
        driver = CLIDriver()
        # Test non-interactive subcommand
        driver.start(args=["profile", "status"])
        output = driver.read_output(timeout=3)
        error = driver.read_error(timeout=1)
        driver.stop()

        if not output and error:
            print(f"DEBUG: Stderr: {error}")

        self.assertIn("active:", output.lower())

if __name__ == '__main__':
    unittest.main()
