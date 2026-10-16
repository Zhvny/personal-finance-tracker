"""
backend/finance/budget_service.py — Budget engine + alerts (Phase 6)
=====================================================================
Canonical-ledger budget status: limits live in `budgets` (per-profile,
via budget.db bridge), actuals come from the canonical ledger
(`transactions` where type = 'expense'), exactly like Phase 5 reports.

Alert thresholds are configurable (env BUDGET_WARN_PCT / BUDGET_ALERT_PCT /
BUDGET_OVER_PCT, defaults 70 / 90 / 100) and the n8n WF-08 path
(`check_budget_alerts`) is idempotent: an alert row is keyed by
(year, month, category, level) so repeated checks never duplicate alerts.
"""
import os
from datetime import date
from typing import Any, Dict, List, Optional

from packages.core.infrastructure.persistence.database import Database

DEFAULT_THRESHOLDS = {"warn": 70.0, "alert": 90.0, "over": 100.0}

BUDGETS_DDL = """CREATE TABLE IF NOT EXISTS budgets (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    year      INTEGER NOT NULL,
    month     INTEGER NOT NULL,
    category  TEXT    NOT NULL DEFAULT 'total',
    limit_amt REAL    NOT NULL,
    UNIQUE(year, month, category)
)"""

BUDGET_ALERTS_DDL = """CREATE TABLE IF NOT EXISTS budget_alerts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    year       INTEGER NOT NULL,
    month      INTEGER NOT NULL,
    category   TEXT    NOT NULL,
    level      TEXT    NOT NULL,
    pct_used   REAL    NOT NULL,
    actual     REAL    NOT NULL,
    limit_amt  REAL    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(year, month, category, level)
)"""


class BudgetError(Exception):
    """Invalid budget request (bad month, non-positive limit, ...)."""


def _thresholds() -> Dict[str, float]:
    def _env(name: str, default: float) -> float:
        try:
            raw = os.getenv(name, "").strip()
            return float(raw) if raw else default
        except ValueError:
            return default

    return {
        "warn": _env("BUDGET_WARN_PCT", DEFAULT_THRESHOLDS["warn"]),
        "alert": _env("BUDGET_ALERT_PCT", DEFAULT_THRESHOLDS["alert"]),
        "over": _env("BUDGET_OVER_PCT", DEFAULT_THRESHOLDS["over"]),
    }


def _validate_month(year: int, month: int) -> None:
    if not isinstance(year, int) or not isinstance(month, int) or not (1 <= month <= 12):
        raise BudgetError("Bulan tidak valid (harus antara 1 dan 12)")


def _validate_limit(limit: Any) -> float:
    try:
        value = float(limit)
    except (TypeError, ValueError):
        raise BudgetError("Limit harus berupa angka") from None
    if value <= 0:
        raise BudgetError("Limit harus lebih besar dari 0")
    return round(value, 2)


def _ensure_budget_db(budget_db: str) -> None:
    Database.execute(budget_db, BUDGETS_DDL)


def _ensure_alerts_db(budget_db: str) -> None:
    Database.execute(budget_db, BUDGET_ALERTS_DDL)


def _month_bounds(year: int, month: int) -> tuple:
    if month == 12:
        return date(year, 12, 1), date(year + 1, 1, 1)
    return date(year, month, 1), date(year, month + 1, 1)


# ═════════════════════════════════════════════════════════════════════════════
# § Limits
# ═════════════════════════════════════════════════════════════════════════════

def set_budget_limit(budget_db: str, year: int, month: int, category: str, limit: Any) -> Dict[str, Any]:
    """Upsert a per-category limit for (year, month)."""
    _validate_month(year, month)
    limit_value = _validate_limit(limit)
    cat = str(category or "").strip().lower() or "total"
    _ensure_budget_db(budget_db)
    Database.execute(
        budget_db,
        "INSERT INTO budgets (year, month, category, limit_amt) VALUES (?, ?, ?, ?)"
        " ON CONFLICT (year, month, category) DO UPDATE SET limit_amt = excluded.limit_amt",
        (year, month, cat, limit_value),
    )
    return {"year": year, "month": month, "category": cat, "limit": limit_value}


def delete_budget_limit(budget_db: str, year: int, month: int, category: str) -> Dict[str, Any]:
    """Remove a per-category limit (and its future alert keys)."""
    _validate_month(year, month)
    cat = str(category or "").strip().lower()
    _ensure_budget_db(budget_db)
    Database.execute(
        budget_db,
        "DELETE FROM budgets WHERE year = ? AND month = ? AND category = ?",
        (year, month, cat),
    )
    return {"ok": True}


# ═════════════════════════════════════════════════════════════════════════════
# § Status
# ═════════════════════════════════════════════════════════════════════════════

def _level_for(pct: float, thresholds: Dict[str, float]) -> str:
    if pct >= thresholds["over"]:
        return "over"
    if pct >= thresholds["alert"]:
        return "alert"
    if pct >= thresholds["warn"]:
        return "warn"
    return "ok"


def _actuals_by_category(ledger_db: str, year: int, month: int) -> Dict[str, Dict[str, Any]]:
    start, end = _month_bounds(year, month)
    rows = Database.query(
        ledger_db,
        "SELECT COALESCE(category, 'Lainnya') AS category, SUM(amount) AS total, COUNT(*) AS count"
        " FROM transactions WHERE type = 'expense' AND tx_date >= ? AND tx_date < ?"
        " GROUP BY category",
        (start.isoformat(), end.isoformat()),
    )
    return {
        str(r["category"] or "Lainnya"): {"actual": float(r["total"] or 0), "count": int(r["count"] or 0)}
        for r in rows
    }


def _limits_by_category(budget_db: str, year: int, month: int) -> Dict[str, float]:
    rows = Database.query(
        budget_db,
        "SELECT category, limit_amt FROM budgets WHERE year = ? AND month = ?",
        (year, month),
    )
    return {str(r["category"]): float(r["limit_amt"] or 0) for r in rows}


def build_budget_status(
    ledger_db: str,
    budget_db: str,
    year: int,
    month: int,
    thresholds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Budget vs actual per category for (year, month) from the canonical ledger."""
    _validate_month(year, month)
    _ensure_budget_db(budget_db)
    thr = thresholds or _thresholds()
    actuals = _actuals_by_category(ledger_db, year, month)
    limits = _limits_by_category(budget_db, year, month)

    categories = []
    for cat, limit in sorted(limits.items()):
        actual = actuals.get(cat, {"actual": 0.0, "count": 0})
        pct = round(actual["actual"] / limit * 100, 1) if limit else 0.0
        categories.append({
            "category": cat,
            "limit": round(limit, 2),
            "actual": round(actual["actual"], 2),
            "remaining": round(limit - actual["actual"], 2),
            "pct_used": pct,
            "level": _level_for(pct, thr),
        })

    return {
        "year": year,
        "month": month,
        "thresholds": thr,
        "categories": categories,
    }


# ═════════════════════════════════════════════════════════════════════════════
# § Alerts (n8n WF-08, dedup via UNIQUE(year, month, category, level))
# ═════════════════════════════════════════════════════════════════════════════

def check_budget_alerts(
    ledger_db: str,
    budget_db: str,
    year: int,
    month: int,
    thresholds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Compute budget status and persist only NEW alerts (idempotent).

    A category-level pair is alerted once per (year, month, category, level);
    repeated calls (e.g. n8n WF-08 every hour) return no duplicates. Raising
    the limit lowers the level (no new key); lowering it escalates and emits
    a new alert.
    """
    status = build_budget_status(ledger_db, budget_db, year, month, thresholds)
    _ensure_alerts_db(budget_db)

    # Satu SELECT untuk semua kunci (year, month) — hindari N exists-check per jam.
    existing = Database.query(
        budget_db,
        "SELECT category, level FROM budget_alerts WHERE year = ? AND month = ?",
        (year, month),
    )
    seen = {(r["category"], r["level"]) for r in existing}

    new_alerts = []
    for c in status["categories"]:
        if c["level"] not in ("warn", "alert", "over"):
            continue
        if (c["category"], c["level"]) in seen:
            continue
        try:
            Database.execute(
                budget_db,
                "INSERT INTO budget_alerts (year, month, category, level, pct_used, actual, limit_amt)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (year, month, c["category"], c["level"], c["pct_used"], c["actual"], c["limit"]),
            )
        except Exception:
            continue  # UNIQUE(year,month,category,level) — sudah ada (race), skip
        seen.add((c["category"], c["level"]))
        new_alerts.append(c)

    return {"year": year, "month": month, "new_alerts": new_alerts}


def list_budget_alerts(budget_db: str, year: int, month: int) -> List[Dict[str, Any]]:
    """Alert history for (year, month), newest first."""
    _validate_month(year, month)
    _ensure_alerts_db(budget_db)
    rows = Database.query(
        budget_db,
        "SELECT year, month, category, level, pct_used, actual, limit_amt, created_at"
        " FROM budget_alerts WHERE year = ? AND month = ?"
        " ORDER BY created_at DESC, id DESC",
        (year, month),
    )
    return [
        {
            "category": r["category"],
            "level": r["level"],
            "pct_used": float(r["pct_used"] or 0),
            "actual": float(r["actual"] or 0),
            "limit": float(r["limit_amt"] or 0),
            "created_at": r["created_at"],
        }
        for r in rows
    ]
