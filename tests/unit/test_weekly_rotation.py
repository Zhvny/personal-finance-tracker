"""Task 6: Weekly reward rotation, claims, carry-over, and expiry tests (TDD)."""
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch
import pytest

from packages.core.infrastructure.persistence.reward_pool import seed_pool
from packages.core.infrastructure.persistence.reward_rotation_repository import (
    RewardRotationRepository,
)
from packages.core.domain.services.reward_rotation_service import (
    RewardRotationService,
    ClaimConflictError,
    ClaimExpiredError,
    ClaimNotFoundError,
)


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    seed_pool(conn)
    repo = RewardRotationRepository()
    repo.ensure_tables(conn)
    return conn


@pytest.fixture
def service(db_conn):
    return RewardRotationService(conn=db_conn)


def test_rotation_composition(service):
    """Weekly rotation must select exactly 12 items: 5 basic, 4 mid, 2 premium, 1 ultra."""
    week_start = date(2026, 10, 19) # Monday
    pool = service.rotate_week(target_week_start=week_start)
    
    assert pool["week_start"] == "2026-10-19"
    assert pool["backfilled"] is False
    assert len(pool["items"]) == 12

    tiers = {}
    for item in pool["items"]:
        tiers[item["tier"]] = tiers.get(item["tier"], 0) + 1

    assert tiers.get("basic", 0) == 5
    assert tiers.get("mid", 0) == 4
    assert tiers.get("premium", 0) == 2
    assert tiers.get("ultra", 0) == 1


def test_rotation_idempotent(service):
    """Running rotate_week twice for the same week returns existing pool without duplicate rows."""
    week_start = date(2026, 10, 19)
    first = service.rotate_week(target_week_start=week_start)
    second = service.rotate_week(target_week_start=week_start)

    assert first["week_start"] == second["week_start"]
    assert [i["id"] for i in first["items"]] == [i["id"] for i in second["items"]]

    # Verify only 1 row in reward_weekly_pool table
    cur = service.conn.cursor()
    cur.execute("SELECT COUNT(*) FROM reward_weekly_pool WHERE week_start = ?", ("2026-10-19",))
    count = cur.fetchone()[0]
    assert count == 1


def test_backfill_missing_weeks(service):
    """If scheduler missed weeks, rotating target week backfills missing weeks with backfilled=True."""
    week_1 = date(2026, 10, 5)  # Monday
    week_3 = date(2026, 10, 19) # 2 weeks later

    service.rotate_week(target_week_start=week_1)
    # Week 2 (2026-10-12) was missed! Now rotate week 3:
    res = service.rotate_week(target_week_start=week_3)

    assert res["week_start"] == "2026-10-19"
    assert res["backfilled"] is False

    cur = service.conn.cursor()
    cur.execute("SELECT week_start, backfilled FROM reward_weekly_pool ORDER BY week_start ASC")
    rows = cur.fetchall()
    
    assert len(rows) == 3
    assert rows[0][0] == "2026-10-05" and rows[0][1] in (0, False)
    assert rows[1][0] == "2026-10-12" and rows[1][1] in (1, True)
    assert rows[2][0] == "2026-10-19" and rows[2][1] in (0, False)


def test_claim_and_expiry_boundary(service):
    """Day 14 is valid for redeem; Day 15 is rejected with ClaimExpiredError (HTTP 410 equivalent)."""
    week_start = date(2026, 10, 19)
    pool = service.rotate_week(target_week_start=week_start)
    item_id = pool["items"][0]["id"]
    profile_id = "default"

    # Claim on day 0
    claim_time = datetime(2026, 10, 19, 10, 0, 0)
    claim = service.claim_reward(
        profile_id=profile_id,
        item_id=item_id,
        week_start=week_start,
        now=claim_time,
    )
    assert claim["item_id"] == item_id
    assert claim["profile_id"] == profile_id
    assert claim["week_start"] == "2026-10-19"
    # Expiry is week_start + 14 days
    assert claim["expires_at"].startswith("2026-11-02")

    # Double claim of same item in same week -> ClaimConflictError (409)
    with pytest.raises(ClaimConflictError):
        service.claim_reward(
            profile_id=profile_id,
            item_id=item_id,
            week_start=week_start,
            now=claim_time,
        )

    # Redeem on day 14 (2026-11-02 23:59:00) -> valid!
    day_14_time = datetime(2026, 11, 2, 23, 59, 0)
    redeemed = service.redeem_claim(
        claim_id=claim["id"],
        profile_id=profile_id,
        now=day_14_time,
    )
    assert redeemed["redeemed_at"] is not None

    # Double redeem -> ClaimConflictError (409)
    with pytest.raises(ClaimConflictError):
        service.redeem_claim(
            claim_id=claim["id"],
            profile_id=profile_id,
            now=day_14_time,
        )

    # Test second claim that expires on day 15
    item_2_id = pool["items"][1]["id"]
    claim_2 = service.claim_reward(
        profile_id=profile_id,
        item_id=item_2_id,
        week_start=week_start,
        now=claim_time,
    )
    day_15_time = datetime(2026, 11, 3, 0, 0, 1) # Day 15!
    with pytest.raises(ClaimExpiredError):
        service.redeem_claim(
            claim_id=claim_2["id"],
            profile_id=profile_id,
            now=day_15_time,
        )


def test_catalogue_extended_contract(service):
    """Catalogue returns week_start, expires_at, and claimed state per item."""
    week_start = date(2026, 10, 19)
    service.rotate_week(target_week_start=week_start)

    catalogue = service.get_catalogue(profile_id="user_1", ref_date=week_start)
    assert catalogue["week_start"] == "2026-10-19"
    assert "expires_at" in catalogue
    assert len(catalogue["items"]) == 12

    # All initially unclaimed
    for item in catalogue["items"]:
        assert item["claimed"] is False
        assert item["redeemed"] is False
        assert "desc_en" in item
        assert "desc_id" in item

    # Claim one item
    first_item = catalogue["items"][0]
    service.claim_reward(
        profile_id="user_1",
        item_id=first_item["id"],
        week_start=week_start,
        now=datetime(2026, 10, 20, 12, 0, 0),
    )

    # Catalogue now reflects claimed state
    updated_cat = service.get_catalogue(profile_id="user_1", ref_date=week_start)
    updated_first = [i for i in updated_cat["items"] if i["id"] == first_item["id"]][0]
    assert updated_first["claimed"] is True
    assert updated_first["redeemed"] is False


def test_claim_after_14_days_rejected(service):
    """Claiming an item after day 14 (day 15) must raise ClaimExpiredError."""
    week_start = date(2026, 10, 19)
    pool = service.rotate_week(target_week_start=week_start)
    item_id = pool["items"][0]["id"]

    day_15 = datetime(2026, 11, 3, 10, 0, 0)
    with pytest.raises(ClaimExpiredError):
        service.claim_reward(
            profile_id="default",
            item_id=item_id,
            week_start=week_start,
            now=day_15,
        )


def test_history_relaxation_on_pool_exhaustion(service, caplog):
    """When pool runs out of eligible items in a tier, oldest history is relaxed with a warning."""
    import logging
    cur = service.conn.cursor()
    # Find all ultra items
    cur.execute("SELECT id FROM reward_pool_master WHERE tier = 'ultra'")
    ultra_ids = [r[0] for r in cur.fetchall()]
    assert len(ultra_ids) == 75

    # Pretend all 75 ultra items were used in the last 26 weeks (within cutoff)
    for idx, u_id in enumerate(ultra_ids):
        w_start = (date(2026, 10, 19) - timedelta(days=7 * ((idx % 25) + 1))).isoformat()
        cur.execute("INSERT INTO reward_history (item_id, week_start) VALUES (?, ?)", (u_id, w_start))
    service.conn.commit()

    # Now rotate for 2026-10-19: all ultra items are in history!
    # Service must relax the oldest one and log a warning
    with caplog.at_level(logging.WARNING):
        pool = service.rotate_week(target_week_start=date(2026, 10, 19))
    
    assert len(pool["items"]) == 12
    ultra_picked = [i for i in pool["items"] if i["tier"] == "ultra"]
    assert len(ultra_picked) == 1
    assert "Pool near exhaustion" in caplog.text


def test_api_weekly_rotation_and_claims(db_conn, monkeypatch):
    """Test FastAPI /api/rewards endpoints with TestClient."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from packages.api.backend.routers.rewards import router
    from packages.api.backend.security.core import require_scope

    monkeypatch.setenv("FINANCE_TRACKER_DEV_MODE", "1")

    app = FastAPI()
    # Override auth to no-op for unit testing
    app.dependency_overrides[require_scope("write")] = lambda: {"user_id": "test_user"}
    app.dependency_overrides[require_scope("read")] = lambda: {"user_id": "test_user"}
    app.include_router(router)

    # Patch DatabaseManager connection to use our in-memory seeded db
    with patch("packages.core.infrastructure.persistence.postgres_manager.DatabaseManager.get_connection", return_value=db_conn):
        client = TestClient(app)

        # 1. GET Catalogue
        res = client.get("/api/rewards/catalogue", params={"profile_id": "prof_1", "week_start": "2026-10-19"})
        assert res.status_code == 200
        cat = res.json()
        assert cat["week_start"] == "2026-10-19"
        assert len(cat["items"]) == 12
        assert cat["items"][0]["claimed"] is False

        # 2. POST Claim item
        item_id = cat["items"][0]["id"]
        res_claim = client.post(
            "/api/rewards/weekly/claim",
            json={"profile_id": "prof_1", "item_id": item_id, "week_start": "2026-10-19"},
        )
        assert res_claim.status_code == 200
        claim_data = res_claim.json()
        assert claim_data["ok"] is True
        claim_id = claim_data["claim"]["id"]

        # 3. Double claim -> 409 Conflict
        res_dup = client.post(
            "/api/rewards/weekly/claim",
            json={"profile_id": "prof_1", "item_id": item_id, "week_start": "2026-10-19"},
        )
        assert res_dup.status_code == 409

        # 4. POST Redeem item
        res_redeem = client.post(
            "/api/rewards/weekly/redeem",
            json={"claim_id": claim_id, "profile_id": "prof_1"},
        )
        assert res_redeem.status_code == 200
        assert res_redeem.json()["ok"] is True

        # 5. Double redeem -> 409 Conflict
        res_redeem_dup = client.post(
            "/api/rewards/weekly/redeem",
            json={"claim_id": claim_id, "profile_id": "prof_1"},
        )
        assert res_redeem_dup.status_code == 409

        # 6. Unknown claim ID -> 404
        res_not_found = client.post(
            "/api/rewards/weekly/redeem",
            json={"claim_id": 999999, "profile_id": "prof_1"},
        )
        assert res_not_found.status_code == 404
