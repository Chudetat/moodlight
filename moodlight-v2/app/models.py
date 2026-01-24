"""
SQLAlchemy models for Moodlight.
Matches existing PostgreSQL schema from create_users_table.py.
"""
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    String, Integer, Boolean, DateTime, Date, Float, Text,
    ForeignKey, Index, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """
    User model - matches existing users table schema.
    Supports subscription tiers and brief quotas.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Subscription tier
    tier: Mapped[str] = mapped_column(String(20), default="starter")
    briefs_used: Mapped[int] = mapped_column(Integer, default=0)
    briefs_reset_date: Mapped[Optional[date]] = mapped_column(Date, default=func.current_date())

    # Stripe integration
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Add-ons
    extra_briefs_addon: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_seats: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    # Relationships
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.tier})>"


class UserSession(Base):
    """
    User session model - replaces file-based session_manager.py.
    Enforces single active session per user.
    """
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)

    # Session metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp(), nullable=False
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("ix_user_sessions_user_active", "user_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<UserSession {self.session_id[:8]}... for user_id={self.user_id}>"


class NewsItem(Base):
    """
    News/social item model - matches existing news_scored/social_scored tables.
    Stores fetched content with empathy scoring.
    """
    __tablename__ = "news_items"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Source info
    link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # x, news, reddit_*
    topic: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Engagement
    engagement: Mapped[float] = mapped_column(Float, default=0.0)

    # Geographic
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Empathy scoring
    intensity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    empathy_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    empathy_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Top emotions from GoEmotions
    emotion_top_1: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    emotion_top_2: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    emotion_top_3: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Metadata
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_news_items_created_source", "created_at", "source"),
        Index("ix_news_items_topic_created", "topic", "created_at"),
    )

    @property
    def emotion(self) -> Optional[str]:
        """Alias for emotion_top_1 for convenience."""
        return self.emotion_top_1

    def __repr__(self) -> str:
        return f"<NewsItem {self.id[:20]}... ({self.source})>"


class Brief(Base):
    """
    Generated strategic brief model.
    Tracks brief generation for billing and history.
    """
    __tablename__ = "briefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Brief input - the user's request/prompt
    prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # Brief output
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Frameworks used (stored as JSON list in PostgreSQL)
    _frameworks_used: Mapped[Optional[str]] = mapped_column("frameworks_used", Text, nullable=True)

    # Status
    emailed: Mapped[bool] = mapped_column(Boolean, default=False)
    emailed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        Index("ix_briefs_user_created", "user_id", "created_at"),
    )

    @property
    def frameworks_used(self) -> list[str]:
        """Get frameworks as list."""
        if not self._frameworks_used:
            return []
        import json
        try:
            return json.loads(self._frameworks_used)
        except (json.JSONDecodeError, TypeError):
            return []

    @frameworks_used.setter
    def frameworks_used(self, value: list[str]) -> None:
        """Set frameworks from list."""
        import json
        self._frameworks_used = json.dumps(value) if value else None

    def __repr__(self) -> str:
        return f"<Brief {self.id} for user_id={self.user_id}>"
