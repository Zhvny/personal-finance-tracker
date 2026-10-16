"""
backend/routers/analytics.py — Analytics + Behavioral trend routes
===================================================================
Extracted from api_server.py as part of Step 5 router split.
Architecture: High Cohesion — this file owns only /api/behavioral/lifestyle-trend|/api/analytics routes.
Low Coupling : depends only on backend/routers/deps.py and FastAPI. Never imports other routers.
"""

import logging
import time
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from packages.api.backend.routers.deps import (
    BALANCES_DB_PATH,
    ROOT,
    _db,
    _month_range,
    _query,
)
from packages.api.backend.security.core import require_scope

router = APIRouter(dependencies=[Depends(require_scope("read"))])
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# § PHASE 2.3 — Lifestyle Inflation Trend (6-month rolling)
# ══════════════════════════════════════════════════════════════════════════════

# Simple in-memory cache for analytics
_ANALYTICS_CACHE = {}
_ANALYTICS_TTL = 300  # 5 minutes


def get_cached(key):
    global _ANALYTICS_CACHE
    entry = _ANALYTICS_CACHE.get(key)
    if entry and (time.time() - entry["ts"]) < _ANALYTICS_TTL:
        return entry["data"]
    return None


def set_cached(key, data):
    global _ANALYTICS_CACHE
    _ANALYTICS_CACHE[key] = {"data": data, "ts": time.time()}


@router.get("/api/behavioral/lifestyle-trend")
def lifestyle_trend(months: int = 6):
    cached = get_cached(f"lifestyle_{months}")
    if cached:
        return cached

    # ... (existing logic)

    exp_db = _db("expense_tracker", "expense.db")
    inc_db = _db("income_tracker", "income.db")
    now = datetime.now()
    y, m = now.year, now.month

    series = []
    for offset in range(months + 1, -1, -1):  # fetch 1 extra for growth calculation
        mo = m - offset
        yr = y
        while mo <= 0:
            mo += 12
            yr -= 1
        ms, me = _month_range(yr, mo)

        inc_rows = _query(inc_db, "SELECT SUM(amount) as t FROM incomes  WHERE date>=? AND date<?", (ms, me))
        mi = inc_rows[0]["t"] if inc_rows and inc_rows[0]["t"] is not None else 0.0

        exp_rows = _query(exp_db, "SELECT SUM(amount) as t FROM expenses WHERE date>=? AND date<?", (ms, me))
        mex = exp_rows[0]["t"] if exp_rows and exp_rows[0]["t"] is not None else 0.0

        series.append({"label": date(yr, mo, 1).strftime("%b %Y"), "exp": round(mex, 2), "inc": round(mi, 2)})

    # Compute growth rates from consecutive months
    result = []
    for i in range(1, len(series)):
        prev = series[i - 1]
        curr = series[i]
        exp_g = (curr["exp"] - prev["exp"]) / prev["exp"] if prev["exp"] > 0 else 0.0
        inc_g = (curr["inc"] - prev["inc"]) / prev["inc"] if prev["inc"] > 0 else 0.0
        li = round(exp_g - inc_g, 4)
        verdict = "inflating" if li > 0.05 else ("healthy" if li < -0.05 else "stable")
        result.append(
            {
                "label": curr["label"],
                "exp": curr["exp"],
                "inc": curr["inc"],
                "exp_growth": round(exp_g, 4),
                "inc_growth": round(inc_g, 4),
                "li_score": li,
                "verdict": verdict,
            }
        )

    # Rolling 3-month average LI score
    rolling = []
    for i in range(len(result)):
        window = result[max(0, i - 2) : i + 1]
        rolling.append(round(sum(r["li_score"] for r in window) / len(window), 4))

    for i, r in enumerate(result):
        r["li_rolling"] = rolling[i]

    # Severity classification based on most recent 3 months
    recent_li = [r["li_score"] for r in result[-3:]] if len(result) >= 3 else [r["li_score"] for r in result]
    avg_li = sum(recent_li) / len(recent_li) if recent_li else 0
    severity = "severe" if avg_li > 0.15 else "moderate" if avg_li > 0.05 else "mild" if avg_li > 0 else "healthy"

    res = {
        "ok": True,
        "months_shown": len(result),
        "severity": severity,
        "avg_li_3mo": round(avg_li, 4),
        "trend": result,
    }
    set_cached(f"lifestyle_{months}", res)
    return res


# ══════════════════════════════════════════════════════════════════════════════
# § PHASE 3.1 — Expense Prediction (linear regression, next 3 months)
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/api/analytics/expense-prediction")
def expense_prediction(months_history: int = 6, months_ahead: int = 3):
    cached = get_cached(f"exp_pred_{months_history}_{months_ahead}")
    if cached:
        return cached
    # ... logic ...

    exp_db = _db("expense_tracker", "expense.db")
    now = datetime.now()
    y, m = now.year, now.month

    # Collect history
    history_raw = []
    for offset in range(months_history - 1, -1, -1):
        mo = m - offset
        yr = y
        while mo <= 0:
            mo += 12
            yr -= 1
        ms, me = _month_range(yr, mo)
        total = (
            _query(exp_db, "SELECT SUM(amount) as t FROM expenses WHERE date>=? AND date<?", (ms, me))[0]["t"] or 0.0
        )
        history_raw.append({"label": date(yr, mo, 1).strftime("%b %Y"), "amount": round(total, 2), "yr": yr, "mo": mo})

    # Reject if insufficient data
    actuals = [h["amount"] for h in history_raw if h["amount"] > 0]
    if len(actuals) < 3:
        return {
            "ok": True,
            "insufficient_data": True,
            "history": history_raw,
            "predictions": [],
            "slope": 0,
            "r_squared": 0,
        }

    # Linear regression over non-zero months
    xs = [i for i, h in enumerate(history_raw) if h["amount"] > 0]
    ys = actuals
    n = len(xs)
    sx, sy, sxy, sxx = sum(xs), sum(ys), sum(x * y for x, y in zip(xs, ys)), sum(x * x for x in xs)
    denom = n * sxx - sx * sx
    slope = (n * sxy - sx * sy) / denom if denom else 0.0
    intercept = (sy - slope * sx) / n

    # R²
    y_mean = sy / n
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # Generate predictions
    base_idx = len(history_raw)
    predictions = []
    for i in range(months_ahead):
        mo = m + i + 1
        yr = y
        while mo > 12:
            mo -= 12
            yr += 1
        pred = max(0, intercept + slope * (base_idx + i))
        predictions.append(
            {
                "label": date(yr, mo, 1).strftime("%b %Y"),
                "amount": round(pred, 2),
                "lower": round(max(0, pred * 0.85), 2),  # 15% confidence band
                "upper": round(pred * 1.15, 2),
            }
        )

    res = {
        "ok": True,
        "insufficient_data": False,
        "history": history_raw,
        "predictions": predictions,
        "slope": round(slope, 2),
        "r_squared": round(r2, 4),
        "trend": "rising" if slope > 500 else "falling" if slope < -500 else "stable",
    }
    set_cached(f"exp_pred_{months_history}_{months_ahead}", res)
    return res


# ══════════════════════════════════════════════════════════════════════════════
# § PHASE 3.2 — Saving Projection (compound growth, configurable)
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/api/analytics/saving-projection")
def saving_projection(years: int = 5, annual_return_pct: float = 7.0):
    cached = get_cached(f"saving_{years}_{annual_return_pct}")
    if cached:
        return cached
    # ... logic ...

    exp_db = _db("expense_tracker", "expense.db")
    inc_db = _db("income_tracker", "income.db")
    now = datetime.now()
    y, m = now.year, now.month

    # Calculate avg monthly saving from last 3 months
    monthly_savings = []
    for offset in range(1, 4):
        mo = m - offset
        yr = y
        while mo <= 0:
            mo += 12
            yr -= 1
        ms, me = _month_range(yr, mo)
        mi = _query(inc_db, "SELECT SUM(amount) as t FROM incomes  WHERE date>=? AND date<?", (ms, me))[0]["t"] or 0.0
        mex = _query(exp_db, "SELECT SUM(amount) as t FROM expenses WHERE date>=? AND date<?", (ms, me))[0]["t"] or 0.0
        s = mi - mex
        if s > 0:
            monthly_savings.append(s)

    monthly_saving = sum(monthly_savings) / len(monthly_savings) if monthly_savings else 0.0
    monthly_rate = (annual_return_pct / 100) / 12

    # Current cash starting point (goals.db)
    try:
        gdb = str(BALANCES_DB_PATH)
        row = _query(gdb, "SELECT physical_cash + bank_savings as total FROM cash_split ORDER BY id DESC LIMIT 1")
        start = float(row[0]["total"]) if row else 0.0
    except Exception:
        start = 0.0

    projections = []
    balance = start
    for yr_offset in range(1, years + 1):
        yr_label = f"{y + yr_offset}"
        # 12 months of compound deposits
        for _ in range(12):
            balance = balance * (1 + monthly_rate) + monthly_saving
        projections.append(
            {
                "year": y + yr_offset,
                "label": yr_label,
                "total": round(balance, 2),
                "contributed": round(start + monthly_saving * 12 * yr_offset, 2),
                "growth": round(balance - start - monthly_saving * 12 * yr_offset, 2),
            }
        )

    res = {
        "ok": True,
        "monthly_saving": round(monthly_saving, 2),
        "starting_balance": round(start, 2),
        "annual_return_pct": annual_return_pct,
        "years": years,
        "projections": projections,
        "final_total": projections[-1]["total"] if projections else 0,
    }
    set_cached(f"saving_{years}_{annual_return_pct}", res)
    return res


# ══════════════════════════════════════════════════════════════════════════════
# § PHASE 3.3 — Portfolio Risk Simulation (Monte Carlo-style, upgraded)
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/api/analytics/portfolio-risk")
def portfolio_risk_simulation():
    cached = get_cached("portfolio_risk")
    if cached:
        return cached

    db = _db("investment_tracker", "portfolio.db")
    try:
        # Use _query for transparent redirection
        holdings = _query(
            db,
            """
            SELECT i.ticker, i.asset_type,
                   COALESCE(i.remaining_quantity, i.quantity) AS quantity,
                   i.buy_price AS avg_buy_price, i.buy_currency,
                   (SELECT price_idr FROM historical_prices hp
                    WHERE hp.investment_id = i.id
                    ORDER BY hp.snapshot_date DESC LIMIT 1) AS current_price_idr
            FROM investments i
            WHERE i.status != ?
              AND COALESCE(i.remaining_quantity, i.quantity) > ?
        """,
            ("sold", 0),
        )
    except Exception:
        logger.exception("Portfolio risk query error")
        holdings = []

    # Asset-type volatility assumptions (annual std deviation %)
    VOL = {"crypto": 80.0, "stock": 22.0, "etf": 18.0, "reksa_dana": 12.0, "gold": 14.0, "other": 20.0}
    # Expected annual return assumptions %
    RET = {"crypto": 35.0, "stock": 12.0, "etf": 10.0, "reksa_dana": 9.0, "gold": 7.0, "other": 8.0}

    FX_RATE = 16_500  # fallback IDR/USD rate

    assets = []
    for h in holdings:
        atype = (h["asset_type"] or "other").lower()
        # Use latest IDR price if available; otherwise convert buy_price to IDR
        if h["current_price_idr"]:
            cp = h["current_price_idr"]
        elif (h["buy_currency"] or "IDR") == "USD":
            cp = (h["avg_buy_price"] or 0) * FX_RATE
        else:
            cp = h["avg_buy_price"] or 0
        value = h["quantity"] * cp
        if value <= 0:
            continue
        assets.append(
            {
                "ticker": h["ticker"],
                "type": atype,
                "value": round(value, 2),
                "vol": VOL.get(atype, 20.0),
                "ret": RET.get(atype, 8.0),
            }
        )

    total_value = sum(a["value"] for a in assets)

    if total_value <= 0:
        return {"ok": True, "empty_portfolio": True, "allocation": [], "risk_score": 0, "scenarios": [], "warnings": []}

    # Compute allocation percentages
    for a in assets:
        a["pct"] = round(a["value"] / total_value * 100, 2)

    # Portfolio weighted return and vol
    w_ret = sum(a["pct"] / 100 * a["ret"] for a in assets)
    w_vol = sum(a["pct"] / 100 * a["vol"] for a in assets)  # simplified (no correlation)

    # Concentration risk: HHI (Herfindahl-Hirschman Index) by asset type
    type_pcts: dict = {}
    for a in assets:
        type_pcts[a["type"]] = type_pcts.get(a["type"], 0) + a["pct"]
    hhi = sum(p**2 for p in type_pcts.values()) / 10_000

    # Risk score 0-100 (higher = more risky)
    risk_score = min(
        100,
        round(
            (w_vol / 80 * 50)  # 50% weight on volatility
            + (hhi * 30)  # 30% concentration
            + (type_pcts.get("crypto", 0) / 100 * 20),  # 20% crypto exposure
            1,
        ),
    )

    # 3-scenario 1-year simulation (bear / base / bull)
    scenarios = [
        {
            "label": "Bear (-1 std)",
            "return_pct": round(w_ret - w_vol, 1),
            "value": round(total_value * (1 + (w_ret - w_vol) / 100), 2),
        },
        {"label": "Base (expected)", "return_pct": round(w_ret, 1), "value": round(total_value * (1 + w_ret / 100), 2)},
        {
            "label": "Bull (+1 std)",
            "return_pct": round(w_ret + w_vol, 1),
            "value": round(total_value * (1 + (w_ret + w_vol) / 100), 2),
        },
    ]

    # Warnings
    warnings = []
    if type_pcts.get("crypto", 0) > 40:
        warnings.append(f"Crypto concentration {type_pcts['crypto']:.0f}% — high volatility risk.")
    if hhi > 0.50:
        warnings.append("Portfolio highly concentrated in one asset type.")
    single_largest = max(assets, key=lambda a: a["pct"]) if assets else None
    if single_largest and single_largest["pct"] > 40:
        warnings.append(
            f"{single_largest['ticker']} = {single_largest['pct']:.0f}% of portfolio — single-asset concentration."
        )

    # Group by type for allocation chart
    allocation = [{"type": t, "pct": round(p, 2)} for t, p in sorted(type_pcts.items(), key=lambda x: -x[1])]

    res = {
        "ok": True,
        "empty_portfolio": False,
        "total_value": round(total_value, 2),
        "weighted_return_pct": round(w_ret, 2),
        "weighted_vol_pct": round(w_vol, 2),
        "risk_score": risk_score,
        "concentration_hhi": round(hhi, 3),
        "allocation": allocation,
        "assets": sorted(assets, key=lambda a: -a["value"]),
        "scenarios": scenarios,
        "warnings": warnings,
    }
    set_cached("portfolio_risk", res)
    return res


# ═════════════════════════════════════════════════════════════════════
# LOG COCKPIT — Live Log Monitoring API
# ═════════════════════════════════════════════════════════════════════


@router.get("/api/logs/recent")
def get_recent_logs(source: str = "cli", lines: int = 100, level: Optional[str] = None):
    """
    Returns recent log entries from the specified log source for the Live Log Cockpit.
    """
    log_paths = {
        "cli": ROOT / "logs" / "app.log",
        "microservice": ROOT / "apps" / "api" / "alpha_microservice.log",
        "api": ROOT / "packages" / "api" / "api_server.log",
        "optimizer": ROOT / "logs" / "optimizer_exclusions.log",
        "dr_backup": ROOT / "logs" / "dr_backup.log",
        "security": ROOT / "logs" / "security_audit.log",
    }

    path = log_paths.get(source, log_paths["cli"])
    if not path.exists():
        return {"source": source, "lines": [], "size_bytes": 0, "status": "File not found"}

    try:
        size = path.stat().st_size
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            raw_lines = f.readlines()

        recent = raw_lines[-max(1, min(lines, 1000)) :]
        filtered = []
        for line in recent:
            cleaned = line.strip()
            if level and level.upper() != "ALL":
                if level.upper() not in cleaned.upper():
                    continue
            filtered.append(cleaned)

        return {"source": source, "lines": filtered, "total_lines": len(raw_lines), "size_bytes": size, "status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(exc)}") from exc
