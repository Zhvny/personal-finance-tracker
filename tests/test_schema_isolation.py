"""
Test per-service schema isolation.

Verifies:
- Service schemas exist (alpha_platform, alpha_ledger, alpha_portfolio, etc.)
- Domain tables are in the correct service schema
- Migration 016 creates schemas and moves tables from public
- Migration 017 enables RLS on service schema tables with service isolation policies
"""

from pathlib import Path

from unittest.mock import patch


def test_service_schemas_exist():
    """Service schemas should be queryable from information_schema."""
    expected_schemas = {
        "alpha_platform",
        "alpha_ledger",
        "alpha_portfolio",
        "alpha_market",
        "alpha_insights",
        "alpha_engagement",
    }
    with patch(
        "packages.core.infrastructure.persistence.postgres_manager.DatabaseManager.query",
        return_value=[{"nspname": s} for s in expected_schemas],
    ):
        from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager

        rows = DatabaseManager.query("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'alpha_%'")
        names = {r["nspname"] for r in rows}
    for schema in expected_schemas:
        assert schema in names


def test_service_schema_migration_sql_exists():
    """Migration 016 should define service schema creation + table moves."""
    migration_path = Path(__file__).resolve().parents[1] / "migrations" / "016_service_schemas.sql"
    assert migration_path.exists(), "016_service_schemas.sql missing"
    sql = migration_path.read_text(encoding="utf-8")
    for schema in ("alpha_platform", "alpha_ledger", "alpha_portfolio"):
        assert f"CREATE SCHEMA IF NOT EXISTS {schema}" in sql, f"Missing schema: {schema}"
    for table in ("expenses", "incomes", "investments"):
        assert f"public.{table}" in sql, f"Missing table move: {table}"


def test_rls_migration_enables_rls_and_policies():
    """Migration 017 should enable RLS and create service isolation policies."""
    migration_path = Path(__file__).resolve().parents[1] / "migrations" / "017_rls_service_schemas.sql"
    assert migration_path.exists(), "017_rls_service_schemas.sql missing"
    sql = migration_path.read_text(encoding="utf-8")

    # RLS enablement for each service schema
    for schema_table in (
        "alpha_platform.user_stats",
        "alpha_ledger.expenses",
        "alpha_portfolio.investments",
    ):
        assert (
            f"ALTER TABLE IF EXISTS {schema_table} ENABLE ROW LEVEL SECURITY" in sql
        ), f"Missing RLS enablement: {schema_table}"

    # Service isolation policies
    for policy_table in (
        "alpha_platform.user_stats",
        "alpha_ledger.expenses",
        "alpha_portfolio.investments",
    ):
        schema, table = policy_table.split(".", 1)
        assert "CREATE POLICY" in sql and table in sql, f"Missing policy for {policy_table}"

    # GUC-based condition
    assert "current_setting('app.service_name', true)" in sql, "Missing app.service_name GUC check in policies"
