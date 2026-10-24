"""
backend/routers/rewards.py — Rewards / Gamification (Reward points) routes
=========================================================================
Architecture: High Cohesion — this file owns only /api/rewards routes.
Supports Local Rewards + Google Drive (Masked via Backend Proxy).
Upgraded: Async HTTPX proxy, Thumbnail caching, and Robust Video Streaming.
Feature: Aggressive Media Caching (Pre-download all Drive files to local temp).
"""

import asyncio
import json
import logging
import os
import re
import shutil
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, field_validator

from packages.api.backend.routers.deps import (
    _GUI,
    reward_service,
)
from packages.api.backend.security.core import require_scope

router = APIRouter(dependencies=[Depends(require_scope("write"))])
logger = logging.getLogger(__name__)

# ── Proxy Configuration ──────────────────────────────────────────────────────

THUMB_CACHE_DIR = _GUI / "data" / "cache" / "thumbnails"
THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Aggressive Media Cache (Full files)
MEDIA_CACHE_DIR = _GUI / "data" / "cache" / "temp_media"
MEDIA_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Shared client for connection pooling
client = httpx.AsyncClient(
    timeout=httpx.Timeout(30.0, connect=10.0), # Increased timeout for full downloads
    follow_redirects=True,
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
)

confirm_tokens = {} # drive_id -> (token, expiry)

_DRIVE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,200}$")

def _validate_drive_id(drive_id: str) -> str:
    """Reject path separators and other untrusted filename characters."""
    if not _DRIVE_ID_RE.fullmatch(drive_id):
        raise HTTPException(status_code=400, detail="Invalid media identifier")
    return drive_id

# ── Helper for Background Pre-warming ───────────────────────────────────────
async def prewarm_thumbnail(drive_id: str, sz: str = "w320"):
    """Background task to fetch and cache thumbnails before they are requested."""
    drive_id = _validate_drive_id(drive_id)

    sz_final = sz if sz.startswith("w") else f"w{sz}"
    cache_path = THUMB_CACHE_DIR / f"{drive_id}_{sz_final}.jpg"
    if cache_path.exists():
        return

    urls = [
        f"https://drive.google.com/thumbnail?id={drive_id}&sz={sz_final}",
        f"https://lh3.googleusercontent.com/u/0/d/{drive_id}={sz_final}",
        f"https://drive.google.com/u/0/uc?id={drive_id}&export=download",
    ]

    async def fetch_one(url):
        try:
            res = await client.get(url, timeout=15.0)
            if res.status_code == 200:
                ctype = res.headers.get("Content-Type", "").lower()
                if "image" in ctype and len(res.content) > 500:
                    return (res.content, ctype)
        except: pass
        logger.exception("Error while processing reward operation")
        return None

    tasks = [fetch_one(url) for url in urls]
    for coro in asyncio.as_completed(tasks):
        result = await coro
        if result:
            content, ctype = result
            if not cache_path.exists():
                with open(cache_path, "wb") as f:
                    f.write(content)
            return

async def fully_cache_media(drive_id: str):
    """Aggressive: Downloads the entire file from Drive to local temp storage."""
    drive_id = _validate_drive_id(drive_id)
    local_path = MEDIA_CACHE_DIR / drive_id
    ctype_path = MEDIA_CACHE_DIR / f"{drive_id}.ctype"

    # If file exists and is reasonably large, skip
    if local_path.exists() and local_path.stat().st_size > 10000: return

    url = f"https://drive.google.com/uc?export=download&id={drive_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        # 1. Initial hit to check for virus warning
        res = await client.get(url, headers=headers, timeout=15.0)
        final_url = url

        if "text/html" in res.headers.get("content-type", ""):
            body = res.text
            match = re.search(r'confirm=([0-9A-Za-z_]+)', body)
            if not match: match = re.search(r'name="confirm"\s+value="([^"]+)"', body)
            if match:
                token = match.group(1)
                confirm_tokens[drive_id] = (token, time.time() + 3600)
                final_url = f"https://drive.google.com/uc?export=download&id={drive_id}&confirm={token}"

        # 2. Stream the full download to disk
        async with client.stream("GET", final_url, headers=headers) as response:
            if response.status_code == 200:
                ctype = response.headers.get("content-type", "application/octet-stream")
                temp_file = str(local_path) + ".tmp"
                with open(temp_file, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=16384):
                        f.write(chunk)

                # Check if we actually got a real file (not a small error page)
                if os.path.getsize(temp_file) > 5000:
                    os.replace(temp_file, local_path)
                    with open(ctype_path, "w") as f: f.write(ctype)
                    logger.info(f"Aggressive Cache: Saved {drive_id} locally ({ctype}).")
                else:
                    try: os.remove(temp_file)
                    except Exception:
                        logger.warning("Error while cleaning up temp file")
    except Exception as e:
        logger.error(f"Aggressive Cache Failed for {drive_id}: {e}")

def cleanup_media_cache():
    """Wipe the temp_media directory on shutdown."""
    if MEDIA_CACHE_DIR.exists():
        shutil.rmtree(MEDIA_CACHE_DIR)
        MEDIA_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Backend Proxy for Google Drive (Masking) ─────────────────────────────────

@router.get("/api/rewards/media/{drive_id}")
async def proxy_drive_media(drive_id: str, request: Request, sz: Optional[str] = None):
    drive_id = _validate_drive_id(drive_id)
    # ── Handle Thumbnails ────────────────────────────────────────────────────
    if sz:
        sz_final = sz if sz.startswith("w") else f"w{sz}"
        cache_path = THUMB_CACHE_DIR / f"{drive_id}_{sz_final}.jpg"
        if cache_path.exists():
            return FileResponse(cache_path, media_type="image/jpeg", headers={"X-Cache": "HIT"})

        # Quick attempt
        urls = [f"https://drive.google.com/thumbnail?id={drive_id}&sz={sz_final}", f"https://lh3.googleusercontent.com/u/0/d/{drive_id}={sz_final}"]
        for url in urls:
            try:
                res = await client.get(url, timeout=5.0)
                if res.status_code == 200 and "image" in res.headers.get("content-type",""):
                    with open(cache_path, "wb") as f: f.write(res.content)
                    return Response(content=res.content, media_type="image/jpeg")
            except: continue
        raise HTTPException(status_code=404)

    # ── Handle Full Content (Prefer Local Cache) ─────────────────────────────
    local_path = MEDIA_CACHE_DIR / drive_id
    ctype_path = MEDIA_CACHE_DIR / f"{drive_id}.ctype"

    if local_path.exists():
        ctype = "application/octet-stream"
        if ctype_path.exists():
            with open(ctype_path, "r") as f: ctype = f.read().strip()

        # Support Range requests for locally cached files (Fast Seek)
        return FileResponse(
            local_path,
            media_type=ctype,
            headers={"X-Cache": "LOCAL-AGGRESSIVE", "Accept-Ranges": "bytes"}
        )

    # Fallback to streaming proxy
    token, _ = confirm_tokens.get(drive_id, (None, 0))
    base_url = f"https://drive.google.com/uc?export=download&id={drive_id}"
    if token: base_url += f"&confirm={token}"

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
    if r := request.headers.get("range"): headers["range"] = r

    try:
        res = await client.send(client.build_request("GET", base_url, headers=headers), stream=True)

        if "text/html" in res.headers.get("content-type", ""):
            body = await res.aread()
            match = re.search(r'confirm=([0-9A-Za-z_]+)', body.decode(errors='ignore'))
            if match:
                token = match.group(1)
                confirm_tokens[drive_id] = (token, time.time() + 3600)
                confirm_url = f"https://drive.google.com/uc?export=download&id={drive_id}&confirm={token}"
                res = await client.send(client.build_request("GET", confirm_url, headers=headers), stream=True)

        resp_headers = {
            "Accept-Ranges": "bytes",
            "Content-Type":  res.headers.get("content-type", "application/octet-stream"),
            "Content-Length": res.headers.get("content-length"),
            "Content-Range":  res.headers.get("content-range"),
            "Cache-Control": "public, max-age=3600"
        }
        resp_headers = {k: v for k, v in resp_headers.items() if v is not None}

        return StreamingResponse(res.aiter_bytes(1024*1024), status_code=res.status_code, headers=resp_headers)
    except Exception:
        logger.exception("Error streaming Drive media")
        raise HTTPException(status_code=500, detail="Internal server error. Check server logs for details.")

class WeeklyClaimRequest(BaseModel):
    item_id: int
    profile_id: Optional[str] = "default"
    week_start: Optional[str] = None


class WeeklyRedeemRequest(BaseModel):
    claim_id: int
    profile_id: Optional[str] = "default"


class RewardPreferenceRequest(BaseModel):
    halal_only: bool
    profile_id: Optional[str] = "default"


@router.get("/api/rewards/catalogue")
async def get_catalogue(request: Request, profile_id: Optional[str] = "default", week_start: Optional[str] = None, legacy: bool = False):
    from fastapi import BackgroundTasks
    bg = BackgroundTasks()

    if not legacy:
        try:
            from datetime import date
            from packages.core.domain.services.reward_rotation_service import RewardRotationService
            service = RewardRotationService()
            ref = date.fromisoformat(week_start) if week_start else None
            cat = service.get_catalogue(profile_id=profile_id or "default", ref_date=ref)
            return cat
        except Exception as exc:
            logger.warning(f"Weekly rotation catalogue fetch failed, falling back to static manifests: {exc}")

    local_path = _GUI / "public" / "rewards"
    local_rewards = []
    index_file = local_path / "rewards-index.json"
    proxy_base = "/api/rewards/media"

    if index_file.exists():
        try:
            with open(index_file, "r") as f:
                folder_names = json.load(f)
            for fname in folder_names:
                m_path = local_path / fname / "manifest.json"
                if m_path.exists():
                    with open(m_path, "r") as f:
                        m = json.load(f)
                        m["id"] = fname
                        if "contents" in m:
                            for item in m["contents"]:
                                if "drive_id" in item:
                                    fid = item["drive_id"]
                                    item["url"] = f"{proxy_base}/{fid}"
                                    bg.add_task(prewarm_thumbnail, fid, "w120")
                                    bg.add_task(fully_cache_media, fid)

                        if "thumbnail" in m and m["thumbnail"]:
                            tid = m["thumbnail"]
                            if not tid.startswith("/") and not tid.startswith("http"):
                                m["thumbnail_url"] = f"{proxy_base}/{tid}?sz=w320"
                                m["_thumb_is_drive"] = True
                                bg.add_task(prewarm_thumbnail, tid, "w320")
                        local_rewards.append(m)
        except Exception:
            pass
    logger.info("Fetched reward catalogue")
    local_rewards.sort(key=lambda x: (x.get("season", 0), x.get("cost", 0)))
    return Response(content=json.dumps(local_rewards), media_type="application/json", background=bg)


@router.post("/api/rewards/weekly/claim")
def claim_weekly_reward(payload: WeeklyClaimRequest):
    try:
        from datetime import date
        from packages.core.domain.services.reward_rotation_service import (
            RewardRotationService,
            ClaimConflictError,
            ClaimExpiredError,
        )
        service = RewardRotationService()
        w_start = date.fromisoformat(payload.week_start) if payload.week_start else None
        claim = service.claim_reward(
            profile_id=payload.profile_id or "default",
            item_id=payload.item_id,
            week_start=w_start,
        )
        return {"ok": True, "claim": claim}
    except ClaimConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ClaimExpiredError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/rewards/weekly/redeem")
def redeem_weekly_reward(payload: WeeklyRedeemRequest):
    try:
        from packages.core.domain.services.reward_rotation_service import (
            RewardRotationService,
            ClaimConflictError,
            ClaimExpiredError,
            ClaimNotFoundError,
        )
        service = RewardRotationService()
        redeemed = service.redeem_claim(
            claim_id=payload.claim_id,
            profile_id=payload.profile_id or "default",
        )
        return {"ok": True, "redeemed": redeemed}
    except ClaimNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ClaimConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ClaimExpiredError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/rewards/preferences")
def update_reward_preferences(payload: RewardPreferenceRequest):
    try:
        from packages.core.domain.services.reward_rotation_service import RewardRotationService
        service = RewardRotationService()
        prof = payload.profile_id or "default"
        service.set_halal_preference(prof, payload.halal_only)
        return {"status": "ok", "profile_id": prof, "halal_only": payload.halal_only}
    except Exception as exc:
        logger.error(f"Failed to update reward preferences: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

REWARD_TYPES = ("reward", "savings")


class SelfRewardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    cost: float
    rewardType: Optional[str] = "reward"
    description: Optional[str] = ""
    icon: Optional[str] = "gift"

    @field_validator("rewardType")
    @classmethod
    def _check_reward_type(cls, v: Optional[str]) -> str:
        v = v or "reward"
        if v not in REWARD_TYPES:
            raise ValueError(f"rewardType must be one of: {', '.join(REWARD_TYPES)}")
        return v

# ═════════════════════════════════════════════════════════════════════
# REWARDS — State Persistence
# ═════════════════════════════════════════════════════════════════════

@router.get("/api/rewards/state")
def get_reward_state():
    return reward_service.get_state()

@router.put("/api/rewards/state")
def put_reward_state(body: dict):
    try:
        state = reward_service.save_state(body)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "state": state}

@router.post("/api/rewards/state/patch")
def patch_reward_state(body: dict):
    reward_service.patch_state(body)
    return {"ok": True, "state": reward_service.get_state()}

# ═════════════════════════════════════════════════════════════════════
# SELF-REWARDS — Custom User Rewards
# ═════════════════════════════════════════════════════════════════════

@router.post("/api/rewards/self-reward")
def create_self_reward(payload: SelfRewardCreate):
    try:
        item = reward_service.add_self_reward(
            title=payload.title,
            cost=payload.cost,
            reward_type=payload.rewardType or "reward",
            description=payload.description or "",
            icon=payload.icon or "gift"
        )
        return {"ok": True, "reward": item, "state": reward_service.get_state()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/api/rewards/self-reward/{reward_id}/redeem")
def redeem_self_reward(reward_id: str):
    try:
        item = reward_service.redeem_self_reward(reward_id)
        return {"ok": True, "redeemed": item, "state": reward_service.get_state()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.delete("/api/rewards/self-reward/{reward_id}")
def delete_self_reward(reward_id: str):
    success = reward_service.delete_self_reward(reward_id)
    if not success:
        raise HTTPException(status_code=404, detail="Self reward not found")
    return {"ok": True, "state": reward_service.get_state()}
