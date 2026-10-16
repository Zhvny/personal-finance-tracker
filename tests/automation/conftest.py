"""
Automation test fixtures for Finance Tracker CLI.

DB Isolation Strategy
---------------------
Each test gets an isolated temporary data root via FINANCE_DATA_ROOT env var.
This prevents test pollution from production data and ensures deterministic
P/L calculations in FIFO sell tests.
"""

from pathlib import Path

import pytest

from tests.automation.cli_driver import CLIDriver


@pytest.fixture
def project_root():
    return Path(__file__).parent.parent.parent


@pytest.fixture
def isolated_data_root(tmp_path):
    """
    Create a temporary profile data directory for test isolation.
    Sets FINANCE_DATA_ROOT so every CLI subprocess reads/writes to this tmp dir.
    """
    # Mimic the profile-scoped structure: <root>/profiles/<profile>/
    # The active profile defaults to "personal" so we create that subtree.
    profile_data = tmp_path / "profiles" / "personal"
    profile_data.mkdir(parents=True)
    yield tmp_path


@pytest.fixture
def cli_driver(project_root, isolated_data_root):
    """
    CLIDriver with isolated FINANCE_DATA_ROOT so each test gets a fresh DB.
    """
    driver = CLIDriver(project_root)
    driver.env["FINANCE_DATA_ROOT"] = str(isolated_data_root)
    # Keep CLI subprocesses on disposable SQLite (never the shared live Postgres).
    driver.env["ALPHA_FORCE_SQLITE"] = "1"
    return driver


class DummyReporter:
    def log_result(self, name, status, msg, duration):
        print(f"[REPORTER] {name}: {status} - {msg} ({duration:.2f}s)")


@pytest.fixture
def reporter():
    return DummyReporter()


@pytest.fixture
def setup_qa_environment(project_root, isolated_data_root):
    return {"root_dir": str(project_root), "qa_profile_dir": str(isolated_data_root / "profiles" / "personal")}
