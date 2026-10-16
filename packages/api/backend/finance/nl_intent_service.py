"""
backend/finance/nl_intent_service.py — NL Finance Query (Phase 11)
==================================================================
Intent detection → controlled endpoints. The backend computes; the
explanation layer ("AI explains") renders the computed result in plain
Indonesian with the reasoning surfaced — no LLM in the compute path, so
answers are deterministic and verifiable.

Supported intents:
  GET_BALANCE        saldo / uang / rekening + question marker
  GET_SAFE_TO_SPEND  aman belanja / sisa aman / safe to spend
  GET_FORECAST       proyeksi / prediksi / arus kas / cashflow
  GET_REPORT         laporan (hari ini / minggu ini / bulan ini)
  GET_BUDGET_STATUS  budget / limit / sisa budget
  GET_RECENT         transaksi terakhir / riwayat

Each intent maps to a Phase 5-10 service so the numbers are identical to
what the dedicated commands/APIs would produce.
"""
import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from packages.api.backend.finance.anomaly_service import (
    AnomalyError,
    detect_anomalies,
)
from packages.api.backend.finance.budget_service import build_budget_status
from packages.api.backend.finance.forecast_service import (
    ForecastError,
    build_cashflow_forecast,
)
from packages.api.backend.finance.ledger_engine import (
    account_balance,
    list_accounts,
    list_transactions,
)
from packages.api.backend.finance.report_service import build_report
from packages.api.backend.finance.safe_spend_service import (
    SafeSpendError,
    build_safe_to_spend,
)

_INTENTS: List[Tuple[str, List[re.Pattern], List[str]]] = [
    (
        "GET_BALANCE",
        [
            re.compile(r"\b(?:berapa|cek|lihat|total|sisa)\s+(?:saldo|uang|balance|rekening)\b", re.IGNORECASE),
            re.compile(r"\b(?:saldo|uang|balance|rekening)\s+(?:saya|aku|berapaku|berapa)\b", re.IGNORECASE),
            re.compile(r"^cek\s+(?:saldo|uang|balance)$", re.IGNORECASE),
        ],
        [],
    ),
    (
        "GET_SAFE_TO_SPEND",
        [
            re.compile(r"\b(?:aman|sisa|boleh)\s+belanja\b", re.IGNORECASE),
            re.compile(r"\bsisa\s+aman\b", re.IGNORECASE),
            re.compile(r"\bsafe\s+to\s+spend\b", re.IGNORECASE),
            re.compile(r"\b(?:uang|saldo)\s+aman\b", re.IGNORECASE),
            re.compile(r"\baman\s+dibelanjakan\b", re.IGNORECASE),
        ],
        ["days"],
    ),
    (
        "GET_FORECAST",
        [
            re.compile(r"\b(?:proyeksi|prediksi|forecast)\b", re.IGNORECASE),
            re.compile(r"\b(?:arus\s+kas|cash\s*flow|cashflow)\b", re.IGNORECASE),
        ],
        ["days"],
    ),
    (
        "GET_REPORT",
        [
            re.compile(r"\b(?:laporan|report)\b", re.IGNORECASE),
        ],
        ["period"],
    ),
    (
        "GET_BUDGET_STATUS",
        [
            re.compile(r"\bbudget\b", re.IGNORECASE),
            re.compile(r"\b(?:limit|sisa)\s+budget\b", re.IGNORECASE),
            re.compile(r"\banggaran\b", re.IGNORECASE),
        ],
        [],
    ),
    (
        "GET_NET_WORTH",
        [
            re.compile(r"\b(?:kekayaan|net\s*worth)\b", re.IGNORECASE),
            re.compile(r"\b(?:total\s+)?harta\b", re.IGNORECASE),
        ],
        [],
    ),
    (
        "GET_HEALTH_SCORE",
        [
            re.compile(r"\b(?:skor\s+)?kesehatan\s+keuangan\b", re.IGNORECASE),
            re.compile(r"\bhealth\s*score\b", re.IGNORECASE),
            re.compile(r"\bsehatkah\b", re.IGNORECASE),
        ],
        [],
    ),
    (
        "GET_INSIGHTS",
        [
            re.compile(r"\b(?:wawasan|insight|insights)\b", re.IGNORECASE),
            re.compile(r"\b(?:ringkasan|kesimpulan)\s+keuangan\b", re.IGNORECASE),
        ],
        [],
    ),
    (
        "GET_ANOMALIES",
        [
            re.compile(r"\b(?:anomali|anomaly|kejanggalan|pola\s+aneh)\b", re.IGNORECASE),
        ],
        [],
    ),
    (
        "GET_RECENT",
        [
            re.compile(r"\b(?:transaksi|pengeluaran|pemasukan|riwayat|history)\s+(?:terakhir|terbaru|baru|recent)\b", re.IGNORECASE),
            re.compile(r"\b(?:transaksi|pengeluaran|pemasukan)\s+terakhir\b", re.IGNORECASE),
        ],
        ["count"],
    ),
]


class NLIntentError(Exception):
    """Raised when intent computation fails (propagated from Phase 5-10)."""


def detect_finance_intent(text: str) -> Optional[Dict[str, Any]]:
    """Classify free-form finance text into a controlled intent + params."""
    low = (text or "").strip().lower()
    if not low:
        return None

    # GET_REPORT period: find mention of today/week/month near the laporan word
    days_match = re.search(r"(\d+)\s*(?:hari|days|day)\b", low)
    for intent, patterns, param_keys in _INTENTS:
        if not any(p.search(low) for p in patterns):
            continue
        params: Dict[str, Any] = {}
        if "days" in param_keys:
            if days_match:
                params["days"] = int(days_match.group(1))
            elif re.search(r"\b(?:minggu\s+ini|week)\b", low):
                params["days"] = 7
            elif re.search(r"\b(?:bulan\s+ini|month)\b", low):
                params["days"] = 30
        if "period" in param_keys:
            params["period"] = _report_period(low) or "month"
        if "count" in param_keys:
            count_match = re.search(r"(\d+)\s*(?:transaksi|buah|item)?\s*(?:terakhir|terbaru|baru|recent)?", low)
            params["count"] = int(count_match.group(1)) if count_match and count_match.group(1) else 5
        return {"intent": intent, "params": params}

    return None


def _report_period(low: str) -> Optional[str]:
    if re.search(r"\b(?:hari\s+ini|today)\b", low):
        return "today"
    if re.search(r"\b(?:minggu\s+ini|minggu lalu|week)\b", low):
        return "week"
    if re.search(r"\b(?:bulan\s+ini|bulan lalu|month)\b", low):
        return "month"
    return None


def _fmt_amount(value: float) -> str:
    return f"Rp {abs(value):,.0f}".replace(",", ".")


def _balance_data(ledger_db: str, as_of: date) -> Dict[str, Any]:
    accounts = list_accounts(ledger_db, include_inactive=False)
    per_account = []
    total = 0.0
    for acc in accounts:
        bal = account_balance(ledger_db, acc["id"], as_of=as_of)
        per_account.append({"name": acc["name"], "balance": round(bal, 2)})
        total += bal
    recent = list_transactions(ledger_db, limit=3)
    return {
        "total_balance": round(total, 2),
        "per_account": per_account,
        "recent": [
            {"date": t["tx_date"], "type": t["type"], "amount": round(t["amount"], 2),
             "description": t["description"]}
            for t in recent
        ],
    }


def _recent_data(ledger_db: str, count: int, as_of: date) -> Dict[str, Any]:
    txns = list_transactions(ledger_db, limit=min(max(count, 1), 20))
    return {
        "count": len(txns),
        "transactions": [
            {"date": t["tx_date"], "type": t["type"], "amount": round(t["amount"], 2),
             "description": t["description"], "category": t["category"]}
            for t in txns
        ],
    }


def execute_finance_intent(
    ledger_db: str,
    budget_db: Optional[str] = None,
    text: Optional[str] = None,
    *,
    intent: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    as_of: Optional[date] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve a finance question to a controlled endpoint computation.

    Either pass `text` (auto-detect) or pass `intent`+`params` explicitly
    (e.g. from an LLM that classified the intent). Returns None when the
    text carries no recognized finance intent.
    """
    if intent is None:
        detected = detect_finance_intent(text or "")
        if detected is None:
            return None
        intent = detected["intent"]
        params = detected["params"] or {}
    params = params or {}
    today = as_of or date.today()

    if intent == "GET_BALANCE":
        data = _balance_data(ledger_db, today)
        return {
            "intent": intent,
            "explanation": (
                f"Saldo kamu saat ini {_fmt_amount(data['total_balance'])}. "
                f"Rincian per rekening: "
                + ", ".join(f"{a['name']} {_fmt_amount(a['balance'])}" for a in data["per_account"])
                + "."
            ),
            "data": data,
        }

    if intent == "GET_SAFE_TO_SPEND":
        try:
            result = build_safe_to_spend(
                ledger_db, horizon=params.get("days", "month"), buffer_pct=10.0, as_of=today
            )
        except SafeSpendError as exc:
            raise NLIntentError(str(exc)) from None
        return {
            "intent": intent,
            "explanation": (
                f"Dalam {result['horizon_days']} hari ke depan kamu aman belanja hingga "
                f"{_fmt_amount(result['safe_to_spend'])} — saldo {_fmt_amount(result['current_balance'])}, "
                f"pengeluaran mendatang {_fmt_amount(result['upcoming_outflows'])} "
                f"(Expected {_fmt_amount(result['expected_outflows'])}, "
                f"Estimated {_fmt_amount(result['estimated_outflows'])}), "
                f"buffer {result['buffer_pct']:.0f}% ({_fmt_amount(result['buffer_amount'])})."
            ),
            "data": result,
        }

    if intent == "GET_FORECAST":
        try:
            result = build_cashflow_forecast(ledger_db, days=params.get("days", 30), as_of=today)
        except ForecastError as exc:
            raise NLIntentError(str(exc)) from None
        low = result["insight"] or {"warning": False}
        extra = (
            f" Namun saldo kumulatif diproyeksikan minus "
            f"{_fmt_amount(low['low_point'])} pada {low['low_date']}."
            if low["warning"]
            else ""
        )
        return {
            "intent": intent,
            "explanation": (
                f"Proyeksi arus kas {result['window_start']} s/d {result['window_end']}: "
                f"net {_fmt_amount(result['totals']['forecast'])} "
                f"(Known {_fmt_amount(result['totals']['known'])}, "
                f"Expected {_fmt_amount(result['totals']['expected'])}, "
                f"Estimated {_fmt_amount(result['totals']['estimated'])})."
                f"{extra}"
            ),
            "data": result,
        }

    if intent == "GET_REPORT":
        period = params.get("period") or _report_period((text or "").lower()) or "month"
        report = build_report(ledger_db, period=period, as_of=today)
        t, p = report["totals"], report["previous"]
        return {
            "intent": intent,
            "explanation": (
                f"Laporan {period}: pemasukan {_fmt_amount(t['income'])}, "
                f"pengeluaran {_fmt_amount(t['expense'])}, "
                f"net {_fmt_amount(t['net'])} ({report['range']['start']} s/d {report['range']['end']}). "
                f"Periode sebelumnya: net {_fmt_amount(p['net'])}."
            ),
            "data": report,
        }

    if intent == "GET_BUDGET_STATUS":
        if not budget_db:
            raise NLIntentError("budget_db wajib diisi untuk GET_BUDGET_STATUS")
        status = build_budget_status(ledger_db, budget_db, today.year, today.month)
        over = sum(1 for c in status["categories"] if c["level"] == "over")
        alert = sum(1 for c in status["categories"] if c["level"] == "alert")
        warn = sum(1 for c in status["categories"] if c["level"] == "warn")
        return {
            "intent": intent,
            "explanation": (
                f"Budget {status['year']}-{status['month']:02d}: "
                f"{len(status['categories'])} kategori punya limit, "
                f"{over} over, {alert} alert, {warn} warning."
            ),
            "data": status,
        }

    if intent == "GET_NET_WORTH":
        from packages.api.backend.finance.net_worth_service import build_net_worth
        result = build_net_worth(ledger_db, as_of=today)
        return {
            "intent": intent,
            "explanation": (
                f"Kekayaan bersihmu {_fmt_amount(result['net_worth'])} — "
                f"kas {_fmt_amount(result['cash_assets'])} "
                f"(investasi {_fmt_amount(result['investments'])}). "
                f"Transfer antar rekening tidak mengubah total."
            ),
            "data": result,
        }

    if intent == "GET_HEALTH_SCORE":
        from packages.api.backend.finance.health_score_service import build_health_score
        if not budget_db:
            raise NLIntentError("budget_db wajib diisi untuk GET_HEALTH_SCORE")
        result = build_health_score(ledger_db, budget_db, as_of=today)
        worst = min(result["components"], key=lambda c: c["score"])
        return {
            "intent": intent,
            "explanation": (
                f"Skor kesehatan keuanganmu {result['total_score']}/100 "
                f"({result['grade']}). Komponen terlemah: "
                f"{worst['explanation']}"
            ),
            "data": result,
        }

    if intent == "GET_INSIGHTS":
        from packages.api.backend.finance.insights_service import build_insights
        if not budget_db:
            raise NLIntentError("budget_db wajib diisi untuk GET_INSIGHTS")
        result = build_insights(ledger_db, budget_db, as_of=today)
        s = result["summary"]
        top = result["insights"][0] if result["insights"] else None
        explanation = (
            f"{len(result['insights'])} wawasan: {s['alert']} alert, {s['warning']} warning, "
            f"{s['info']} info, {s['positive']} positif."
            + (f" Prioritas: {top['explanation']}" if top else "")
        )
        return {"intent": intent, "explanation": explanation, "data": result}

    if intent == "GET_ANOMALIES":
        try:
            result = detect_anomalies(ledger_db, as_of=today)
        except AnomalyError as exc:
            raise NLIntentError(str(exc)) from None
        anomalies = result["anomalies"]
        if not anomalies:
            explanation = (
                f"Tidak ada anomali terdeteksi pada {result['window']['start']} "
                f"s/d {result['window']['end']} (dibanding baseline {result['baseline']['days']} hari)."
            )
        else:
            top = anomalies[0]
            explanation = (
                f"{len(anomalies)} anomali terdeteksi pada "
                f"{result['window']['start']} s/d {result['window']['end']}. "
                f"Terbesar: {top['category']} naik {top['ratio']:.1f}x "
                f"(rata-rata harian "
                f"{_fmt_amount(top['baseline_avg'])} -> {_fmt_amount(top['window_avg'])})."
            )
        return {"intent": intent, "explanation": explanation, "data": result}

    if intent == "GET_RECENT":
        data = _recent_data(ledger_db, params.get("count", 5), today)
        return {
            "intent": intent,
            "explanation": (
                f"{data['count']} transaksi terakhir: "
                + ", ".join(
                    f"{t['date']} {t['description'] or t['category']} {_fmt_amount(t['amount'])}"
                    for t in data["transactions"]
                )
                + "."
            ),
            "data": data,
        }

    return None


# ═════════════════════════════════════════════════════════════════════════════
# § Telegram renderer
# ═════════════════════════════════════════════════════════════════════════════

def format_intent_reply(result: Dict[str, Any]) -> str:
    intent = result["intent"]
    heading = {
        "GET_BALANCE": "Saldo Kamu",
        "GET_SAFE_TO_SPEND": "Aman Belanja",
        "GET_FORECAST": "Proyeksi Arus Kas",
        "GET_REPORT": "Laporan",
        "GET_BUDGET_STATUS": "Status Budget",
        "GET_ANOMALIES": "Anomali Keuangan",
        "GET_INSIGHTS": "Wawasan Keuangan",
        "GET_HEALTH_SCORE": "Skor Kesehatan Keuangan",
        "GET_NET_WORTH": "Kekayaan Bersih",
        "GET_RECENT": "Transaksi Terakhir",
    }.get(intent, intent)
    lines = [heading, "", result["explanation"]]

    data = result.get("data") or {}
    if intent == "GET_BALANCE":
        lines.append("")
        lines.append("Rincian rekening:")
        for acc in data.get("per_account", []):
            lines.append(f"- {acc['name']}: {_fmt_amount(acc['balance'])}")
    elif intent == "GET_RECENT":
        lines.append("")
        for t in data.get("transactions", [])[:10]:
            sign = "+" if t["type"] == "income" else "-"
            lines.append(f"- {t['date']} | {t['description'] or t['category']} | {sign}{_fmt_amount(t['amount'])}")
    elif intent == "GET_SAFE_TO_SPEND":
        from packages.api.backend.finance.safe_spend_service import format_safe_to_spend_text
        lines.append("")
        lines.append(format_safe_to_spend_text(data))
    elif intent == "GET_REPORT":
        lines.append("")
        lines.append(f"Periode: {data['range']['start']} s/d {data['range']['end']}")
    elif intent == "GET_FORECAST":
        lines.append("")
        lines.append(f"Jendela: {data['window_start']} s/d {data['window_end']}")
    elif intent == "GET_ANOMALIES":
        from packages.api.backend.finance.anomaly_service import format_anomalies_text
        lines.append("")
        lines.append(format_anomalies_text(data))
    elif intent == "GET_INSIGHTS":
        from packages.api.backend.finance.insights_service import format_insights_text
        lines.append("")
        lines.append(format_insights_text(data))
    elif intent == "GET_HEALTH_SCORE":
        from packages.api.backend.finance.health_score_service import format_health_score_text
        lines.append("")
        lines.append(format_health_score_text(data))
    elif intent == "GET_NET_WORTH":
        from packages.api.backend.finance.net_worth_service import format_net_worth_text
        lines.append("")
        lines.append(format_net_worth_text(data))

    return "\n".join(lines)
