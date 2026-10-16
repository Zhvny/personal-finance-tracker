import logging

logger = logging.getLogger(__name__)

from pathlib import Path
from typing import List


class ProfileService:
    """
    Manages user profiles (e.g., Personal vs Business).
    Handles persistence of the active profile and provides isolation logic.
    """
    def __init__(self, project_root: Path) -> None:
        self.project_root: Path = project_root
        self.profile_file: Path = project_root / "data" / "active_profile.txt"
        self.profiles: List[str] = ["personal", "business", "test_qa_profile"]

    def get_active_profile(self) -> str:
        """Returns the currently active profile name."""
        if self.profile_file.exists():
            try:
                profile: str = self.profile_file.read_text().strip().lower()
                if profile in self.profiles:
                    return profile
            except Exception:
                logger.warning("Failed to reading profile configuration", exc_info=True)
                pass
        return "personal"

    def set_active_profile(self, profile: str) -> None:
        """Sets the active profile and persists it."""
        profile = profile.lower()
        if profile in self.profiles:
            self.profile_file.parent.mkdir(parents=True, exist_ok=True)
            self.profile_file.write_text(profile)
        else:
            raise ValueError(f"Invalid profile: {profile}. Must be one of {self.profiles}")

    def get_available_profiles(self) -> List[str]:
        """Returns list of supported profiles."""
        return self.profiles
