import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

# Add paths for imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "apps" / "stock_analyzer"))
sys.path.append(str(ROOT / "apps" / "cli"))

try:
    from domain.config import AppConfig
    CONFIG_LOADED = True
except ImportError:
    CONFIG_LOADED = False

RAW_DIR = ROOT / "data" / "raw"
AUDIT_DB = ROOT / "data" / "audit" / "genetic_audit.db"

def audit_universe(dry_run=False):
    print("--- Universe Integrity Audit ---")

    if CONFIG_LOADED:
        config = AppConfig.load()
        max_assets = config.ga_max_assets
        perf_limit = 600 # Hardcoded in PortfolioOptimizer
        print(f"Config loaded. ga_max_assets: {max_assets}")
    else:
        max_assets = 7
        perf_limit = 600
        print("Config NOT loaded. Using defaults (max_assets=7, perf_limit=100)")

    # 1. Count Tickers in data/raw
    tickers = []
    if RAW_DIR.exists():
        for cat_dir in RAW_DIR.iterdir():
            if cat_dir.is_dir():
                cat_tickers = [f.stem for f in cat_dir.glob("*.csv")]
                tickers.extend([(t, cat_dir.name) for t in cat_tickers])

    total_raw = len(tickers)
    print(f"Total tickers in raw data: {total_raw}")

    if total_raw == 0:
        print("Error: No raw data found in data/raw")
        return

    # 2. Simulate PortfolioOptimizer.get_universe_audit logic
    # We'll check a few files to see if they are valid
    print(f"Auditing samples from {total_raw} tickers...")

    eligible_count = 0
    excluded = []

    # Check first 50 tickers as sample if not dry_run, else just assume all eligible
    sample_size = min(50, total_raw)
    for i in range(sample_size):
        t, cat = tickers[i]
        fpath = RAW_DIR / cat / f"{t}.csv"
        try:
            df = pd.read_csv(fpath, index_col=0, parse_dates=True)
            if df.isna().all().all():
                excluded.append({"ticker": t, "reason": "All NaNs"})
            elif len(df) < 10: # Minimum history check
                excluded.append({"ticker": t, "reason": "Insufficient history"})
            else:
                eligible_count += 1
        except Exception as e:
            excluded.append({"ticker": t, "reason": f"Read error: {str(e)}"})

    # Extrapolate eligible count
    estimated_eligible = int((eligible_count / sample_size) * total_raw) if sample_size > 0 else 0
    print(f"Estimated eligible tickers: {estimated_eligible} (based on {sample_size} samples)")

    # 3. Check Performance Fallback (Universe > 100)
    final_eligible = estimated_eligible
    if estimated_eligible > perf_limit:
        print(f"⚠️ Performance fallback would trigger: {estimated_eligible} > {perf_limit}")
        print(f"Universe would be shrunk to top {perf_limit} assets.")
        final_eligible = perf_limit

    # 4. Check Truncation Watchdog (eligible <= max_assets)
    if final_eligible <= max_assets:
        print(f"⚠️ TRUNCATION ALERT: Optimizer would run on only {final_eligible} assets (Constraint: {max_assets}).")
    else:
        print(f"Optimizer would run on {final_eligible} assets.")

    # 5. Check Database for actually evolved tickers
    evolved_count = 0
    if AUDIT_DB.exists():
        try:
            conn = sqlite3.connect(str(AUDIT_DB))
            df_logs = pd.read_sql_query("SELECT DISTINCT ticker FROM evolution_logs", conn)
            evolved_count = len(df_logs)
            print(f"Tickers actually evolved in logs: {evolved_count}")
            conn.close()
        except Exception as e:
            print(f"Error reading Audit DB: {e}")
    else:
        print("Audit DB not found yet (normal if no evolutions run).")

    if not dry_run:
        # Write report to logs
        LOG_DIR = ROOT / "logs"
        LOG_DIR.mkdir(exist_ok=True)
        report_path = LOG_DIR / "universe_audit.log"
        with open(report_path, "w") as f:
            f.write("--- Universe Integrity Audit Report ---\n")
            f.write(f"Timestamp: {pd.Timestamp.now()}\n")
            f.write(f"Total Raw Tickers: {total_raw}\n")
            f.write(f"Estimated Eligible: {estimated_eligible}\n")
            f.write(f"Final Universe Size (post-fallback): {final_eligible}\n")
            f.write(f"Evolved Tickers (logged): {evolved_count}\n")
            if excluded:
                f.write("\nSample Exclusions:\n")
                for ex in excluded[:10]:
                    f.write(f"  - {ex['ticker']}: {ex['reason']}\n")
        print(f"Report written to {report_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    audit_universe(dry_run=args.dry_run)
