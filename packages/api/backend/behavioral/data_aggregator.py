from __future__ import annotations

"""
backend/behavioral/data_aggregator.py — Financial Data Aggregator
==================================================================
Single source of truth for monthly financial data assembly.

Exposes:
  _gather_financial_data(now)     — raw dict of the report month's data
  _build_financial_context(now)   — formatted text prompt for LLM analysis
  _format_financial_context(d)    — format an already-gathered dict

Architecture:
  Single Responsibility : this module owns ONLY data collection + formatting.
  DRY                   : previously duplicated in api_server.py AND
                          backend/routers/ai.py — now one canonical location.
  Zero side-effects     : all functions are pure read-only DB queries.

Behavioral accuracy (matches DashboardService):
  - Report month auto-falls back to the last month with data when the current
    calendar month is empty (same rule as the main dashboard).
  - Transfer income (income_type == "transfer") is EXCLUDED from income
    totals, consistent with PostgresIncomeRepository — a transfer into the
    account is not real income.
  - Adds personalization data: active profile, goals, anomalies, 3-month
    trend, and impulse-ranked top transactions from the behavioral snapshot.

Imported by:
  - backend/routers/ai.py      (LLM prompts + rule-engine fallback)
  - api_server.py              (re-exports _gather_financial_data for dashboard)

Step 7 of the api_server.py God-Object split.
"""
import json
import logging

logger = logging.getLogger(__name__)


from calendar import monthrange
from datetime import datetime

from packages.api.backend.routers.deps import (
    _balances_db,
    _behavioral_db,
    _budget_db,
    _db,
    _goals_db,
    _month_range,
    _query,
)
from packages.core.infrastructure.config import Config

_IS_TRANSFER = lambda itype: str(itype or "").strip().lower() == "transfer"


def _prev_ym(year: int, month: int):
    """Previous (year, month) pair."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _monthly_totals(exp_db: str, inc_db: str, y: int, m: int) -> dict:
    """Totals (expense + income) for a single month — used for fallback scan."""
    s, e = _month_range(y, m)
    exp = sum(r["amount"] for r in _query(exp_db, "SELECT amount FROM expenses WHERE date>=? AND date<?", (s, e)))
    inc = sum(r["amount"] for r in _query(inc_db, "SELECT amount FROM incomes WHERE date>=? AND date<?", (s, e)))
    return {"exp": float(exp), "inc": float(inc)}


def _profile_info() -> tuple[str, str]:
    """Return (active_profile_name, profile_type). Never raises."""
    try:
        from packages.core.application.profile_service import ProfileService
        svc = ProfileService(Config.BASE_DIR)
        name = svc.get_active_profile()
        try:
            ptype = svc.get_profile_type(name)
        except Exception:
            ptype = ""
        return str(name or "personal"), str(ptype or "")
    except Exception:
        try:
            return str(Config.get_active_profile() or "personal"), ""
        except Exception:
            return "personal", ""


def _gather_financial_data(now: datetime, allow_fallback: bool = True) -> dict:
    """
    Collect the report month's financial data from the CLI databases.

    The report month is the current calendar month, UNLESS the current month
    has no data and allow_fallback is True — in that case the last month that
    actually has data is used (consistent with DashboardService.get_summary).

    Returns a flat dict consumed by both _format_financial_context (LLM prompt)
    and rule_based_insights (rule-engine fallback). Keys are stable — adding
    new keys is backward-compatible; never rename existing ones.

    Keys:
        exp_this        list[dict]  — expense rows for report month
        inc_this        list[dict]  — REAL income rows (transfers excluded)
        exp_prev_total  float       — total expense in previous month
        inc_prev_total  float       — total REAL income in previous month
        by_cat          dict        — {category: total_amount}
        budget_rows     list[dict]  — {category, limit_amt} rows (may be empty)
        emergency_fund  float       — current emergency fund balance
        total_exp       float       — sum of exp_this amounts
        total_inc       float       — sum of inc_this amounts (transfers excluded)
        transfer_income float       — total transfer inflow this month
        income_sources  int         — distinct real income_type count
        month_label     str         — "July 2026" (report month)
        selected_year   int         — report month year
        selected_month  int         — report month month
        fallback_applied bool       — True when current month was empty
        fbs_score       float|None  — Financial Behavior Score (0-100)
        fbs_grade       str|None    — FBS grade label
        impulse_index   float|None  — impulse spending ratio (0-1)
        by_payment      dict        — {payment_method: total_amount}
        exp_prev_by_cat dict        — previous month category breakdown
        tx_count        int         — total transaction count this month
        profile_name    str         — active profile name
        profile_type    str         — active profile type (may be "")
        goals           list[dict]  — {name, target_amount, current_amount, target_date}
        impulse_top     list[dict]  — top impulse-ranked expenses from snapshot
        anomalies       list[dict]  — simple rule-based anomaly flags
        trend           list[dict]  — last 3 months {year,month,income,expense}
    """
    y, m = now.year, now.month
    exp_db = _db("expense_tracker", "expense.db")
    inc_db = _db("income_tracker",  "income.db")

    # ── Resolve report month: fall back to last month with data ──────────────
    fallback_applied = False
    if allow_fallback:
        base = _monthly_totals(exp_db, inc_db, y, m)
        if base["exp"] == 0 and base["inc"] == 0:
            cy, cm = y, m
            for _ in range(12):
                cy, cm = _prev_ym(cy, cm)
                t = _monthly_totals(exp_db, inc_db, cy, cm)
                if t["exp"] > 0 or t["inc"] > 0:
                    y, m = cy, cm
                    fallback_applied = True
                    break

    prevY, prevM = _prev_ym(y, m)
    s_this, e_this = _month_range(y,     m)
    s_prev, e_prev = _month_range(prevY, prevM)

    exp_this = _query(exp_db,
        "SELECT amount,category,description,payment_method,date FROM expenses "
        "WHERE date>=? AND date<?", (s_this, e_this))

    # Real income only (transfer inflow is NOT income — matches the dashboard)
    inc_raw  = _query(inc_db,
        "SELECT amount,income_type,source,description FROM incomes "
        "WHERE date>=? AND date<?", (s_this, e_this))
    inc_this = [r for r in inc_raw if not _IS_TRANSFER(r.get("income_type"))]
    transfer_income = sum(r["amount"] for r in inc_raw) - sum(r["amount"] for r in inc_this)

    exp_prev_rows = _query(exp_db,
        "SELECT amount,category FROM expenses WHERE date>=? AND date<?", (s_prev, e_prev))
    exp_prev_total = sum(r["amount"] for r in exp_prev_rows)
    inc_prev_rows  = _query(inc_db,
        "SELECT amount,income_type FROM incomes WHERE date>=? AND date<?", (s_prev, e_prev))
    inc_prev_total = sum(r["amount"] for r in inc_prev_rows if not _IS_TRANSFER(r.get("income_type")))

    # Budget rows — optional, never raises
    budget_rows: list = []
    try:
        bdb = _budget_db()
        budget_rows = _query(bdb,
            "SELECT category,limit_amt FROM budgets WHERE year=? AND month=?", (y, m))
    except Exception:
        logger.exception("Error while aggregating financial data segment")
        pass

    ef_rows        = _query(_balances_db(), "SELECT value FROM manual_balances WHERE key='emergency_fund'")
    emergency_fund = ef_rows[0]["value"] if ef_rows else 0.0

    by_cat: dict = {}
    for r in exp_this:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["amount"]

    # Previous month category breakdown for comparison
    exp_prev_by_cat: dict = {}
    for r in exp_prev_rows:
        exp_prev_by_cat[r["category"]] = exp_prev_by_cat.get(r["category"], 0) + r["amount"]

    # Payment method breakdown
    by_payment: dict = {}
    for r in exp_this:
        pm = r.get("payment_method") or "cash"
        by_payment[pm] = by_payment.get(pm, 0) + r["amount"]

    # FBS score + impulse ranking from behavioral snapshot (optional enrichment)
    fbs_score = fbs_grade = impulse_index = None
    impulse_top: list = []
    try:
        beh_db = _behavioral_db()
        beh_rows = _query(beh_db,
            "SELECT payload FROM behavioral_snapshots WHERE year=? AND month=? ORDER BY id DESC LIMIT 1",
            (y, m))
        if beh_rows:
            beh = json.loads(beh_rows[0]["payload"])
            fbs_score     = beh.get("fbs", {}).get("score")
            fbs_grade     = beh.get("fbs", {}).get("grade")
            impulse_index = beh.get("fbs", {}).get("impulse_index")
            per_tx        = beh.get("impulse", {}).get("per_tx", []) or []
            scored = [
                (t.get("tx", {}), float(t.get("is", 0)))
                for t in per_tx if isinstance(t, dict) and t.get("is")
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            impulse_top = [
                {"description": tx.get("description") or tx.get("category", ""),
                 "category": tx.get("category", ""),
                 "amount": float(tx.get("amount", 0)),
                 "score": s}
                for tx, s in scored[:5]
            ]
    except Exception:
        logger.debug("No behavioral snapshot found — skipping FBS enrichment")

    # Goals (optional, never raises). Schema-agnostic: Postgres uses
    # title/deadline, legacy SQLite uses name/target_date.
    goals: list = []
    try:
        gdb = _goals_db()
        rows = _query(gdb, "SELECT * FROM goals ORDER BY id")
        goals = [
            {
                "name": g.get("name") or g.get("title") or f"Goal #{g.get('id')}",
                "target_amount": g.get("target_amount") or 0,
                "current_amount": g.get("current_amount") or 0,
                "target_date": g.get("target_date") or g.get("deadline"),
            }
            for g in rows
        ]
    except Exception:
        logger.debug("No goals available — skipping")

    # ── Simple anomaly flags (rule-based, keeps LLM honest about risks) ───────
    anomalies: list = []
    net = sum(r["amount"] for r in inc_this) - sum(r["amount"] for r in exp_this)
    total_exp = float(sum(r["amount"] for r in exp_this))
    total_inc = float(sum(r["amount"] for r in inc_this))
    for cat, amt in sorted(by_cat.items(), key=lambda x: x[1], reverse=True):
        prev = exp_prev_by_cat.get(cat, 0)
        if prev > 0 and amt > prev * 1.5 and (amt - prev) >= 50000:
            anomalies.append({
                "type": "category_spike",
                "message": f"Kategori '{cat}' melonjak dari Rp {prev:,.0f} ke Rp {amt:,.0f} bulan ini (+{(amt - prev) / prev * 100:.0f}%).",
            })
    if total_exp > 0:
        for e in sorted(exp_this, key=lambda x: x["amount"], reverse=True)[:1]:
            amt = float(e["amount"])
            if amt >= total_exp * 0.3 and amt >= 100000:
                anomalies.append({
                    "type": "concentration",
                    "message": f"Transaksi besar '{e.get('description') or e['category']}' sebesar Rp {amt:,.0f} = {amt / total_exp * 100:.0f}% dari total pengeluaran.",
                })
    if net < 0:
        anomalies.append({
            "type": "deficit",
            "message": f"Defisit bulan ini: pengeluaran Rp {total_exp:,.0f} melebihi pemasukan Rp {total_inc:,.0f} (kurang Rp {abs(net):,.0f}).",
        })
    elif total_inc > 0 and inc_prev_total > 0 and total_inc < inc_prev_total * 0.7:
        anomalies.append({
            "type": "income_drop",
            "message": f"Pemasukan riil turun {((inc_prev_total - total_inc) / inc_prev_total * 100):.0f}% vs bulan lalu (Rp {inc_prev_total:,.0f} → Rp {total_inc:,.0f}).",
        })
    if transfer_income > 0 and total_inc > 0 and transfer_income > total_inc * 3:
        anomalies.append({
            "type": "transfer_heavy",
            "message": f"Banyak pemindahan dana (transfer) masuk bulan ini: Rp {transfer_income:,.0f} — ini bukan pemasukan riil dan tidak dihitung sebagai income.",
        })
    anomalies = anomalies[:5]

    # ── 3-month history trend (excl transfers for income) ─────────────────────
    trend: list = []
    cy, cm = _prev_ym(y, m)
    for _ in range(3):
        s, e = _month_range(cy, cm)
        t_exp = sum(r["amount"] for r in _query(exp_db, "SELECT amount FROM expenses WHERE date>=? AND date<?", (s, e)))
        t_inc = sum(r["amount"] for r in _query(inc_db, "SELECT amount,income_type FROM incomes WHERE date>=? AND date<?", (s, e)) if not _IS_TRANSFER(r.get("income_type")))
        trend.append({"year": cy, "month": cm, "income": float(t_inc), "expense": float(t_exp)})
        cy, cm = _prev_ym(cy, cm)

    profile_name, profile_type = _profile_info()

    return {
        "exp_this":         exp_this,
        "inc_this":         inc_this,
        "exp_prev_total":   float(exp_prev_total),
        "inc_prev_total":   float(inc_prev_total),
        "by_cat":           by_cat,
        "budget_rows":      budget_rows,
        "emergency_fund":   float(emergency_fund),
        "total_exp":        total_exp,
        "total_inc":        total_inc,
        "transfer_income":  float(transfer_income),
        "income_sources":   len({r.get("income_type", "other") for r in inc_this}),
        "month_label":      datetime(y, m, 1).strftime("%B %Y"),
        "selected_year":    y,
        "selected_month":   m,
        "fallback_applied": fallback_applied,
        "fbs_score":        fbs_score,
        "fbs_grade":        fbs_grade,
        "impulse_index":    impulse_index,
        "by_payment":       by_payment,
        "exp_prev_by_cat":  exp_prev_by_cat,
        "tx_count":         len(exp_this),
        "profile_name":     profile_name,
        "profile_type":     profile_type,
        "goals":            goals,
        "impulse_top":      impulse_top,
        "anomalies":        anomalies,
        "trend":            trend,
    }


def _format_financial_context(d: dict) -> str:
    """Format an already-gathered dict into the LLM prompt text block."""
    exp_this         = d["exp_this"]
    inc_this         = d["inc_this"]
    by_cat           = d["by_cat"]
    budget_rows      = d["budget_rows"]
    emergency_fund   = d["emergency_fund"]
    exp_prev_total   = d["exp_prev_total"]
    inc_prev_total   = d["inc_prev_total"]
    total_exp        = d["total_exp"]
    total_inc        = d["total_inc"]
    transfer_income  = d.get("transfer_income", 0.0)
    fbs_score        = d.get("fbs_score")
    fbs_grade        = d.get("fbs_grade")
    impulse_index    = d.get("impulse_index")
    by_payment       = d.get("by_payment", {})
    exp_prev_by_cat  = d.get("exp_prev_by_cat", {})
    tx_count         = d.get("tx_count", len(exp_this))
    month_label      = d.get("month_label", "bulan ini")
    profile_name     = d.get("profile_name", "personal")
    profile_type     = d.get("profile_type", "")
    goals            = d.get("goals", [])
    impulse_top      = d.get("impulse_top", [])
    anomalies        = d.get("anomalies", [])
    trend            = d.get("trend", [])
    fallback_applied = d.get("fallback_applied", False)

    net          = total_inc - total_exp
    saving_rate  = (net / total_inc * 100) if total_inc > 0 else 0
    top_txs      = sorted(exp_this, key=lambda x: x["amount"], reverse=True)[:10]
    days_in_month = monthrange(d.get("selected_year", 1), d.get("selected_month", 1))[1]
    avg_daily    = total_exp / max(days_in_month, 1)

    budget_lines = "\n".join(
        f'  {r["category"]}: limit Rp {r["limit_amt"]:,.0f} | '
        f'aktual Rp {by_cat.get(r["category"], 0):,.0f} | '
        f'{"OVER (melebihi budget)" if by_cat.get(r["category"], 0) > r["limit_amt"] else "OK (dalam budget)"}'
        for r in budget_rows
    ) or "  (tidak ada budget yang diset)"

    # Category with MoM delta for each
    cat_lines = "\n".join(
        f'  {cat}: Rp {amt:,.0f} ({amt / total_exp * 100:.1f}% dari total)'
        + (f' [↑{((amt - exp_prev_by_cat[cat]) / exp_prev_by_cat[cat] * 100):+.0f}% vs bulan lalu]'
           if cat in exp_prev_by_cat and exp_prev_by_cat[cat] > 0 else
           ' [baru bulan ini]' if amt > 0 and exp_prev_by_cat.get(cat, 0) == 0 else "")
        for cat, amt in sorted(by_cat.items(), key=lambda x: x[1], reverse=True)
    ) or "  (tidak ada data)"

    def _desc(t):
        desc = (t.get("description") or t.get("category") or "").strip()
        return desc[:60]

    tx_lines = "\n".join(
        f'  Rp {t["amount"]:,.0f} — {_desc(t)} '
        f'({t["category"]}, bayar: {t.get("payment_method") or "cash"}, {t["date"][:10]})'
        for t in top_txs
    ) or "  (tidak ada transaksi)"

    inc_lines = "\n".join(
        f'  [{r["income_type"]}] {r.get("source") or r.get("description") or r["income_type"]}: Rp {r["amount"]:,.0f}'
        for r in inc_this
    ) or "  (tidak ada pemasukan riil bulan ini)"
    if transfer_income > 0:
        inc_lines += f'\n  [transfer] Pindah dana masuk (BUKAN pemasukan): Rp {transfer_income:,.0f}'

    pay_lines = "\n".join(
        f'  {pm}: Rp {amt:,.0f} ({amt / total_exp * 100:.1f}%)'
        for pm, amt in sorted(by_payment.items(), key=lambda x: x[1], reverse=True)
    ) or "  (tidak ada data)"

    exp_pct_chg = ((total_exp - exp_prev_total) / exp_prev_total * 100) if exp_prev_total > 0 else 0
    inc_pct_chg = ((total_inc - inc_prev_total) / inc_prev_total * 100) if inc_prev_total > 0 else 0

    # FBS/behavioral section — only shown if available
    fbs_section = ""
    if fbs_score is not None:
        impulse_pct = f"{impulse_index * 100:.1f}%" if impulse_index is not None else "N/A"
        fbs_section = f"""
SKOR PERILAKU KEUANGAN (FBS)
  Skor FBS      : {fbs_score:.1f}/100  (grade: {fbs_grade or 'N/A'})
  Impulse Index : {impulse_pct}  (rasio pengeluaran impulsif dari total)
  Catatan: Gunakan skor ini untuk kalibrasi rekomendasi — skor rendah = butuh perhatian lebih"""

    anomaly_lines = "\n".join(f"  - {a['message']}" for a in anomalies) or "  (tidak ada anomali mencolok)"

    trend_lines = "\n".join(
        f'  {datetime(t["year"], t["month"], 1).strftime("%B")}: income Rp {t["income"]:,.0f} | expense Rp {t["expense"]:,.0f}'
        for t in reversed(trend)
    ) or "  (tidak ada data historis)"

    impulse_lines = "\n".join(
        f'  Rp {t["amount"]:,.0f} — {_desc(t)} (skor impulsif {t["score"]:.2f})'
        for t in impulse_top
    ) or "  (tidak tersedia)"

    goal_lines = "\n".join(
        f'  {g["name"]}: Rp {g["current_amount"]:,.0f} / Rp {g["target_amount"]:,.0f}'
        + (f' (target {g["target_date"]})' if g.get("target_date") else "")
        for g in goals
    ) or "  (tidak ada goal tersimpan)"

    fallback_note = ""
    if fallback_applied:
        fallback_note = f"""
CATATAN PENTING: bulan berjalan (kalender) belum memiliki data, jadi analisis ini
memakai bulan terakhir yang berisi data: {month_label}. Saat membahas "bulan ini",
merujuklah pada {month_label}."""

    profile_line = f"PROFIL AKTIF: {profile_name}" + (f" (tipe: {profile_type})" if profile_type else "")

    return f"""DATA KEUANGAN PENGGUNA — {month_label}
(Data real-time dari database lokal; diproses pada {datetime.now().strftime('%d %B %Y %H:%M')})
{profile_line}
{fallback_note}

RINGKASAN BULAN INI ({month_label})
  Total Pemasukan (riil, tanpa transfer): Rp {total_inc:,.0f}
  Total Pengeluaran: Rp {total_exp:,.0f}
  Selisih (Net)    : Rp {net:,.0f}  {"(DEFISIT)" if net < 0 else "(surplus)"}
  Saving Rate      : {saving_rate:.1f}%
  Dana Darurat     : Rp {emergency_fund:,.0f}
  Total Transaksi  : {tx_count} transaksi
  Rata-rata/hari   : Rp {avg_daily:,.0f}/hari
{fbs_section}
PERBANDINGAN BULAN SEBELUMNYA
  Pemasukan bulan lalu  : Rp {inc_prev_total:,.0f}
  Pengeluaran bulan lalu: Rp {exp_prev_total:,.0f}
  Perubahan pengeluaran : {exp_pct_chg:+.1f}%
  Perubahan pemasukan   : {inc_pct_chg:+.1f}%

TREN 3 BULAN TERAKHIR
{trend_lines}

BREAKDOWN PENGELUARAN PER KATEGORI (dengan perubahan MoM)
{cat_lines}

METODE PEMBAYARAN
{pay_lines}

BUDGET vs AKTUAL
{budget_lines}

ANOMALI / FLAG TERDETEKSI
{anomaly_lines}

10 TRANSAKSI TERBESAR BULAN INI
{tx_lines}

SUMBER PEMASUKAN (riil)
{inc_lines}

TRANSAKSI IMPULSIF TERATAS (dari skor perilaku)
{impulse_lines}

GOALS / TARGET KEUANGAN
{goal_lines}"""


def _build_financial_context(now: datetime) -> str:
    """
    Build a formatted text summary of the report month's financial data.

    Used as the user-turn content in LLM prompts. Bilingual (ID labels,
    IDR formatting). Includes: income/expense summary, category breakdown,
    budget vs actual, top transactions, income sources, FBS score,
    payment method breakdown, category-level MoM comparison, anomalies,
    trend, goals, and impulse-ranked transactions.
    """
    return _format_financial_context(_gather_financial_data(now))
