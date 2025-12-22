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
            SELECT tier, briefs_used, briefs_reset_date, extra_briefs_addon
            FROM users WHERE username = :username
        """), {"username": username})
        row = result.fetchone()
        if row:
            return {
                "tier": row[0],
                "briefs_used": row[1],
                "briefs_reset_date": row[2],
                "extra_briefs_addon": row[3]
            }
    return {"tier": "solo", "briefs_used": 0, "briefs_reset_date": date.today(), "extra_briefs_addon": False}

def get_brief_limit(tier: str, extra_briefs: bool = False) -> int:
    """Get brief limit based on tier"""
    limits = {
        "solo": 3,
        "team": 10,
        "enterprise": 999999  # unlimited
    }
    base = limits.get(tier, 3)
    if tier == "solo" and extra_briefs:
        base = 5
    return base

def can_generate_brief(username: str) -> tuple[bool, str]:
    """Check if user can generate a brief"""
    user = get_user_tier(username)
    limit = get_brief_limit(user["tier"], user["extra_briefs_addon"])
    
    # Reset monthly count if needed
    today = date.today()
    if user["briefs_reset_date"] and user["briefs_reset_date"].month != today.month:
        reset_brief_count(username)
        user["briefs_used"] = 0
    
    if user["briefs_used"] >= limit:
        tier = user["tier"]
        has_addon = user["extra_briefs_addon"]
        if tier == "solo" and not has_addon:
            return False, f"You've used all {limit} briefs this month. Contact us to add 2 more briefs/month for $199."
        elif tier == "solo" and has_addon:
            return False, f"You've used all {limit} briefs this month. [Upgrade to Team](https://buy.stripe.com/bJe6oz4fxgc2g7Bh0I8ww04) for 10 briefs/month."
        elif tier == "team":
            return False, f"You've used all {limit} briefs this month. Contact us to upgrade to Enterprise for unlimited briefs."
        else:
            return False, f"You've used all {limit} briefs this month."
    return True, ""
def increment_brief_count(username: str):

    """Increment brief count after generation"""
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE users SET briefs_used = briefs_used + 1, updated_at = CURRENT_TIMESTAMP
            WHERE username = :username
        """), {"username": username})
        conn.commit()

def reset_brief_count(username: str):
    """Reset brief count at start of month"""
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE users SET briefs_used = 0, briefs_reset_date = CURRENT_DATE, updated_at = CURRENT_TIMESTAMP
            WHERE username = :username
        """), {"username": username})
        conn.commit()

def has_feature_access(username: str, feature: str) -> bool:
    """Check if user has access to a feature"""
    user = get_user_tier(username)
    tier = user["tier"]
    
    features = {
        "brand_focus": ["team", "enterprise"],
        "competitive_tracking": ["team", "enterprise"],
        "white_label": ["enterprise"],
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
