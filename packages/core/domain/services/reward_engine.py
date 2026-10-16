from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


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

class RewardEngine:
    """
    Pure computation layer for reward unlocks.
    """

    MILESTONE_RULES: List[Dict[str, Any]] = [
        {"metric": "total_saved_cumulative", "threshold": 500_000, "reward_id": "reward-1", "description": "Nabung pertama Rp 500K!"},
        {"metric": "total_saved_cumulative", "threshold": 2_000_000, "reward_id": "reward-2", "description": "Tabungan Rp 2 juta!"},
        {"metric": "total_saved_cumulative", "threshold": 5_000_000, "reward_id": "reward-3", "description": "Tabungan Rp 5 juta!"},
        {"metric": "lust", "threshold": 500, "reward_id": "reward-6", "description": "500 Lust tercapai!"},
        {"metric": "lust", "threshold": 2_000, "reward_id": "reward-7", "description": "2.000 Lust tercapai!"},
        {"metric": "streak_days", "threshold": 3, "reward_id": "reward-10", "description": "3 hari streak nabung!"},
        {"metric": "lifetime_lust", "threshold": 8_000, "reward_id": "reward-13", "description": "Gold rank tercapai!"},
    ]

    def check_unlocks(self, ctx: UnlockContext) -> List[Dict[str, str]]:
        newly_unlocked: List[Dict[str, str]] = []
        already = set(ctx.already_unlocked)

        for rule in self.MILESTONE_RULES:
            reward_id = rule["reward_id"]
            if reward_id in already:
                continue

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
                continue

        return newly_unlocked
