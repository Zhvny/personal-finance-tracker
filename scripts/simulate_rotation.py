#!/usr/bin/env python3
"""Simulation script for 26-week reward rotation.

Proves:
  1. Exactly 12 items selected each week.
  2. Exact tier composition: 5 basic, 4 mid, 2 premium, 1 ultra.
  3. Zero intra-week duplicates (all 12 items distinct each week).
  4. Ultra items: 0 repeat across all 26 weeks (26 distinct out of 75).
  5. Premium items: 0 repeat across all 26 weeks (52 distinct out of 75).
  6. Mid & Basic: 0 repeat until initial pool capacity is exhausted
     (18 weeks for mid, 15 weeks for basic), then oldest items are reused
     with maximum possible separation (>= 15 weeks for basic, >= 18 weeks for mid).
  7. Pool never exhausts; all 312 slots successfully filled.
"""
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

# Add project root to sys.path so packages/ is importable
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from packages.core.infrastructure.persistence.reward_pool import seed_pool
from packages.core.infrastructure.persistence.reward_rotation_repository import (
    RewardRotationRepository,
)
from packages.core.domain.services.reward_rotation_service import (
    RewardRotationService,
    TIER_QUOTAS,
)


def run_simulation(halal_only: bool = True):
    mode_label = "halal_only=1" if halal_only else "halal_only=0 (all)"
    print(f"\n[*] Starting 26-week reward rotation simulation ({mode_label})...")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # 1. Seed master pool
    n_seeded = seed_pool(conn)
    print(f"[*] Seeded master pool: {n_seeded} items.")
    assert n_seeded >= 300, f"Expected >= 300 items, got {n_seeded}"

    repo = RewardRotationRepository()
    repo.ensure_tables(conn)
    service = RewardRotationService(repository=repo, conn=conn)

    start_monday = date(2026, 1, 5) # Week 1
    total_slots = 0
    all_selections = [] # list of (week_idx, week_date, pool)
    item_history = defaultdict(list) # item_id -> list of week_indices when chosen

    for week_idx in range(1, 27):
        current_monday = start_monday + timedelta(days=7 * (week_idx - 1))
        pool = service.rotate_week(target_week_start=current_monday, halal_only=halal_only)
        items = pool["items"]
        total_slots += len(items)

        # 1. Exactly 12 items per week
        assert len(items) == 12, f"Week {week_idx} ({current_monday}) did not have 12 items, got {len(items)}"
        if halal_only:
            assert all(i.get("halal", True) is True for i in items)
            assert not any(i["name_en"] in ("Tonkotsu Ramen Bowl", "Ramen and Gyoza Set", "Personal Charcuterie Box") for i in items)

        # 2. Composition check
        tiers = Counter(i["tier"] for i in items)
        for tier, expected_count in TIER_QUOTAS.items():
            assert tiers[tier] == expected_count, (
                f"Week {week_idx} tier {tier} count {tiers[tier]} != expected {expected_count}"
            )

        # 3. No intra-week duplicates
        item_ids = [i["id"] for i in items]
        assert len(set(item_ids)) == 12, f"Week {week_idx} has intra-week duplicates: {item_ids}"

        # Track appearances
        for it in items:
            item_history[it["id"]].append(week_idx)

        all_selections.append((week_idx, current_monday, pool))

    print(f"[+] All 26 weeks simulated successfully ({total_slots} slots filled).")

    # 4. Ultra tier: 26 weeks * 1 = 26 items needed. Pool has 75. Must have ZERO repeats.
    ultra_items = [item_id for item_id, weeks in item_history.items() if any(w for w in weeks if _get_tier(conn, item_id) == "ultra")]
    ultra_multi_picks = [item_id for item_id in ultra_items if len(item_history[item_id]) > 1]
    assert len(ultra_multi_picks) == 0, f"Ultra tier had repeating items: {ultra_multi_picks}"
    print(f"[+] Ultra tier: 26 distinct items selected across 26 weeks (0 repeats).")

    # 5. Premium tier: 26 weeks * 2 = 52 items needed. Pool has 75. Must have ZERO repeats.
    premium_items = [item_id for item_id, weeks in item_history.items() if any(w for w in weeks if _get_tier(conn, item_id) == "premium")]
    premium_multi_picks = [item_id for item_id in premium_items if len(item_history[item_id]) > 1]
    assert len(premium_multi_picks) == 0, f"Premium tier had repeating items: {premium_multi_picks}"
    print(f"[+] Premium tier: 52 distinct items selected across 26 weeks (0 repeats).")

    # 6. Basic tier: 75 items in pool, 5 needed/week -> 15 weeks zero-repeat.
    # When repeating in week 16+, gap between repeats must be >= 15 weeks.
    for item_id, weeks in item_history.items():
        if _get_tier(conn, item_id) == "basic" and len(weeks) > 1:
            for i in range(len(weeks) - 1):
                gap = weeks[i + 1] - weeks[i]
                assert gap >= 15, f"Basic item {item_id} repeated with too small gap: {gap} weeks (weeks: {weeks})"
    print(f"[+] Basic tier: initial 15 weeks 0-repeat, subsequent repeats separated by >= 15 weeks.")

    # 7. Mid tier: 75 items in pool, 4 needed/week -> 18 weeks zero-repeat.
    # When repeating in week 19+, gap between repeats must be >= 18 weeks.
    for item_id, weeks in item_history.items():
        if _get_tier(conn, item_id) == "mid" and len(weeks) > 1:
            for i in range(len(weeks) - 1):
                gap = weeks[i + 1] - weeks[i]
                assert gap >= 18, f"Mid item {item_id} repeated with too small gap: {gap} weeks (weeks: {weeks})"
    print(f"[+] Mid tier: initial 18 weeks 0-repeat, subsequent repeats separated by >= 18 weeks.")

    # 8. Idempotency verification: re-running any week produces identical result
    recheck_week = service.rotate_week(target_week_start=start_monday + timedelta(days=7 * 5))
    assert [i["id"] for i in recheck_week["items"]] == [i["id"] for i in all_selections[5][2]["items"]]
    print(f"[+] Idempotency recheck on week 6 verified.")

    print("\n[SUCCESS] 26-week simulation PASSED all criteria.")


def _get_tier(conn, item_id: int) -> str:
    cur = conn.cursor()
    cur.execute("SELECT tier FROM reward_pool_master WHERE id = ?", (item_id,))
    row = cur.fetchone()
    return row[0] if row else ""


def test_26_week_simulation():
    """Pytest entrypoint for 26-week rotation simulation."""
    run_simulation(halal_only=True)
    run_simulation(halal_only=False)


if __name__ == "__main__":
    try:
        run_simulation()
    except Exception as e:
        print(f"\n[FAILURE] Simulation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
