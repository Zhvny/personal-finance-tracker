"""
backend/finance/recurring_service.py — Recurring detection + reminders (Phase 7)
=================================================================================
Canonical-ledger recurring engine (Phase 5/6 architecture):

  * detect_recurring()          — scan `transactions` (expense + income),
                                   group by type/category/merchant/normalised
                                   description, detect monthly (same day-of-month
                                   +/- tolerance) or weekly (same weekday)
                                   cadence, score confidence 0.0-1.0
                                   (occurrence count + interval regularity +
                                   amount stability), and idempotently upsert
                                   candidates keyed by SHA-256 (n8n WF-09).
  * verify_candidate()          — user confirmation of a candidate; confirmed
                                   candidates become reminder templates.
  * generate_reminders()        — for each confirmed template, if the next due
                                   date is within the reminder window and no
                                   matching transaction was recorded for the
                                   current period, persist a reminder row keyed
                                   by UNIQUE(candidate_id, period_key) so
                                   repeated daily checks (n8n WF-10) never
                                   duplicate reminders.
  * list_candidates/reminders   — history, newest first.
"""
import hashlib
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from packages.core.infrastructure.persistence.database import Database
from packages.api.backend.finance.period_utils import (
    AMOUNT_TOLERANCE,
    DEFAULT_REMINDER_LOOKAHEAD_DAYS,
    DEFAULT_REMINDER_LOOKBACK_DAYS,
    period_covered as _period_covered,
)

CANDIDATES_DDL = """CREATE TABLE IF NOT EXISTS recurrence_candidates (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    key          TEXT    NOT NULL UNIQUE,
    tx_type      TEXT    NOT NULL,
    category     TEXT    NOT NULL DEFAULT 'Lainnya',
    merchant     TEXT,
    description  TEXT,
    amount       REAL    NOT NULL,
    frequency    TEXT    NOT NULL,
    day_of_week  INTEGER,
    day_of_month INTEGER,
    occurrences  INTEGER NOT NULL,
    confidence   REAL    NOT NULL,
    is_confirmed BOOLEAN NOT NULL DEFAULT 0,
    last_seen    TEXT,
    next_due     TEXT,
    created_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
)"""

REMINDERS_DDL = """CREATE TABLE IF NOT EXISTS recurring_reminders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    period_key   TEXT    NOT NULL,
    due_date     TEXT    NOT NULL,
    amount       REAL    NOT NULL,
    category     TEXT    NOT NULL DEFAULT 'Lainnya',
    description  TEXT,
    status       TEXT    NOT NULL DEFAULT 'pending',
    created_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(candidate_id, period_key)
)"""

MIN_OCCURRENCES = 2
MONTHLY_DAY_TOLERANCE_DAYS = 3
WEEKLY_DAY_TOLERANCE_DAYS = 1
# AMOUNT_TOLERANCE, DEFAULT_REMINDER_LOOKAHEAD_DAYS, DEFAULT_REMINDER_LOOKBACK_DAYS
# moved to packages.api.backend.finance.period_utils (M2 refactor, 2026-09-05)

_TRAIL_RE = re.compile(
    r"\s*[-–#/]\s*\w+$"
    r"|\s+\d{4,}$"
    r"|\s*\(.*?\)$"
    r"|\s*\d+x\s*$",
    re.IGNORECASE,
)


class RecurringError(Exception):
    """Invalid recurring request (unknown candidate, bad params, ...)."""


def _norm(description: str) -> str:
    s = _TRAIL_RE.sub("", (description or "").strip())
    return re.sub(r"\s+", " ", s).lower().strip()


def _candidate_key(tx_type: str, category: str, merchant: str, description: str, frequency: str) -> str:
    raw = "|".join([tx_type, category, merchant or "", _norm(description), frequency])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _period_key(frequency: str, due: date) -> str:
    if frequency == "weekly":
        iso = due.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    return due.strftime("%Y-%m")


def _ensure_candidates_db(db_path: str) -> None:
    Database.execute(db_path, CANDIDATES_DDL)


def _ensure_reminders_db(db_path: str) -> None:
    Database.execute(db_path, REMINDERS_DDL)


def _to_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _month_cutoff(months_lookback: int) -> str:
    today = date.today()
    year = today.year - (months_lookback // 12)
    month = today.month - (months_lookback % 12)
    if month <= 0:
        month += 12
        year -= 1
    return f"{year:04d}-{month:02d}-01"


# ═════════════════════════════════════════════════════════════════════════════
# § Detection (n8n WF-09)
# ═════════════════════════════════════════════════════════════════════════════

def _detect_frequency(dates: List[date]) -> Tuple[Optional[str], float, int]:
    """Return (frequency, confidence-regularity, avg_interval_days)."""
    intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
    if not intervals:
        return None, 0.0, 0.0
    avg_interval = sum(intervals) / len(intervals)

    weekly_matches = sum(1 for iv in intervals if abs(iv - 7) <= WEEKLY_DAY_TOLERANCE_DAYS)
    monthly_matches = sum(1 for iv in intervals if abs(iv - 30) <= MONTHLY_DAY_TOLERANCE_DAYS)

    if weekly_matches >= monthly_matches and weekly_matches >= max(1, len(intervals) // 2):
        return "weekly", weekly_matches / len(intervals), avg_interval
    if monthly_matches >= max(1, len(intervals) // 2):
        return "monthly", monthly_matches / len(intervals), avg_interval
    return None, 0.0, avg_interval


def _confidence(regularity: float, occurrences: int, amounts: List[float]) -> float:
    occ_score = min(1.0, occurrences / 4.0)
    if amounts:
        avg = sum(amounts) / len(amounts)
        if avg > 0:
            deviations = [abs(a - avg) / avg for a in amounts]
            amount_score = max(0.0, 1.0 - (sum(deviations) / len(deviations)) / AMOUNT_TOLERANCE)
        else:
            amount_score = 1.0
    else:
        amount_score = 1.0
    return round(regularity * 0.45 + occ_score * 0.35 + amount_score * 0.20, 3)


def _next_due(frequency: str, dates: List[date]) -> date:
    latest = dates[-1]
    if frequency == "weekly":
        return latest + timedelta(days=7)
    return latest + timedelta(days=30)


def _merge_candidate_txs(rows: List[Dict[str, Any]]) -> Dict[tuple, List[Dict[str, Any]]]:
    groups: Dict[tuple, List[Dict[str, Any]]] = {}
    for r in rows:
        key = (
            r.get("type", "expense"),
            str(r.get("category") or "Lainnya"),
            str(r.get("merchant") or ""),
            _norm(r.get("description") or ""),
        )
        groups.setdefault(key, []).append(r)
    return groups


def detect_recurring(ledger_db: str, months_lookback: int = 6, as_of: Optional[date] = None) -> Dict[str, Any]:
    """Scan the canonical ledger and idempotently upsert recurring candidates."""
    if months_lookback < 2 or months_lookback > 24:
        raise RecurringError("months_lookback harus antara 2 dan 24")
    cutoff = _month_cutoff(months_lookback)
    today = as_of or date.today()

    rows = Database.query(
        ledger_db,
        "SELECT t.type, t.amount, t.category, t.tx_date, COALESCE(m.name, '') AS merchant,"
        " t.description"
        " FROM transactions t LEFT JOIN merchants m ON m.id = t.merchant_id"
        " WHERE t.type IN ('expense', 'income') AND t.tx_date >= ?",
        (cutoff,),
    )
    if not rows:
        return {"detected": 0, "persisted": 0, "candidates": []}

    detected = []
    for (tx_type, category, merchant, description), entries in _merge_candidate_txs(rows).items():
        dates = sorted(d for d in (_to_date(e.get("tx_date")) for e in entries) if d)
        if len(dates) < MIN_OCCURRENCES:
            continue
        frequency, regularity, _ = _detect_frequency(dates)
        if frequency is None or regularity < 0.5:
            continue
        amounts = [float(e.get("amount") or 0) for e in entries]
        confidence = _confidence(regularity, len(dates), amounts)
        if confidence < 0.35:
            continue
        avg_amount = round(sum(amounts) / len(amounts), 2)
        due = _next_due(frequency, dates)
        detected.append({
            "tx_type": tx_type,
            "category": category,
            "merchant": merchant,
            "description": entries[-1].get("description") or None,
            "amount": avg_amount,
            "frequency": frequency,
            "day_of_week": dates[-1].weekday() if frequency == "weekly" else None,
            "day_of_month": dates[-1].day if frequency == "monthly" else None,
            "occurrences": len(dates),
            "confidence": confidence,
            "last_seen": dates[-1].isoformat(),
            "next_due": due.isoformat(),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        })

    detected.sort(key=lambda c: c["confidence"], reverse=True)
    _ensure_candidates_db(ledger_db)

    persisted = 0
    for c in detected:
        key = _candidate_key(c["tx_type"], c["category"], c["merchant"], c["description"], c["frequency"])
        c["key"] = key
        Database.execute(
            ledger_db,
            "INSERT INTO recurrence_candidates"
            " (key, tx_type, category, merchant, description, amount, frequency,"
            "  day_of_week, day_of_month, occurrences, confidence, is_confirmed,"
            "  last_seen, next_due, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)"
            " ON CONFLICT(key) DO UPDATE SET"
            "  category = EXCLUDED.category, merchant = EXCLUDED.merchant,"
            "  description = EXCLUDED.description, amount = EXCLUDED.amount,"
            "  frequency = EXCLUDED.frequency, day_of_week = EXCLUDED.day_of_week,"
            "  day_of_month = EXCLUDED.day_of_month, occurrences = EXCLUDED.occurrences,"
            "  confidence = EXCLUDED.confidence,"
            "  is_confirmed = COALESCE(recurrence_candidates.is_confirmed, 0),"
            "  last_seen = EXCLUDED.last_seen, next_due = EXCLUDED.next_due,"
            "  updated_at = EXCLUDED.updated_at",
            (key, c["tx_type"], c["category"], c["merchant"], c["description"],
             c["amount"], c["frequency"], c["day_of_week"], c["day_of_month"],
             c["occurrences"], c["confidence"], c["last_seen"], c["next_due"],
             c["updated_at"]),
        )
        persisted += 1

    today_iso = today.isoformat()
    return {
        "detected": len(detected),
        "persisted": persisted,
        "candidates": [
            {k: c[k] for k in ("key", "tx_type", "category", "merchant", "description",
                               "amount", "frequency", "day_of_week", "day_of_month",
                               "occurrences", "confidence", "last_seen", "next_due")}
            for c in detected if c["next_due"] >= today_iso
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
# § Verification
# ═════════════════════════════════════════════════════════════════════════════

def _get_candidate(db_path: str, candidate_id: int) -> Optional[Dict[str, Any]]:
    rows = Database.query(
        db_path,
        "SELECT * FROM recurrence_candidates WHERE id = ?",
        (candidate_id,),
    )
    return rows[0] if rows else None


def verify_candidate(ledger_db: str, candidate_id: int, confirmed: bool) -> Dict[str, Any]:
    """User confirmation gate: confirmed candidates become reminder templates."""
    _ensure_candidates_db(ledger_db)
    candidate = _get_candidate(ledger_db, candidate_id)
    if candidate is None:
        raise RecurringError(f"Kandidat tidak ditemukan: {candidate_id}")
    Database.execute(
        ledger_db,
        "UPDATE recurrence_candidates SET is_confirmed = ?, updated_at = ? WHERE id = ?",
        (1 if confirmed else 0, datetime.now().isoformat(timespec="seconds"), candidate_id),
    )
    return {
        "candidate_id": candidate_id,
        "is_confirmed": bool(confirmed),
        "frequency": candidate["frequency"],
        "amount": float(candidate["amount"]),
        "category": candidate["category"],
        "next_due": candidate["next_due"],
    }


def list_candidates(ledger_db: str, status: Optional[str] = None, min_confidence: float = 0.0) -> List[Dict[str, Any]]:
    _ensure_candidates_db(ledger_db)
    where = []
    params: List[Any] = []
    if status == "confirmed":
        where.append("is_confirmed = 1")
    elif status == "pending":
        where.append("is_confirmed = 0")
    elif status is not None:
        raise RecurringError("status harus 'pending' atau 'confirmed'")
    if min_confidence > 0:
        where.append("confidence >= ?")
        params.append(min_confidence)
    sql = "SELECT * FROM recurrence_candidates"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY confidence DESC, id DESC"
    rows = Database.query(ledger_db, sql, tuple(params))
    return [
        {
            "candidate_id": r["id"],
            "tx_type": r["tx_type"],
            "category": r["category"],
            "merchant": r["merchant"],
            "description": r["description"],
            "amount": float(r["amount"] or 0),
            "frequency": r["frequency"],
            "day_of_week": r["day_of_week"],
            "day_of_month": r["day_of_month"],
            "occurrences": r["occurrences"],
            "confidence": float(r["confidence"] or 0),
            "is_confirmed": bool(r["is_confirmed"]),
            "last_seen": r["last_seen"],
            "next_due": r["next_due"],
        }
        for r in rows
    ]


# ═════════════════════════════════════════════════════════════════════════════
# § Reminders (n8n WF-10, dedup via UNIQUE(candidate_id, period_key))
# ═════════════════════════════════════════════════════════════════════════════

# _period_covered and AMOUNT_TOLERANCE/LOOK*_DAYS moved to
# packages.api.backend.finance.period_utils (M2 refactor, 2026-09-05).
# Imported at module top with alias `_period_covered` for backward-compat.

def _next_due_on_or_after(ledger_db: str, candidate: Dict[str, Any], as_of: date) -> Optional[date]:
    """Next due date >= as_of, recomputed from the template cadence."""
    frequency = candidate["frequency"]
    if frequency == "weekly":
        weekday = candidate["day_of_week"]
        if weekday is None:
            return None
        delta = (weekday - as_of.weekday()) % 7
        return as_of + timedelta(days=delta)
    day = candidate["day_of_month"]
    if day is None:
        return None
    try:
        due = date(as_of.year, as_of.month, day)
    except ValueError:
        return None
    if due < as_of:
        try:
            due = date(as_of.year, as_of.month + 1, day) if as_of.month < 12 else date(as_of.year + 1, 1, day)
        except ValueError:
            return None
    return due


def generate_reminders(
    ledger_db: str,
    as_of: Optional[date] = None,
    lookahead_days: int = DEFAULT_REMINDER_LOOKAHEAD_DAYS,
    lookback_days: int = DEFAULT_REMINDER_LOOKBACK_DAYS,
) -> Dict[str, Any]:
    """Persist only NEW reminders for confirmed templates due in the window.

    Idempotent: a reminder row is keyed UNIQUE(candidate_id, period_key), so
    daily n8n WF-10 runs return no duplicates. A template whose transaction
    was already recorded for the period is skipped.
    """
    _ensure_candidates_db(ledger_db)
    _ensure_reminders_db(ledger_db)
    today = as_of or date.today()

    rows = Database.query(
        ledger_db,
        "SELECT * FROM recurrence_candidates WHERE is_confirmed = 1",
    )
    new_reminders = []
    anchor = today - timedelta(days=lookback_days)
    horizon = today + timedelta(days=lookahead_days)
    for r in rows:
        candidate = {
            "id": r["id"],
            "tx_type": r["tx_type"],
            "category": r["category"],
            "description": r["description"],
            "amount": r["amount"],
            "frequency": r["frequency"],
            "day_of_week": r["day_of_week"],
            "day_of_month": r["day_of_month"],
        }
        due = _next_due_on_or_after(ledger_db, candidate, anchor)
        if due is None or due > horizon:
            continue
        period_key = _period_key(candidate["frequency"], due)
        exists = Database.query(
            ledger_db,
            "SELECT id FROM recurring_reminders WHERE candidate_id = ? AND period_key = ?",
            (r["id"], period_key),
        )
        if exists:
            continue
        if _period_covered(ledger_db, candidate, due, today):
            continue
        Database.execute(
            ledger_db,
            "INSERT INTO recurring_reminders (candidate_id, period_key, due_date, amount,"
            " category, description, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
            (r["id"], period_key, due.isoformat(),
             float(candidate["amount"] or 0), candidate["category"], candidate["description"]),
        )
        new_reminders.append({
            "reminder_id": Database.query(
                ledger_db,
                "SELECT id FROM recurring_reminders WHERE candidate_id = ? AND period_key = ?",
                (r["id"], period_key),
            )[0]["id"],
            "candidate_id": r["id"],
            "period_key": period_key,
            "due_date": due.isoformat(),
            "amount": float(candidate["amount"] or 0),
            "category": candidate["category"],
            "description": candidate["description"],
            "status": "pending",
        })

    return {"as_of": today.isoformat(), "new_reminders": new_reminders}


def list_reminders(ledger_db: str, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Reminder history, newest first."""
    _ensure_reminders_db(ledger_db)
    where = []
    params: List[Any] = []
    if status in ("pending", "sent"):
        where.append("status = ?")
        params.append(status)
    elif status is not None:
        raise RecurringError("status harus 'pending' atau 'sent'")
    sql = ("SELECT * FROM recurring_reminders")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = Database.query(ledger_db, sql, tuple(params))
    return [
        {
            "reminder_id": r["id"],
            "candidate_id": r["candidate_id"],
            "period_key": r["period_key"],
            "due_date": r["due_date"],
            "amount": float(r["amount"] or 0),
            "category": r["category"],
            "description": r["description"],
            "status": r["status"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def mark_reminder_sent(ledger_db: str, reminder_id: int) -> Dict[str, Any]:
    """WF-10 marks a reminder as sent after delivering it."""
    _ensure_reminders_db(ledger_db)
    rows = Database.query(ledger_db, "SELECT id FROM recurring_reminders WHERE id = ?", (reminder_id,))
    if not rows:
        raise RecurringError(f"Reminder tidak ditemukan: {reminder_id}")
    Database.execute(ledger_db, "UPDATE recurring_reminders SET status = 'sent' WHERE id = ?", (reminder_id,))
    return {"ok": True, "reminder_id": reminder_id, "status": "sent"}
