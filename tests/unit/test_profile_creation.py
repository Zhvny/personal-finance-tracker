import pytest

from packages.core.application.profile_service import ProfileService
from packages.core.infrastructure.config import Config


@pytest.fixture
def test_env(tmp_path):
    """Sets up a temporary project structure for profile tests."""
    # Create necessary folders (exist_ok=True since conftest autouse may already create them)
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "apps" / "cli").mkdir(parents=True, exist_ok=True)

    # Delete copied real profiles registry to start clean
    registry = tmp_path / "apps" / "cli" / "profiles.json"
    if registry.exists():
        registry.unlink()

    # Initialize ProfileService with tmp_path
    service = ProfileService(tmp_path)
    return tmp_path, service

def test_add_profile_success(test_env):
    tmp_path, service = test_env
    profile_name = "trading_test"

    service.add_profile(profile_name)

    # Verify registry update
    profiles = service.get_available_profiles()
    assert profile_name in profiles

    # Verify directory creation
    profile_dir = tmp_path / "apps" / "cli" / "profiles" / profile_name
    assert profile_dir.exists()
    assert profile_dir.is_dir()

def test_add_profile_invalid_name(test_env):
    _, service = test_env
    invalid_names = ["My Profile", "test-profile", "test@123", ""]

    for name in invalid_names:
        with pytest.raises(ValueError, match="Invalid profile name"):
            service.add_profile(name)

def test_add_profile_duplicate(test_env):
    _, service = test_env
    service.add_profile("investor")

    with pytest.raises(ValueError, match="Profile already exists"):
        service.add_profile("investor")

def test_get_available_profiles_initial(test_env):
    _, service = test_env
    assert service.get_available_profiles() == ["personal", "business"]

def test_active_profile_persistence(test_env):
    tmp_path, service = test_env
    service.add_profile("crypto")
    service.set_active_profile("crypto")

    assert service.get_active_profile() == "crypto"

    # Verify file content
    profile_file = tmp_path / "data" / "active_profile.txt"
    assert profile_file.read_text() == "crypto"

def test_config_path_resolution_with_profiles(test_env, monkeypatch):
    """
    Verifies that Config.get_cli_data_root() respects the active profile.
    This tests the integration between ProfileService and Config.
    """
    tmp_path, service = test_env

    # Mock Config.BASE_DIR to point to our tmp_path
    monkeypatch.setattr(Config, "BASE_DIR", tmp_path)
    # Ensure Config resets its cached profile
    Config.reset_cache()

    # Default should be personal
    assert "personal" in str(Config.get_cli_data_root())

    # Switch to business
    service.set_active_profile("business")
    Config.reset_cache()
    assert "business" in str(Config.get_cli_data_root())

    # Add and switch to new profile
    service.add_profile("vault")
    service.set_active_profile("vault")
    Config.reset_cache()

    root = Config.get_cli_data_root()
    assert "vault" in str(root)
    assert root == tmp_path / "apps" / "cli" / "profiles" / "vault"
