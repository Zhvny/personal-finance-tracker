"""
backend/finance/safe_spend_service.py — Safe-to-Spend (Phase 10)
=================================================================
Deterministic, fully transparent answer to "how much can I safely spend?":

  safe_to_spend = current_balance
                  - upcoming_outflows (Expected + Estimated expense
                    templates due within the horizon)
                  - safety_buffer (buffer_pct % of current balance)

Reuses the Phase 9 forecast machinery so the reasoning (labeled
Expected/Estimated sources, due dates, buffer) can be surfaced verbatim in
Telegram. Safe-to-spend is recomputed on demand; nothing is stored.
"""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from packages.api.backend.finance.forecast_service import (
    _due_dates_in_window,
    _signed_amount,
    _templates,
)
from packages.core.infrastructure.persistence.database import Database

HORIZONS = {"today": 1, "week": 7, "month": 30}


class SafeSpendError(Exception):
    """Invalid safe-to-spend request (bad horizon, buffer, ...)."""


def _validate_buffer_pct(value: Any) -> float:
    try:
        pct = float(value)
    except (TypeError, ValueError):
        raise SafeSpendError("buffer_pct harus berupa angka") from None
    if not (0.0 <= pct <= 50.0):
        raise SafeSpendError("buffer_pct harus antara 0 dan 50")
    return pct


def _horizon_days(horizon: Any) -> int:
    if isinstance(horizon, str) and horizon.strip().lower() in HORIZONS:
        return HORIZONS[horizon.strip().lower()]
    try:
        days = int(horizon)
    except (TypeError, ValueError):
        raise SafeSpendError("horizon harus 'today', 'week', 'month', atau jumlah hari") from None
    if not (1 <= days <= 90):
        raise SafeSpendError("horizon harus antara 1 dan 90 hari")
    return days


def _balance_now(ledger_db: str, as_of: date) -> float:
    rows = Database.query(
        ledger_db,
        "SELECT type, SUM(amount) AS total FROM transactions"
        " WHERE type IN ('expense', 'income') AND tx_date <= ?"
        " GROUP BY type",
        (as_of.isoformat(),),
    )
    totals = {r["type"]: float(r["total"] or 0) for r in rows}
    return round(totals.get("income", 0.0) - totals.get("expense", 0.0), 2)


def build_safe_to_spend(
    ledger_db: str,
    horizon: Any = "month",
    buffer_pct: Any = 10.0,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """Compute safe-to-spend with a fully transparent breakdown."""
    days = _horizon_days(horizon)
    buffer = _validate_buffer_pct(buffer_pct)
    today = as_of or date.today()
    window_end = today + timedelta(days=days)

    balance = _balance_now(ledger_db, today)
    upcoming: List[Dict[str, Any]] = []
    expected_total = 0.0
    estimated_total = 0.0

    for tpl in _templates(ledger_db):
        amount = _signed_amount(tpl["tx_type"], tpl["amount"])
        if amount >= 0:
            continue  # only outflows reduce what is safe to spend
        due_dates = _due_dates_in_window(tpl, today + timedelta(days=1), window_end)
        for due in due_dates:
            if tpl["is_confirmed"]:
                expected_total += amount
                label = "Expected"
            else:
                estimated_total += amount
                label = "Estimated"
            upcoming.append({
                "label": label,
                "description": tpl["description"],
                "category": tpl["category"],
                "amount": round(amount, 2),
                "due_date": due.isoformat(),
                "frequency": tpl["frequency"],
                "confidence": tpl["confidence"],
            })

    expected_total = round(expected_total, 2)
    estimated_total = round(estimated_total, 2)
    upcoming_outflows = round(expected_total + estimated_total, 2)  # negative
    buffer_amount = round(balance * buffer / 100.0, 2)
    safe = round(balance + upcoming_outflows - buffer_amount, 2)

    if safe >= 0:
        insight = {
            "warning": False,
            "message_id": f"Kamu bisa belanja hingga Rp {abs(safe):,.0f} dengan aman dalam {days} hari ke depan.",
            "safe_to_spend": safe,
        }
    else:
        insight = {
            "warning": True,
            "message_id": (
                f"Saldo tidak cukup: pengeluaran mendatang (Rp {abs(upcoming_outflows):,.0f}) "
                f"melebihi saldo aman sebesar Rp {abs(safe):,.0f}. Kurangi pengeluaran atau tunda "
                f"pembelian besar."
            ),
            "safe_to_spend": safe,
        }

    return {
        "as_of": today.isoformat(),
        "horizon_days": days,
        "window_end": window_end.isoformat(),
        "current_balance": balance,
        "expected_outflows": expected_total,
        "estimated_outflows": estimated_total,
        "upcoming_outflows": upcoming_outflows,
        "buffer_pct": buffer,
        "buffer_amount": buffer_amount,
        "safe_to_spend": safe,
        "sources": upcoming,
        "insight": insight,
    }


# ═════════════════════════════════════════════════════════════════════════════
# § Telegram renderer (reasoning surfaced in chat)
# ═════════════════════════════════════════════════════════════════════════════

def format_safe_to_spend_text(result: Dict[str, Any]) -> str:
    def fmt(v):
        return f"Rp {abs(v):,.0f}".replace(",", ".")

    lines = [
        "Aman Belanja",
        f"Horizon: {result['horizon_days']} hari (s/d {result['window_end']})",
        f"Saldo saat ini: {fmt(result['current_balance'])}",
        f"Pengeluaran mendatang (Expected): {fmt(result['expected_outflows'])}",
        f"Pengeluaran mendatang (Estimated): {fmt(result['estimated_outflows'])}",
        f"Buffer aman ({result['buffer_pct']:.0f}%): {fmt(result['buffer_amount'])}",
        f"Safe-to-spend: {fmt(result['safe_to_spend'])}",
    ]
    if result["sources"]:
        lines.append("")
        lines.append("Sumber pengeluaran:")
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
