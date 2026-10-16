"""
backend/finance/health_score_service.py — Behavioral Health Score (Phase 14)
==============================================================================
Explainable composite health score (0-100) computed ONLY from verified
backend data — every component is a Phase 5-13 service result carrying its
own explanation; the composite is a weighted sum with published weights.

Components:
  savings_rate   30  — 30-day (income - expense)/income; >=20% → 100
  budget_habits  20  — over → 0; alert-level → 50; all within → 100
  anomaly_safety 15  — high anomaly → 0; medium → 50; none → 100
  safe_spend     15  — safe<0 → 0; margin >=20% of balance → 100
  recurring_load 10  — confirmed recurring outflow share >=50% → 0
  trend_stability 10 — expense +20% → 0; <=0% → 100

Grade: >=80 Sehat, 60-79 Cukup, 40-59 Perlu Perhatian, <40 Kritis.
"""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from packages.api.backend.finance.anomaly_service import detect_anomalies
from packages.api.backend.finance.budget_service import build_budget_status
from packages.api.backend.finance.forecast_service import _templates
from packages.api.backend.finance.report_service import build_report
from packages.api.backend.finance.safe_spend_service import build_safe_to_spend
from packages.core.infrastructure.persistence.database import Database

WEIGHTS = {
    "savings_rate": 30,
    "budget_habits": 20,
    "anomaly_safety": 15,
    "safe_spend": 15,
    "recurring_load": 10,
    "trend_stability": 10,
}

GRADES = [
    (80, "Sehat"),
    (60, "Cukup"),
    (40, "Perlu Perhatian"),
    (0, "Kritis"),
]


def _fmt(v: float) -> str:
    return f"Rp {v:,.0f}".replace(",", ".")


def _score_savings_rate(ledger_db: str, today: date) -> Dict[str, Any]:
    start = today - timedelta(days=29)
    rows = Database.query(
        ledger_db,
        "SELECT type, SUM(amount) AS total FROM transactions"
        " WHERE type IN ('expense', 'income') AND tx_date >= ? AND tx_date <= ?"
        " GROUP BY type",
        (start.isoformat(), today.isoformat()),
    )
    totals = {r["type"]: float(r["total"] or 0) for r in rows}
    income, expense = totals.get("income", 0.0), totals.get("expense", 0.0)
    if income <= 0:
        return {"key": "savings_rate", "score": 0,
                "explanation": "Belum ada pemasukan dalam 30 hari terakhir — tidak ada tabungan terbentuk."}
    rate = (income - expense) / income * 100.0
    if rate >= 20:
        score = 100
    elif rate >= 0:
        score = round(rate / 20 * 100)
    else:
        score = 0
    return {"key": "savings_rate", "score": score,
            "explanation": (f"Rasio tabungan 30 hari {rate:.0f}% (pemasukan {_fmt(income)}, "
                            f"pengeluaran {_fmt(expense)}).")}


def _score_budget_habits(ledger_db: str, budget_db: str, today: date) -> Dict[str, Any]:
    status = build_budget_status(ledger_db, budget_db, today.year, today.month)
    over = [c for c in status["categories"] if c["level"] == "over"]
    alert = [c for c in status["categories"] if c["level"] == "alert"]
    if over:
        score, detail = 0, f"{len(over)} kategori melampaui limit: {', '.join(c['category'] for c in over[:3])}."
    elif alert:
        score, detail = 50, f"{len(alert)} kategori mendekati limit: {', '.join(c['category'] for c in alert[:3])}."
    else:
        score, detail = 100, "Semua kategori dalam batas budget."
    return {"key": "budget_habits", "score": score, "explanation": detail}


def _score_anomaly_safety(ledger_db: str, today: date) -> Dict[str, Any]:
    result = detect_anomalies(ledger_db, as_of=today)
    high = [a for a in result["anomalies"] if a["severity"] == "high"]
    if high:
        score = 0
        detail = (f"{len(high)} anomali tinggi terdeteksi: "
                  f"{', '.join(f'{a['category']} ({a['ratio']:.1f}x)' for a in high[:3])}.")
    elif result["anomalies"]:
        score = 50
        detail = f"{len(result['anomalies'])} anomali sedang terdeteksi pada jendela 30 hari."
    else:
        score = 100
        detail = "Tidak ada anomali pengeluaran terdeteksi."
    return {"key": "anomaly_safety", "score": score, "explanation": detail}


def _score_safe_spend(ledger_db: str, today: date) -> Dict[str, Any]:
    result = build_safe_to_spend(ledger_db, horizon="month", buffer_pct=10.0, as_of=today)
    safe, balance = result["safe_to_spend"], result["current_balance"]
    if safe < 0:
        return {"key": "safe_spend", "score": 0,
                "explanation": f"Saldo aman bulan ini negatif ({_fmt(safe)})."}
    if balance <= 0:
        return {"key": "safe_spend", "score": 0,
                "explanation": "Saldo saat ini tidak positif — tidak ada ruang belanja aman."}
    margin = safe / balance
    score = 100 if margin >= 0.2 else round(margin / 0.2 * 100)
    return {"key": "safe_spend", "score": score,
            "explanation": (f"Margin aman belanja {margin:.0%} dari saldo "
                            f"{_fmt(balance)} (aman {_fmt(safe)}).")}


def _score_recurring_load(ledger_db: str, today: date) -> Dict[str, Any]:
    month_total = 0.0
    for tpl in _templates(ledger_db):
        if tpl["is_confirmed"] and tpl["tx_type"] == "expense":
            month_total += abs(tpl["amount"])
    if month_total <= 0:
        return {"key": "recurring_load", "score": 100,
                "explanation": "Belum ada langganan rutin terkonfirmasi."}
    report = build_report(ledger_db, period="month", as_of=today)
    income = report["totals"]["income"]
    if income <= 0:
        return {"key": "recurring_load", "score": 50,
                "explanation": f"Beban langganan rutin {_fmt(month_total)}/bulan, pemasukan bulan ini belum tercatat."}
    share = month_total / income * 100.0
    score = 0 if share >= 50 else round((50 - share) / 50 * 100)
    return {"key": "recurring_load", "score": score,
            "explanation": (f"Langganan rutin {_fmt(month_total)}/bulan = {share:.0f}% "
                            f"dari pemasukan {_fmt(income)}.")}


def _score_trend_stability(ledger_db: str, today: date) -> Dict[str, Any]:
    report = build_report(ledger_db, period="month", as_of=today)
    pct = report["comparison"]["expense_pct"]
    if pct is None:
        return {"key": "trend_stability", "score": 100,
                "explanation": "Belum ada data bulan sebelumnya untuk perbandingan."}
    if pct <= 0:
        score = 100
    elif pct >= 20:
        score = 0
    else:
        score = round((20 - pct) / 20 * 100)
    return {"key": "trend_stability", "score": score,
            "explanation": f"Pengeluaran bulan ini {pct:+.1f}% vs bulan lalu."}


def build_health_score(
    ledger_db: str,
    budget_db: str,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """Composite, explainable health score from verified data only."""
    today = as_of or date.today()
    builders = {
        "savings_rate": lambda: _score_savings_rate(ledger_db, today),
        "budget_habits": lambda: _score_budget_habits(ledger_db, budget_db, today),
        "anomaly_safety": lambda: _score_anomaly_safety(ledger_db, today),
        "safe_spend": lambda: _score_safe_spend(ledger_db, today),
        "recurring_load": lambda: _score_recurring_load(ledger_db, today),
        "trend_stability": lambda: _score_trend_stability(ledger_db, today),
    }
    components: List[Dict[str, Any]] = []
    total = 0.0
    for key, builder in builders.items():
        comp = builder()
        comp["weight"] = WEIGHTS[key]
        total += comp["score"] * comp["weight"] / 100.0
        components.append(comp)
    total_score = round(total)
    grade = next(label for threshold, label in GRADES if total_score >= threshold)
    return {
        "as_of": today.isoformat(),
        "total_score": total_score,
        "grade": grade,
        "components": components,
        "weights": WEIGHTS,
    }


# ═════════════════════════════════════════════════════════════════════════════
# § Telegram renderer
# ═════════════════════════════════════════════════════════════════════════════

def format_health_score_text(result: Dict[str, Any]) -> str:
    lines = [
        "Skor Kesehatan Keuangan",
        f"Skor: {result['total_score']}/100 ({result['grade']})",
        f"As of: {result['as_of']}",
    ]
    for comp in result["components"]:
        lines.append("")
        lines.append(f"[{comp['score']:3d}/100 | bobot {comp['weight']}] {comp['explanation']}")
    return "\n".join(lines)
