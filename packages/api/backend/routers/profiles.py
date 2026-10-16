
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from packages.api.backend.security.core import require_scope
from packages.core.application.profile_service import ProfileService
from packages.core.infrastructure.config import Config

router = APIRouter(
    prefix="/api/profile",
    tags=["Profile"],
    dependencies=[Depends(require_scope("write"))]
)

# Initialize Profile Service with project root
profile_service = ProfileService(Config.BASE_DIR)

import re

from pydantic import field_validator


class ProfileUpdate(BaseModel):
    profile: str

    @field_validator("profile")
    @classmethod
    def sanitize_profile(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-z0-9_]{1,32}$", v):
            raise ValueError("Profile name must be 1-32 alphanumeric characters or underscores.")
        return v

class ProfileCreate(BaseModel):
    name: str
    type: str = "personal"  # "personal" | "business"

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-z0-9_]{1,32}$", v):
            raise ValueError("Profile name must be 1-32 alphanumeric characters or underscores.")
        return v

    @field_validator("type")
    @classmethod
    def sanitize_type(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ["personal", "business"]:
            return "personal"
        return v

@router.get("/")
def get_active_profile():
    active = profile_service.get_active_profile()
    return {
        "active": active,
        "active_type": profile_service.get_profile_type(active),
        "available": profile_service.get_available_profiles(),
        "types": profile_service.get_profile_types_map()
    }

@router.post("/create")
async def create_profile(body: ProfileCreate):
    try:
        profile_service.add_profile(body.name, profile_type=body.type)
        return {
            "status": "success",
            "name": body.name,
            "type": body.type,
            "available": profile_service.get_available_profiles(),
            "types": profile_service.get_profile_types_map()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/switch")
async def switch_profile(update: ProfileUpdate):
    try:
        profile_service.set_active_profile(update.profile)
        # Clear config cache so future DB operations use the new schema
        Config.reset_cache()

        # Disconnect and reconnect Prisma client to the new schema
        import packages.database.index as db_index
        from packages.database.index import connect as prisma_connect
        from packages.database.index import disconnect as prisma_disconnect

        await prisma_disconnect()
        db_index.db = None # Force re-instantiation of Prisma client with updated DATABASE_URL schema
        await prisma_connect()

        # Ensure PostgreSQL tables and columns exist for the newly selected profile schema
        try:
            from packages.api.backend.infrastructure.schemas import SchemaInitializer
            from packages.api.backend.routers.deps import _db
            SchemaInitializer(_db).ensure_all()
        except Exception as schema_err:
            import logging
            logging.getLogger("backend.routers.profiles").warning(f"Profile schema initialization warning: {schema_err}")

        return {"status": "success", "active": update.profile}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{name}")
async def delete_profile(name: str):
    try:
        profile_service.delete_profile(name)
        return {"status": "success", "deleted": name, "available": profile_service.get_available_profiles()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
