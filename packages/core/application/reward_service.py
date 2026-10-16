from typing import Any, Dict, List, Optional

from packages.core.domain.services.reward_engine import RewardEngine, UnlockContext
from packages.core.infrastructure.persistence.postgres_reward_repository import PostgresRewardRepository


class RewardService:
    def __init__(self, repository: Optional[PostgresRewardRepository] = None):
        self.repository = repository or PostgresRewardRepository()
        self.engine = RewardEngine()

    def get_state(self) -> Dict[str, Any]:
        """Fetch current reward state."""
        return self.repository.get_state()

    def save_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Overwrite / merge reward state."""
        return self.repository.save_state(state)

    def check_and_apply(self, conn: Any = None) -> List[Dict[str, str]]:
        """
        Fetches current state, checks for new unlocks, and updates state if needed.
        Returns list of newly unlocked rewards.
        Uses atomic update to prevent race conditions.
        """
        newly_unlocked = []

        def update_logic(state: Dict[str, Any]):
            nonlocal newly_unlocked
            ctx = UnlockContext(
                lust=float(state.get("lust", 0)),
                lifetime_lust=float(state.get("lifetimeLust", 0)),
                streak_days=int(state.get("streakDays", 0)),
                total_saved_cumulative=float(state.get("totalSavedCumulative", 0)),
                already_unlocked=tuple(state.get("unlockedRewards", []))
            )

            newly_unlocked = self.engine.check_unlocks(ctx)

            if newly_unlocked:
                unlocked_ids = [r["reward_id"] for r in newly_unlocked]
                state["unlockedRewards"] = list(set(state.get("unlockedRewards", []) + unlocked_ids))

        self.repository._update_state_atomic(update_logic, conn=conn)
        return newly_unlocked

    def patch_state(self, patch: Dict[str, Any], conn: Any = None):
        """Atomically merge a patch into the reward state."""
        def update_logic(state: Dict[str, Any]):
            state.update(patch)

        self.repository._update_state_atomic(update_logic, conn=conn)

    def add_lust_points(self, amount: float, conn: Any = None):
        self.repository.add_lust_points(amount, conn=conn)
        return self.check_and_apply(conn=conn)

    def add_savings(self, amount: float, conn: Any = None):
        self.repository.add_savings(amount, conn=conn)
        return self.check_and_apply(conn=conn)

    # ── Self Reward Management ───────────────────────────────────────────────
    def add_self_reward(self, title: str, cost: float, cost_type: str = "lust", description: str = "", icon: str = "🎁") -> Dict[str, Any]:
        """Create a new user self-reward item."""
        return self.repository.add_self_reward(title, cost, cost_type, description, icon)

    def redeem_self_reward(self, reward_id: str) -> Dict[str, Any]:
        """Redeem a user self-reward item."""
        return self.repository.redeem_self_reward(reward_id)

    def delete_self_reward(self, reward_id: str) -> bool:
        """Remove a user self-reward item."""
        return self.repository.delete_self_reward(reward_id)
