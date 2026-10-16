import os
import threading
from pathlib import Path
from typing import Dict


class Config:
    _lock = threading.Lock()
    _instance = None

    def __new__(cls):
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def get_root(start_path: Path | None = None) -> Path:
        """Dynamically detects project root using marker files."""
        # Marker-chain detection (Vector 1.1)
        current = (start_path or Path(__file__)).resolve()
        for parent in current.parents:
            if (parent / ".setup_done").exists() or (parent / "package.json").exists():
                return parent
        return (start_path or Path(__file__)).resolve().parents[3]

    # Get the project root (finance-tracker/)
    BASE_DIR: Path = get_root()
    CLI_DATA_ROOT: Path = BASE_DIR / "apps" / "cli"
    APP_LOG_FILE: Path = BASE_DIR / "logs" / "app.log"
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

    # Encryption Configuration
    ENCRYPTION_KEY: str = os.environ.get("ENCRYPTION_KEY", "")

    _cached_profile: str | None = None

    @classmethod
    def load_with_encoding(cls, path: Path):
        """Robustly loads a .env file with BOM support (Vector 1.8)."""
        import io

        from dotenv import load_dotenv

        if not path.exists():
            return

        try:
            with open(path, 'rb') as f:
                raw_data = f.read()
        except Exception:
            # If we can't read it as bytes, let load_dotenv try its default
            load_dotenv(path)
            return

        if not raw_data:
            return

        # Explicit BOM detection (Vector 1.8)
        # UTF-8 with BOM: EF BB BF
        if raw_data.startswith(b'\xef\xbb\xbf'):
            encoding = 'utf-8-sig'
        # UTF-16 Little Endian BOM: FF FE
        elif raw_data.startswith(b'\xff\xfe'):
            encoding = 'utf-16'
        # UTF-16 Big Endian BOM: FE FF
        elif raw_data.startswith(b'\xfe\xff'):
            encoding = 'utf-16'
        else:
            # Fallback to chardet if available
            encoding = 'utf-8' # Default
            try:
                import chardet
                result = chardet.detect(raw_data)
                if result and result['encoding']:
                    encoding = result['encoding']
            except (ImportError, Exception):
                pass

        try:
            # Using 'utf-16' (without -le/-be) handles the BOM correctly
            content = raw_data.decode(encoding)
            load_dotenv(stream=io.StringIO(content))
        except Exception:
            # Final fallback to standard loader
            try:
                load_dotenv(path)
            except Exception:
                pass

    @classmethod
    def initialize(cls):
        """Initializes the environment and project-local settings."""
        import yfinance as yf

        with cls._lock:
            # Support test environment override to isolate databases and protect production data
            root_override = os.environ.get("FINANCE_ROOT_OVERRIDE")
            if root_override:
                cls.BASE_DIR = Path(root_override).resolve()
                cls.CLI_DATA_ROOT = cls.BASE_DIR / "apps" / "cli"
                cls.APP_LOG_FILE = cls.BASE_DIR / "logs" / "app.log"

                # Pre-create sandboxed directories
                cls.BASE_DIR.mkdir(parents=True, exist_ok=True)
                cls.CLI_DATA_ROOT.mkdir(parents=True, exist_ok=True)
                (cls.BASE_DIR / "logs").mkdir(parents=True, exist_ok=True)
                (cls.BASE_DIR / "data").mkdir(parents=True, exist_ok=True)

            # Ensure BASE_DIR exists
            if not cls.BASE_DIR.exists():
                 raise RuntimeError(f"BASE_DIR does not exist: {cls.BASE_DIR}")

            # Load local .env
            cls.load_with_encoding(cls.BASE_DIR / ".env")

            # Also try loading from apps/api/.env if root .env is missing or for DB_URL
            cls.load_with_encoding(cls.BASE_DIR / "apps" / "api" / ".env")

            # Ensure we re-read the key after loading .env
            cls.ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")

            # Isolate yfinance cache to project directory
            cache_dir = cls.BASE_DIR / ".cache" / "yfinance"
            cache_dir.mkdir(parents=True, exist_ok=True)
            try:
                # yfinance 0.2.0+ supports custom cache location
                yf.set_tz_cache_location(str(cache_dir))
            except Exception:
                pass

    @classmethod
    def get_active_profile(cls) -> str:
        """Reads the active profile using ProfileService for consistency."""
        if cls._cached_profile:
            return cls._cached_profile

        with cls._lock:
            # Double-check after acquiring lock
            if cls._cached_profile:
                return cls._cached_profile

            try:
                from packages.core.application.profile_service import ProfileService
                cls._cached_profile = ProfileService(cls.BASE_DIR).get_active_profile()
                return cls._cached_profile
            except Exception:
                return "personal"

    @classmethod
    def reset_cache(cls):
        """Resets the cached profile (useful after switching profiles)."""
        with cls._lock:
            cls._cached_profile = None

    @classmethod
    def is_feature_enabled(cls, feature: str) -> bool:
        """Checks if a feature is enabled for the current profile."""
        profile = cls.get_active_profile()
        if profile == "business":
            # Disable non-business features
            if feature.lower() in ["reward", "ml", "behavioral", "stocks"]:
                return False
        return True

    @classmethod
    def get_cli_data_root(cls) -> Path:
        """Returns the profile-specific data root."""
        root_override = os.environ.get("FINANCE_ROOT_OVERRIDE")
        if root_override:
            base = cls.BASE_DIR / "apps" / "cli"
        else:
            base_env: str | None = os.environ.get("FINANCE_DATA_ROOT")
            base: Path = Path(base_env) if base_env else cls.BASE_DIR / "apps" / "cli"
        profile: str = cls.get_active_profile()
        return base / "profiles" / profile

    @classmethod
    def get_db_paths(cls) -> Dict[str, Path]:
        """Returns the dictionary of database paths for the current profile."""
        root: Path = cls.get_cli_data_root()
        return {
            "expense": root / "expense_tracker" / "data" / "expense.db",
            "income": root / "income_tracker" / "data" / "income.db",
            "investment": root / "investment_tracker" / "data" / "portfolio.db",
            "behavioral": root / "behavioral_finance" / "data" / "behavioral.db",
            "goals": root / "advanced_features" / "data" / "goals.db",
            "budget": root / "advanced_features" / "data" / "budget.db",
            "finance": root / "advanced_features" / "data" / "finance.db",
            "chat": root / "advanced_features" / "data" / "chat.db",
            "market": cls.BASE_DIR / "data" / "market.db",
        }

    # Postgres Configuration
    POSTGRES_DB: str = os.environ.get("POSTGRES_DB", "finance_tracker")
    POSTGRES_USER: str = os.environ.get("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.environ.get("POSTGRES_PASSWORD", "postgres")
    POSTGRES_HOST: str = os.environ.get("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.environ.get("POSTGRES_PORT", "5432")

    @classmethod
    def get_db_path(cls, name: str) -> str:
        """Retrieves and prepares the path for a specific database."""
        path: Path | None = cls.get_db_paths().get(name)
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            return str(path)
        raise ValueError(f"Unknown database: {name}")
