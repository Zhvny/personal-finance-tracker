import asyncio
import logging
import os
import re

from prisma import Prisma

from packages.core.infrastructure.config import Config

logger = logging.getLogger("database.index")

# NOTE: db is initialized lazily in connect() to ensure DATABASE_URL is patched
# with the correct profile schema BEFORE Prisma reads it.
db: Prisma = None  # type: ignore[assignment]
_connected_loop = None
_main_loop = None
_active_profile: str | None = None  # Track which profile Prisma is connected to


def _read_active_profile_direct() -> str:
    """Read active profile directly from file, bypassing Config cache."""
    try:
        profile_path = Config.BASE_DIR / "data" / "active_profile.txt"
        if profile_path.exists():
            profile = profile_path.read_text().strip().lower()
            if profile:
                return profile
    except Exception:
        pass
    return "personal"

def _prepare_db_client() -> str:
    """Prepare the Prisma client for the current active profile.
    
    Returns the current profile name. Forces re-instantiation if the profile
    has changed since the client was last prepared (e.g., after a test run).
    """
    global db, _active_profile
    # Always read directly from file to bypass stale Config cache
    profile = _read_active_profile_direct()
    # Also reset Config cache so it stays in sync
    Config.reset_cache()
    db_url = os.environ.get("DATABASE_URL")

    if db_url:
        if "schema=" in db_url:
            db_url = re.sub(r"schema=[^&]+", f"schema={profile}", db_url)
        else:
            separator = "&" if "?" in db_url else "?"
            db_url = f"{db_url}{separator}schema={profile}"

        # Ensure search_path is passed via PostgreSQL options parameter
        search_path_opt = f"options=-c%20search_path%3D{profile},public"
        if "options=" in db_url:
            db_url = re.sub(r"options=[^&]+", search_path_opt, db_url)
        else:
            separator = "&" if "?" in db_url else "?"
            db_url = f"{db_url}{separator}{search_path_opt}"

        os.environ["DATABASE_URL"] = db_url
        logger.info(f"[Prisma] DATABASE_URL set to: {db_url}")
    else:
        logger.warning("[Prisma] DATABASE_URL is not set in environment! Prisma will fall back to default/schema.prisma url.")

    # Force re-instantiate client if profile changed (e.g., after test run switched profile)
    if _active_profile is not None and _active_profile != profile:
        logger.warning(f"[Prisma] Profile changed from '{_active_profile}' to '{profile}'. Forcing client re-instantiation.")
        db = None

    if db is None:
        db = Prisma()
        _active_profile = profile
        logger.info(f"[Prisma] Prisma client instantiated with profile={profile}")

    return profile

async def connect():
    global db, _connected_loop, _main_loop
    _prepare_db_client()

    if not db.is_connected():
        await db.connect()
        logger.info(f"[Prisma] Connected to PostgreSQL schema={Config.get_active_profile()}")
    else:
        logger.info("[Prisma] Prisma client is already connected.")

    _connected_loop = asyncio.get_running_loop()
    _main_loop = _connected_loop

async def get_db() -> Prisma:
    """Get the active Prisma client. Connects/reconnects automatically if the loop changed."""
    global db, _connected_loop
    _prepare_db_client()

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if not db.is_connected():
        await db.connect()
        if current_loop:
            _connected_loop = current_loop
        logger.info("[Prisma] Connected to PostgreSQL automatically.")
    elif current_loop and (_connected_loop is not current_loop or _connected_loop.is_closed()):
        logger.warning(f"[Prisma] Loop changed or closed. Reconnecting Prisma client... (Current loop: {current_loop}, Connected loop: {_connected_loop})")
        try:
            await db.disconnect()
        except Exception as e:
            logger.debug(f"[Prisma] Disconnect failed: {e}")

        db = None
        _prepare_db_client()
        await db.connect()
        _connected_loop = current_loop
        logger.info("[Prisma] Reconnected to PostgreSQL automatically on new loop.")

    return db

async def disconnect():
    global db
    if db is not None and db.is_connected():
        await db.disconnect()
        logger.info("[Prisma] Prisma client disconnected.")

def run_query(coro):
    """
    Run an async database query.
    If we are in a thread pool and the main event loop is running,
    we run it on the main loop. Otherwise, we run it using asyncio.run().
    """
    global _main_loop

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if current_loop is not None:
        if _main_loop is not None and _main_loop.is_running() and current_loop is not _main_loop:
            future = asyncio.run_coroutine_threadsafe(coro, _main_loop)
            return future.result()
        # Fallback if no other option
        return current_loop.run_until_complete(coro)

    if _main_loop is not None and _main_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(coro, _main_loop)
        return future.result()

    return asyncio.run(coro)

