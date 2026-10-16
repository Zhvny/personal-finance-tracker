"""
Alpha Microservice Configuration Module
=======================================
Centralized configuration management for the Alpha API Microservice.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Path resolution
API_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = API_DIR.parent.parent

# Load environment variables (.env in apps/api or project root)
if (API_DIR / ".env").exists():
    load_dotenv(API_DIR / ".env")
elif (PROJECT_ROOT / ".env").exists():
    load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    """
    honey: env dibaca di __init__ (bukan class body) supaya patch.dict(os.environ)
    dalam test berefek pada instansiasi baru.
    """

    def __init__(self) -> None:
        self.SERVICE_NAME: str = "Alpha Microservice API"
        self.SERVICE_VERSION: str = "2.1.1"
        # honey: 127.0.0.1 default agar mode non-docker tidak ekspos ke LAN
        # (SECURITY-AUDIT S-3); docker compose menyetel HOST=0.0.0.0 eksplisit.
        self.HOST: str = os.getenv("HOST", os.getenv("FINANCE_TRACKER_HOST", "127.0.0.1"))
        self.PORT: int = int(os.getenv("PORT", os.getenv("FINANCE_TRACKER_PORT", "8444")))

        # honey: kredensial TIDAK punya default — tanpa env, aplikasi gagal cepat
        # (SECURITY-AUDIT: default postgres/postgres = kredensial bawaan di source).
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "")

        self.SECRET_KEY: str = os.getenv("SECRET_KEY", "")
        self.DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
        self.TESTING: bool = os.getenv("TESTING", "").lower() in ("true", "1", "yes")

        # SSL Paths (env override dulu; fallback ke packages/api/certs)
        self.SSL_CERT_PATH: Path = Path(
            os.getenv(
                "FINANCE_TRACKER_CERT",
                str(PROJECT_ROOT / "packages" / "api" / "certs" / "server.crt"),
            )
        )
        self.SSL_KEY_PATH: Path = Path(
            os.getenv(
                "FINANCE_TRACKER_KEY",
                str(PROJECT_ROOT / "packages" / "api" / "certs" / "server.key"),
            )
        )

        # CORS: read from env, default to localhost only (never wildcard)
        self.ALLOWED_ORIGINS: list[str] = [
            o.strip()
            for o in os.getenv(
                "FINANCE_TRACKER_CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
            ).split(",")
            if o.strip()
        ]


settings = Settings()


def validate_security_settings(settings: "Settings") -> None:
    """
    Fail-fast guard, dipisah sebagai fungsi murni agar bisa diuji langsung
    tanpa reload modul (dotenv saat reload menimpa env var yang di-pop).
    """
    if settings.TESTING:
        return
    if "placeholder" in (settings.DATABASE_URL or ""):
        raise RuntimeError(
            "CRITICAL: DATABASE_URL still contains the build-time placeholder "
            "(see apps/api/Dockerfile). Provide a real postgresql:// URL via "
            "environment or .env."
        )
    if not settings.SECRET_KEY:
        raise RuntimeError(
            "CRITICAL: SECRET_KEY is not set. Provide it via environment or .env "
            "(no insecure default is shipped anymore)."
        )
    if not settings.DATABASE_URL and not settings.DEBUG:
        raise RuntimeError(
            "CRITICAL: DATABASE_URL is not set. Provide a postgresql:// URL via "
            "environment or .env (no credential-bearing default is shipped anymore)."
        )


validate_security_settings(settings)
