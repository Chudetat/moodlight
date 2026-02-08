import os
from datetime import date
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

def get_db_engine():
    return create_engine(os.getenv("DATABASE_URL"))

def get_user_tier(username: str) -> dict:
    """Get user tier info from database"""
    engine = get_db_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT tier, brief_credits
            FROM users WHERE username = :username
        """), {"username": username})
        row = result.fetchone()
        if row:
            return {
                "tier": row[0],
                "brief_credits": row[1]
            }
    return {"tier": "professional", "brief_credits": 0}

def can_generate_brief(username: str) -> tuple[bool, str]:
    """Check if user can generate a brief - Professional and Enterprise have unlimited access"""
    user = get_user_tier(username)
    tier = user["tier"]

    # Professional and Enterprise users have unlimited briefs
    if tier in ("professional", "enterprise"):
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
    """Get remaining brief credits for a user - Professional and Enterprise have unlimited"""
    user = get_user_tier(username)
    if user["tier"] in ("professional", "enterprise"):
        return -1  # unlimited
    return user["brief_credits"]

def has_feature_access(username: str, feature: str) -> bool:
    """Check if user has access to a feature"""
    user = get_user_tier(username)
    tier = user["tier"]

    # Professional gets all standard features
    # Only enterprise-exclusive features are gated
    features = {
        "brand_focus": ["professional", "enterprise"],
        "competitive_tracking": ["professional", "enterprise"],
        "white_label": ["enterprise"],
        "advanced_predictive": ["enterprise"],
    }

    allowed_tiers = features.get(feature, [])
    return tier in allowed_tiers

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
