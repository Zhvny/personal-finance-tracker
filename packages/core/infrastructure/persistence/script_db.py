"""Single source of truth for Postgres connection defaults (audit A-H01).

Every script that talks to Postgres imports ``connect_from_env()`` and
refuses to run if ``POSTGRES_PASSWORD`` is not set. The previous
fallback to a literal ``postgres:postgres`` was a footgun: a repo clone
+ ``docker compose up`` would silently attempt the default credentials
against a DB whose password the operator had rotated.

Usage:
    from packages.core.infrastructure.persistence.script_db import connect_from_env
    conn = connect_from_env()
"""
from __future__ import annotations

import os
import sys

import psycopg2
import psycopg2.extensions


DEFAULTS = {
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5432",
    "POSTGRES_DB": "finance_tracker",
    "POSTGRES_USER": "postgres",
}


def _missing_env_var_message() -> str:
    return (
        "POSTGRES_PASSWORD is not set. Refusing to fall back to a default "
        "credential (audit A-H01). Set POSTGRES_PASSWORD in your shell or "
        ".env before running this script, e.g.\n"
        "  export POSTGRES_PASSWORD=...    # bash\n"
        "  $env:POSTGRES_PASSWORD = '...'  # PowerShell\n"
    )


def connect_from_env(**overrides) -> psycopg2.extensions.connection:
    """Connect to Postgres using only env-supplied credentials.

    Raises ``SystemExit(2)`` if POSTGRES_PASSWORD is missing or empty.
    Per-call kwargs override env defaults (useful for tests that point
    at a throwaway DB).
    """
    password = os.environ.get("POSTGRES_PASSWORD", "").strip()
    if not password:
        sys.stderr.write(_missing_env_var_message())
        sys.exit(2)

    params = {key: os.environ.get(key, default) for key, default in DEFAULTS.items()}
    params["password"] = password
    params.update(overrides)
    return psycopg2.connect(**params)


def dsn_from_env() -> str:
    """Return a libpq-style DSN built from the env, or exit if unset."""
    password = os.environ.get("POSTGRES_PASSWORD", "").strip()
    if not password:
        sys.stderr.write(_missing_env_var_message())
        sys.exit(2)
    user = os.environ.get("POSTGRES_USER", DEFAULTS["POSTGRES_USER"])
    host = os.environ.get("POSTGRES_HOST", DEFAULTS["POSTGRES_HOST"])
    port = os.environ.get("POSTGRES_PORT", DEFAULTS["POSTGRES_PORT"])
    db = os.environ.get("POSTGRES_DB", DEFAULTS["POSTGRES_DB"])
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"
