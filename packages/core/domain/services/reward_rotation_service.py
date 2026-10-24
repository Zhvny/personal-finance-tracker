"""Domain and application service for weekly reward rotation, carry-over claims, and expiry."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Python fallback if tzdata not installed
    ZoneInfo = None

from packages.core.infrastructure.persistence.reward_rotation_repository import (
    RewardRotationRepository,
    _is_sqlite,
)

logger = logging.getLogger("rewards.rotation")

TIER_QUOTAS = {
    "basic": 5,
    "mid": 4,
    "premium": 2,
    "ultra": 1,
}
TOTAL_ITEMS = 12
HISTORY_WEEKS = 26
CLAIM_WINDOW_DAYS = 14


class ClaimConflictError(Exception):
    """Raised on double claim or double redeem (HTTP 409 equivalent)."""


class ClaimExpiredError(Exception):
    """Raised when claiming or redeeming after the 14-day expiry (HTTP 410 equivalent)."""


class ClaimNotFoundError(Exception):
    """Raised when a claim ID does not exist (HTTP 404 equivalent)."""


def get_current_week_start(ref_date: Optional[date | datetime] = None) -> date:
    """Return Monday 00:00:00 of the week for given date (defaults to Asia/Jakarta now)."""
    if ref_date is None:
        if ZoneInfo:
            try:
                now_dt = datetime.now(ZoneInfo("Asia/Jakarta"))
            except Exception:
                now_dt = datetime.now()
        else:
            now_dt = datetime.now()
        d = now_dt.date()
    elif isinstance(ref_date, datetime):
        d = ref_date.date()
    else:
        d = ref_date

    # Monday is weekday 0 in Python
    monday = d - timedelta(days=d.weekday())
    return monday


def get_expiry_datetime(week_start: date) -> datetime:
    """End of day for week_start + 14 days (inclusive day 14, expires on day 15)."""
    expiry_date = week_start + timedelta(days=CLAIM_WINDOW_DAYS)
    return datetime.combine(expiry_date, time(23, 59, 59))


class RewardRotationService:
    def __init__(self, repository: Optional[RewardRotationRepository] = None, conn: Optional[Any] = None):
        self.repo = repository or RewardRotationRepository()
        self._conn = conn

    @property
    def conn(self) -> Any:
        if self._conn is not None:
            return self._conn
        from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
        return DatabaseManager().get_connection()

    def _get_active_pool_items_by_tier(self, tier: str, halal_only: bool = False) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        tbl = self.repo._qualify("reward_pool_master", self.conn)
        halal_filter = " AND halal = 1" if (_is_sqlite(self.conn) and halal_only) else (" AND halal = TRUE" if halal_only else "")
        cur.execute(
            f"SELECT id, name_en, name_id, desc_en, desc_id, kategori, tier, cost, halal "
            f"FROM {tbl} WHERE tier = ? AND active = 1{halal_filter} ORDER BY id ASC"
            if _is_sqlite(self.conn)
            else f"SELECT id, name_en, name_id, desc_en, desc_id, kategori, tier, cost, halal "
            f"FROM {tbl} WHERE tier = %s AND active = TRUE{halal_filter} ORDER BY id ASC",
            (tier,),
        )
        return [
            {
                "id": r[0],
                "name_en": r[1],
                "name_id": r[2],
                "desc_en": r[3],
                "desc_id": r[4],
                "kategori": r[5],
                "tier": r[6],
                "cost": r[7],
                "halal": bool(r[8]),
            }
            for r in cur.fetchall()
        ]

    def _get_items_by_ids(self, item_ids: List[int]) -> List[Dict[str, Any]]:
        if not item_ids:
            return []
        cur = self.conn.cursor()
        tbl = self.repo._qualify("reward_pool_master", self.conn)
        placeholders = ",".join("?" if _is_sqlite(self.conn) else "%s" for _ in item_ids)
        cur.execute(
            f"SELECT id, name_en, name_id, desc_en, desc_id, kategori, tier, cost, halal "
            f"FROM {tbl} WHERE id IN ({placeholders})",
            tuple(item_ids),
        )
        by_id = {
            r[0]: {
                "id": r[0],
                "name_en": r[1],
                "name_id": r[2],
                "desc_en": r[3],
                "desc_id": r[4],
                "kategori": r[5],
                "tier": r[6],
                "cost": r[7],
                "halal": bool(r[8]),
            }
            for r in cur.fetchall()
        }
        # Preserve original item_ids order
        return [by_id[i] for i in item_ids if i in by_id]

    def _select_items_for_week(self, week_start: date, halal_only: bool = True) -> List[int]:
        cutoff_date = week_start - timedelta(days=HISTORY_WEEKS * 7)
        history_rows = self.repo.get_history_items_since(cutoff_date.isoformat(), self.conn)

        # Map item_id -> most recent week_start seen
        recent_history: Dict[int, str] = {}
        for r in history_rows:
            recent_history[r["item_id"]] = r["week_start"]

        selected_ids: List[int] = []

        for tier, quota in TIER_QUOTAS.items():
            all_tier_items = self._get_active_pool_items_by_tier(tier, halal_only=halal_only)
            if not all_tier_items:
                if halal_only:
                    logger.warning(f"No halal active items found in reward_pool_master for tier: {tier}")
                    continue
                raise RuntimeError(f"No active items found in reward_pool_master for tier: {tier}")

            # Eligible: not in 26-week history
            eligible = [i for i in all_tier_items if i["id"] not in recent_history]

            if len(eligible) < quota:
                needed = quota - len(eligible)
                logger.warning(
                    f"Pool near exhaustion for tier '{tier}': needed {quota}, available {len(eligible)}. "
                    f"Relaxing history from oldest seen items."
                )
                # Sort previously used tier items by latest appearance date ascending (oldest first)
                tier_history_items = [i for i in all_tier_items if i["id"] in recent_history]
                tier_history_items.sort(key=lambda x: (recent_history[x["id"]], x["id"]))

                relaxed = tier_history_items[:needed]
                eligible.extend(relaxed)

            # Pick up to quota items (or fewer if halal tier capacity exhausted)
            selected_ids.extend([i["id"] for i in eligible[:quota]])

        return selected_ids

    def rotate_week(
        self,
        target_week_start: Optional[date] = None,
        halal_only: Optional[bool] = None,
        profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute weekly rotation idempotently, backfilling skipped weeks."""
        self.repo.ensure_tables(self.conn)
        target = target_week_start or get_current_week_start()
        target_str = target.isoformat()

        if halal_only is None:
            if profile_id:
                halal_only = self.repo.get_halal_preference(profile_id, self.conn)
            else:
                halal_only = True

        # Idempotent return
        existing = self.repo.get_weekly_pool(target_str, self.conn)
        if existing:
            items = self._get_items_by_ids(existing["item_ids"])
            return {
                "week_start": existing["week_start"],
                "backfilled": existing["backfilled"],
                "items": items,
            }

        # Check for gap between latest and target to backfill
        latest = self.repo.get_latest_weekly_pool(self.conn)
        if latest:
            latest_date = date.fromisoformat(latest["week_start"])
            missed_date = latest_date + timedelta(days=7)
            while missed_date < target:
                missed_str = missed_date.isoformat()
                if not self.repo.get_weekly_pool(missed_str, self.conn):
                    missed_ids = self._select_items_for_week(missed_date, halal_only=halal_only)
                    self.repo.save_weekly_pool(missed_str, missed_ids, backfilled=True, conn=self.conn)
                    self.repo.add_history(missed_ids, missed_str, self.conn)
                    logger.info(f"Backfilled missed weekly rotation for {missed_str}")
                missed_date += timedelta(days=7)

        # Generate target week
        selected_ids = self._select_items_for_week(target, halal_only=halal_only)
        self.repo.save_weekly_pool(target_str, selected_ids, backfilled=False, conn=self.conn)
        self.repo.add_history(selected_ids, target_str, self.conn)

        items = self._get_items_by_ids(selected_ids)
        return {
            "week_start": target_str,
            "backfilled": False,
            "items": items,
        }

    def claim_reward(
        self, profile_id: str, item_id: int, week_start: Optional[date] = None, now: Optional[datetime] = None
    ) -> Dict[str, Any]:
        self.repo.ensure_tables(self.conn)
        w_start = week_start or get_current_week_start()
        now_dt = now or datetime.now()

        expiry_dt = get_expiry_datetime(w_start)
        if now_dt > expiry_dt:
            raise ClaimExpiredError(f"Claim window for week {w_start.isoformat()} has expired on {expiry_dt.isoformat()}")

        # Check if already claimed
        existing_claims = self.repo.get_claims_by_profile_and_week(profile_id, w_start.isoformat(), self.conn)
        if any(c["item_id"] == item_id for c in existing_claims):
            raise ClaimConflictError(f"Item {item_id} has already been claimed for week {w_start.isoformat()}")

        try:
            return self.repo.create_claim(
                profile_id=profile_id,
                item_id=item_id,
                week_start_str=w_start.isoformat(),
                expires_at_str=expiry_dt.isoformat(),
                conn=self.conn,
            )
        except Exception as exc:
            raise ClaimConflictError(f"Failed to create claim: {exc}") from exc

    def redeem_claim(self, claim_id: int, profile_id: str, now: Optional[datetime] = None) -> Dict[str, Any]:
        self.repo.ensure_tables(self.conn)
        now_dt = now or datetime.now()

        claim = self.repo.get_claim(claim_id, self.conn)
        if not claim:
            raise ClaimNotFoundError(f"Claim {claim_id} not found")

        if claim["profile_id"] != profile_id:
            raise ClaimNotFoundError(f"Claim {claim_id} does not belong to profile {profile_id}")

        if claim["redeemed_at"] is not None:
            raise ClaimConflictError(f"Claim {claim_id} was already redeemed at {claim['redeemed_at']}")

        expiry_dt = datetime.fromisoformat(claim["expires_at"])
        if now_dt > expiry_dt:
            raise ClaimExpiredError(f"Claim {claim_id} expired at {claim['expires_at']}")

        redeemed = self.repo.mark_claim_redeemed(claim_id, now_dt.isoformat(), self.conn)
        return redeemed

    def get_catalogue(self, profile_id: str = "default", ref_date: Optional[date] = None) -> Dict[str, Any]:
        """Fetch catalogue of weekly pool items + claimed state for current profile."""
        w_start = ref_date or get_current_week_start()
        halal_only = self.repo.get_halal_preference(profile_id, self.conn)
        pool = self.rotate_week(target_week_start=w_start, halal_only=halal_only, profile_id=profile_id)

        claims = self.repo.get_claims_by_profile_and_week(profile_id, pool["week_start"], self.conn)
        claims_by_item = {c["item_id"]: c for c in claims}

        expiry_dt = get_expiry_datetime(date.fromisoformat(pool["week_start"]))

        decorated_items = []
        for item in pool["items"]:
            c = claims_by_item.get(item["id"])
            decorated_items.append({
                **item,
                "claimed": c is not None,
                "claim_id": c["id"] if c else None,
                "redeemed": (c is not None and c["redeemed_at"] is not None),
                "expires_at": expiry_dt.isoformat(),
            })

        return {
            "week_start": pool["week_start"],
            "expires_at": expiry_dt.isoformat(),
            "halal_only": halal_only,
            "items": decorated_items,
        }

    def set_halal_preference(self, profile_id: str, enabled: bool) -> None:
        self.repo.set_halal_preference(profile_id, enabled, self.conn)

    def get_halal_preference(self, profile_id: str) -> bool:
        return self.repo.get_halal_preference(profile_id, self.conn)
