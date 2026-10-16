import os

# Must be set BEFORE any project imports so config.py sees it at module-load time
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("DEBUG", "True")

import os
import shutil
import sys
from pathlib import Path

import pytest

# Add project root to sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Add apps/cli to sys.path for direct CLI module imports (repositories, services, etc.)
_CLI_ROOT = _ROOT / "apps" / "cli"
if str(_CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CLI_ROOT))

# Add tests/automation to sys.path so test_infrastructure is available
_AUTO_ROOT = _ROOT / "tests" / "automation"
if str(_AUTO_ROOT) not in sys.path:
    sys.path.append(str(_AUTO_ROOT))

# Add apps/cli/investment_tracker to sys.path so its services can be imported relatively
_INV_ROOT = _ROOT / "apps" / "cli" / "investment_tracker"
if str(_INV_ROOT) not in sys.path:
    sys.path.append(str(_INV_ROOT))

# Add packages/api to sys.path for backend routers/services
_API_ROOT = _ROOT / "packages" / "api"
if str(_API_ROOT) not in sys.path:
    sys.path.append(str(_API_ROOT))

from packages.core.infrastructure.config import Config


@pytest.fixture(autouse=True)
def isolate_test_environment(tmp_path, monkeypatch):
    """Automatically isolates all tests by overriding FINANCE_ROOT_OVERRIDE and resetting Config."""
    # Setup standard sandbox folder structure
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "logs").mkdir(exist_ok=True)
    (tmp_path / "apps" / "cli").mkdir(parents=True, exist_ok=True)

    # Copy profiles registry to sandbox if it exists
    real_profiles = _ROOT / "apps" / "cli" / "profiles.json"
    if real_profiles.exists():
        shutil.copy(real_profiles, tmp_path / "apps" / "cli" / "profiles.json")

    # Force Config to use the test folder
    monkeypatch.setenv("FINANCE_ROOT_OVERRIDE", str(tmp_path))
    monkeypatch.delenv("FINANCE_DATA_ROOT", raising=False)
    monkeypatch.setenv("ALPHA_FORCE_SQLITE", "1")

    # Initialize config with overridden paths
    Config.reset_cache()
    Config.initialize()

    yield

    # Clean up after test
    monkeypatch.delenv("FINANCE_ROOT_OVERRIDE", raising=False)
    monkeypatch.delenv("ALPHA_FORCE_SQLITE", raising=False)
    Config.reset_cache()


@pytest.fixture
def temp_test_dir(tmp_path):
    """Provides a temporary directory for file-based tests."""
    return tmp_path


@pytest.fixture
def profile_data_dir(temp_test_dir):
    """Sets up a mock data directory for ProfileService."""
    data_dir = temp_test_dir / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def anyio_backend():
    """Forces anyio to use only asyncio backend to avoid Trio dependency/AttributeError issues."""
    return "asyncio"
