"""
backend/finance/insights_service.py — AI Insights (Phase 13)
=============================================================
Insights are computed ONLY from verified backend data (the Phase 5-12
services) — an LLM may summarize/rephrase them, but it never invents
numbers. Each insight card carries its type, severity, an explanation with
the exact numbers, and the refs to the service/endpoint that produced it.

Cards (all deterministic):
  net_savings_rate   last-30d (income - expense) / income
  expense_trend      current month vs previous month (Phase 5 comparison)
  top_category       top expense category share of the month total
  recurring_load     confirmed recurring outflow vs monthly income (Phase 7)
  budget_pressure    categories over/alert/warn (Phase 6)
  anomaly_count      high/medium anomalies in the window (Phase 12)
  safe_to_spend      safe margin vs balance (Phase 10)
"""
from datetime import date, timedelta
from typing import Any, Dict, Optional

from packages.api.backend.finance.anomaly_service import detect_anomalies
from packages.api.backend.finance.budget_service import build_budget_status
from packages.api.backend.finance.forecast_service import _templates
from packages.api.backend.finance.report_service import build_report
from packages.api.backend.finance.safe_spend_service import build_safe_to_spend

SEVERITY_ORDER = {"alert": 0, "warning": 1, "info": 2, "positive": 3}


def _fmt(v: float) -> str:
    return f"Rp {v:,.0f}".replace(",", ".")


def _pct(v: float) -> str:
    return f"{v:+.1f}%"


def _net_savings_rate(ledger_db: str, today: date) -> Dict[str, Any]:
    start = today - timedelta(days=29)
    from packages.core.infrastructure.persistence.database import Database
    rows = Database.query(
        ledger_db,
        "SELECT type, SUM(amount) AS total FROM transactions"
        " WHERE type IN ('expense', 'income') AND tx_date >= ? AND tx_date <= ?"
        " GROUP BY type",
        (start.isoformat(), today.isoformat()),
    )
    totals = {r["type"]: float(r["total"] or 0) for r in rows}
    income = totals.get("income", 0.0)
    expense = totals.get("expense", 0.0)
    if income <= 0:
        severity, explanation = "info", "Belum ada pemasukan tercatat dalam 30 hari terakhir."
    else:
        rate = (income - expense) / income * 100.0
        if rate >= 20:
            severity, explanation = "positive", (
                f"Rasio tabungan 30 hari terakhir {rate:.0f}% — sehat "
                f"(pemasukan {_fmt(income)}, pengeluaran {_fmt(expense)})."
            )
        elif rate >= 0:
            severity, explanation = "info", (
                f"Rasio tabungan 30 hari terakhir {rate:.0f}% "
                f"(pemasukan {_fmt(income)}, pengeluaran {_fmt(expense)})."
            )
        else:
            severity, explanation = "warning", (
                f"Pengeluaran 30 hari terakhir ({_fmt(expense)}) MELEBIHI pemasukan "
                f"({_fmt(income)}) — defisit {_fmt(expense - income)}."
            )
    return {"type": "net_savings_rate", "severity": severity, "explanation": explanation,
            "refs": {"endpoint": "/api/reports?period=month"}}


def _expense_trend(ledger_db: str, today: date) -> Dict[str, Any]:
    report = build_report(ledger_db, period="month", as_of=today)
    pct = report["comparison"]["expense_pct"]
    prev = report["previous"]["expense"]
    cur = report["totals"]["expense"]
    if pct is None or prev <= 0:
        return {"type": "expense_trend", "severity": "info",
                "explanation": "Belum ada data bulan sebelumnya untuk perbandingan.",
                "refs": {"endpoint": "/api/reports?period=month"}}
    if pct >= 20:
        severity = "warning"
        explanation = f"Pengeluaran bulan ini {_pct(pct)} vs bulan lalu ({_fmt(prev)} -> {_fmt(cur)})."
    elif pct <= -10:
        severity = "positive"
        explanation = f"Pengeluaran turun {_pct(pct)} vs bulan lalu ({_fmt(prev)} -> {_fmt(cur)})."
    else:
        severity = "info"
        explanation = f"Pengeluaran stabil {_pct(pct)} vs bulan lalu ({_fmt(prev)} -> {_fmt(cur)})."
    return {"type": "expense_trend", "severity": severity, "explanation": explanation,
            "refs": {"endpoint": "/api/reports?period=month"}}


def _top_category(ledger_db: str, today: date) -> Dict[str, Any]:
    report = build_report(ledger_db, period="month", as_of=today)
    total = report["totals"]["expense"]
    if total <= 0 or not report["top_categories"]:
        return {"type": "top_category", "severity": "info",
                "explanation": "Belum ada pengeluaran bulan ini.",
                "refs": {"endpoint": "/api/reports?period=month"}}
    top = report["top_categories"][0]
    share = top["total"] / total * 100.0
    if share >= 40:
        severity = "warning"
        explanation = (
            f"Kategori {top['name']} mendominasi {share:.0f}% dari total pengeluaran "
            f"({_fmt(top['total'])} dari {_fmt(total)})."
        )
    else:
        severity = "info"
        explanation = (
            f"Kategori terbesar bulan ini: {top['name']} "
            f"({share:.0f}% dari {_fmt(total)})."
        )
    return {"type": "top_category", "severity": severity, "explanation": explanation,
            "refs": {"endpoint": "/api/reports?period=month"}}


def _recurring_load(ledger_db: str, today: date) -> Dict[str, Any]:
    month_total = 0.0
    for tpl in _templates(ledger_db):
        if tpl["is_confirmed"] and tpl["tx_type"] == "expense":
            month_total += abs(tpl["amount"])
    if month_total <= 0:
        return {"type": "recurring_load", "severity": "info",
                "explanation": "Belum ada langganan rutin terkonfirmasi.",
                "refs": {"endpoint": "/api/recurring/candidates"}}
    report = build_report(ledger_db, period="month", as_of=today)
    income = report["totals"]["income"]
    if income <= 0:
        return {"type": "recurring_load", "severity": "info",
                "explanation": f"Beban langganan rutin {_fmt(month_total)}/bulan (pemasukan belum tercatat).",
                "refs": {"endpoint": "/api/recurring/candidates"}}
    share = month_total / income * 100.0
    severity = "warning" if share >= 50 else "info"
    return {
        "type": "recurring_load", "severity": severity,
        "explanation": (
            f"Langganan rutin terkonfirmasi {_fmt(month_total)}/bulan = {share:.0f}% dari pemasukan bulan ini."
        ),
        "refs": {"endpoint": "/api/recurring/candidates"},
    }


def _budget_pressure(ledger_db: str, budget_db: str, today: date) -> Dict[str, Any]:
    status = build_budget_status(ledger_db, budget_db, today.year, today.month)
    over = [c for c in status["categories"] if c["level"] == "over"]
    alert = [c for c in status["categories"] if c["level"] == "alert"]
    if over:
        names = ", ".join(c["category"] for c in over[:3])
        return {"type": "budget_pressure", "severity": "alert",
                "explanation": f"{len(over)} kategori MELAMPAUI limit: {names}.",
                "refs": {"endpoint": "/api/budget/status"}}
    if alert:
        names = ", ".join(c["category"] for c in alert[:3])
        return {"type": "budget_pressure", "severity": "warning",
                "explanation": f"{len(alert)} kategori mendekati limit: {names}.",
                "refs": {"endpoint": "/api/budget/status"}}
    return {"type": "budget_pressure", "severity": "positive",
            "explanation": "Semua kategori dalam batas budget.",
            "refs": {"endpoint": "/api/budget/status"}}


def _anomaly_count(ledger_db: str, today: date) -> Dict[str, Any]:
    result = detect_anomalies(ledger_db, as_of=today)
    high = [a for a in result["anomalies"] if a["severity"] == "high"]
    if high:
        names = ", ".join(f"{a['category']} ({a['ratio']:.1f}x)" for a in high[:3])
        return {"type": "anomaly_count", "severity": "alert",
                "explanation": f"{len(high)} anomali tinggi terdeteksi: {names}.",
                "refs": {"endpoint": "/api/anomalies/status"}}
    if result["anomalies"]:
        return {"type": "anomaly_count", "severity": "warning",
                "explanation": f"{len(result['anomalies'])} anomali sedang terdeteksi pada jendela 30 hari.",
                "refs": {"endpoint": "/api/anomalies/status"}}
    return {"type": "anomaly_count", "severity": "positive",
            "explanation": "Tidak ada anomali pengeluaran terdeteksi.",
            "refs": {"endpoint": "/api/anomalies/status"}}


def _safe_to_spend(ledger_db: str, today: date) -> Dict[str, Any]:
    result = build_safe_to_spend(ledger_db, horizon="month", buffer_pct=10.0, as_of=today)
    safe = result["safe_to_spend"]
    balance = result["current_balance"]
    if safe < 0:
        return {"type": "safe_to_spend", "severity": "alert",
                "explanation": f"Saldo aman bulan ini NEGATIF ({_fmt(safe)}) — pengeluaran mendatang melebihi saldo.",
                "refs": {"endpoint": "/api/safe-to-spend"}}
    if balance > 0 and safe / balance < 0.2:
        return {"type": "safe_to_spend", "severity": "warning",
                "explanation": f"Margin aman belanja tipis: {_fmt(safe)} dari saldo {_fmt(balance)} ({safe / balance:.0%}).",
                "refs": {"endpoint": "/api/safe-to-spend"}}
    return {"type": "safe_to_spend", "severity": "positive",
            "explanation": f"Saldo aman bulan ini {_fmt(safe)} dari saldo {_fmt(balance)}.",
            "refs": {"endpoint": "/api/safe-to-spend"}}


def build_insights(
    ledger_db: str,
    budget_db: str,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """Compute all insight cards from verified backend data only."""
    today = as_of or date.today()
    cards = [
        _net_savings_rate(ledger_db, today),
        _expense_trend(ledger_db, today),
        _top_category(ledger_db, today),
        _recurring_load(ledger_db, today),
        _budget_pressure(ledger_db, budget_db, today),
        _anomaly_count(ledger_db, today),
        _safe_to_spend(ledger_db, today),
    ]
    cards.sort(key=lambda c: SEVERITY_ORDER[c["severity"]])
    summary = {
        "alert": sum(1 for c in cards if c["severity"] == "alert"),
        "warning": sum(1 for c in cards if c["severity"] == "warning"),
        "positive": sum(1 for c in cards if c["severity"] == "positive"),
        "info": sum(1 for c in cards if c["severity"] == "info"),
    }
    return {"as_of": today.isoformat(), "summary": summary, "insights": cards}


# ═════════════════════════════════════════════════════════════════════════════
# § Telegram renderer
# ═════════════════════════════════════════════════════════════════════════════

def format_insights_text(result: Dict[str, Any]) -> str:
    s = result["summary"]
    lines = [
        "Wawasan Keuangan",
        f"As of: {result['as_of']}",
        f"Ringkasan: {s['alert']} alert, {s['warning']} warning, {s['info']} info, {s['positive']} positif",
    ]
    if not result["insights"]:
        lines.append("")
        lines.append("Belum ada data cukup untuk wawasan.")
        return "\n".join(lines)
    for card in result["insights"]:
        lines.append("")
        lines.append(f"[{card['severity'].upper()}] {card['explanation']}")
    return "\n".join(lines)
