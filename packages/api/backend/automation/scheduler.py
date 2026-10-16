"""
scheduler.py — Scheduled Automation System
===========================================
Standalone process. Run separately from api_server.py:

    python scheduler.py

Uses APScheduler (pip install apscheduler --break-system-packages).

Jobs
----
  A. Net Worth Snapshot  — daily 00:05
     Reads balances + portfolio from api_server data, writes to networth_history.db

  B. Portfolio Price Update — every 5 minutes
     Calls /api/investments/refresh-prices on running api_server

  C. Behavioral Score Update — daily 01:00
     Calls /api/behavioral/report to force recompute and cache result

  D. Recurring Detection — daily 02:00
     Calls /api/expenses/detect-recurring

Design
------
  High Cohesion  : scheduler orchestrates jobs, each job is its own function.
  Low Coupling   : jobs call the REST API — no direct DB or Python module imports.
  YAGNI          : APScheduler only, no Celery/Redis/Kafka.
  Resilience     : every job is wrapped in try/except; one failure never kills others.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Optional

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("scheduler")


# ── Config ────────────────────────────────────────────────────────────────────
API_BASE    = os.environ.get("API_BASE", "http://localhost:8444/api")
DATA_DIR    = Path(__file__).parent.parent.parent / "data"
NW_DB_PATH  = DATA_DIR / "networth_history.db"


# ══════════════════════════════════════════════════════════════════════════════
# § NET WORTH HISTORY DB
# ══════════════════════════════════════════════════════════════════════════════

NW_SCHEMA = """
CREATE TABLE IF NOT EXISTS networth_snapshots (
    date           TEXT PRIMARY KEY,
    total_networth REAL NOT NULL DEFAULT 0,
    cash           REAL NOT NULL DEFAULT 0,
    bank_savings   REAL NOT NULL DEFAULT 0,
    emergency_fund REAL NOT NULL DEFAULT 0,
    crypto         REAL NOT NULL DEFAULT 0,
    stocks         REAL NOT NULL DEFAULT 0,
    gold           REAL NOT NULL DEFAULT 0,
    other_assets   REAL NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL
)
"""

def _nw_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(NW_DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(NW_SCHEMA)
    con.commit()
    return con


# ══════════════════════════════════════════════════════════════════════════════
# § HTTP HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get(path: str, timeout: int = 10) -> Optional[dict]:
    """GET {API_BASE}{path}. Returns parsed JSON or None on failure."""
    url = f"{API_BASE}{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        log.warning(f"GET {url} failed: {e}")
        return None


def _post(path: str, body: dict = None, timeout: int = 30) -> Optional[dict]:
    """POST {API_BASE}{path} with JSON body. Returns parsed JSON or None."""
    url = f"{API_BASE}{path}"
    try:
        data = json.dumps(body or {}).encode("utf-8")
        req  = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        log.warning(f"POST {url} failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# § JOB A — Net Worth Snapshot
# ══════════════════════════════════════════════════════════════════════════════

def job_networth_snapshot():
    """
    Read current balances from API, write daily snapshot to networth_history.db.
    Upserts so re-running on same day overwrites.
    """
    log.info("JOB A: Net Worth Snapshot starting…")
    try:
        balances  = _get("/balances")
        if not balances:
            log.warning("JOB A: Could not fetch balances — skipping.")
            return

        cash           = float(balances.get("physical_cash",  0))
        bank_savings   = float(balances.get("bank_savings",   0))
        emergency_fund = float(balances.get("emergency_fund", 0))
        crypto_val     = float(balances.get("crypto",         0))

        # Net worth = all financial assets
        # investments breakdown from /api/investments
        invs = _get("/investments") or []
        stocks = gold = other = 0.0
        crypto_from_inv = 0.0
        for h in invs:
            asset_type = (h.get("asset_type") or "").lower()
            qty     = h.get("remaining_quantity") or h.get("quantity") or 0
            cp_idr  = h.get("current_price_idr") or h.get("buy_price") or 0
            val     = float(cp_idr) * float(qty)
            if asset_type == "crypto":
                crypto_from_inv += val
            elif asset_type in ("stock", "etf", "reksa_dana"):
                stocks += val
            elif asset_type == "gold":
                gold += val
            else:
                other += val

        # Use the larger crypto value (portfolio.db is authoritative if prices loaded)
        crypto = max(crypto_val, crypto_from_inv)
        net_worth = bank_savings + emergency_fund + crypto + stocks + gold + other

        today = date.today().isoformat()
        con   = _nw_db()
        con.execute("""
            INSERT INTO networth_snapshots
                (date, total_networth, cash, bank_savings, emergency_fund,
                 crypto, stocks, gold, other_assets, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(date) DO UPDATE SET
                total_networth = excluded.total_networth,
                cash           = excluded.cash,
                bank_savings   = excluded.bank_savings,
                emergency_fund = excluded.emergency_fund,
                crypto         = excluded.crypto,
                stocks         = excluded.stocks,
                gold           = excluded.gold,
                other_assets   = excluded.other_assets,
                created_at     = excluded.created_at
        """, (today, net_worth, cash, bank_savings, emergency_fund,
              crypto, stocks, gold, other, datetime.now().isoformat()))
        con.commit()
        con.close()
        log.info(f"JOB A: Snapshot saved — net_worth=Rp{net_worth:,.0f}")

    except Exception as e:
        log.error(f"JOB A failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# § JOB B — Portfolio Price Update
# ══════════════════════════════════════════════════════════════════════════════

def job_portfolio_price_update():
    """Trigger portfolio price refresh via API."""
    log.info("JOB B: Portfolio price update…")
    try:
        result = _post("/investments/refresh-prices")
        if result:
            log.info(f"JOB B: Prices refreshed — {result.get('updated', '?')} assets")
        else:
            log.warning("JOB B: Refresh returned no data.")
    except Exception as e:
        log.error(f"JOB B failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# § JOB C — Behavioral Score Update
# ══════════════════════════════════════════════════════════════════════════════

def job_behavioral_score_update():
    """Force recompute of behavioral finance report via API."""
    log.info("JOB C: Behavioral score update…")
    try:
        result = _get("/behavioral")   # correct endpoint — /api/behavioral
        if result:
            score = result.get("fbs", {}).get("score", "?")
            log.info(f"JOB C: Behavioral score recomputed — FBS score={score}")
        else:
            log.warning("JOB C: No behavioral data returned.")
    except Exception as e:
        log.error(f"JOB C failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# § JOB D — Recurring Detection
# ══════════════════════════════════════════════════════════════════════════════

def job_recurring_detection():
    """Run recurring transaction detection via API."""
    log.info("JOB D: Recurring detection…")
    try:
        result = _post("/expenses/detect-recurring", {"months_lookback": 6})
        if result:
            log.info(f"JOB D: Detected {result.get('detected', 0)} recurring patterns.")
        else:
            log.warning("JOB D: No result from recurring detection.")
    except Exception as e:
        log.error(f"JOB D failed: {e}")


import subprocess


def job_stock_ml_update():
    """Run optimized Live ML Sync & Inference."""
    log.info("JOB E: Live Stock ML Sync & Inference starting…")
    try:
        ml_root = Path(__file__).parent.parent.parent.parent / "apps" / "cli" / "stock_ml"
        python_exe = sys.executable

        # Use absolute paths for scripts to avoid WinError 2
        sync_script = ml_root / "01_live_sync.py"
        inference_script = ml_root / "07_live_inference.py"

        # 1. Live Sync (Incremental)
        log.info("JOB E [1/2]: Live Data Sync…")
        subprocess.run([python_exe, str(sync_script)], cwd=str(ml_root), check=True, timeout=300)

        # 2. Live Inference (Fast)
        log.info("JOB E [2/2]: Live Inference…")
        subprocess.run([python_exe, str(inference_script)], cwd=str(ml_root), check=True, timeout=300)

        log.info("JOB E: Live Stock ML Update completed successfully.")
    except subprocess.TimeoutExpired as e:
        log.error(f"JOB E failed (timeout): {e}")
        raise
    except subprocess.CalledProcessError as e:
        log.error(f"JOB E failed (process error): {e}")
        raise
    except Exception as e:
        log.error(f"JOB E failed: {e}")
        raise

def job_genetic_optimization():
    """Run Task 6.3: Evolving Sniper (Genetic Hyperparameter Tuning)."""
    log.info("JOB F: Genetic Optimization (Evolving Sniper) starting…")
    try:
        cli_root = Path(__file__).parent.parent.parent.parent / "apps" / "cli"
        python_exe = sys.executable
        opt_script = cli_root / "genetic_optimizer.py"

        subprocess.run([python_exe, str(opt_script)], cwd=str(cli_root), check=True, timeout=300)
        log.info("JOB F: Genetic Optimization completed successfully.")
    except subprocess.TimeoutExpired as e:
        log.error(f"JOB F failed (timeout): {e}")
        raise
    except subprocess.CalledProcessError as e:
        log.error(f"JOB F failed (process error): {e}")
        raise
    except Exception as e:
        log.error(f"JOB F failed: {e}")
        raise

# ══════════════════════════════════════════════════════════════════════════════
# § JOB STATUS TRACKER
# ══════════════════════════════════════════════════════════════════════════════

_job_status: dict = {
    "networth_snapshot":   {"last_run": None, "last_status": "pending", "last_duration_s": 0.0, "error_count": 0, "consecutive_failures": 0, "next_run_after": None},
    "portfolio_prices":    {"last_run": None, "last_status": "pending", "last_duration_s": 0.0, "error_count": 0, "consecutive_failures": 0, "next_run_after": None},
    "behavioral_score":    {"last_run": None, "last_status": "pending", "last_duration_s": 0.0, "error_count": 0, "consecutive_failures": 0, "next_run_after": None},
    "recurring_detection": {"last_run": None, "last_status": "pending", "last_duration_s": 0.0, "error_count": 0, "consecutive_failures": 0, "next_run_after": None},
    "stock_ml_update":     {"last_run": None, "last_status": "pending", "last_duration_s": 0.0, "error_count": 0, "consecutive_failures": 0, "next_run_after": None},
    "genetic_optimization": {"last_run": None, "last_status": "pending", "last_duration_s": 0.0, "error_count": 0, "consecutive_failures": 0, "next_run_after": None},
}

import time
from datetime import timedelta


def _wrap_job(name: str, fn):
    """Wrap a job function to track last_run, last_status, duration, and backoff."""
    def wrapped():
        # Check backoff
        next_run = _job_status[name].get("next_run_after")
        if next_run:
            next_run_dt = datetime.fromisoformat(next_run)
            if datetime.now() < next_run_dt:
                log.info(f"JOB {name} skipped due to backoff (next run after {next_run})")
                return

        start_time = time.time()
        try:
            fn()
            duration = time.time() - start_time
            _job_status[name]["last_run"]    = datetime.now().isoformat()
            _job_status[name]["last_status"] = "ok"
            _job_status[name]["last_duration_s"] = duration
            _job_status[name]["consecutive_failures"] = 0
            _job_status[name]["next_run_after"] = None
            log.info(f"JOB {name} completed in {duration:.2f}s with status ok")
        except Exception as e:
            duration = time.time() - start_time
            _job_status[name]["last_run"]    = datetime.now().isoformat()
            _job_status[name]["last_status"] = f"error: {e}"
            _job_status[name]["last_duration_s"] = duration
            _job_status[name]["error_count"] += 1
            _job_status[name]["consecutive_failures"] += 1

            failures = _job_status[name]["consecutive_failures"]
            if failures >= 3:
                backoff_minutes = min(2 ** (failures - 3), 60)
                next_run_time = datetime.now() + timedelta(minutes=backoff_minutes)
                _job_status[name]["next_run_after"] = next_run_time.isoformat()
                log.warning(f"JOB {name} failed {failures} times, backing off for {backoff_minutes} minutes")
            log.info(f"JOB {name} failed in {duration:.2f}s with status error")

    return wrapped


# ══════════════════════════════════════════════════════════════════════════════
# § SCHEDULER SETUP
# ══════════════════════════════════════════════════════════════════════════════

def build_scheduler():
    """Build and configure the APScheduler instance."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        log.error("APScheduler not installed. Run: pip install apscheduler --break-system-packages")
        sys.exit(1)

    scheduler = BlockingScheduler(timezone="Asia/Jakarta")

    # Job A: Net Worth Snapshot — daily at 00:05
    scheduler.add_job(
        _wrap_job("networth_snapshot", job_networth_snapshot),
        CronTrigger(hour=0, minute=5),
        id="networth_snapshot",
        name="Net Worth Snapshot",
        misfire_grace_time=300,
    )

    # Job B: Portfolio Price Update — every 5 minutes
    scheduler.add_job(
        _wrap_job("portfolio_prices", job_portfolio_price_update),
        IntervalTrigger(minutes=5),
        id="portfolio_prices",
        name="Portfolio Price Update",
        misfire_grace_time=60,
    )

    # Job C: Behavioral Score Update — daily at 01:00
    scheduler.add_job(
        _wrap_job("behavioral_score", job_behavioral_score_update),
        CronTrigger(hour=1, minute=0),
        id="behavioral_score",
        name="Behavioral Score Update",
        misfire_grace_time=300,
    )

    # Job D: Recurring Detection — daily at 02:00
    scheduler.add_job(
        _wrap_job("recurring_detection", job_recurring_detection),
        CronTrigger(hour=2, minute=0),
        id="recurring_detection",
        name="Recurring Detection",
        misfire_grace_time=300,
    )

    # Job E: Stock ML Update — every hour
    scheduler.add_job(
        _wrap_job("stock_ml_update", job_stock_ml_update),
        IntervalTrigger(hours=1),
        id="stock_ml_update",
        name="Stock ML Update",
        misfire_grace_time=3600,
    )

    # Job F: Genetic Optimization — monthly (1st day of month at 03:00)
    scheduler.add_job(
        _wrap_job("genetic_optimization", job_genetic_optimization),
        CronTrigger(day=1, hour=3, minute=0),
        id="genetic_optimization",
        name="Genetic Optimization",
        misfire_grace_time=86400, # 1 day grace
    )

    return scheduler


# ══════════════════════════════════════════════════════════════════════════════
# § STATUS API (lightweight HTTP for /api/scheduler/status)
#   Exposed via api_server.py — not a separate HTTP server.
#   These functions are imported by api_server.py.
# ══════════════════════════════════════════════════════════════════════════════

def get_status() -> dict:
    """Return current job status. Called by api_server.py /api/scheduler/status."""
    return {"jobs": _job_status}


def trigger_job(job_name: str) -> dict:
    """
    Manually trigger a specific job by name.
    Called by api_server.py POST /api/scheduler/trigger.
    Runs synchronously (blocking) — intended for admin/debug use.
    """
    jobs = {
        "networth":   job_networth_snapshot,
        "prices":     job_portfolio_price_update,
        "behavioral": job_behavioral_score_update,
        "recurring":  job_recurring_detection,
        "ml":         job_stock_ml_update,
        "genetic":    job_genetic_optimization,
    }
    fn = jobs.get(job_name)
    if not fn:
        return {"ok": False, "error": f"Unknown job '{job_name}'. Valid: {list(jobs.keys())}"}
    try:
        _wrap_job(job_name, fn)()
        return {"ok": True, "job": job_name, "status": _job_status.get(job_name, {})}
    except Exception as e:
        return {"ok": False, "job": job_name, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# § NETWORTH HISTORY READER (for Phase 2 graph)
# ══════════════════════════════════════════════════════════════════════════════

def get_networth_history(days: int = 90) -> list:
    """
    Return the last `days` net worth snapshots for graph visualisation.
    Called by api_server.py GET /api/networth/history.
    """
    try:
        con = _nw_db()
        rows = con.execute(
            "SELECT date, total_networth, cash, bank_savings, emergency_fund, "
            "crypto, stocks, gold, other_assets "
            "FROM networth_snapshots ORDER BY date DESC LIMIT ?",
            (days,)
        ).fetchall()
        con.close()
        return [dict(r) for r in reversed(rows)]   # chronological order for charts
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# § ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

PID_FILE = DATA_DIR / "scheduler.pid"

def _acquire_pid_lock() -> bool:
    import psutil
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if psutil.pid_exists(pid):
                return False
        except Exception:
            pass
    try:
        PID_FILE.write_text(str(os.getpid()))
        return True
    except Exception:
        return False

def _release_pid_lock():
    try:
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            if pid == os.getpid():
                PID_FILE.unlink()
    except Exception:
        pass

if __name__ == "__main__":
    if not _acquire_pid_lock():
        log.error("Another instance of the scheduler is already running. Exiting.")
        sys.exit(1)

    try:
        log.info("Finance Tracker Scheduler starting…")
        log.info(f"  API_BASE   : {API_BASE}")
        log.info(f"  NW_DB      : {NW_DB_PATH}")
        log.info("  Jobs       : A=networth(daily 00:05) B=prices(5min) C=behavioral(01:00) D=recurring(02:00)")

        # Run Job A once immediately on startup to seed networth_history.db
        log.info("Running initial net worth snapshot on startup…")
        job_networth_snapshot()

        scheduler = build_scheduler()
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")
    finally:
        _release_pid_lock()
