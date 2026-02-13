import os
from datetime import date
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

# All paid tiers get full access (professional/enterprise no longer offered but existing subscribers kept)
ACTIVE_TIERS = ("monthly", "annually", "professional", "enterprise")

TIER_FEATURES = {
    "competitive_war_room": ACTIVE_TIERS,
    "intelligence_reports": ACTIVE_TIERS,
    "ask_moodlight": ACTIVE_TIERS,
    "intelligence_dashboard": ACTIVE_TIERS,
    "prediction_markets": ACTIVE_TIERS,
    "strategic_brief": ACTIVE_TIERS,
    "brand_watchlist": ACTIVE_TIERS,
    "topic_watchlist": ACTIVE_TIERS,
    "brand_focus": ACTIVE_TIERS,
    "competitive_tracking": ACTIVE_TIERS,
}

TIER_LIMITS = {
    "brand_watchlist_max": {tier: 5 for tier in ACTIVE_TIERS},
    "topic_watchlist_max": {tier: 10 for tier in ACTIVE_TIERS},
}


def get_db_engine():
    return create_engine(os.getenv("DATABASE_URL"))

def get_user_tier(username: str) -> dict:
    """Get user tier info from database"""
    engine = get_db_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT tier, brief_credits, stripe_customer_id
            FROM users WHERE username = :username
        """), {"username": username})
        row = result.fetchone()
        if row:
            return {
                "tier": row[0],
                "brief_credits": row[1],
                "stripe_customer_id": row[2],
            }
    return {"tier": "monthly", "brief_credits": 0, "stripe_customer_id": None}

def can_generate_brief(username: str) -> tuple[bool, str]:
    """Check if user can generate a brief - all active tiers have unlimited access"""
    user = get_user_tier(username)
    tier = user["tier"]

    # All active tiers have unlimited briefs
    if tier in ("monthly", "annually", "professional", "enterprise"):
        return True, ""

    # Unknown/invalid tier - deny access
    return False, "Your account does not have access to strategic briefs. Please contact support."

def decrement_brief_credits(username: str):
    """Decrement brief credits by 1 after successful generation"""
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE users SET brief_credits = brief_credits - 1, updated_at = CURRENT_TIMESTAMP
            WHERE username = :username AND brief_credits > 0
        """), {"username": username})
        conn.commit()

def add_brief_credits(username: str, credits: int):
    """Add brief credits to a user (after purchasing a brief pack)"""
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE users SET brief_credits = brief_credits + :credits, updated_at = CURRENT_TIMESTAMP
            WHERE username = :username
        """), {"username": username, "credits": credits})
        conn.commit()

def get_brief_credits(username: str) -> int:
    """Get remaining brief credits for a user - all active tiers have unlimited"""
    user = get_user_tier(username)
    if user["tier"] in ("monthly", "annually", "professional", "enterprise"):
        return -1  # unlimited
    return user["brief_credits"]

def has_feature_access(username: str, feature: str) -> bool:
    """Check if user has access to a feature based on their tier"""
    user = get_user_tier(username)
    tier = user["tier"]
    allowed_tiers = TIER_FEATURES.get(feature, ACTIVE_TIERS)
    return tier in allowed_tiers


def get_tier_limit(username: str, limit_name: str) -> int:
    """Get a numeric limit for a user's tier (e.g. brand_watchlist_max).
    Returns 0 if user's tier has no access."""
    user = get_user_tier(username)
    tier = user["tier"]
    limits = TIER_LIMITS.get(limit_name, {})
    return limits.get(tier, 0)

def get_user_preferences(username: str) -> dict:
    """Get email preferences for a user. Defaults all to True if no row exists."""
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT digest_daily, digest_weekly, alert_emails
                FROM user_preferences WHERE username = :username
            """), {"username": username})
            row = result.fetchone()
            if row:
                return {
                    "digest_daily": row[0],
                    "digest_weekly": row[1],
                    "alert_emails": row[2],
                }
    except Exception:
        pass
    return {"digest_daily": True, "digest_weekly": True, "alert_emails": True}


def update_user_preferences(username: str, **kwargs):
    """Upsert email preferences for a user."""
    engine = get_db_engine()
    digest_daily = kwargs.get("digest_daily", True)
    digest_weekly = kwargs.get("digest_weekly", True)
    alert_emails = kwargs.get("alert_emails", True)
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO user_preferences (username, digest_daily, digest_weekly, alert_emails, updated_at)
            VALUES (:username, :daily, :weekly, :alerts, NOW())
            ON CONFLICT (username) DO UPDATE SET
                digest_daily = :daily,
                digest_weekly = :weekly,
                alert_emails = :alerts,
                updated_at = NOW()
        """), {
            "username": username,
            "daily": digest_daily,
            "weekly": digest_weekly,
            "alerts": alert_emails,
        })
        conn.commit()


def log_user_event(username: str, event_type: str, event_data: str = None):
    """Fire-and-forget event logging. Never raises."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO user_events (username, event_type, event_data)
                VALUES (:username, :event_type, :event_data)
            """), {"username": username, "event_type": event_type, "event_data": event_data})
            conn.commit()
    except Exception:
        pass


def update_user_tier(username: str, tier: str, stripe_customer_id: str = None, stripe_subscription_id: str = None):
    """Update user tier after Stripe payment"""
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE users
            SET tier = :tier,
                stripe_customer_id = COALESCE(:stripe_customer_id, stripe_customer_id),
                stripe_subscription_id = COALESCE(:stripe_subscription_id, stripe_subscription_id),
                updated_at = CURRENT_TIMESTAMP
            WHERE username = :username
        """), {
            "username": username,
            "tier": tier,
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription_id": stripe_subscription_id
        })
        conn.commit()
