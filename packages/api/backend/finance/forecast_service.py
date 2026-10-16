"""
backend/finance/forecast_service.py — Deterministic cashflow forecast (Phase 9)
================================================================================
Canonical-ledger forecast with a fully transparent breakdown. No SMA or
statistical projection: every future day is composed of labeled components.

  Known      — actual ledger transactions (today's net; nothing future-dated
               can exist in the ledger)
  Expected   — confirmed recurring templates (Phase 7) with a due date in the
               window (period already covered by a real transaction is skipped)
  Estimated  — unconfirmed recurring candidates due in the window (user has
               not verified them yet — flagged as less reliable)
  Forecast   — the composite net = known + expected + estimated

Reasoning is surfaced to Telegram (labels, sources, and a warning when the
projected cumulative balance dips below zero, with the earliest date).
"""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from packages.api.backend.finance.period_utils import period_covered as _period_covered
from packages.core.infrastructure.persistence.database import Database

MAX_DAYS = 90
MIN_DAYS = 1


class ForecastError(Exception):
    """Invalid forecast request (bad days window, ...)."""


def _validate_days(days: Any) -> int:
    try:
        value = int(days)
    except (TypeError, ValueError):
        raise ForecastError("days harus berupa angka") from None
    if not (MIN_DAYS <= value <= MAX_DAYS):
        raise ForecastError(f"days harus antara {MIN_DAYS} dan {MAX_DAYS}")
    return value


def _signed_amount(tx_type: str, amount: float) -> float:
    return -abs(amount) if tx_type == "expense" else abs(amount)


def _start_balance(ledger_db: str, as_of: date) -> float:
    rows = Database.query(
        ledger_db,
        "SELECT type, SUM(amount) AS total FROM transactions"
        " WHERE type IN ('expense', 'income') AND tx_date < ?"
        " GROUP BY type",
        (as_of.isoformat(),),
    )
    totals = {r["type"]: float(r["total"] or 0) for r in rows}
    return round(totals.get("income", 0.0) - totals.get("expense", 0.0), 2)


def _known_by_day(ledger_db: str, start: date, end: date) -> Dict[str, float]:
    rows = Database.query(
        ledger_db,
        "SELECT type, amount, tx_date FROM transactions"
        " WHERE type IN ('expense', 'income') AND tx_date >= ? AND tx_date <= ?",
        (start.isoformat(), end.isoformat()),
    )
    per_day: Dict[str, float] = {}
    for r in rows:
        key = str(r["tx_date"])[:10]
        per_day[key] = per_day.get(key, 0.0) + _signed_amount(r["type"], float(r["amount"] or 0))
    return {k: round(v, 2) for k, v in per_day.items()}


def _templates(ledger_db: str) -> List[Dict[str, Any]]:
    try:
        rows = Database.query(
            ledger_db,
            "SELECT * FROM recurrence_candidates",
        )
    except Exception:  # noqa: BLE001 — table not yet created by WF-09
        return []
    return [
        {
            "id": r["id"],
            "tx_type": r["tx_type"],
            "category": r["category"],
            "description": r["description"],
            "amount": float(r["amount"] or 0),
            "frequency": r["frequency"],
            "day_of_week": r["day_of_week"],
            "day_of_month": r["day_of_month"],
            "confidence": float(r["confidence"] or 0),
            "is_confirmed": bool(r["is_confirmed"]),
        }
        for r in rows
    ]


def _due_dates_in_window(template: Dict[str, Any], start: date, end: date) -> List[date]:
    due: List[date] = []
    if template["frequency"] == "weekly":
        weekday = template["day_of_week"]
        if weekday is None:
            return []
        cursor = start
        while cursor <= end:
            if cursor.weekday() == weekday:
                due.append(cursor)
            cursor += timedelta(days=1)
        return due

    day = template["day_of_month"]
    if day is None:
        return []
    year, month = start.year, start.month
    while True:
        try:
            candidate = date(year, month, day)
        except ValueError:
            candidate = None
        if candidate is not None:
            if candidate > end:
                break
            if candidate >= start:
                due.append(candidate)
        if month == 12:
            month, year = 1, year + 1
        else:
            month += 1
        if (year, month) > (end.year, end.month):
            break
    return due


def build_cashflow_forecast(
    ledger_db: str,
    days: Any = 30,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """Deterministic forecast: labeled daily breakdown + transparent sources."""
    horizon = _validate_days(days)
    today = as_of or date.today()
    window_start = today
    window_end = today + timedelta(days=horizon - 1)

    known_by_day = _known_by_day(ledger_db, window_start, window_end)
    templates = _templates(ledger_db)

    daily: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []
    totals = {"known": 0.0, "expected": 0.0, "estimated": 0.0}

    for offset in range(horizon):
        day = window_start + timedelta(days=offset)
        day_known = known_by_day.get(day.isoformat(), 0.0)
        day_expected = 0.0
        day_estimated = 0.0
        for tpl in templates:
            if day not in _due_dates_in_window(tpl, day, day):
                continue
            if day == today and _period_covered(
                ledger_db, tpl, day, today
            ):
                continue
            amount = _signed_amount(tpl["tx_type"], tpl["amount"])
            if tpl["is_confirmed"]:
                day_expected += amount
                label = "Expected"
            else:
                day_estimated += amount
                label = "Estimated"
            sources.append({
                "label": label,
                "description": tpl["description"],
                "category": tpl["category"],
                "amount": round(amount, 2),
                "due_date": day.isoformat(),
                "frequency": tpl["frequency"],
                "confidence": tpl["confidence"],
            })
        day_expected = round(day_expected, 2)
        day_estimated = round(day_estimated, 2)
        totals["known"] += day_known
        totals["expected"] += day_expected
        totals["estimated"] += day_estimated
        daily.append({
            "date": day.isoformat(),
            "known": day_known,
            "expected": day_expected,
            "estimated": day_estimated,
            "net": round(day_known + day_expected + day_estimated, 2),
        })

    totals = {k: round(v, 2) for k, v in totals.items()}
    totals["forecast"] = round(sum(totals.values()), 2)

    start_balance = _start_balance(ledger_db, today)
    cumulative = start_balance
    low_point = None
    low_date = None
    for entry in daily:
        cumulative = round(cumulative + entry["net"], 2)
        entry["cumulative"] = cumulative
        if low_point is None or cumulative < low_point:
            low_point = cumulative
            low_date = entry["date"]

    insight = None
    if low_point is not None and low_point < 0:
        insight = {
            "warning": True,
            "message_id": f"Saldo diproyeksikan minus (Rp {low_point:,.0f}) pada {low_date}",
            "low_date": low_date,
            "low_point": low_point,
        }
    elif totals["forecast"] >= 0:
        insight = {"warning": False, "message_id": "Saldo diproyeksikan aman dalam jendela ini"}

    return {
        "as_of": today.isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "days": horizon,
        "start_balance": start_balance,
        "totals": totals,
        "daily": daily,
        "sources": sources,
        "insight": insight,
    }


# ═════════════════════════════════════════════════════════════════════════════
# § Telegram renderer (reasoning surfaced in chat)
# ═════════════════════════════════════════════════════════════════════════════

def format_forecast_text(result: Dict[str, Any]) -> str:
    def fmt(v):
        return f"Rp {abs(v):,.0f}".replace(",", ".") + (" minus" if v < 0 else "")

    totals = result["totals"]
    lines = [
        "Proyeksi Arus Kas",
        f"Jendela: {result['window_start']} s/d {result['window_end']} ({result['days']} hari)",
        f"Saldo awal: {fmt(result['start_balance'])}",
        "",
        "Rincian transparan:",
        f"- Known (transaksi nyata): {fmt(totals['known'])}",
        f"- Expected (langganan terkonfirmasi): {fmt(totals['expected'])}",
        f"- Estimated (pola belum dikonfirmasi): {fmt(totals['estimated'])}",
        f"- Forecast (net jendela): {fmt(totals['forecast'])}",
    ]
    if result["sources"]:
        lines.append("")
        lines.append("Sumber:")
        for s in result["sources"][:10]:
            label = {"Expected": "E", "Estimated": "?"}.get(s["label"], s["label"])
            lines.append(
                f"- [{label}] {s['description'] or s['category']} "
                f"{fmt(s['amount'])} ({s['due_date']})"
            )
        if len(result["sources"]) > 10:
            lines.append(f"- ... dan {len(result['sources']) - 10} sumber lain")
    if result.get("insight"):
        lines.append("")
        lines.append(result["insight"]["message_id"])
    return "\n".join(lines)
