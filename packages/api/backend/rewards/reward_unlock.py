"""
reward_unlock.py — Server-side Automatic Reward Unlock
=======================================================
Pure computation layer. No I/O, no FastAPI, no side effects.

Clean Architecture : Domain ring — only unlock rules live here.
Single Responsibility: ONLY determines which rewards should auto-unlock.
Open/Closed         : Add new milestone rules without touching callers.
DRY                 : All thresholds defined once in MILESTONE_RULES.

Called from api_server.py after:
  - POST /api/income       (income added)
  - POST /api/expenses     (expense/saving recorded)
  - POST /api/receipt/export (receipt imported)

Returns list of reward IDs that became newly eligible so the caller
can patch them into the persistent reward state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

# ══════════════════════════════════════════════════════════════════════════════
# § 1  MILESTONE RULES — single source of truth
#
# Each rule defines ONE unlock condition keyed to a financial metric.
# The reward_id must match a folder name in public/rewards/.
#
# metric        : key in the FinancialContext dict
# threshold     : value that must be reached (>=)
# reward_id     : which reward to auto-unlock
# description   : human-readable reason (shown in UI notification)
# ══════════════════════════════════════════════════════════════════════════════

MILESTONE_RULES: List[Dict[str, Any]] = [
    # ── Saving milestones (cumulative totalSavedCumulative from lust state) ──
    {
        "metric":      "total_saved_cumulative",
        "threshold":   500_000,
        "reward_id":   "reward-1",
        "description": "Nabung pertama Rp 500K — reward ke-1 terbuka!",
    },
    {
        "metric":      "total_saved_cumulative",
        "threshold":   2_000_000,
        "reward_id":   "reward-2",
        "description": "Tabungan kumulatif Rp 2 juta — reward ke-2 terbuka!",
    },
    {
        "metric":      "total_saved_cumulative",
        "threshold":   5_000_000,
        "reward_id":   "reward-3",
        "description": "Tabungan kumulatif Rp 5 juta — reward ke-3 terbuka!",
    },
    {
        "metric":      "total_saved_cumulative",
        "threshold":   10_000_000,
        "reward_id":   "reward-4",
        "description": "Tabungan kumulatif Rp 10 juta — reward ke-4 terbuka!",
    },
    {
        "metric":      "total_saved_cumulative",
        "threshold":   25_000_000,
        "reward_id":   "reward-5",
        "description": "Tabungan kumulatif Rp 25 juta — reward ke-5 terbuka!",
    },
    # ── Lust (Lust points) milestones ────────────────────────────────────────
    {
        "metric":      "lust",
        "threshold":   500,
        "reward_id":   "reward-6",
        "description": "500 Lust tercapai — reward ke-6 terbuka!",
    },
    {
        "metric":      "lust",
        "threshold":   2_000,
        "reward_id":   "reward-7",
        "description": "2.000 Lust tercapai — reward ke-7 terbuka!",
    },
    {
        "metric":      "lust",
        "threshold":   5_000,
        "reward_id":   "reward-8",
        "description": "5.000 Lust tercapai — reward ke-8 terbuka!",
    },
    {
        "metric":      "lust",
        "threshold":   10_000,
        "reward_id":   "reward-9",
        "description": "10.000 Lust tercapai — reward ke-9 terbuka!",
    },
    # ── Streak milestones ─────────────────────────────────────────────────────
    {
        "metric":      "streak_days",
        "threshold":   3,
        "reward_id":   "reward-10",
        "description": "3 hari streak nabung — reward ke-10 terbuka!",
    },
    {
        "metric":      "streak_days",
        "threshold":   7,
        "reward_id":   "reward-11",
        "description": "7 hari streak nabung — reward ke-11 terbuka!",
    },
    {
        "metric":      "streak_days",
        "threshold":   30,
        "reward_id":   "reward-12",
        "description": "30 hari streak nabung — reward ke-12 terbuka!",
    },
    # ── Lifetime Lust milestones ──────────────────────────────────────────────
    {
        "metric":      "lifetime_lust",
        "threshold":   8_000,
        "reward_id":   "reward-13",
        "description": "Gold rank tercapai — reward ke-13 terbuka!",
    },
    {
        "metric":      "lifetime_lust",
        "threshold":   25_000,
        "reward_id":   "reward-14",
        "description": "Platinum rank tercapai — reward ke-14 terbuka!",
    },
    {
        "metric":      "lifetime_lust",
        "threshold":   75_000,
        "reward_id":   "reward-15",
        "description": "Diamond rank tercapai — reward ke-15 terbuka!",
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# § 2  CONTEXT — typed input for the unlock checker
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class UnlockContext:
    """
    Financial metrics snapshot passed to check_unlocks().
    All values are safe defaults (0) when data is unavailable.
    """
    lust:                  float = 0.0
    lifetime_lust:         float = 0.0
    streak_days:           int   = 0
    total_saved_cumulative: float = 0.0
    already_unlocked:      tuple = ()   # tuple of reward_id strings already unlocked


# ══════════════════════════════════════════════════════════════════════════════
# § 3  PURE UNLOCK CHECKER
# ══════════════════════════════════════════════════════════════════════════════

def check_unlocks(ctx: UnlockContext) -> List[Dict[str, str]]:
    """
    Evaluate all MILESTONE_RULES against the given context.
    Returns only rewards that are:
      1. Not already unlocked (not in ctx.already_unlocked)
      2. Threshold met (ctx.<metric> >= rule.threshold)

    Returns list of { reward_id, description } dicts.
    Never raises — individual rule errors are silently skipped.
    """
    newly_unlocked: List[Dict[str, str]] = []
    already = set(ctx.already_unlocked)

    for rule in MILESTONE_RULES:
        reward_id = rule["reward_id"]
        if reward_id in already:
            continue  # already unlocked — skip

        try:
            metric_val = getattr(ctx, rule["metric"], 0) or 0
            if metric_val >= rule["threshold"]:
                newly_unlocked.append({
                    "reward_id":   reward_id,
                    "description": rule["description"],
                    "metric":      rule["metric"],
                    "threshold":   rule["threshold"],
                    "value":       metric_val,
                })
        except Exception:
            continue  # rule evaluation failure must never break caller

    return newly_unlocked


def build_context_from_state(reward_state: dict) -> UnlockContext:
    """
    Build UnlockContext from the persisted reward_state dict (from goals.db).
    Handles missing/None keys safely.
    """
    already = tuple(reward_state.get("unlockedRewards") or [])
    return UnlockContext(
        lust=float(reward_state.get("lust") or 0),
        lifetime_lust=float(reward_state.get("lifetimeLust") or 0),
        streak_days=int(reward_state.get("streakDays") or 0),
        total_saved_cumulative=float(reward_state.get("totalSavedCumulative") or 0),
        already_unlocked=already,
    )
