"""Live Postgres smoke (explicitly live, NOT part of the fast gate).

Runs against the shared Postgres via ensure_profile + REAL-root pinning.
Skipped unless Postgres is reachable — never a hard fail.

Marker ``live_pg`` is used WITHOUT registration (pyproject owner registers
it separately).
"""

import os
import socket
from pathlib import Path

import pytest

pytestmark = pytest.mark.live_pg

# Skip (not fail) when the PG driver is absent.
pytest.importorskip("psycopg2")


def _pg_reachable() -> bool:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def test_flow_pg_smoke_buy_sell():
    if not _pg_reachable():
        pytest.skip("postgres not reachable; live_pg smoke needs services")
    from test_infrastructure import CLIRunner, ensure_profile, reset_profile_tables

    root = Path(__file__).resolve().parent.parent.parent
    cli = root / "apps" / "cli" / "main.py"
    assert ensure_profile("automation_e2e", root, cli), "could not ensure automation_e2e profile"
    reset_profile_tables("automation_e2e", root)
    env = {"FINANCE_ROOT_OVERRIDE": str(root)}

    buy = CLIRunner(root, cli, "pg_smoke_buy", env_overrides=env)
    buy.run(["1", "1", "1", "PGSMOKE", "1", "10", "2", "", "y", "n", "y"])
    assert "PGSMOKE" in buy.stdout

    sell = CLIRunner(root, cli, "pg_smoke_sell", env_overrides=env)
    sell.run(["1", "7", "1", "1", "12", "2", "", "0"])
    assert "SELL EXECUTED" in (sell.stdout or "").upper()
