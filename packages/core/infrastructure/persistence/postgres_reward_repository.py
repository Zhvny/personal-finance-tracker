import json
import logging
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from packages.core.infrastructure.config import Config

logger = logging.getLogger(__name__)


def _normalize_cost_type(cost_type: Optional[str], reward_id: str = "") -> str:
    """Map legacy/unknown cost types to the supported set with an explicit log.

    Old items stored under the pre-rename cost type must not pass through
    silently — they are converted to "reward" with a warning.
    """
    if cost_type in ("reward", "savings"):
        return cost_type  # type: ignore[return-value]
    scope = f" for self-reward {reward_id}" if reward_id else ""
    logger.warning("Legacy costType %r%s; converting to 'reward'", cost_type, scope)
    return "reward"


class PostgresRewardRepository:
    """
    Persistent Reward Repository (File + Memory + DB compatible).
    Prevents data loss on application restart and supports Self-Rewards.
    """
    def __init__(self, storage_path: Optional[Path] = None):
        self._lock = threading.Lock()
        if storage_path:
            self.storage_path = storage_path
        else:
            data_dir = Config.BASE_DIR / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.storage_path = data_dir / "rewards_state.json"

        self.state: Dict[str, Any] = {
            "reward": 0.0,
            "lifetimeReward": 0.0,
            "streakDays": 0,
            "totalSavedCumulative": 0.0,
            "unlockedRewards": [],
            "selfRewards": []
        }
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Loads state from persistent storage file if it exists."""
        if not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.state.update(data)
                    # Normalize types
                    self.state["reward"] = float(self.state.get("reward", 0) or 0)
                    self.state["lifetimeReward"] = float(self.state.get("lifetimeReward", 0) or 0)
                    self.state["streakDays"] = int(self.state.get("streakDays", 0) or 0)
                    self.state["totalSavedCumulative"] = float(self.state.get("totalSavedCumulative", 0) or 0)
                    if not isinstance(self.state.get("unlockedRewards"), list):
                        self.state["unlockedRewards"] = []
                    if not isinstance(self.state.get("selfRewards"), list):
                        self.state["selfRewards"] = []
        except Exception:
            pass

    def _save_to_disk(self) -> None:
        """Atomically saves state to persistent storage file."""
        try:
            temp_path = self.storage_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, self.storage_path)
        except Exception:
            pass

    def get_state(self) -> Dict[str, Any]:
        """Return a copy so callers cannot mutate repository state accidentally."""
        with self._lock:
            return deepcopy(self.state)

    def save_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Replace the reward state after validating the API payload shape."""
        if not isinstance(state, dict):
            raise ValueError("Reward state must be an object")

        with self._lock:
            next_state = deepcopy(self.state)
            next_state.update(deepcopy(state))
            next_state["reward"] = float(next_state.get("reward", 0) or 0)
            next_state["lifetimeReward"] = float(next_state.get("lifetimeReward", 0) or 0)
            next_state["streakDays"] = int(next_state.get("streakDays", 0) or 0)
            next_state["totalSavedCumulative"] = float(next_state.get("totalSavedCumulative", 0) or 0)

            unlocked = next_state.get("unlockedRewards", [])
            if not isinstance(unlocked, list):
                raise ValueError("unlockedRewards must be a list")
            next_state["unlockedRewards"] = unlocked

            self_rewards = next_state.get("selfRewards", [])
            if not isinstance(self_rewards, list):
                raise ValueError("selfRewards must be a list")
            next_state["selfRewards"] = self_rewards

            self.state = next_state
            self._save_to_disk()
            return deepcopy(self.state)

    def _update_state_atomic(self, update_fn: Callable[[Dict[str, Any]], None], conn: Any = None):
        """Thread-safe atomic state update."""
        with self._lock:
            update_fn(self.state)
            self._save_to_disk()

    def add_reward_points(self, amount: float, conn: Any = None):
        with self._lock:
            self.state["reward"] += float(amount)
            self.state["lifetimeReward"] += float(amount)
            self._save_to_disk()

    def add_savings(self, amount: float, conn: Any = None):
        with self._lock:
            self.state["totalSavedCumulative"] += float(amount)
            self._save_to_disk()

    def add_self_reward(self, title: str, cost: float, cost_type: str = "reward", description: str = "", icon: str = "🎁") -> Dict[str, Any]:
        """Add a custom user self-reward item."""
        cost_type = _normalize_cost_type(cost_type)
        with self._lock:
            reward_id = f"sr-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
            new_item = {
                "id": reward_id,
                "title": title.strip(),
                "cost": float(cost),
                "costType": cost_type, # "reward" or "savings"
                "description": description.strip(),
                "icon": icon,
                "redeemed": False,
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "redeemedAt": None
            }
            if "selfRewards" not in self.state or not isinstance(self.state["selfRewards"], list):
                self.state["selfRewards"] = []
            self.state["selfRewards"].append(new_item)
            self._save_to_disk()
            return new_item

    def redeem_self_reward(self, reward_id: str) -> Dict[str, Any]:
        """Redeem a custom self-reward item, deducting cost if cost_type is reward."""
        with self._lock:
            self_rewards = self.state.get("selfRewards", [])
            target = None
            for item in self_rewards:
                if item.get("id") == reward_id:
                    target = item
                    break

            if not target:
                raise ValueError(f"Self reward with ID '{reward_id}' not found")

            if target.get("redeemed"):
                raise ValueError("Self reward has already been redeemed")

            cost = float(target.get("cost", 0))
            cost_type = _normalize_cost_type(target.get("costType", "reward"), reward_id)

            if cost_type == "reward":
                if self.state["reward"] < cost:
                    raise ValueError(f"Insufficient Reward points! Required: {cost}, Available: {self.state['reward']}")
                self.state["reward"] -= cost

            target["redeemed"] = True
            target["redeemedAt"] = datetime.now(timezone.utc).isoformat()
            self._save_to_disk()
            return target

    def delete_self_reward(self, reward_id: str) -> bool:
        """Remove a custom self-reward item."""
        with self._lock:
            self_rewards = self.state.get("selfRewards", [])
            initial_len = len(self_rewards)
            self.state["selfRewards"] = [r for r in self_rewards if r.get("id") != reward_id]
            if len(self.state["selfRewards"]) < initial_len:
                self._save_to_disk()
                return True
            return False
