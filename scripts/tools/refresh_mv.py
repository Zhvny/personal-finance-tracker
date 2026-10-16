#!/usr/bin/env python3
"""
Refresh materialized views for Alpha Finance Tracker.

Run this periodically (e.g., via cron every 5 minutes) to keep
materialized view data fresh.

Usage:
    python scripts/tools/refresh_mv.py              # Refresh all
    python scripts/tools/refresh_mv.py --view monthly  # Refresh specific

Cron example (every 5 minutes):
    */5 * * * * cd /app && python scripts/tools/refresh_mv.py
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))


def refresh_view(view_name: str, db_url: str = None) -> bool:
    """Refresh a single materialized view."""
    import psycopg2

    conn = psycopg2.connect(db_url) if db_url else None
    if not conn:
        # Try using DATABASE_URL env var
        import os

        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            logger.error("No database connection - set DATABASE_URL or pass --db-url")
            return False
        conn = psycopg2.connect(db_url)

    try:
        with conn.cursor() as cur:
            cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}")
            conn.commit()
        logger.info(f"Refreshed: {view_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to refresh {view_name}: {e}")
        return False
    finally:
        conn.close()


def refresh_all(db_url: str = None) -> dict:
    """Refresh all Alpha materialized views."""
    views = [
        "mv_monthly_expense_summary",
        "mv_monthly_income_summary",
        "mv_expense_category_current",
        "mv_monthly_pnl",
    ]

    results = {}
    for view in views:
        results[view] = refresh_view(view, db_url)

    return results


def main():
    parser = argparse.ArgumentParser(description="Refresh Alpha materialized views")
    parser.add_argument("--view", help="Specific view to refresh (default: all)")
    parser.add_argument("--db-url", help="PostgreSQL connection URL")
    parser.add_argument("--cron", action="store_true", help="Cron mode: log to file only")
    args = parser.parse_args()

    if args.cron:
        # Redirect stdout to log file for cron
        log_file = Path(__file__).parent.parent.parent / "logs" / "refresh_mv.log"
        log_file.parent.mkdir(exist_ok=True)

    if args.view:
        success = refresh_view(args.view, args.db_url)
        sys.exit(0 if success else 1)
    else:
        results = refresh_all(args.db_url)
        all_success = all(results.values())
        failed = [v for v, s in results.items() if not s]
        if failed:
            logger.warning(f"Failed views: {failed}")
        else:
            logger.info("All materialized views refreshed successfully")
        sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    main()
