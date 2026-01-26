"""
Authentication service - JWT tokens and session management.
Replaces streamlit_authenticator + session_manager.py with database-backed sessions.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import User, UserSession

settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash a password for storage."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data (should include 'sub' for user identifier)
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload dict or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        return payload
    except JWTError:
        return None


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str
) -> Optional[User]:
    """
    Authenticate a user by username and password.

    Args:
        db: Database session
        username: Username to authenticate
        password: Plain text password

    Returns:
        User object if authentication succeeds, None otherwise
    """
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None

    return user


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Get a user by username."""
    result = await db.execute(
        select(User).where(User.username == username)
    )
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get a user by email."""
    result = await db.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get a user by ID."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


# ============================================
# Session Management (replaces session_manager.py)
# ============================================

async def create_session(
    db: AsyncSession,
    user_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    expires_in_days: int = 7
) -> str:
    """
    Create a new session for a user, invalidating any previous sessions.
    This enforces single-session-per-user.

    Args:
        db: Database session
        user_id: User ID
        ip_address: Client IP address
        user_agent: Client user agent string
        expires_in_days: Session expiration in days

    Returns:
        New session ID (UUID string)
    """
    # Invalidate all existing sessions for this user
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id)
        .values(is_active=False)
    )

    # Create new session
    session_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

    session = UserSession(
        user_id=user_id,
        session_id=session_id,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=expires_at,
        is_active=True
    )
    db.add(session)
    await db.commit()

    return session_id


async def validate_session(
    db: AsyncSession,
    user_id: int,
    session_id: str
) -> bool:
    """
    Check if a session is still valid (not replaced by another login).

    Args:
        db: Database session
        user_id: User ID
        session_id: Session ID to validate

    Returns:
        True if session is valid, False otherwise
    """
    result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.session_id == session_id,
            UserSession.is_active == True
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        return False

    # Check expiration
    if session.expires_at and session.expires_at < datetime.utcnow():
        # Session expired
        session.is_active = False
        await db.commit()
        return False

    # Update last activity
    session.last_activity = datetime.utcnow()
    await db.commit()

    return True


async def invalidate_session(
    db: AsyncSession,
    session_id: str
) -> bool:
    """
    Invalidate a specific session (logout).

    Args:
        db: Database session
        session_id: Session ID to invalidate

    Returns:
        True if session was found and invalidated
    """
    result = await db.execute(
        update(UserSession)
        .where(UserSession.session_id == session_id)
        .values(is_active=False)
    )
    await db.commit()
    return result.rowcount > 0


async def invalidate_all_user_sessions(
    db: AsyncSession,
    user_id: int
) -> int:
    """
    Invalidate all sessions for a user (force logout everywhere).

    Args:
        db: Database session
        user_id: User ID

    Returns:
        Number of sessions invalidated
    """
    result = await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id)
        .values(is_active=False)
    )
    await db.commit()
    return result.rowcount


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    """
    Remove expired sessions from database.
    Call periodically to keep table clean.

    Returns:
        Number of sessions deleted
    """
    result = await db.execute(
        delete(UserSession).where(
            UserSession.expires_at < datetime.utcnow()
        )
    )
    await db.commit()
    return result.rowcount


# ============================================
# User Registration
# ============================================

async def create_user(
    db: AsyncSession,
    username: str,
    email: str,
    password: str,
    tier: str = "starter"
) -> User:
    """
    Create a new user.

    Args:
        db: Database session
        username: Unique username
        email: Unique email address
        password: Plain text password (will be hashed)
        tier: Subscription tier (default: starter)

    Returns:
        Created User object
    """
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        tier=tier
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
