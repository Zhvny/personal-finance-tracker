"""Audit T4 (2026-09-02): Alpha audit_logs retention.

Mirrors the Delta `pruneContentReports` pattern and the Iris / Eta /
Gamma / Epsilon / Beta retention templates. The `public.audit_logs`
table is append-only by convention (see migration 006) and
accumulates PII in `ip_address`, `previous_value`, and `new_value`
JSONB columns. Without intervention, the table grows forever.

This module:
- Provides a cron-callable function that NULLs `ip_address`,
  `previous_value`, and `new_value` on rows older than the retention
  window.
- Keeps the row (audit trail) but drops the PII payload.
- Idempotent: re-running within the same window is a no-op.

Pinned to 90 days to match the dispute window documented in
`prisma/schema.prisma:148-152` (reporterIp on Delta's ContentReport).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 90


def _driver_is_postgres(conn) -> bool:
    """Best-effort detection of the underlying driver so the SQL uses
    the right placeholder. Falls back to ``%s`` (psycopg2) when the
    connection does not advertise a known type."""
    driver = getattr(conn, "__class__", type(conn)).__name__.lower()
    module = type(conn).__module__ or ""
    if "psycopg" in module or "pg" in driver or "postgres" in driver:
        return True
    if "sqlite" in module or "sqlite" in driver:
        return False
    # Conservative default: assume Postgres so the production path
    # gets ``%s`` and a SQLite misidentification would fail loudly
    # rather than silently corrupt data.
    return True


@dataclass
class PruneResult:
    scanned_rows: int
    pruned_rows: int
    cutoff_iso: str


def purge_audit_log_pii(
    conn,
    *,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    _placeholder: str | None = None,
) -> PruneResult:
    """NULL the PII columns on `public.audit_logs` rows older than the
    retention window. The row stays for the audit trail.

    `conn` is a DB-API 2.0 connection (psycopg2 or asyncpg wrapper
    that exposes ``execute(sql, params)`` returning a cursor with
    ``rowcount``). The function does not manage the transaction;
    the caller decides whether to commit.

    ``_placeholder`` is an internal override used by the test suite
    to skip the driver detection. Production callers should leave
    it alone; the auto-detection handles psycopg2 and sqlite3.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_iso = cutoff.isoformat()

    if _placeholder is None:
        _placeholder = "%s" if _driver_is_postgres(conn) else "?"
    placeholder = _placeholder

    cur = conn.execute(
        f"""
        SELECT COUNT(*) FROM public.audit_logs
        WHERE timestamp < {placeholder}
          AND (
            ip_address IS NOT NULL
            OR previous_value IS NOT NULL
            OR new_value IS NOT NULL
          )
        """,
        (cutoff,),
    )
    scanned = cur.fetchone()[0]
    cur.close()

    if scanned == 0:
        logger.info(
            "[retention] purge_audit_log_pii: no rows to prune (cutoff=%s)",
            cutoff_iso,
        )
        return PruneResult(scanned_rows=0, pruned_rows=0, cutoff_iso=cutoff_iso)

    cur = conn.execute(
        f"""
        UPDATE public.audit_logs
        SET ip_address = NULL,
            previous_value = NULL,
            new_value = NULL
        WHERE timestamp < {placeholder}
          AND (
            ip_address IS NOT NULL
            OR previous_value IS NOT NULL
            OR new_value IS NOT NULL
          )
        """,
        (cutoff,),
    )
    pruned = cur.rowcount
    cur.close()

    logger.info(
        "[retention] purge_audit_log_pii: scanned=%d pruned=%d cutoff=%s",
        scanned,
        pruned,
        cutoff_iso,
    )
    return PruneResult(
        scanned_rows=scanned, pruned_rows=pruned, cutoff_iso=cutoff_iso
    )
