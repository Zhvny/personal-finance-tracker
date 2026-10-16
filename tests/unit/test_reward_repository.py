
import pytest

from packages.core.application.reward_service import RewardService
from packages.core.infrastructure.persistence.postgres_reward_repository import PostgresRewardRepository


def test_reward_state_can_be_saved_and_read_without_aliasing(tmp_path):
    storage = tmp_path / "rewards_test.json"
    repository = PostgresRewardRepository(storage_path=storage)
    saved = repository.save_state({"lust": 12, "unlockedRewards": ["starter"]})

    assert saved["lust"] == 12.0
    saved["unlockedRewards"].append("mutated-outside")
    assert repository.get_state()["unlockedRewards"] == ["starter"]

def test_reward_state_rejects_invalid_unlocked_rewards(tmp_path):
    storage = tmp_path / "rewards_test.json"
    with pytest.raises(ValueError, match="unlockedRewards"):
        PostgresRewardRepository(storage_path=storage).save_state({"unlockedRewards": "starter"})

def test_self_reward_crud_and_redemption(tmp_path):
    storage = tmp_path / "rewards_test.json"
    repo = PostgresRewardRepository(storage_path=storage)
    service = RewardService(repository=repo)

    # Give user 100 lust points
    service.add_lust_points(100.0)
    assert service.get_state()["lust"] == 100.0

    # Add a self-reward
    reward = service.add_self_reward(
        title="Extra Coffee",
        cost=30.0,
        cost_type="lust",
        description="Treat myself to a caramel macchiato",
        icon="☕"
    )
    assert reward["title"] == "Extra Coffee"
    assert reward["cost"] == 30.0
    assert reward["redeemed"] is False

    # Redeem self-reward
    redeemed = service.redeem_self_reward(reward["id"])
    assert redeemed["redeemed"] is True
    assert service.get_state()["lust"] == 70.0 # 100 - 30

    # Verify persistence: create new repo instance with same storage file
    repo2 = PostgresRewardRepository(storage_path=storage)
    state2 = repo2.get_state()
    assert state2["lust"] == 70.0
    assert len(state2["selfRewards"]) == 1
    assert state2["selfRewards"][0]["title"] == "Extra Coffee"

    # Delete self-reward
    assert service.delete_self_reward(reward["id"]) is True
    assert len(service.get_state()["selfRewards"]) == 0
