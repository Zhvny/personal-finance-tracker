import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to sys.path to import schemas
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Also need to import runner
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
sys.path.insert(0, str(MIGRATIONS_DIR))
import runner

from packages.api.backend.infrastructure.schemas import SchemaInitializer


class TestMigrationSystem(unittest.TestCase):

    def setUp(self):
        self.migrations_dir = MIGRATIONS_DIR

    def test_migration_files_exist(self):
        """Test all 5 numbered migration files exist."""
        files = [
            "001_schema_version_table.sql",
            "002_n8n_automation_tables.sql",
            "003_market_schema.sql",
            "004_add_composite_indexes.sql",
            "005_profile_schema_template.sql"
        ]
        for f in files:
            path = self.migrations_dir / f
            self.assertTrue(path.exists(), f"File {f} is missing")

    def test_migration_files_numbered_sequentially(self):
        r"""Test filenames match \d{3}_.+\.sql format."""
        sql_files = list(self.migrations_dir.glob("*.sql"))
        import re
        for f in sql_files:
            self.assertIsNotNone(re.match(r"^\d{3}_.+\.sql$", f.name), f"File {f.name} doesn't match pattern")

    def test_profile_template_contains_all_tables(self):
        """Read 005_ file, assert all 18 table names present."""
        template_file = self.migrations_dir / "005_profile_schema_template.sql"
        content = template_file.read_text()

        tables = [
            "expenses", "incomes", "investments", "sell_transactions", "historical_prices",
            "recurrence_candidates", "user_stats", "fx_rates", "manual_balances",
            "cash_split", "transfer_log", "behavioral_snapshots", "networth_snapshots",
            "budgets", "goals", "stock_favorites", "virtual_accounts", "reward_state"
        ]
        for t in tables:
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {{PROFILE}}.{t}", content)

    @patch("runner.get_db_connection")
    def test_runner_status_command_runs(self, mock_get_conn):
        """Test runner status command runs without errors."""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        # Mock the cursor and its results
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("001_schema_version_table.sql", "checksum1", "2026-08-11 10:00:00"),
            ("002_n8n_automation_tables.sql", "checksum2", "2026-08-11 10:00:00")
        ]

        # We don't want to sys.exit or print in tests if possible, but runner functions might just print
        with patch("sys.stdout"):
            runner.cmd_status()

        mock_cursor.execute.assert_any_call("SELECT version, checksum, applied_at FROM public.schema_migrations ORDER BY version")

    @patch("runner.get_db_connection")
    def test_runner_apply_marks_version_in_db(self, mock_get_conn):
        """Mock psycopg2, verify INSERT INTO schema_migrations."""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Return empty list so all migrations are "pending"
        mock_cursor.fetchall.return_value = []

        # We just want to test one file, so let's mock get_migration_files to return just one
        mock_file = MagicMock()
        mock_file.name = "001_test.sql"
        mock_file.read_text.return_value = "SELECT 1;"

        with patch("runner.get_migration_files", return_value=[mock_file]), patch("sys.stdout"):
            runner.cmd_apply()

        # Assert execute was called with content
        mock_cursor.execute.assert_any_call("SELECT 1;")

        # Assert insert into schema_migrations
        insert_calls = [c for c in mock_cursor.execute.call_args_list if "INSERT INTO public.schema_migrations" in c[0][0]]
        self.assertTrue(len(insert_calls) > 0)

    @patch("runner.get_db_connection")
    def test_runner_skips_already_applied(self, mock_get_conn):
        """If version in schema_migrations, SQL file not re-executed."""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            ("001_test.sql", "checksum_here", "2026-08-11")
        ]

        mock_file = MagicMock()
        mock_file.name = "001_test.sql"

        with patch("runner.get_migration_files", return_value=[mock_file]), patch("sys.stdout"):
            runner.cmd_apply()

        # Ensure it didn't call read_text or execute the sql
        mock_file.read_text.assert_not_called()

    @patch("runner.get_db_connection")
    def test_runner_verify_detects_tampering(self, mock_get_conn):
        """Write temp SQL file, modify file, verify returns mismatch."""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_file = MagicMock()
        mock_file.name = "001_test.sql"
        mock_file.read_text.return_value = "MODIFIED CONTENT"

        # Stored checksum is for "ORIGINAL CONTENT"
        stored_checksum = hashlib.md5(b"ORIGINAL CONTENT").hexdigest()

        mock_cursor.fetchall.return_value = [
            ("001_test.sql", stored_checksum, "2026-08-11")
        ]

        with patch("runner.get_migration_files", return_value=[mock_file]), patch("sys.stdout"), patch("sys.exit") as mock_exit:
            runner.cmd_verify()
            mock_exit.assert_called_with(1)

    @patch("packages.api.backend.infrastructure.schemas.Config.get_active_profile", return_value="invalid-profile!")
    def test_schema_initializer_profile_name_validation(self, mock_get_profile):
        """Call _ensure_postgres_profile_schema with invalid profile name."""
        initializer = SchemaInitializer(MagicMock())
        # The function catches exceptions and logs them. To verify it caught a ValueError, we could mock logger
        with patch("packages.api.backend.infrastructure.schemas.logger") as mock_logger:
            initializer._ensure_postgres_profile_schema()

            # The error log should contain "Failed to ensure PostgreSQL profile schema"
            error_calls = [c for c in mock_logger.error.call_args_list if "Failed to ensure PostgreSQL profile schema" in str(c[0][0])]
            self.assertTrue(len(error_calls) > 0)

            # Assert ValueError was raised internally
            exception = error_calls[0][0][0]
            self.assertIn("Security error: Invalid profile identifier", str(exception))

if __name__ == "__main__":
    unittest.main()
