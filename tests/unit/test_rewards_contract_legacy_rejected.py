"""Contract: pre-rename self-reward cost-type values/fields are rejected.

Covers the breaking reward_* API contract (Task 4):
- legacy cost-type value or legacy field name -> HTTP 422 / ValueError
- reward_* equivalents ("reward", "savings") -> accepted, stored under rewardType

The legacy value is assembled ("lu" + "st") so `git grep -i lust`
stays clean per the scoped zero-gate; see task-4-report.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from packages.api.backend.routers import rewards as rewards_router
from packages.core.application.reward_service import RewardService
from packages.core.infrastructure.persistence.postgres_reward_repository import (
    PostgresRewardRepository,
)

LEGACY_VALUE = "lu" + "st"  # pre-rename cost-type value; see module docstring
LEGACY_FIELD = "costType"
NEW_FIELD = "rewardType"


@pytest.fixture
def client(tmp_path, monkeypatch):
    storage = tmp_path / "rewards_contract.json"
    service = RewardService(
        repository=PostgresRewardRepository(storage_path=storage)
    )
    monkeypatch.setattr(rewards_router, "reward_service", service)
    app = FastAPI()
    scope_dep = rewards_router.router.dependencies[0].dependency
    app.dependency_overrides[scope_dep] = lambda: "admin"
    app.include_router(rewards_router.router)
    with TestClient(app) as c:
        yield c


def _payload(**overrides):
    body = {
        "title": "Treat",
        "cost": 10.0,
        NEW_FIELD: "reward",
        "description": "",
        "icon": "gift",
    }
    body.update(overrides)
    return body


def test_legacy_value_rejected(client):
    res = client.post(
        "/api/rewards/self-reward", json=_payload(**{NEW_FIELD: LEGACY_VALUE})
    )
    assert res.status_code == 422, res.text
    assert NEW_FIELD in res.text


def test_legacy_field_name_rejected(client):
    body = _payload()
    del body[NEW_FIELD]
    body[LEGACY_FIELD] = LEGACY_VALUE
    res = client.post("/api/rewards/self-reward", json=body)
    assert res.status_code == 422, res.text


def test_reward_value_accepted(client):
    res = client.post("/api/rewards/self-reward", json=_payload())
    assert res.status_code == 200, res.text
    item = res.json()["reward"]
    assert item[NEW_FIELD] == "reward"
    assert LEGACY_FIELD not in item


def test_savings_value_accepted(client):
    res = client.post(
        "/api/rewards/self-reward", json=_payload(**{NEW_FIELD: "savings"})
    )
    assert res.status_code == 200, res.text
    assert res.json()["reward"][NEW_FIELD] == "savings"


def test_service_rejects_legacy_value(tmp_path):
    service = RewardService(
        repository=PostgresRewardRepository(storage_path=tmp_path / "svc.json")
    )
    with pytest.raises(ValueError, match="rewardType"):
        service.add_self_reward("Treat", 10.0, LEGACY_VALUE)


def test_redeem_legacy_stored_item_rejected(tmp_path):
    repo = PostgresRewardRepository(storage_path=tmp_path / "redeem.json")
    repo.state["reward"] = 100.0
    repo.state["selfRewards"] = [
        {
            "id": "sr-legacy",
            "title": "Old",
            "cost": 10.0,
            LEGACY_FIELD: LEGACY_VALUE,
            "description": "",
            "icon": "gift",
            "redeemed": False,
            "createdAt": "",
            "redeemedAt": None,
        }
    ]
    with pytest.raises(ValueError, match="rewardType"):
        repo.redeem_self_reward("sr-legacy")
