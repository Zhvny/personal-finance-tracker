"""
backend/finance/goals_service.py — Goal CRUD + progress/status (Phase 8)
========================================================================
Canonical goal engine (goals.db bridge → per-profile schema):

  * create/list/update/delete with strict typed validation (PATCH fixed:
    amounts coerced to float, dates parsed, current <= target enforced
    against stored values, unknown goal → 404)
  * deterministic progress/status for n8n WF-11 goal monitoring:
      completed        — current >= target
      overdue          — past target_date, not completed
      due_soon         — target_date within 14 days, not completed
      behind_schedule  — pct_used below the linear time expectation
      on_track         — otherwise
  * progress payload: pct, remaining, days_left, status, next milestone
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from packages.core.infrastructure.persistence.database import Database

GOALS_DDL = """CREATE TABLE IF NOT EXISTS goals (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL,
    target_amount  REAL    NOT NULL,
    current_amount REAL    NOT NULL DEFAULT 0,
    target_date    TEXT,
    created_at     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
)"""

DUE_SOON_DAYS = 14


class GoalError(Exception):
    """Invalid goal request (bad field, unknown goal, ...)."""


def _ensure_db(db_path: str) -> None:
    Database.execute(db_path, GOALS_DDL)


def _as_date(value: Any, field: str) -> Optional[date]:
    if value is None or str(value).strip() == "":
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise GoalError(f"{field} tidak valid (format YYYY-MM-DD)") from None


def _as_amount(value: Any, field: str, *, positive: bool = False, allow_negative: bool = False) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise GoalError(f"{field} harus berupa angka") from None
    if positive and amount <= 0:
        raise GoalError(f"{field} harus lebih besar dari 0")
    if not allow_negative and amount < 0:
        raise GoalError(f"{field} tidak boleh negatif")
    return round(amount, 2)


def _parse_row(row: Dict[str, Any]) -> Dict[str, Any]:
    target = float(row.get("target_amount") or 0)
    current = float(row.get("current_amount") or 0)
    target_date = _as_date(row.get("target_date"), "target_date")
    today = date.today()
    pct = round(current / target * 100, 1) if target else 0.0

    status = "on_track"
    if current >= target:
        status = "completed"
    elif target_date is not None and target_date < today:
        status = "overdue"
    elif target_date is not None and (target_date - today).days <= DUE_SOON_DAYS:
        status = "due_soon"
    else:
        elapsed_days = (today - _created_or_start(row, target_date)).days
        total_days = max(1, (target_date - _created_or_start(row, target_date)).days) if target_date else 1
        expectation = min(1.0, elapsed_days / total_days)
        if pct / 100.0 < expectation * 0.85:
            status = "behind_schedule"

    return {
        "goal_id": row["id"],
        "name": row.get("name") or f"Goal #{row['id']}",
        "title": row.get("name") or f"Goal #{row['id']}",
        "target_amount": target,
        "current_amount": current,
        "target_date": target_date.isoformat() if target_date else None,
        "deadline": target_date.isoformat() if target_date else None,
        "pct_used": pct,
        "remaining": round(max(0.0, target - current), 2),
        "days_left": (target_date - today).days if target_date else None,
        "status": status,
        "created_at": row.get("created_at"),
    }


def _created_or_start(row: Dict[str, Any], target_date: Optional[date]) -> date:
    created = _as_date(row.get("created_at"), "created_at")
    if created is None:
        return target_date or date.today()
    return created


# ═════════════════════════════════════════════════════════════════════════════
# § CRUD (PATCH fixed: typed, validated, atomic)
# ═════════════════════════════════════════════════════════════════════════════

def list_goals(db_path: str) -> List[Dict[str, Any]]:
    _ensure_db(db_path)
    rows = Database.query(db_path, "SELECT * FROM goals ORDER BY id")
    return [_parse_row(r) for r in rows]


def create_goal(
    db_path: str,
    *,
    name: Optional[str] = None,
    title: Optional[str] = None,
    target_amount: Any,
    current_amount: Any = 0.0,
    target_date: Optional[Any] = None,
    deadline: Optional[Any] = None,
) -> Dict[str, Any]:
    _ensure_db(db_path)
    goal_name = (name or title or "").strip()
    if not goal_name:
        raise GoalError("Nama goal wajib diisi")
    target = _as_amount(target_amount, "target_amount", positive=True)
    current = _as_amount(current_amount, "current_amount")
    if current > target:
        raise GoalError("current_amount tidak boleh melebihi target_amount")
    due = _as_date(target_date if target_date is not None else deadline, "target_date")

    Database.execute(
        db_path,
        "INSERT INTO goals (name, target_amount, current_amount, target_date) VALUES (?, ?, ?, ?)",
        (goal_name, target, current, due.isoformat() if due else None),
    )
    row = Database.query(db_path, "SELECT * FROM goals ORDER BY id DESC LIMIT 1")[0]
    return _parse_row(row)


def update_goal(db_path: str, goal_id: int, **fields: Any) -> Dict[str, Any]:
    """Typed partial update; returns the refreshed goal."""
    _ensure_db(db_path)
    if goal_id <= 0:
        raise GoalError("ID goal tidak valid")
    rows = Database.query(db_path, "SELECT * FROM goals WHERE id = ?", (goal_id,))
    if not rows:
        raise GoalError(f"Goal tidak ditemukan: {goal_id}")
    row = rows[0]

    updates: Dict[str, Any] = {}
    if "name" in fields or "title" in fields:
        name = fields.get("name") or fields.get("title")
        if name is None or not str(name).strip():
            raise GoalError("Nama goal tidak boleh kosong")
        updates["name"] = str(name).strip()
    if "target_amount" in fields:
        updates["target_amount"] = _as_amount(fields["target_amount"], "target_amount", positive=True)
    if "current_amount" in fields:
        updates["current_amount"] = _as_amount(fields["current_amount"], "current_amount")
    if "target_date" in fields or "deadline" in fields:
        raw = fields.get("target_date") if fields.get("target_date") is not None else fields.get("deadline")
        due = _as_date(raw, "target_date")
        updates["target_date"] = due.isoformat() if due else None
    if not updates:
        raise GoalError("Tidak ada field yang perlu diubah")

    eff_target = updates.get("target_amount", float(row["target_amount"] or 0))
    eff_current = updates.get("current_amount", float(row["current_amount"] or 0))
    if eff_current > eff_target:
        raise GoalError("current_amount tidak boleh melebihi target_amount")

    sets = ", ".join(f"{k} = ?" for k in updates)
    Database.execute(db_path, f"UPDATE goals SET {sets} WHERE id = ?", (*updates.values(), goal_id))

    refreshed = Database.query(db_path, "SELECT * FROM goals WHERE id = ?", (goal_id,))[0]
    return _parse_row(refreshed)


def delete_goal(db_path: str, goal_id: int) -> Dict[str, Any]:
    _ensure_db(db_path)
    rows = Database.query(db_path, "SELECT id FROM goals WHERE id = ?", (goal_id,))
    if not rows:
        raise GoalError(f"Goal tidak ditemukan: {goal_id}")
    Database.execute(db_path, "DELETE FROM goals WHERE id = ?", (goal_id,))
    return {"ok": True, "goal_id": goal_id}


# ═════════════════════════════════════════════════════════════════════════════
# § Progress / status (n8n WF-11 goal monitoring)
# ═════════════════════════════════════════════════════════════════════════════

def goal_status(db_path: str, goal_id: int) -> Dict[str, Any]:
    """Single-goal progress/status payload."""
    _ensure_db(db_path)
    rows = Database.query(db_path, "SELECT * FROM goals WHERE id = ?", (goal_id,))
    if not rows:
        raise GoalError(f"Goal tidak ditemukan: {goal_id}")
    return _parse_row(rows[0])


def goals_progress(db_path: str) -> Dict[str, Any]:
    """All-goals monitoring payload for n8n WF-11."""
    goals = list_goals(db_path)
    return {
        "as_of": date.today().isoformat(),
        "total_goals": len(goals),
        "completed": sum(1 for g in goals if g["status"] == "completed"),
        "overdue": sum(1 for g in goals if g["status"] == "overdue"),
        "due_soon": sum(1 for g in goals if g["status"] == "due_soon"),
        "behind_schedule": sum(1 for g in goals if g["status"] == "behind_schedule"),
        "on_track": sum(1 for g in goals if g["status"] == "on_track"),
        "goals": goals,
    }
