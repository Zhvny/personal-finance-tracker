"""
backend/finance/net_worth_service.py — Net Worth Integration (Phase 15)
=======================================================================
Consistent aggregation everywhere: TRANSFERS NEVER CHANGE NET WORTH.

  cash_assets    = sum of per-account balances (account_balance is
                   transfer_pairs-aware: direction-aware, net-neutral)
  investments    = legacy portfolio positions at latest prices
                   (absent/missing table -> 0, no crash)
  net_worth      = cash_assets + investments

`transfers_transparent` re-derives cash independently as
(income - expense) all-time and compares — both must agree, which proves
transfers did not distort the number. History reuses the same cumulative
(income - expense) series; transfers are excluded by construction.
"""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from packages.api.backend.finance.ledger_engine import (
    account_balance,
    list_accounts,
)
from packages.core.infrastructure.persistence.database import Database


def _cash_snapshot(ledger_db: str, as_of: date) -> Dict[str, Any]:
    accounts = list_accounts(ledger_db, include_inactive=True)
    per_account = []
    total = 0.0
    for acc in accounts:
        bal = account_balance(ledger_db, acc["id"], as_of=as_of)
        per_account.append({"account_id": acc["id"], "name": acc["name"], "balance": round(bal, 2)})
        total += bal
    return {"per_account": per_account, "cash_total": round(total, 2)}


def _income_minus_expense(ledger_db: str, as_of: date) -> float:
    rows = Database.query(
        ledger_db,
        "SELECT type, SUM(amount) AS total FROM transactions"
        " WHERE type IN ('expense', 'income') AND tx_date <= ?"
        " GROUP BY type",
        (as_of.isoformat(),),
    )
    totals = {r["type"]: float(r["total"] or 0) for r in rows}
    return round(totals.get("income", 0.0) - totals.get("expense", 0.0), 2)


def _investment_value(investment_db: Optional[str], as_of: date) -> float:
    """Portfolio positions at latest prices (deterministic snapshot).

    Missing table/db -> 0.0. Uses the same convention as the legacy
    behavioral report: remaining_quantity x latest historical price,
    falling back to buy_price when no price is recorded yet.
    """
    if not investment_db:
        return 0.0
    try:
        rows = Database.query(
            investment_db,
            "SELECT i.remaining_quantity, i.quantity, i.buy_price,"
            " (SELECT h.price_idr FROM historical_prices h"
            "   WHERE h.investment_id = i.id ORDER BY h.id DESC LIMIT 1) AS price_idr"
            " FROM investments i WHERE i.status != ?",
            ("sold",),
        )
    except Exception:
        return 0.0
    total = 0.0
    for r in rows:
        qty = r["remaining_quantity"] if r["remaining_quantity"] is not None else r["quantity"]
        price = r["price_idr"] if r["price_idr"] is not None else r["buy_price"]
        if qty is not None and price is not None:
            total += float(qty) * float(price)
    return round(total, 2)


def build_net_worth(
    ledger_db: str,
    investment_db: Optional[str] = None,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """Net worth with a transfer-neutrality proof and full breakdown."""
    today = as_of or date.today()
    cash = _cash_snapshot(ledger_db, today)
    independent = _income_minus_expense(ledger_db, today)
    investments = _investment_value(investment_db, today)
    return {
        "as_of": today.isoformat(),
        "cash_assets": cash["cash_total"],
        "per_account": cash["per_account"],
        "investments": investments,
        "net_worth": round(cash["cash_total"] + investments, 2),
        "transfers_transparent": abs(cash["cash_total"] - independent) < 0.01,
        "income_minus_expense": independent,
    }


def net_worth_history(
    ledger_db: str,
    investment_db: Optional[str] = None,
    days: int = 90,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """Daily cumulative net worth over the last `days` days.

    Cash uses cumulative (income - expense) — transfers excluded by
    construction. Investment value is the latest snapshot carried through
    the series (documented approximation: historical daily prices are not
    guaranteed in the legacy bridge DB).
    """
    if not (1 <= int(days) <= 365):
        days = 90
    today = as_of or date.today()
    start = today - timedelta(days=int(days) - 1)
    rows = Database.query(
        ledger_db,
        "SELECT tx_date, type, amount FROM transactions"
        " WHERE type IN ('expense', 'income') AND tx_date >= ? AND tx_date <= ?"
        " ORDER BY tx_date ASC",
        (start.isoformat(), today.isoformat()),
    )
    by_day: Dict[str, float] = {}
    for r in rows:
        sign = 1.0 if r["type"] == "income" else -1.0
        by_day[r["tx_date"]] = by_day.get(r["tx_date"], 0.0) + float(r["amount"]) * sign
    base = _income_minus_expense(ledger_db, start - timedelta(days=1))
    inv = _investment_value(investment_db, today)
    series: List[Dict[str, Any]] = []
    cumulative = base
    d = start
    while d <= today:
        cumulative += by_day.get(d.isoformat(), 0.0)
        cash = round(cumulative, 2)
        series.append({
            "date": d.isoformat(),
            "cash_assets": cash,
            "investments": inv,
            "net_worth": round(cash + inv, 2),
        })
        d += timedelta(days=1)
    return {
        "as_of": today.isoformat(),
        "days": int(days),
        "series": series,
        "latest": series[-1],
    }


# ═════════════════════════════════════════════════════════════════════════════
# § Telegram renderer
# ═════════════════════════════════════════════════════════════════════════════

def format_net_worth_text(result: Dict[str, Any]) -> str:
    def fmt(v):
        return f"Rp {v:,.0f}".replace(",", ".")

    lines = [
        "Kekayaan Bersih",
        f"As of: {result['as_of']}",
        f"Kas (semua rekening): {fmt(result['cash_assets'])}",
    ]
    for acc in result["per_account"]:
        lines.append(f"- {acc['name']}: {fmt(acc['balance'])}")
    lines.append(f"Investasi: {fmt(result['investments'])}")
    lines.append(f"Kekayaan bersih: {fmt(result['net_worth'])}")
    lines.append("")
    lines.append(
        "Catatan: transfer antar rekening tidak mengubah total kekayaan"
        if result["transfers_transparent"]
        else "PERINGATAN: total kas tidak konsisten dengan pemasukan - pengeluaran."
    )
    return "\n".join(lines)
