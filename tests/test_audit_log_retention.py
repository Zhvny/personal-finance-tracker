"""Audit T4 (2026-09-02): Alpha audit_logs retention tests.

Validates the ``purge_audit_log_pii`` helper against an in-memory
SQLite engine with a synthetic audit_logs table mirroring the
production schema in `migrations/006_auth_and_rls_policies.sql`.

SQLite does not support `public.audit_logs` schema-qualified names
the way Postgres does, so the tests wrap ``conn.execute`` to
rewrite the qualified name to the unqualified one. The real Postgres
path is untouched.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone


class _ConnWrapper:
    """Wraps a sqlite3.Connection so the public.audit_logs -> audit_logs
    rewrite happens transparently. ``execute`` returns the underlying
    cursor (or a tuple for ``lastrowid`` convenience)."""

    def __init__(self, raw: sqlite3.Connection) -> None:
        self._raw = raw

    def execute(self, sql: str, params: tuple = ()):
        return self._raw.execute(
            sql.replace("public.audit_logs", "audit_logs"), params
        )

    def commit(self) -> None:
        self._raw.commit()

    def close(self) -> None:
        self._raw.close()


@contextmanager
def _sqlite_with_table():
    raw = sqlite3.connect(":memory:")
    raw.execute(
        """
        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            target_table TEXT,
            record_id TEXT,
            previous_value TEXT,
            new_value TEXT,
            ip_address TEXT,
            status TEXT NOT NULL DEFAULT 'SUCCESS'
        )
        """
    )
    conn = _ConnWrapper(raw)
    try:
        yield conn
    finally:
        raw.close()


def _insert(conn, age_days, ip="1.2.3.4", previous='{"a":1}', new='{"b":2}'):
    ts = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
    conn.execute(
        "INSERT INTO audit_logs(timestamp, actor, action, previous_value, new_value, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
        (ts, "u1", "update", previous, new, ip),
    )
    conn.commit()


def test_no_rows_returns_zero():
    from scripts.retention.audit_logs_purge import purge_audit_log_pii

    with _sqlite_with_table() as conn:
        r = purge_audit_log_pii(conn, _placeholder="?")
        assert r.scanned_rows == 0
        assert r.pruned_rows == 0
        assert r.cutoff_iso.endswith("+00:00")


def test_old_row_with_pii_pruned():
    from scripts.retention.audit_logs_purge import purge_audit_log_pii

    with _sqlite_with_table() as conn:
        _insert(conn, 120)
        r = purge_audit_log_pii(conn, _placeholder="?")
        assert r.scanned_rows == 1
        assert r.pruned_rows == 1
        row = conn.execute(
            "SELECT ip_address, previous_value, new_value FROM audit_logs"
        ).fetchone()
        assert row == (None, None, None)


def test_old_row_already_purged_noop():
    from scripts.retention.audit_logs_purge import purge_audit_log_pii

    with _sqlite_with_table() as conn:
        _insert(conn, 120, ip=None, previous=None, new=None)
        r = purge_audit_log_pii(conn, _placeholder="?")
        assert r.scanned_rows == 0
        assert r.pruned_rows == 0


def test_recent_row_not_touched():
    from scripts.retention.audit_logs_purge import purge_audit_log_pii

    with _sqlite_with_table() as conn:
        _insert(conn, 10)
        r = purge_audit_log_pii(conn, _placeholder="?")
        assert r.scanned_rows == 0
        assert r.pruned_rows == 0


def test_custom_retention_window():
    from scripts.retention.audit_logs_purge import purge_audit_log_pii

    with _sqlite_with_table() as conn:
        _insert(conn, 40)
        r = purge_audit_log_pii(conn, retention_days=30, _placeholder="?")
        assert r.pruned_rows == 1
