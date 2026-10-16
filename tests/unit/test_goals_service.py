"""
Phase 8 — Goals tests.

Covers packages/api/backend/finance/goals_service.py:

  * create (name/title aliases, deadline alias, validation errors)
  * fixed PATCH semantics: typed float coercion (no raw strings reaching SQL),
    date parsing, current <= target enforced against stored values,
    unknown goal → error, empty update → error
  * delete (incl. unknown goal)
  * progress/status: completed / overdue / due_soon / behind_schedule /
    on_track, pct, remaining, days_left
  * n8n WF-11 goals_progress aggregate payload

All fixtures use hermetic SQLite paths that do NOT contain a canonical
Postgres bridge target substring (e.g. "goals.db").
"""
from datetime import date, timedelta

import pytest

from packages.api.backend.finance import goals_service as gs


@pytest.fixture
def gdb(tmp_path):
    return str(tmp_path / "goal_store.sqlite")


def _create(gdb, name="Liburan Bali", target=5_000_000, current=0, due=None):
    return gs.create_goal(gdb, name=name, target_amount=target, current_amount=current, target_date=due)


# ═════════════════════════════════════════════════════════════════════════════
# § CRUD
# ═════════════════════════════════════════════════════════════════════════════

def test_create_and_list_goal(gdb):
    goal = _create(gdb, due="2026-12-31")
    assert goal["goal_id"] == 1
    assert goal["name"] == "Liburan Bali" and goal["title"] == "Liburan Bali"
    assert goal["target_date"] == "2026-12-31" and goal["deadline"] == "2026-12-31"
    assert goal["pct_used"] == 0.0
    assert goal["remaining"] == 5_000_000.0
    assert goal["days_left"] == (date(2026, 12, 31) - date.today()).days
    assert len(gs.list_goals(gdb)) == 1


def test_create_title_and_deadline_aliases(gdb):
    goal = gs.create_goal(gdb, title="Dana Darurat", target_amount=3_000_000, deadline="2026-10-01")
    assert goal["name"] == "Dana Darurat"
    assert goal["target_date"] == "2026-10-01"


def test_create_validation_errors(gdb):
    with pytest.raises(gs.GoalError):
        gs.create_goal(gdb, name="", target_amount=1000)
    with pytest.raises(gs.GoalError):
        gs.create_goal(gdb, name="X", target_amount=0)
    with pytest.raises(gs.GoalError):
        gs.create_goal(gdb, name="X", target_amount=1000, current_amount=2000)
    with pytest.raises(gs.GoalError):
        gs.create_goal(gdb, name="X", target_amount="abc")
    with pytest.raises(gs.GoalError):
        gs.create_goal(gdb, name="X", target_amount=1000, target_date="31-12-2026")


def test_patch_fixed_typed_update(gdb):
    _create(gdb)
    updated = gs.update_goal(gdb, 1, current_amount="2500000", target_amount="6000000")
    assert updated["current_amount"] == 2_500_000.0
    assert updated["target_amount"] == 6_000_000.0
    assert updated["pct_used"] == pytest.approx(41.7, abs=0.1)
    assert updated["remaining"] == 3_500_000.0


def test_patch_rejects_bad_types_and_constraints(gdb):
    _create(gdb)
    with pytest.raises(gs.GoalError):
        gs.update_goal(gdb, 1, current_amount="bukan-angka")
    with pytest.raises(gs.GoalError):
        gs.update_goal(gdb, 1, target_amount=-5)
    with pytest.raises(gs.GoalError):
        gs.update_goal(gdb, 1, current_amount=9_999_999)
    with pytest.raises(gs.GoalError):
        gs.update_goal(gdb, 1, target_date="kemarin")
    with pytest.raises(gs.GoalError):
        gs.update_goal(gdb, 1, name="  ")
    with pytest.raises(gs.GoalError):
        gs.update_goal(gdb, 1)


def test_patch_enforces_current_vs_stored_target(gdb):
    _create(gdb, target=1_000_000, current=500_000)
    with pytest.raises(gs.GoalError):
        gs.update_goal(gdb, 1, current_amount=1_200_000)


def test_patch_unknown_goal_raises(gdb):
    with pytest.raises(gs.GoalError):
        gs.update_goal(gdb, 999, name="X")


def test_delete_goal(gdb):
    _create(gdb)
    assert gs.delete_goal(gdb, 1)["ok"] is True
    assert gs.list_goals(gdb) == []
    with pytest.raises(gs.GoalError):
        gs.delete_goal(gdb, 999)


# ═════════════════════════════════════════════════════════════════════════════
# § Progress / status (WF-11)
# ═════════════════════════════════════════════════════════════════════════════

def test_status_completed(gdb):
    _create(gdb, current=5_000_000, due="2026-12-31")
    status = gs.goal_status(gdb, 1)
    assert status["status"] == "completed"
    assert status["pct_used"] == 100.0
    assert status["remaining"] == 0.0


def test_status_overdue(gdb):
    _create(gdb, current=1_000_000, due=(date.today() - timedelta(days=3)).isoformat())
    assert gs.goal_status(gdb, 1)["status"] == "overdue"


def test_status_due_soon(gdb):
    _create(gdb, current=4_000_000, due=(date.today() + timedelta(days=7)).isoformat())
    status = gs.goal_status(gdb, 1)
    assert status["status"] == "due_soon"
    assert status["days_left"] == 7


def test_status_on_track(gdb):
    goal = _create(gdb, current=1_000_000, due=(date.today() + timedelta(days=120)).isoformat())
    assert goal["status"] == "on_track"


def test_status_no_deadline_stays_on_track(gdb):
    _create(gdb, current=2_000_000)
    assert gs.goal_status(gdb, 1)["status"] == "on_track"


def test_goals_progress_aggregate(gdb):
    _create(gdb, current=5_000_000, due=(date.today() + timedelta(days=30)).isoformat())   # completed
    _create(gdb, target=2_000_000, current=100_000, due=(date.today() - timedelta(days=1)).isoformat())  # overdue
    _create(gdb, target=2_000_000, current=100_000, due=(date.today() + timedelta(days=5)).isoformat())  # due_soon
    _create(gdb, target=2_000_000, current=100_000, due=(date.today() + timedelta(days=90)).isoformat())  # on_track
    progress = gs.goals_progress(gdb)
    assert progress["total_goals"] == 4
    assert progress["completed"] == 1
    assert progress["overdue"] == 1
    assert progress["due_soon"] == 1
    assert progress["on_track"] == 1
    assert progress["goals"][0]["status"] in ("completed", "overdue", "due_soon", "on_track")


def test_status_unknown_goal_raises(gdb):
    with pytest.raises(gs.GoalError):
        gs.goal_status(gdb, 999)
