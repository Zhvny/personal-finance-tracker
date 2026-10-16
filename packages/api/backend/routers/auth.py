import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from packages.api.backend.routers.deps import _db, _execute, _query

logger = logging.getLogger("backend.auth")

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class RegisterIn(BaseModel):
    username: str
    password: str

class LoginIn(BaseModel):
    username: str
    password: str

def _hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    # 600k iterasi = panduan OWASP 2023 untuk PBKDF2-HMAC-SHA256.
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 600000).hex()
    return hashed, salt

def _init_users_table():
    db = _db("users", "audit_log.db")
    _execute(
        db,
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "username TEXT UNIQUE NOT NULL, "
        "password_hash TEXT NOT NULL, "
        "salt TEXT NOT NULL, "
        "created_at TEXT NOT NULL)"
    )
    _execute(
        db,
        "CREATE TABLE IF NOT EXISTS user_sessions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
        "token_hash TEXT UNIQUE NOT NULL, expires_at TEXT NOT NULL, "
        "created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))"
    )

_init_users_table()


def _create_session(db: str, username: str) -> str:
    """Issue a token while persisting only its digest and expiry."""
    user = _query(db, "SELECT id FROM users WHERE username = ?", (username,))
    if not user:
        raise RuntimeError("Cannot create a session for an unknown user")
    token = f"user_{secrets.token_urlsafe(32)}"
    now = datetime.utcnow()
    _execute(
        db,
        "INSERT INTO user_sessions (user_id, token_hash, expires_at, created_at) VALUES (?,?,?,?)",
        (user[0][0], hashlib.sha256(token.encode("utf-8")).hexdigest(),
         (now + timedelta(hours=12)).isoformat(sep=" "), now.isoformat(sep=" ")),
    )
    return token

@router.post("/register")
async def register(body: RegisterIn):

    env = (os.environ.get("ENVIRONMENT") or os.environ.get("APP_ENV") or "").lower()
    open_register = os.environ.get("ALLOW_OPEN_REGISTER") == "1"
    # SECURITY fail-closed: /register mencetak Bearer langsung — hanya
    # env dev eksplisit atau operator via ALLOW_OPEN_REGISTER=1.
    if env not in ("dev", "development") and not open_register:
        logger.warning(f"Open registration attempt blocked (env={env!r})")
        raise HTTPException(403, "Registration is closed.")

    username = body.username.strip().lower()
    if not username or len(body.password) < 8:
        raise HTTPException(400, "Username and password (min 8 chars) are required.")

    db = _db("users", "audit_log.db")
    existing = _query(db, "SELECT id FROM users WHERE username = ?", (username,))
    if existing:
        raise HTTPException(400, "Username already registered.")

    hashed, salt = _hash_password(body.password)
    now_str = datetime.utcnow().isoformat()
    _execute(db, "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?,?,?,?)",
             (username, hashed, salt, now_str))

    token = _create_session(db, username)
    return {"ok": True, "token": token, "username": username}

@router.post("/logout")
async def logout(request: Request):
    """Revoke the caller's session (delete its hash). Token via Authorization header."""
    auth_header = request.headers.get("authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(400, "Missing Authorization header.")

    db = _db("users", "audit_log.db")
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    _execute(db, "DELETE FROM user_sessions WHERE token_hash = ?", (token_hash,))
    return {"ok": True}

@router.post("/login")
async def login(body: LoginIn):
    username = body.username.strip().lower()
    db = _db("users", "audit_log.db")
    users = _query(db, "SELECT password_hash, salt FROM users WHERE username = ?", (username,))

    if not users:
        raise HTTPException(401, "Invalid username or password.")

    stored_hash, salt = users[0][0], users[0][1]
    computed_hash, _ = _hash_password(body.password, salt)

    import hmac as _hmac
    if not _hmac.compare_digest(computed_hash, stored_hash):
        raise HTTPException(401, "Invalid username or password.")

    token = _create_session(db, username)
    return {"ok": True, "token": token, "username": username}
