"""
Tier management service - subscription tiers and brief quotas.
Port of tier_helper.py with async database operations.
"""
from datetime import date
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


# Tier configuration - matches existing tier_helper.py
TIER_LIMITS = {
    "starter": 5,
    "pro": 15,
    "enterprise": 999999,  # Unlimited
}

# Features available per tier
TIER_FEATURES = {
    "brand_focus": ["pro", "enterprise"],
    "competitive_tracking": ["pro", "enterprise"],
    "white_label": ["enterprise"],
    "advanced_predictive": ["enterprise"],
    "custom_frameworks": ["enterprise"],
    "api_access": ["enterprise"],
}


async def get_user_tier(db: AsyncSession, username: str) -> dict:
    """
    Get user tier info from database.

    Args:
        db: Database session
        username: Username to look up

    Returns:
        Dict with tier, briefs_used, briefs_reset_date, extra_briefs_addon
    """
    result = await db.execute(
        select(User.tier, User.briefs_used, User.briefs_reset_date, User.extra_briefs_addon)
        .where(User.username == username)
    )
    row = result.first()

    if row:
        return {
            "tier": row[0],
            "briefs_used": row[1] or 0,
            "briefs_reset_date": row[2],
            "extra_briefs_addon": row[3] or False
        }

    # Default for unknown user
    return {
        "tier": "starter",
        "briefs_used": 0,
        "briefs_reset_date": date.today(),
        "extra_briefs_addon": False
    }


def get_brief_limit(tier: str, extra_briefs: bool = False) -> int:
    """
    Get brief limit based on tier.

    Args:
        tier: User's subscription tier
        extra_briefs: Whether user has extra briefs addon

    Returns:
        Maximum briefs allowed per month
    """
    base = TIER_LIMITS.get(tier, 5)

    # Starter tier with addon gets 10 instead of 5
    if tier == "starter" and extra_briefs:
        base = 10

    return base


async def can_generate_brief(db: AsyncSession, username: str) -> tuple[bool, str]:
    """
    Check if user can generate a brief based on quota.

    Args:
        db: Database session
        username: Username to check

    Returns:
        Tuple of (can_generate: bool, message: str)
    """
    user_info = await get_user_tier(db, username)
    limit = get_brief_limit(user_info["tier"], user_info["extra_briefs_addon"])

    # Check if monthly reset is needed
    today = date.today()
    reset_date = user_info["briefs_reset_date"]

    if reset_date and reset_date.month != today.month:
        await reset_brief_count(db, username)
        user_info["briefs_used"] = 0

    if user_info["briefs_used"] >= limit:
        tier = user_info["tier"]
        has_addon = user_info["extra_briefs_addon"]

        if tier == "starter" and not has_addon:
            return False, f"You've used all {limit} briefs this month. Contact us to add 5 more briefs/month for $199."
        elif tier == "starter" and has_addon:
            return False, f"You've used all {limit} briefs this month. Upgrade to Pro for 15 briefs/month."
        elif tier == "pro":
            return False, f"You've used all {limit} briefs this month. Contact us to upgrade to Enterprise for unlimited briefs."
        else:
            return False, f"You've used all {limit} briefs this month."

    remaining = limit - user_info["briefs_used"]
    return True, f"{remaining} briefs remaining this month"


async def increment_brief_count(db: AsyncSession, username: str) -> None:
    """
    Increment brief count after generation.

    Args:
        db: Database session
        username: Username to update
    """
    await db.execute(
        update(User)
        .where(User.username == username)
        .values(briefs_used=User.briefs_used + 1)
    )
    await db.commit()


async def reset_brief_count(db: AsyncSession, username: str) -> None:
    """
    Reset brief count at start of month.

    Args:
        db: Database session
        username: Username to reset
    """
    await db.execute(
        update(User)
        .where(User.username == username)
        .values(briefs_used=0, briefs_reset_date=date.today())
    )
    await db.commit()


def has_feature_access(tier: str, feature: str) -> bool:
    """
    Check if a tier has access to a feature.

    Args:
        tier: User's subscription tier
        feature: Feature name to check

    Returns:
        True if tier has access to the feature
    """
    allowed_tiers = TIER_FEATURES.get(feature, [])
    return tier in allowed_tiers


async def update_user_tier(
    db: AsyncSession,
    username: str,
    tier: str,
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None
) -> bool:
    """
    Update user tier after Stripe payment.

    Args:
        db: Database session
        username: Username to update
        tier: New tier
        stripe_customer_id: Optional Stripe customer ID
        stripe_subscription_id: Optional Stripe subscription ID

    Returns:
        True if user was found and updated
    """
    values = {"tier": tier}
    if stripe_customer_id:
        values["stripe_customer_id"] = stripe_customer_id
    if stripe_subscription_id:
        values["stripe_subscription_id"] = stripe_subscription_id

    result = await db.execute(
        update(User)
        .where(User.username == username)
        .values(**values)
    )
    await db.commit()
    return result.rowcount > 0


async def update_user_tier_by_email(
    db: AsyncSession,
    email: str,
    tier: str,
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None
) -> bool:
    """
    Update user tier by email (for Stripe webhooks).

    Args:
        db: Database session
        email: User email
        tier: New tier
        stripe_customer_id: Optional Stripe customer ID
        stripe_subscription_id: Optional Stripe subscription ID

    Returns:
        True if user was found and updated
    """
    values = {"tier": tier}
    if stripe_customer_id:
        values["stripe_customer_id"] = stripe_customer_id
    if stripe_subscription_id:
        values["stripe_subscription_id"] = stripe_subscription_id

    result = await db.execute(
        update(User)
        .where(User.email == email)
        .values(**values)
    )
    await db.commit()
    return result.rowcount > 0


def get_tier_display_name(tier: str) -> str:
    """Get human-readable tier name."""
    names = {
        "starter": "Starter",
        "pro": "Pro",
        "enterprise": "Enterprise"
    }
    return names.get(tier, tier.title())


def get_upgrade_options(current_tier: str) -> list[dict]:
    """Get available upgrade options for a tier."""
    upgrades = []

    if current_tier == "starter":
        upgrades.append({
            "tier": "pro",
            "name": "Pro",
            "briefs": 15,
            "features": ["Brand Focus", "Competitive Tracking"],
            "price": "$499/month"
        })
        upgrades.append({
            "tier": "enterprise",
            "name": "Enterprise",
            "briefs": "Unlimited",
            "features": ["Everything in Pro", "White Label", "API Access"],
            "price": "Contact Us"
        })
    elif current_tier == "pro":
        upgrades.append({
            "tier": "enterprise",
            "name": "Enterprise",
            "briefs": "Unlimited",
            "features": ["Everything in Pro", "White Label", "API Access"],
            "price": "Contact Us"
        })

    return upgrades


def get_tier_config(tier: str) -> dict:
    """
    Get full tier configuration.

    Args:
        tier: User's subscription tier

    Returns:
        Dict with tier configuration including limits and features
    """
    brief_limit = TIER_LIMITS.get(tier, 5)
    if brief_limit >= 999999:
        brief_limit = -1  # Indicates unlimited

    features = []
    for feature, allowed_tiers in TIER_FEATURES.items():
        if tier in allowed_tiers:
            features.append(feature)

    return {
        "tier": tier,
        "display_name": get_tier_display_name(tier),
        "brief_limit": brief_limit,
        "features": features,
        "has_brand_focus": "brand_focus" in features,
        "has_competitive_tracking": "competitive_tracking" in features,
        "has_white_label": "white_label" in features,
        "has_api_access": "api_access" in features,
    }


def can_generate_brief(user: User) -> bool:
    """
    Simple check if user can generate a brief (synchronous).

    Args:
        user: User object

    Returns:
        True if user can generate another brief
    """
    limit = get_brief_limit(user.tier, user.extra_briefs_addon or False)

    # Check monthly reset
    today = date.today()
    if user.briefs_reset_date and user.briefs_reset_date.month != today.month:
        return True  # Will be reset on next generation

    return (user.briefs_used or 0) < limit


async def increment_brief_count(user: User, db: AsyncSession) -> None:
    """
    Increment brief count for a user object.

    Args:
        user: User object to update
        db: Database session
    """
    today = date.today()

    # Reset if new month
    if user.briefs_reset_date and user.briefs_reset_date.month != today.month:
        user.briefs_used = 1
        user.briefs_reset_date = today
    else:
        user.briefs_used = (user.briefs_used or 0) + 1
        if not user.briefs_reset_date:
            user.briefs_reset_date = today
