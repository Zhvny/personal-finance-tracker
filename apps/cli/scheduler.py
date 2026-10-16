#!/usr/bin/env python3
import os
import sys
from datetime import datetime
from pathlib import Path

# Add monorepo root to sys.path
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path: sys.path.insert(0, str(_root))

from packages.core import bootstrap

ROOT = bootstrap.PROJECT_ROOT

from packages.core.infrastructure.config import Config
from packages.core.infrastructure.logging import get_logger

# Add CLI app to path for modules
CLI_APP_DIR = ROOT / "apps" / "cli"
INVESTMENT_TRACKER_DIR = CLI_APP_DIR / "investment_tracker"

for p in [str(CLI_APP_DIR), str(INVESTMENT_TRACKER_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from apps.cli.genetic_optimizer import run_monthly_optimization
from apps.cli.investment_tracker.services.evaluation_engine import EvaluationEngine

PID_FILE = Config.BASE_DIR / "logs" / "scheduler.pid"
logger = get_logger("scheduler")

def is_running(pid):
    """Check if a process is running on Windows/Linux."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

def run_npm_audit():
    """Run npm audit on packages/web and report any CVEs via Telegram and logs."""
    import json
    import subprocess
    logger.info('Executing npm audit check on packages/web...')
    web_dir = ROOT / "packages" / "web"
    try:
        res = subprocess.run(["npm", "audit", "--json"], cwd=str(web_dir), capture_output=True, text=True)

        log_dir = ROOT / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        audit_log_file = log_dir / "npm_audit.log"
        with open(audit_log_file, "w") as f:
            f.write(res.stdout or res.stderr)

        logger.info(f"npm audit output saved to {audit_log_file}")

        if not res.stdout.strip():
            logger.info("npm audit output is empty.")
            return

        try:
            data = json.loads(res.stdout)
            if "error" in data:
                logger.error(f"npm audit error: {data['error']}")
                return

            vulnerabilities = data.get("metadata", {}).get("vulnerabilities", {})
            total = vulnerabilities.get("total", 0)

            if total > 0:
                msg = (
                    f"⚠️ <b>NPM AUDIT WARNING: VULNERABILITIES DETECTED!</b>\n\n"
                    f"Lokasi: <b>packages/web</b>\n"
                    f"Total CVE: <b>{total}</b>\n"
                    f"• Low: {vulnerabilities.get('low', 0)}\n"
                    f"• Moderate: {vulnerabilities.get('moderate', 0)}\n"
                    f"• High: {vulnerabilities.get('high', 0)}\n"
                    f"• Critical: {vulnerabilities.get('critical', 0)}\n\n"
                    f"Silakan periksa log lengkap di <code>logs/npm_audit.log</code> dan jalankan <code>npm audit fix</code>."
                )
                from packages.core.utils.telegram_notifier import send_telegram_notification
                send_telegram_notification(msg)
                logger.warning(f"Vulnerabilities found: {total}. Telegram alert sent.")
            else:
                logger.info("No vulnerabilities found in packages/web.")
        except Exception as json_err:
            logger.warning(f"Failed to parse npm audit JSON output: {json_err}")
            if res.returncode != 0:
                msg = (
                    "⚠️ <b>NPM AUDIT WARNING</b>\n\n"
                    "Pemeriksaan <code>npm audit</code> di packages/web mendeteksi kerentanan keamanan.\n"
                    "Silakan periksa log lengkap di <code>logs/npm_audit.log</code>."
                )
                from packages.core.utils.telegram_notifier import send_telegram_notification
                send_telegram_notification(msg)
                logger.warning(f"npm audit found issues (non-zero exit code {res.returncode}).")
            else:
                logger.info("npm audit completed successfully with no issues.")
    except Exception as e:
        logger.exception(f'npm audit execution failed: {e}')

def acquire_lock():
    """Acquire PID lock, handles stale PIDs."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    if PID_FILE.exists():
        try:
            with open(PID_FILE, 'r') as f:
                pid_str = f.read().strip()
                if not pid_str:
                    raise ValueError("Empty PID file")
                pid = int(pid_str)

            if is_running(pid):
                logger.warning(f"Scheduler already running with PID {pid}. Exiting.")
                sys.exit(0)
            else:
                logger.info(f"Detected stale PID file (PID {pid} not running). Overwriting.")
        except (ValueError, OSError):
            logger.info("Detected corrupt or empty PID file. Overwriting.")

    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

def release_lock():
    """Remove PID file."""
    if PID_FILE.exists():
        PID_FILE.unlink()

def main():
    acquire_lock()
    try:
        logger.info(f'--- Scheduler Run Started: {datetime.now()} ---')

        logger.info('Executing Monthly Genetic Optimization...')
        try:
            run_monthly_optimization()
        except Exception as e:
            logger.exception(f'Genetic Optimization Failed: {e}')

        logger.info('Executing Agent Senate Evaluation...')
        try:
            engine = EvaluationEngine()
            count = engine.evaluate_pending_predictions()
            logger.info(f'Evaluated {count} Senate predictions.')
        except Exception as e:
            logger.exception(f'Agent Senate Evaluation Failed: {e}')

        logger.info('Executing npm audit vulnerability check...')
        try:
            run_npm_audit()
        except Exception as e:
            logger.exception(f'npm audit check Failed: {e}')

        logger.info('--- Scheduler Run Completed ---')
    finally:
        release_lock()

if __name__ == "__main__":
    main()
