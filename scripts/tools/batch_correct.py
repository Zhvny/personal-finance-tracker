#!/usr/bin/env python3
"""
Batch correct merchant mappings and deduplicate transactions.

Usage:
    python scripts/tools/batch_correct.py mode --dry-run

Modes:
    merchant_review    - Show unmapped merchants for manual review
    merchant_apply     - Apply high-confidence auto-mappings
    dedup_find        - Find potential duplicate transactions
    dedup_remove      - Remove duplicates (always --dry-run first!)

Examples:
    # See unmapped merchants
    python scripts/tools/batch_correct.py merchant_review

    # Preview auto-corrections
    python scripts/tools/batch_correct.py merchant_apply --dry-run

    # Find duplicates
    python scripts/tools/batch_correct.py dedup_find

    # Remove duplicates (preview first!)
    python scripts/tools/batch_correct.py dedup_remove --dry-run
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))


def get_db_connection():
    import os
    import psycopg2

    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/finance_tracker")
    return psycopg2.connect(db_url)


def merchant_review():
    """Show merchants that haven't been mapped yet."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Find distinct raw merchants not in mapping table
            cur.execute("""
                SELECT DISTINCT
                    LEFT(e.description, 100) as raw_merchant,
                    COUNT(*) as txn_count,
                    SUM(e.amount) as total_amount
                FROM expenses e
                LEFT JOIN merchant_mapping mm
                    ON e.description ILIKE '%' || mm.raw_merchant || '%'
                WHERE mm.id IS NULL
                AND e.description IS NOT NULL
                AND e.description != ''
                GROUP BY 1
                ORDER BY total_amount DESC
                LIMIT 50;
            """)
            rows = cur.fetchall()

        print(f"\n{'='*80}")
        print("UNMAPPED MERCHANTS (Top 50 by amount)")
        print(f"{'='*80}")
        print(f"{'Raw Merchant':<50} {'Count':>8} {'Total':>15}")
        print(f"{'-'*50} {'-'*8} {'-'*15}")
        for row in rows:
            print(f"{row[0]:<50} {row[1]:>8} ${row[2]:>14,.2f}")

        print(f"\nTotal unmapped: {len(rows)} merchants")
        return rows
    finally:
        conn.close()


def merchant_apply(dry_run: bool = True):
    """Apply high-confidence merchant auto-corrections."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Find expenses that match merchant mappings
            cur.execute("""
                SELECT e.id, e.description, mm.normalized_merchant, mm.category, mm.confidence_score
                FROM expenses e
                JOIN merchant_mapping mm
                    ON e.description ILIKE '%' || mm.raw_merchant || '%'
                WHERE mm.is_active = TRUE
                AND mm.confidence_score > 0.8
                AND e.description != mm.normalized_merchant
                LIMIT 100;
            """)
            updates = cur.fetchall()

        if not updates:
            print("No auto-corrections to apply.")
            return

        print(f"\n{'='*80}")
        print(f"MERCHANT AUTO-CORRECTIONS ({'DRY RUN' if dry_run else 'LIVE'})")
        print(f"{'='*80}")
        print(f"{'ID':<10} {'From':<30} {'To':<30} {'Conf':<8}")
        print(f"{'-'*10} {'-'*30} {'-'*30} {'-'*8}")
        for row in updates:
            print(f"{row[0]:<10} {row[1][:28]:<30} {row[2][:28]:<30} {row[4]:<8.2f}")

        if dry_run:
            print(f"\n[DRY RUN] Would update {len(updates)} transactions.")
            return

        # Apply updates
        with conn.cursor() as cur:
            for row in updates:
                cur.execute(
                    """
                    UPDATE expenses
                    SET description = %s, category = %s
                    WHERE id = %s
                """,
                    (row[2], row[3], row[0]),
                )

                # Update match count
                cur.execute(
                    """
                    UPDATE merchant_mapping
                    SET match_count = match_count + 1, updated_at = NOW()
                    WHERE raw_merchant = %s
                """,
                    (row[1],),
                )

            conn.commit()
        print(f"\n[LIVE] Updated {len(updates)} transactions.")

    finally:
        conn.close()


def dedup_find():
    """Find potential duplicate transactions."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Find transactions with same date, amount, and description
            cur.execute("""
                SELECT
                    date::date,
                    amount,
                    LEFT(description, 50) as description,
                    COUNT(*) as dup_count,
                    ARRAY_AGG(id) as ids,
                    SUM(amount) as total
                FROM expenses
                WHERE idempotency_key IS NULL
                GROUP BY 1, 2, 3
                HAVING COUNT(*) > 1
                ORDER BY total DESC
                LIMIT 50;
            """)
            duplicates = cur.fetchall()

        print(f"\n{'='*80}")
        print("POTENTIAL DUPLICATES (Top 50 by amount)")
        print(f"{'='*80}")
        print(f"{'Date':<12} {'Amount':>12} {'Description':<30} {'Count':>6} {'IDs':<30}")
        print(f"{'-'*12} {'-'*12} {'-'*30} {'-'*6} {'-'*30}")
        for row in duplicates:
            ids_str = str(row[4])[:28]
            print(f"{str(row[0]):<12} ${row[1]:>11,.2f} {row[2][:28]:<30} {row[3]:>6} {ids_str:<30}")

        print(f"\nTotal duplicate groups: {len(duplicates)}")
        total_dupes = sum(r[3] - 1 for r in duplicates)
        total_amount = sum(r[1] * (r[3] - 1) for r in duplicates)
        print(f"Duplicate transactions: {total_dupes}")
        print(f"Total duplicate amount: ${total_amount:,.2f}")
        return duplicates
    finally:
        conn.close()


def dedup_remove(dry_run: bool = True, keep_first: bool = True):
    """Remove duplicate transactions, keeping the first (or last)."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Find duplicates
            cur.execute("""
                SELECT
                    date::date,
                    amount,
                    description,
                    COUNT(*) as dup_count,
                    ARRAY_AGG(id) as ids
                FROM expenses
                WHERE idempotency_key IS NULL
                GROUP BY 1, 2, 3
                HAVING COUNT(*) > 1
            """)
            duplicates = cur.fetchall()

        if not duplicates:
            print("No duplicates found.")
            return

        to_remove = []
        for row in duplicates:
            ids = row[4]
            # Keep first (oldest by date/id) or last (newest)
            if keep_first:
                remove_ids = ids[1:]  # Remove all but first
            else:
                remove_ids = ids[:-1]  # Remove all but last
            to_remove.extend(remove_ids)

        if dry_run:
            print(f"\n[DRY RUN] Would remove {len(to_remove)} transactions:")
            print(f"  IDs: {to_remove[:20]}{'...' if len(to_remove) > 20 else ''}")
            return to_remove

        # Remove duplicates
        with conn.cursor() as cur:
            for id in to_remove:
                cur.execute("DELETE FROM expenses WHERE id = %s", (id,))
            conn.commit()
        print(f"\n[LIVE] Removed {len(to_remove)} duplicate transactions.")
        return to_remove

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Batch correct data quality issues")
    parser.add_argument(
        "mode", choices=["merchant_review", "merchant_apply", "dedup_find", "dedup_remove"], help="Operation mode"
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=True, help="Preview changes without applying (default: True)"
    )
    parser.add_argument("--live", action="store_true", help="Actually apply changes (default: dry-run)")
    args = parser.parse_args()

    dry_run = not args.live

    if args.mode == "merchant_review":
        merchant_review()
    elif args.mode == "merchant_apply":
        merchant_apply(dry_run)
    elif args.mode == "dedup_find":
        dedup_find()
    elif args.mode == "dedup_remove":
        dedup_remove(dry_run)


if __name__ == "__main__":
    main()
