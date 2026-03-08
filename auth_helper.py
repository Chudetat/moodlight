"""
auth_helper.py — JWT authentication helpers for the Moodlight API.

Stateless JWT auth with bcrypt password verification.
Tier is NOT stored in the JWT — checked from DB on every protected request.
"""

import os
import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text as sql_text

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

ADMIN_EMAILS = frozenset({"daniel@moodlightintel.com", "intel@moodlightintel.com"})

_bearer_scheme = HTTPBearer(auto_error=False)

# Pre-computed dummy hash for timing-attack mitigation on unknown users
_DUMMY_HASH = bcrypt.hashpw(b"dummy_password_for_timing", bcrypt.gensalt()).decode()


def create_access_token(username: str, email: str, session_id: str | None = None) -> str:
    """Create a signed JWT with username, email, and session_id claims."""
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET not configured")
    payload = {
        "sub": username,
        "email": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_session(engine, username: str) -> str:
    """Create a new session for a user, invalidating any previous session.
    Stores session_id in users table. Returns the new session_id."""
    sid = str(uuid.uuid4())
    try:
        with engine.connect() as conn:
            conn.execute(
                sql_text("UPDATE users SET session_id = :sid WHERE username = :u"),
                {"sid": sid, "u": username},
            )
            conn.commit()
    except Exception as e:
        print(f"WARNING: create_session failed: {e}")
    return sid


def validate_session(engine, username: str, session_id: str) -> bool:
    """Check if session_id matches the current active session in DB."""
    if not session_id:
        return True  # Legacy tokens without sid are allowed (graceful migration)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                sql_text("SELECT session_id FROM users WHERE username = :u"),
                {"u": username},
            ).fetchone()
            if not row:
                return False
            db_sid = row[0]
            if db_sid is None:
                return True  # No session enforcement yet for this user
            return db_sid == session_id
    except Exception as e:
        print(f"WARNING: validate_session failed: {e}")
        return True  # Fail open on DB errors


def clear_session(engine, username: str):
    """Clear the session on logout, invalidating the current token."""
    try:
        with engine.connect() as conn:
            conn.execute(
                sql_text("UPDATE users SET session_id = NULL WHERE username = :u"),
                {"u": username},
            )
            conn.commit()
    except Exception as e:
        print(f"WARNING: clear_session failed: {e}")


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def verify_password(plain: str, hashed: str) -> bool:
    """Check plaintext password against bcrypt hash. Returns False on any error."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def lookup_user(engine, *, email: str = None, username: str = None) -> dict | None:
    """Look up a user by email or username. Returns dict with user fields or None."""
    if not email and not username:
        return None
    try:
        with engine.connect() as conn:
            if email:
                row = conn.execute(
                    sql_text(
                        "SELECT username, email, password_hash, tier, "
                        "COALESCE(brief_credits, 0), COALESCE(extra_seats, 0) "
                        "FROM users WHERE email = :email"
                    ),
                    {"email": email},
                ).fetchone()
            else:
                row = conn.execute(
                    sql_text(
                        "SELECT username, email, password_hash, tier, "
                        "COALESCE(brief_credits, 0), COALESCE(extra_seats, 0) "
                        "FROM users WHERE username = :username"
                    ),
                    {"username": username},
                ).fetchone()
            if row:
                return {
                    "username": row[0],
                    "email": row[1],
                    "password_hash": row[2],
                    "tier": row[3],
                    "brief_credits": row[4],
                    "extra_seats": row[5],
                }
    except Exception as e:
        print(f"WARNING: lookup_user failed: {e}")
    return None


def is_admin_email(email: str) -> bool:
    """Check if an email belongs to an admin."""
    return email.strip().lower() in ADMIN_EMAILS


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict:
    """FastAPI dependency: extract and validate JWT from Authorization header.

    Usage in endpoint:  payload: dict = Depends(require_auth)
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(credentials.credentials)
