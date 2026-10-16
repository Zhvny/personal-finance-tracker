"""
Regression tests for goal PATCH semantics (Phase 8).

Covers the fix for the destructive-bug where PATCH /api/goals/{id} executed a
DELETE instead of an UPDATE, and the typed-update hardening (amounts coerced
to float, dates parsed, current <= target enforced against stored values) now
living in packages/api/backend/finance/goals_service.py (router:
packages/api/backend/routers/goals.py).
"""
import pytest

from packages.api.backend.finance import goals_service as gs


@pytest.fixture
def goals_db(tmp_path):
    """Hermetic SQLite goals DB (avoid the 'goals.db' Postgres redirection)."""
    return str(tmp_path / "unit_goals.sqlite")


def _add_goal(goals_db, **kwargs):
    body = {
        "name": "Laptop",
        "target_amount": 12_000_000,
        "current_amount": 5_000_000,
        "target_date": "2026-12-31",
    }
    body.update(kwargs)
    return gs.create_goal(goals_db, **body)["goal_id"]


def test_patch_updates_instead_of_deleting(goals_db):
    goal_id = _add_goal(goals_db)
    result = gs.update_goal(goals_db, goal_id, current_amount=6_000_000)
    assert result["current_amount"] == 6_000_000

    goals = gs.list_goals(goals_db)
    assert len(goals) == 1, "goal must still exist after PATCH"
    assert goals[0]["current_amount"] == 6_000_000
    assert goals[0]["name"] == "Laptop"
    assert goals[0]["target_amount"] == 12_000_000


def test_patch_supports_name_title_and_deadline_aliases(goals_db):
    goal_id = _add_goal(goals_db)
    updated = gs.update_goal(goals_db, goal_id, title="Gaming Laptop", deadline="2027-06-30")
    assert updated["name"] == "Gaming Laptop"
    assert updated["target_date"] == "2027-06-30"


def test_patch_multiple_fields_at_once(goals_db):
    goal_id = _add_goal(goals_db)
    updated = gs.update_goal(
        goals_db, goal_id,
        name="MacBook", target_amount=25_000_000, current_amount=10_000_000,
    )
    assert updated["name"] == "MacBook"
    assert updated["target_amount"] == 25_000_000
    assert updated["current_amount"] == 10_000_000


def test_patch_rejects_current_above_target(goals_db):
    goal_id = _add_goal(goals_db)
    with pytest.raises(gs.GoalError):
        gs.update_goal(goals_db, goal_id, current_amount=13_000_000)
    with pytest.raises(gs.GoalError):
        gs.update_goal(goals_db, goal_id, target_amount=100_000)
    with pytest.raises(gs.GoalError):
        gs.update_goal(goals_db, goal_id, current_amount=6_000_000, target_amount=10)


def test_patch_rejects_invalid_values(goals_db):
    goal_id = _add_goal(goals_db)
    with pytest.raises(gs.GoalError):
        gs.update_goal(goals_db, goal_id, target_amount=0)
    with pytest.raises(gs.GoalError):
        gs.update_goal(goals_db, goal_id, current_amount=-1)
    with pytest.raises(gs.GoalError):
        gs.update_goal(goals_db, goal_id, unknown_field=1)


def test_patch_unknown_goal_raises(goals_db):
    with pytest.raises(gs.GoalError):
        gs.update_goal(goals_db, 999_999, current_amount=1)


def test_patch_invalid_goal_id(goals_db):
    with pytest.raises(gs.GoalError):
        gs.update_goal(goals_db, 0, current_amount=1)
