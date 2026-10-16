import logging

logger = logging.getLogger(__name__)

import json
import re
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
        self.registry_file: Path = project_root / "apps" / "cli" / "profiles.json"
        self.types_file: Path = project_root / "apps" / "cli" / "profile_types.json"
        self._ensure_registry()

    def _ensure_registry(self) -> None:
        """Initializes profiles.json if it doesn't exist."""
        if not self.registry_file.exists():
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.registry_file, "w") as f:
                json.dump(["personal", "business"], f)

    def _load_profiles(self) -> List[str]:
        """Loads profiles from registry file (automation flows use qa_* profiles)."""
        try:
            with open(self.registry_file, "r") as f:
                raw = json.load(f)
                return list(raw)
        except (FileNotFoundError, json.JSONDecodeError):
            return ["personal", "business"]

    def _save_profiles(self, profiles: List[str]) -> None:
        """Saves profiles to registry file."""
        with open(self.registry_file, "w") as f:
            json.dump(profiles, f)

    def get_profile_types_map(self) -> dict:
        """Loads or infers profile types mapping: { name: 'personal'|'business' }."""
        types_map = {"personal": "personal", "business": "business"}
        if self.types_file.exists():
            try:
                with open(self.types_file, "r") as f:
                    loaded = json.load(f)
                    for k, v in loaded.items():
                        if not k.startswith("qa_"):
                            types_map[k] = v
            except Exception:
                pass
        profiles = self._load_profiles()
        for p in profiles:
            if p not in types_map:
                types_map[p] = "business" if "business" in p.lower() or "biz" in p.lower() else "personal"
        return types_map

    def _save_types_map(self, types_map: dict) -> None:
        with open(self.types_file, "w") as f:
            json.dump(types_map, f, indent=2)

    def get_profile_type(self, name: str) -> str:
        """Returns 'business' or 'personal' for a given profile name."""
        name = name.lower()
        types_map = self.get_profile_types_map()
        if name in types_map:
            return types_map[name]
        return "business" if "business" in name or "biz" in name else "personal"

    def add_profile(self, name: str, profile_type: str = "personal") -> None:
        """
        Adds a new profile to the registry and creates its directory with personal/business classification.
        """
        name = name.lower().strip()
        profile_type = profile_type.lower().strip()
        if profile_type not in ["personal", "business"]:
            profile_type = "personal"

        if not re.match(r"^[a-z0-9_]+$", name):
            raise ValueError(f"Invalid profile name: {name}. Only alphanumeric and underscores allowed.")

        profiles = self._load_profiles()
        if name in profiles:
            raise ValueError(f"Profile already exists: {name}")

        # Create directory
        profile_dir = self.project_root / "apps" / "cli" / "profiles" / name
        profile_dir.mkdir(parents=True, exist_ok=True)

        # Update registry
        profiles.append(name)
        self._save_profiles(profiles)

        # Update type mapping
        tmap = self.get_profile_types_map()
        tmap[name] = profile_type
        self._save_types_map(tmap)

    def get_active_profile(self) -> str:
        """Returns the currently active profile name."""
        profiles = self._load_profiles()
        if self.profile_file.exists():
            try:
                profile: str = self.profile_file.read_text().strip().lower()
                if profile in profiles and re.match(r"^[a-z0-9_]+$", profile):
                    return profile
            except Exception:
                logger.warning("Failed to scanning profiles directory", exc_info=True)
                pass
        return "personal"

    def set_active_profile(self, profile: str) -> None:
        """Sets the active profile and persists it."""
        profile = profile.lower().strip()
        if not re.match(r"^[a-z0-9_]{1,32}$", profile):
            raise ValueError(f"Invalid profile name format: {profile}")
        profiles = self._load_profiles()
        if profile in profiles:
            self.profile_file.parent.mkdir(parents=True, exist_ok=True)
            self.profile_file.write_text(profile)
        else:
            raise ValueError(f"Invalid profile: {profile}. Must be one of {profiles}")

    def delete_profile(self, name: str) -> None:
        """
        Deletes a profile from registry, drops its PostgreSQL schema, and removes its profile directory.
        """
        name = name.lower().strip()
        if not re.match(r"^[a-z0-9_]{1,32}$", name):
            raise ValueError(f"Invalid profile name format: {name}")

        if name in ["personal", "business"]:
            raise ValueError(f"Default system profile '{name}' cannot be deleted.")

        profiles = self._load_profiles()
        if name in profiles:
            profiles.remove(name)
            self._save_profiles(profiles)

        # Drop PostgreSQL schema safely after strict regex validation
        try:
            from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager

            DatabaseManager.execute(f"DROP SCHEMA IF EXISTS {name} CASCADE;")
        except Exception as e:
            logger.warning(f"Could not drop PostgreSQL schema for {name}: {e}")

        # Delete directory
        import shutil

        profile_dir = self.project_root / "apps" / "cli" / "profiles" / name
        if profile_dir.exists():
            shutil.rmtree(profile_dir, ignore_errors=True)

        if self.get_active_profile() == name:
            self.set_active_profile("personal")

    def get_available_profiles(self) -> List[str]:
        """Returns list of supported profiles."""
        return self._load_profiles()
