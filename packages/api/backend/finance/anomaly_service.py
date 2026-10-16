"""
backend/finance/anomaly_service.py — Deterministic anomaly detection (Phase 12)
================================================================================
Deterministic, explainable anomaly rules over the canonical ledger — no ML,
no black-box statistics. Every anomaly carries the exact numbers that
triggered it so the reasoning can be surfaced verbatim (Telegram, n8n WF):

  Rule 1  category_spike   — a category's daily average in the WINDOW is at
                             least `spike_ratio` x its BASELINE daily average,
                             the absolute delta is >= `min_delta`, and the
                             window has >= 2 transactions in that category.
  Rule 2  oversized_tx     — a single expense exceeds `oversized_factor` x the
                             category's baseline daily average AND is >=
                             `min_large` (guards tiny baseline noise).

WINDOW   = last `window_days` (default 30) ending at as_of.
BASELINE = the `baseline_days` (default 90) immediately before the window.

Persistence mirrors Phase 6 budget alerts: `check_anomaly_alerts` is
idempotent — an alert row is keyed by (year, month, rule, category) so the
n8n WF-12 path never duplicates alerts.
"""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from packages.core.infrastructure.persistence.database import Database

DEFAULT_WINDOW_DAYS = 30
DEFAULT_BASELINE_DAYS = 90
DEFAULT_SPIKE_RATIO = 2.0
DEFAULT_MIN_DELTA = 100_000.0
DEFAULT_OVERSIZED_FACTOR = 15.0
DEFAULT_MIN_LARGE = 500_000.0

ANOMALIES_DDL = """CREATE TABLE IF NOT EXISTS finance_anomalies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    year        INTEGER NOT NULL,
    month       INTEGER NOT NULL,
    rule        TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    severity    TEXT    NOT NULL,
    window_avg  REAL    NOT NULL,
    baseline_avg REAL   NOT NULL,
    ratio       REAL    NOT NULL,
    window_total REAL   NOT NULL,
    baseline_total REAL NOT NULL,
    evidence    TEXT,
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(year, month, rule, category)
)"""


class AnomalyError(Exception):
    """Invalid anomaly request (bad window/baseline/thresholds)."""


def _fmt(v: float) -> str:
    return f"Rp {v:,.0f}".replace(",", ".")


# ═════════════════════════════════════════════════════════════════════════════
# § Detection engine (compute only — no side effects)
# ═════════════════════════════════════════════════════════════════════════════

def _category_aggregates(
    ledger_db: str, start: date, end: date, ttype: str = "expense"
) -> Dict[str, Dict[str, float]]:
    rows = Database.query(
        ledger_db,
        "SELECT category, SUM(amount) AS total, COUNT(*) AS cnt"
        " FROM transactions WHERE type = ? AND tx_date >= ? AND tx_date <= ?"
        " GROUP BY category",
        (ttype, start.isoformat(), end.isoformat()),
    )
    return {
        r["category"]: {
            "total": float(r["total"] or 0),
            "count": int(r["cnt"] or 0),
        }
        for r in rows
    }


def _window_txs(ledger_db: str, start: date, end: date) -> List[Dict[str, Any]]:
    return Database.query(
        ledger_db,
        "SELECT tx_date, category, amount, description FROM transactions"
        " WHERE type = 'expense' AND tx_date >= ? AND tx_date <= ?"
        " ORDER BY amount DESC",
        (start.isoformat(), end.isoformat()),
    )


def _validate_params(window_days, baseline_days, spike_ratio, oversized_factor) -> None:
    if not (7 <= int(window_days) <= 180):
        raise AnomalyError("window_days harus antara 7 dan 180")
    if not (7 <= int(baseline_days) <= 365):
        raise AnomalyError("baseline_days harus antara 7 dan 365")
    if not (1.1 <= float(spike_ratio) <= 20.0):
        raise AnomalyError("spike_ratio harus antara 1.1 dan 20")
    if not (2.0 <= float(oversized_factor) <= 100.0):
        raise AnomalyError("oversized_factor harus antara 2 dan 100")


def detect_anomalies(
    ledger_db: str,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    baseline_days: int = DEFAULT_BASELINE_DAYS,
    spike_ratio: float = DEFAULT_SPIKE_RATIO,
    min_delta: float = DEFAULT_MIN_DELTA,
    oversized_factor: float = DEFAULT_OVERSIZED_FACTOR,
    min_large: float = DEFAULT_MIN_LARGE,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """Run the two deterministic rules; return labeled, explainable anomalies."""
    _validate_params(window_days, baseline_days, spike_ratio, oversized_factor)
    today = as_of or date.today()
    window_start = today - timedelta(days=window_days - 1)
    baseline_start = window_start - timedelta(days=baseline_days)
    baseline_end = window_start - timedelta(days=1)

    baseline = _category_aggregates(ledger_db, baseline_start, baseline_end)
    window = _category_aggregates(ledger_db, window_start, today)

    anomalies: List[Dict[str, Any]] = []

    # Rule 1: category spike (expense AND income)
    for ttype in ("expense", "income"):
        base = _category_aggregates(ledger_db, baseline_start, baseline_end, ttype)
        cur = _category_aggregates(ledger_db, window_start, today, ttype)
        for cat, c in cur.items():
            b = base.get(cat, {"total": 0.0, "count": 0})
            base_avg = b["total"] / baseline_days
            win_avg = c["total"] / window_days
            if base_avg <= 0 or c["count"] < 2:
                continue
            ratio = win_avg / base_avg
            delta = c["total"] - base_avg * window_days
            if ratio >= spike_ratio and delta >= min_delta:
                anomalies.append({
                    "rule": "category_spike",
                    "ttype": ttype,
                    "category": cat,
                    "severity": "high" if ratio >= spike_ratio * 1.5 else "medium",
                    "window_total": round(c["total"], 2),
                    "baseline_total": round(b["total"], 2),
                    "window_avg": round(win_avg, 2),
                    "baseline_avg": round(base_avg, 2),
                    "ratio": round(ratio, 2),
                    "delta": round(delta, 2),
                    "evidence": None,
                })

    # Rule 2: oversized single expense in the window
    for tx in _window_txs(ledger_db, window_start, today):
        cat = tx["category"]
        base = baseline.get(cat, {"total": 0.0, "count": 0})
        base_avg = base["total"] / baseline_days
        amount = float(tx["amount"])
        if base_avg <= 0:
            continue
        if amount >= base_avg * oversized_factor and amount >= min_large:
            anomalies.append({
                "rule": "oversized_tx",
                "ttype": "expense",
                "category": cat,
                "severity": "high" if amount >= min_large * 3 else "medium",
                "window_total": amount,
                "baseline_total": round(base["total"], 2),
                "window_avg": round(base_avg * oversized_factor, 2),
                "baseline_avg": round(base_avg, 2),
                "ratio": round(amount / base_avg, 2),
                "delta": round(amount - base_avg, 2),
                "evidence": f"{tx['tx_date']} | {tx['description'] or cat} | {_fmt(amount)}",
            })

    anomalies.sort(key=lambda a: a["ratio"], reverse=True)
    return {
        "as_of": today.isoformat(),
        "window": {"start": window_start.isoformat(), "end": today.isoformat()},
        "baseline": {
            "start": baseline_start.isoformat(),
            "end": baseline_end.isoformat(),
            "days": baseline_days,
        },
        "params": {
            "window_days": window_days,
            "spike_ratio": spike_ratio,
            "min_delta": min_delta,
            "oversized_factor": oversized_factor,
            "min_large": min_large,
        },
        "anomalies": anomalies,
    }


# ═════════════════════════════════════════════════════════════════════════════
# § Persistence (n8n WF-12, dedup via UNIQUE(year, month, rule, category))
# ═════════════════════════════════════════════════════════════════════════════

def check_anomaly_alerts(
    ledger_db: str,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    baseline_days: int = DEFAULT_BASELINE_DAYS,
    spike_ratio: float = DEFAULT_SPIKE_RATIO,
    min_delta: float = DEFAULT_MIN_DELTA,
    oversized_factor: float = DEFAULT_OVERSIZED_FACTOR,
    min_large: float = DEFAULT_MIN_LARGE,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """Detect anomalies and persist only NEW ones (idempotent)."""
    result = detect_anomalies(
        ledger_db,
        window_days=window_days,
        baseline_days=baseline_days,
        spike_ratio=spike_ratio,
        min_delta=min_delta,
        oversized_factor=oversized_factor,
        min_large=min_large,
        as_of=as_of,
    )
    today = result["as_of"][:10]
    year, month = int(today[:4]), int(today[5:7])
    Database.execute(ledger_db, ANOMALIES_DDL)

    new_alerts = []
    # Satu SELECT untuk semua kunci (year, month) — hindari N exists-check.
    existing = Database.query(
        ledger_db,
        "SELECT rule, category FROM finance_anomalies WHERE year = ? AND month = ?",
        (year, month),
    )
    seen = {(r["rule"], r["category"]) for r in existing}

    for a in result["anomalies"]:
        if (a["rule"], a["category"]) in seen:
            continue
        try:
            Database.execute(
                ledger_db,
                "INSERT INTO finance_anomalies"
                " (year, month, rule, category, severity, window_avg, baseline_avg,"
                "  ratio, window_total, baseline_total, evidence)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    year, month, a["rule"], a["category"], a["severity"],
                    a["window_avg"], a["baseline_avg"], a["ratio"],
                    a["window_total"], a["baseline_total"], a.get("evidence"),
                ),
            )
        except Exception:
            continue  # sudah ada (race) — skip
        seen.add((a["rule"], a["category"]))
        new_alerts.append(a)

    return {"year": year, "month": month, "detected": len(result["anomalies"]), "new_alerts": new_alerts}


def list_anomaly_alerts(ledger_db: str, year: Optional[int] = None, month: Optional[int] = None) -> List[Dict[str, Any]]:
    """Persisted anomaly alerts, newest first (optionally filtered)."""
    Database.execute(ledger_db, ANOMALIES_DDL)
    where, params = "", []
    if year and month:
        where = " WHERE year = ? AND month = ?"
        params = [year, month]
    rows = Database.query(
        ledger_db,
        "SELECT year, month, rule, category, severity, window_avg, baseline_avg,"
        " ratio, window_total, baseline_total, evidence, created_at"
        f" FROM finance_anomalies{where} ORDER BY created_at DESC, id DESC",
        params,
    )
    return [
        {
            "year": r["year"],
            "month": r["month"],
            "rule": r["rule"],
            "category": r["category"],
            "severity": r["severity"],
            "window_avg": float(r["window_avg"] or 0),
            "baseline_avg": float(r["baseline_avg"] or 0),
            "ratio": float(r["ratio"] or 0),
            "window_total": float(r["window_total"] or 0),
            "baseline_total": float(r["baseline_total"] or 0),
            "evidence": r["evidence"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ═════════════════════════════════════════════════════════════════════════════
# § Telegram renderer (reasoning surfaced in chat)
# ═════════════════════════════════════════════════════════════════════════════

def format_anomalies_text(result: Dict[str, Any]) -> str:
    anomalies = result["anomalies"]
    lines = [
        "Anomali Keuangan",
        f"Jendela: {result['window']['start']} s/d {result['window']['end']}",
        f"Baseline: {result['baseline']['start']} s/d {result['baseline']['end']} "
        f"({result['baseline']['days']} hari)",
    ]
    if not anomalies:
        lines.append("")
        lines.append("Tidak ada anomali terdeteksi pada jendela ini.")
        return "\n".join(lines)

    rule_name = {
        "category_spike": "Kenaikan kategori",
        "oversized_tx": "Transaksi jumbo",
    }
    for a in anomalies[:10]:
        label = rule_name.get(a["rule"], a["rule"])
        lines.append("")
        lines.append(f"[{a['severity'].upper()}] {label} - {a['category']}")
        lines.append(
            f"Rata-rata harian {_fmt(a['baseline_avg'])} -> {_fmt(a['window_avg'])} "
            f"({a['ratio']:.1f}x)"
        )
        if a["evidence"]:
            lines.append(f"Bukti: {a['evidence']}")
    if len(anomalies) > 10:
        lines.append("")
        lines.append(f"... dan {len(anomalies) - 10} anomali lain")
    return "\n".join(lines)
