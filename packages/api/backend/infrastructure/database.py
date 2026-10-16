"""Legacy import-path shim — forward-only re-export of the canonical bridge.

Canonical implementation lives in
``packages.core.infrastructure.persistence.database``. Do NOT add logic here.
"""

from packages.core.infrastructure.persistence.database import (
    CanonicalPersistenceUnavailableError,
    Database,
    DatabaseManager,
)

__all__ = [
    "CanonicalPersistenceUnavailableError",
    "Database",
    "DatabaseManager",
]
