"""Task 5: per-profile DDL is canonical — 23 tables, every table has user_id."""
from unittest.mock import MagicMock

from packages.api.backend.infrastructure.schemas import EXPECTED_TABLES_PER_PROFILE, SchemaInitializer
from packages.core.infrastructure.persistence.per_profile_ddl import _TABLE_COUNT, build_all_ddl_for_profile


def test_table_count_matches_actual_ddl():
    """CREATE TABLE count == _TABLE_COUNT == EXPECTED_TABLES_PER_PROFILE == 23."""
    tables = [s for s in build_all_ddl_for_profile("qa_count") if "CREATE TABLE" in s.upper()]
    assert len(tables) == 23
    assert _TABLE_COUNT == 23
    assert EXPECTED_TABLES_PER_PROFILE == 23


def test_provision_profile_schema_all_tables_have_user_id(monkeypatch):
    """provision_profile_schema() emits user_id on every profile table."""
    from packages.core.infrastructure.persistence import postgres_manager as pm

    calls: list = []
    monkeypatch.setattr(pm.DatabaseManager, "execute", lambda sql, *a, **k: calls.append(sql))

    SchemaInitializer(MagicMock()).provision_profile_schema("qa_userid")

    tables = [c for c in calls if "CREATE TABLE" in c.upper()]
    assert len(tables) == EXPECTED_TABLES_PER_PROFILE
    missing = [t for t in tables if "user_id" not in t.lower()]
    assert not missing, f"tables without user_id: {missing}"
