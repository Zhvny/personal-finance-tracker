"""
Phase 5 — Report service (Daily / Weekly / Monthly Reports).

All numbers are computed from the canonical ledger (transactions table) through
the Database bridge — PostgreSQL canonical in production (per-active-profile
schema), SQLite only for hermetic unit tests. Transfers are excluded from
income/expense aggregates (they are balance-neutral).

build_report(db_path, period, as_of=None, top_n=5) -> dict with:
  totals / previous (income, expense, net cashflow)
  comparison  (period-over-period % change, None when base is zero)
  top_categories / top_income_categories / top_merchants
  largest_transactions
  trend       (daily buckets for week/month, hourly buckets for today)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from packages.core.infrastructure.persistence.database import Database

PERIODS = ("today", "week", "month")


class ReportError(Exception):
    """Raised for invalid report inputs."""


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _pct_change(current: float, previous: float) -> Optional[float]:
    """Period-over-period % change; None when the base period has no data."""
    if previous == 0:
        return None
    return (current - previous) / previous * 100.0


def _period_bounds(period: str, as_of: Optional[date] = None) -> Tuple[date, date]:
    """Inclusive [start, end] for the current period (to-date windows)."""
    as_of = as_of or date.today()
    if period == "today":
        return as_of, as_of
    if period == "week":
        return as_of - timedelta(days=6), as_of
    if period == "month":
        return as_of.replace(day=1), as_of
    raise ReportError(f"Unsupported period {period!r}; allowed: {sorted(PERIODS)}")


def _previous_bounds(period: str, as_of: Optional[date] = None) -> Tuple[date, date]:
    """Inclusive [start, end] of the immediately preceding equivalent window.

    today -> yesterday; week -> the 7 days before; month -> previous month
    with the same day-of-month cut (to-date), so comparisons are fair.
    """
    as_of = as_of or date.today()
    if period == "today":
        prev = as_of - timedelta(days=1)
        return prev, prev
    if period == "week":
        end = as_of - timedelta(days=7)
        return end - timedelta(days=6), end
    if period == "month":
        first = as_of.replace(day=1)
        prev_end = first - timedelta(days=1)  # last day of previous month
        prev_start = prev_end.replace(day=1)
        day_cut = min(as_of.day, prev_end.day)
        return prev_start, prev_start.replace(day=day_cut)
    raise ReportError(f"Unsupported period {period!r}; allowed: {sorted(PERIODS)}")


def _aggregate(db_path: str, start: date, end: date) -> Dict[str, float]:
    """Income / expense totals (transfers and investments excluded)."""
    rows = Database.query(
        db_path,
        """
        SELECT
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) AS expense
        FROM transactions
        WHERE tx_date BETWEEN ? AND ?
        """,
        (start.isoformat(), end.isoformat()),
    )
    row = rows[0] if rows else {}
    return {"income": _float(row.get("income")), "expense": _float(row.get("expense"))}


def _top_categories(db_path: str, start: date, end: date, kind: str, top_n: int) -> List[Dict[str, Any]]:
    rows = Database.query(
        db_path,
        """
        SELECT COALESCE(c.name, t.category, 'Lainnya') AS name,
               SUM(t.amount) AS total, COUNT(*) AS n
        FROM transactions t
        LEFT JOIN categories c ON c.id = t.category_id
        WHERE t.type = ? AND t.tx_date BETWEEN ? AND ?
        GROUP BY COALESCE(c.name, t.category)
        ORDER BY total DESC
        LIMIT ?
        """,
        (kind, start.isoformat(), end.isoformat(), top_n),
    )
    return [
        {"name": str(r.get("name") or "Lainnya"), "total": _float(r.get("total")), "count": int(r.get("n") or 0)}
        for r in rows
    ]


def _top_merchants(db_path: str, start: date, end: date, top_n: int) -> List[Dict[str, Any]]:
    rows = Database.query(
        db_path,
        """
        SELECT COALESCE(m.name, 'Tidak diketahui') AS name,
               SUM(t.amount) AS total, COUNT(*) AS n
        FROM transactions t
        LEFT JOIN merchants m ON m.id = t.merchant_id
        WHERE t.type = 'expense' AND t.tx_date BETWEEN ? AND ?
        GROUP BY COALESCE(m.name, 'Tidak diketahui')
        ORDER BY total DESC
        LIMIT ?
        """,
        (start.isoformat(), end.isoformat(), top_n),
    )
    return [
        {"name": str(r.get("name") or "Tidak diketahui"), "total": _float(r.get("total")), "count": int(r.get("n") or 0)}
        for r in rows
    ]


def _largest_transactions(db_path: str, start: date, end: date, top_n: int) -> List[Dict[str, Any]]:
    rows = Database.query(
        db_path,
        """
        SELECT t.id, t.type, t.amount, t.tx_date,
               COALESCE(m.name, t.description, 'Tidak diketahui') AS name
        FROM transactions t
        LEFT JOIN merchants m ON m.id = t.merchant_id
        WHERE t.type IN ('expense', 'income') AND t.tx_date BETWEEN ? AND ?
        ORDER BY t.amount DESC
        LIMIT ?
        """,
        (start.isoformat(), end.isoformat(), top_n),
    )
    return [
        {
            "id": int(r["id"]),
            "type": r["type"],
            "amount": _float(r.get("amount")),
            "date": str(r.get("tx_date") or "")[:10],
            "name": str(r.get("name") or "Tidak diketahui"),
        }
        for r in rows
    ]


def _daily_series(db_path: str, start: date, end: date) -> List[Dict[str, Any]]:
    """Daily buckets for the whole [start, end] window (zero-filled)."""
    rows = Database.query(
        db_path,
        """
        SELECT t.tx_date AS d, t.type, SUM(t.amount) AS total
        FROM transactions t
        WHERE t.type IN ('expense', 'income') AND t.tx_date BETWEEN ? AND ?
        GROUP BY t.tx_date, t.type
        """,
        (start.isoformat(), end.isoformat()),
    )
    per_day: Dict[str, Dict[str, float]] = {}
    for r in rows:
        day = str(r.get("d") or "")[:10]
        bucket = per_day.setdefault(day, {"income": 0.0, "expense": 0.0, "net": 0.0})
        amt = _float(r.get("total"))
        if r.get("type") == "income":
            bucket["income"] += amt
        else:
            bucket["expense"] += amt

    trend: List[Dict[str, Any]] = []
    cursor = start
    while cursor <= end:
        bucket = per_day.get(cursor.isoformat(), {"income": 0.0, "expense": 0.0, "net": 0.0})
        trend.append({
            "label": cursor.strftime("%d/%m"),
            "income": bucket["income"],
            "expense": bucket["expense"],
            "net": bucket["income"] - bucket["expense"],
        })
        cursor += timedelta(days=1)
    return trend


def _hourly_series(db_path: str, day: date) -> List[Dict[str, Any]]:
    """Hourly buckets (00:00 .. current hour) for a single day."""
    rows = Database.query(
        db_path,
        """
        SELECT t.type, t.amount, t.created_at
        FROM transactions t
        WHERE t.type IN ('expense', 'income') AND t.tx_date = ?
        """,
        (day.isoformat(),),
    )
    buckets: Dict[int, Dict[str, float]] = {}
    for r in rows:
        created = r.get("created_at")
        hour = 0
        if created:
            try:
                hour = int(str(created)[11:13])  # 'YYYY-MM-DD HH:MM:SS' / ISO
            except (TypeError, ValueError):
                hour = 0
        bucket = buckets.setdefault(hour, {"income": 0.0, "expense": 0.0})
        amt = _float(r.get("amount"))
        if r.get("type") == "income":
            bucket["income"] += amt
        else:
            bucket["expense"] += amt

    now = datetime.now()
    max_hour = now.hour if now.date() == day else 23
    trend: List[Dict[str, Any]] = []
    for hour in range(max_hour + 1):
        bucket = buckets.get(hour, {"income": 0.0, "expense": 0.0})
        trend.append({
            "label": f"{hour:02d}:00",
            "income": bucket["income"],
            "expense": bucket["expense"],
            "net": bucket["income"] - bucket["expense"],
        })
    return trend


def build_report(
    db_path: str,
    period: str = "month",
    as_of: Optional[date] = None,
    top_n: int = 5,
) -> Dict[str, Any]:
    """Compute a full report for the given period from the ledger."""
    period = (period or "").strip().lower()
    if period not in PERIODS:
        raise ReportError(f"Unsupported period {period!r}; allowed: {sorted(PERIODS)}")

    start, end = _period_bounds(period, as_of)
    prev_start, prev_end = _previous_bounds(period, as_of)

    totals = _aggregate(db_path, start, end)
    previous = _aggregate(db_path, prev_start, prev_end)
    net = totals["income"] - totals["expense"]
    prev_net = previous["income"] - previous["expense"]

    return {
        "period": period,
        "as_of": (as_of or date.today()).isoformat(),
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "previous_range": {"start": prev_start.isoformat(), "end": prev_end.isoformat()},
        "totals": {"income": totals["income"], "expense": totals["expense"], "net": net},
        "previous": {"income": previous["income"], "expense": previous["expense"], "net": prev_net},
        "comparison": {
            "income_pct": _pct_change(totals["income"], previous["income"]),
            "expense_pct": _pct_change(totals["expense"], previous["expense"]),
            "net_pct": _pct_change(net, prev_net),
        },
        "top_categories": _top_categories(db_path, start, end, "expense", top_n),
        "top_income_categories": _top_categories(db_path, start, end, "income", top_n),
        "top_merchants": _top_merchants(db_path, start, end, top_n),
        "largest_transactions": _largest_transactions(db_path, start, end, top_n),
        "trend": _hourly_series(db_path, end) if period == "today" else _daily_series(db_path, start, end),
    }
