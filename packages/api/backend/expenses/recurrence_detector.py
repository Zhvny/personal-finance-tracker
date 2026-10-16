"""
recurrence_detector.py — Recurring Transaction Detector
=========================================================
Single Responsibility : analyse expense history → identify recurring patterns.
Resilience            : Uses Database utility for transparent Postgres support.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

# Bridge to project database utility
try:
    # Try adding backend to path if needed for lazy-loading
    import sys
    from pathlib import Path
    _backend_root = str(Path(__file__).parent.parent.parent)
    if _backend_root not in sys.path:
        sys.path.insert(0, _backend_root)
    from packages.api.backend.infrastructure.database import Database
except Exception:
    try:
        from ..infrastructure.database import Database
    except Exception:
        Database = None

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# § TABLE BOOTSTRAP
# ══════════════════════════════════════════════════════════════════════════════

SCHEMA = """
CREATE TABLE IF NOT EXISTS recurrence_candidates (
    id            SERIAL PRIMARY KEY,
    description   TEXT    NOT NULL UNIQUE,
    category      TEXT,
    avg_amount    REAL,
    amount        REAL,
    interval_days REAL,
    occurrences   INTEGER,
    last_seen     TEXT,
    confidence    REAL,
    is_confirmed  BOOLEAN NOT NULL DEFAULT FALSE,
    status        TEXT    DEFAULT 'pending',
    updated_at    TEXT    NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

def ensure_schema(db_path: str) -> None:
    """Create recurrence_candidates table if missing."""
    if not Database: return
    Database.execute(db_path, SCHEMA)


# ══════════════════════════════════════════════════════════════════════════════
# § DATA CLASS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RecurringCandidate:
    description:   str
    category:      Optional[str]
    avg_amount:    float
    interval_days: float
    occurrences:   int
    last_seen:     str          # ISO date
    confidence:    float        # 0.0–1.0
    is_confirmed:  bool = False


# ══════════════════════════════════════════════════════════════════════════════
# § NORMALISATION
# ══════════════════════════════════════════════════════════════════════════════

_TRAIL_RE = re.compile(
    r"\s*[-–#/]\s*\w+$"         # " - TXN123" / " # 456"
    r"|\s+\d{4,}$"              # " 20250301"
    r"|\s*\(.*?\)$"             # " (promo)"
    r"|\s*\d+x\s*$"             # " 2x"
    , re.IGNORECASE
)

def _norm(description: str) -> str:
    """Normalise to a stable lowercase key for grouping."""
    s = _TRAIL_RE.sub("", (description or "").strip())
    return re.sub(r"\s+", " ", s).lower().strip()


# ══════════════════════════════════════════════════════════════════════════════
# § CONFIDENCE COMPUTATION
# ══════════════════════════════════════════════════════════════════════════════

def _interval_score(avg_days: float) -> float:
    deviation = abs(avg_days - 30.0)
    if deviation >= 15.0: return 0.0
    return round(1.0 - deviation / 15.0, 3)

def _occurrence_score(n: int) -> float:
    return min(1.0, n / 4.0)

def _confidence(avg_days: float, occurrences: int) -> float:
    return round(_interval_score(avg_days) * _occurrence_score(occurrences), 3)


# ══════════════════════════════════════════════════════════════════════════════
# § DETECTION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

INTERVAL_MIN = 22.0
INTERVAL_MAX = 38.0
MIN_OCCURRENCES = 2

def detect(db_path: str, months_lookback: int = 6) -> List[RecurringCandidate]:
    if not Database: return []

    today = date.today()
    cutoff_year  = today.year  - (months_lookback // 12)
    cutoff_month = today.month - (months_lookback %  12)
    if cutoff_month <= 0:
        cutoff_month += 12
        cutoff_year  -= 1
    cutoff = f"{cutoff_year:04d}-{cutoff_month:02d}-01"

    rows = Database.query(db_path,
        "SELECT description, category, amount, date FROM expenses WHERE date >= ? AND is_recurring = 0",
        (cutoff,)
    )

    if not rows: return []

    groups: Dict[str, List] = {}
    for r in rows:
        key = _norm(r.get("description", ""))
        if not key: continue
        groups.setdefault(key, []).append({
            "description": r.get("description", "Unknown"),
            "category":    r.get("category", "other"),
            "amount":      r.get("amount", 0.0),
            "date":        r.get("date")
        })

    candidates: List[RecurringCandidate] = []
    for key, entries in groups.items():
        if len(entries) < MIN_OCCURRENCES: continue

        try:
            dates = []
            for e in entries:
                d = e["date"]
                if isinstance(d, str): d = datetime.strptime(d[:10], "%Y-%m-%d").date()
                elif isinstance(d, datetime): d = d.date()
                dates.append(d)
            dates.sort()
        except: continue

        if len(dates) < 2: continue
        intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates) - 1)]
        avg_interval = sum(intervals) / len(intervals)

        if not (INTERVAL_MIN <= avg_interval <= INTERVAL_MAX): continue

        conf = _confidence(avg_interval, len(entries))
        if conf < 0.1: continue

        avg_amount  = sum(e["amount"] for e in entries) / len(entries)
        cat_counts: Dict[str, int] = {}
        for e in entries:
            c = e.get("category") or "other"
            cat_counts[c] = cat_counts.get(c, 0) + 1
        top_cat = max(cat_counts, key=cat_counts.get) if cat_counts else "other"

        latest_entry = max(entries, key=lambda e: str(e["date"]))
        candidates.append(RecurringCandidate(
            description=latest_entry["description"],
            category=top_cat,
            avg_amount=round(avg_amount, 2),
            interval_days=round(avg_interval, 1),
            occurrences=len(entries),
            last_seen=dates[-1].isoformat(),
            confidence=conf,
        ))

    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates

# ══════════════════════════════════════════════════════════════════════════════
# § PERSISTENCE
# ══════════════════════════════════════════════════════════════════════════════

def persist_candidates(db_path: str, candidates: List[RecurringCandidate]) -> int:
    if not Database: return 0
    ensure_schema(db_path)
    if not candidates: return 0

    now = datetime.now().isoformat()
    upserted = 0
    for c in candidates:
        sql = """
            INSERT INTO recurrence_candidates
                (description, category, avg_amount, amount, interval_days, occurrences,
                 last_seen, confidence, is_confirmed, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'pending', ?)
            ON CONFLICT(description) DO UPDATE SET
                category      = EXCLUDED.category,
                avg_amount    = EXCLUDED.avg_amount,
                amount        = EXCLUDED.amount,
                interval_days = EXCLUDED.interval_days,
                occurrences   = EXCLUDED.occurrences,
                last_seen     = EXCLUDED.last_seen,
                confidence    = EXCLUDED.confidence,
                is_confirmed  = COALESCE(recurrence_candidates.is_confirmed, FALSE),
                status        = CASE WHEN recurrence_candidates.is_confirmed THEN 'confirmed' ELSE 'pending' END,
                updated_at    = EXCLUDED.updated_at
        """
        Database.execute(db_path, sql, (
            c.description, c.category, c.avg_amount, c.avg_amount, c.interval_days,
            c.occurrences, c.last_seen, c.confidence, now,
        ))
        upserted += 1
    return upserted

def run_detection(db_path: str, months_lookback: int = 6) -> dict:
    candidates = detect(db_path, months_lookback)
    persisted  = persist_candidates(db_path, candidates)
    return {
        "detected":  len(candidates),
        "persisted": persisted,
        "candidates": [
            {
                "description":   c.description,
                "category":      c.category,
                "avg_amount":    c.avg_amount,
                "interval_days": c.interval_days,
                "occurrences":   c.occurrences,
                "last_seen":     c.last_seen,
                "confidence":    c.confidence,
                "is_confirmed":  c.is_confirmed,
            }
            for c in candidates
        ],
    }
