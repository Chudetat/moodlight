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


# ---------------------------------------------------------------------------
# Alert tuning preferences
# ---------------------------------------------------------------------------

SENSITIVITY_MULTIPLIERS = {
    "low": 1.5,
    "medium": 1.0,
    "high": 0.7,
}

ALERT_TYPE_CATEGORIES = {
    "brand": [
        "brand_white_space", "brand_velocity_spike", "brand_narrative_fading",
        "brand_saturation", "brand_mention_surge", "brand_sentiment_shift", "brand_crisis",
    ],
    "topic": [
        "topic_mention_surge", "topic_sentiment_shift", "topic_intensity_spike",
        "topic_velocity_spike", "topic_saturation",
    ],
    "global": [
        "mood_shift", "market_mood_divergence", "intensity_cluster", "topic_emergence",
        "regulatory_policy_spike", "breaking_signal", "geopolitical_risk_escalation",
    ],
    "predictive": [
        "predictive_mood_shift", "predictive_intensity_cluster",
        "predictive_brand_velocity_spike", "predictive_brand_saturation",
        "predictive_brand_white_space", "predictive_market_mood_divergence",
        "predictive_compound_signal", "predictive_topic_velocity_spike",
        "predictive_topic_saturation",
    ],
    "competitive": [
        "competitor_momentum", "share_of_voice_shift", "competitive_white_space",
    ],
}


def get_user_alert_preferences(username: str) -> dict:
    """Get per-user alert type preferences. Returns {alert_type: {enabled, sensitivity}}."""
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT alert_type, enabled, sensitivity
                FROM user_alert_preferences WHERE username = :username
            """), {"username": username})
            prefs = {}
            for row in result.fetchall():
                prefs[row[0]] = {"enabled": row[1], "sensitivity": row[2]}
            return prefs
    except Exception:
        return {}


def update_user_alert_preferences(username: str, alert_type: str,
                                   enabled: bool = True, sensitivity: str = "medium"):
    """Upsert a single alert type preference for a user."""
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO user_alert_preferences (username, alert_type, enabled, sensitivity, updated_at)
            VALUES (:username, :alert_type, :enabled, :sensitivity, NOW())
            ON CONFLICT (username, alert_type) DO UPDATE SET
                enabled = :enabled, sensitivity = :sensitivity, updated_at = NOW()
        """), {
            "username": username, "alert_type": alert_type,
            "enabled": enabled, "sensitivity": sensitivity,
        })
        conn.commit()


def bulk_update_alert_sensitivity(username: str, sensitivity: str):
    """Update sensitivity for all alert types for a user."""
    engine = get_db_engine()
    all_types = []
    for types in ALERT_TYPE_CATEGORIES.values():
        all_types.extend(types)
    with engine.connect() as conn:
        for alert_type in all_types:
            conn.execute(text("""
                INSERT INTO user_alert_preferences (username, alert_type, sensitivity, updated_at)
                VALUES (:username, :alert_type, :sensitivity, NOW())
                ON CONFLICT (username, alert_type) DO UPDATE SET
                    sensitivity = :sensitivity, updated_at = NOW()
            """), {"username": username, "alert_type": alert_type, "sensitivity": sensitivity})
        conn.commit()


def should_show_alert(username: str, alert_type: str, prefs: dict = None) -> bool:
    """Check if a specific alert type should be shown to this user."""
    if prefs is None:
        prefs = get_user_alert_preferences(username)
    pref = prefs.get(alert_type)
    if pref is None:
        return True
    return pref.get("enabled", True)


# ---------------------------------------------------------------------------
# Notification center helpers
# ---------------------------------------------------------------------------

def get_unread_alert_count(username: str) -> int:
    """Get count of unread alerts for this user (last 7 days)."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM alerts a
                WHERE a.timestamp > NOW() - INTERVAL '7 days'
                  AND (a.username IS NULL OR a.username = :user)
                  AND NOT EXISTS (
                      SELECT 1 FROM alert_read_status rs
                      WHERE rs.alert_id = a.id AND rs.username = :user
                  )
            """), {"user": username})
            return result.scalar() or 0
    except Exception:
        return 0


def mark_alert_read(username: str, alert_id: int):
    """Mark a single alert as read for a user. Fire-and-forget."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO alert_read_status (alert_id, username)
                VALUES (:alert_id, :username)
                ON CONFLICT (alert_id, username) DO NOTHING
            """), {"alert_id": alert_id, "username": username})
            conn.commit()
    except Exception:
        pass


def mark_all_alerts_read(username: str):
    """Mark all current alerts as read for a user."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO alert_read_status (alert_id, username)
                SELECT a.id, :user FROM alerts a
                WHERE a.timestamp > NOW() - INTERVAL '7 days'
                  AND (a.username IS NULL OR a.username = :user)
                  AND NOT EXISTS (
                      SELECT 1 FROM alert_read_status rs
                      WHERE rs.alert_id = a.id AND rs.username = :user
                  )
            """), {"user": username})
            conn.commit()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Report schedule helpers
# ---------------------------------------------------------------------------

def get_report_schedules(username: str) -> list:
    """Get all report schedules for a user."""
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, subject, subject_type, frequency, days_lookback,
                       enabled, last_run, next_run
                FROM report_schedules WHERE username = :username ORDER BY created_at
            """), {"username": username})
            return result.fetchall()
    except Exception:
        return []


def create_report_schedule(username: str, subject: str, subject_type: str,
                           frequency: str, days_lookback: int = 7) -> bool:
    """Create a new report schedule."""
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    engine = get_db_engine()
    now = _dt.now(_tz.utc)
    if frequency == "daily":
        next_run = (now + _td(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    else:
        days_ahead = 7 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_run = (now + _td(days=days_ahead)).replace(hour=8, minute=0, second=0, microsecond=0)
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO report_schedules
                    (username, subject, subject_type, frequency, days_lookback, next_run)
                VALUES (:username, :subject, :subject_type, :frequency, :days, :next_run)
            """), {
                "username": username, "subject": subject,
                "subject_type": subject_type, "frequency": frequency,
                "days": days_lookback, "next_run": next_run,
            })
            conn.commit()
        return True
    except Exception:
        return False


def delete_report_schedule(schedule_id: int):
    """Delete a report schedule."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM report_schedules WHERE id = :id"),
                         {"id": schedule_id})
            conn.commit()
    except Exception:
        pass


def toggle_report_schedule(schedule_id: int, enabled: bool):
    """Enable/disable a report schedule."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE report_schedules SET enabled = :enabled, updated_at = NOW()
                WHERE id = :id
            """), {"id": schedule_id, "enabled": enabled})
            conn.commit()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Team helpers
# ---------------------------------------------------------------------------

def get_user_team(username: str) -> dict | None:
    """Get the team this user belongs to (if any)."""
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT t.id, t.team_name, t.owner_username, tm.role
                FROM team_members tm
                JOIN teams t ON t.id = tm.team_id
                WHERE tm.username = :username LIMIT 1
            """), {"username": username})
            row = result.fetchone()
            if row:
                return {"id": row[0], "team_name": row[1], "owner_username": row[2], "role": row[3]}
    except Exception:
        pass
    return None


def get_team_members(team_id: int) -> list:
    """Get all members of a team."""
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT tm.username, tm.role, tm.joined_at, u.email
                FROM team_members tm
                JOIN users u ON u.username = tm.username
                WHERE tm.team_id = :team_id
                ORDER BY tm.role DESC, tm.joined_at
            """), {"team_id": team_id})
            return result.fetchall()
    except Exception:
        return []


def get_team_capacity(owner_username: str) -> int:
    """Get remaining team seats based on extra_seats column."""
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT u.extra_seats, COUNT(tm.id) AS current_members
                FROM users u
                LEFT JOIN teams t ON t.owner_username = u.username
                LEFT JOIN team_members tm ON tm.team_id = t.id AND tm.username != u.username
                WHERE u.username = :username
                GROUP BY u.extra_seats
            """), {"username": owner_username})
            row = result.fetchone()
            if row:
                return max(0, (row[0] or 0) - (row[1] or 0))
    except Exception:
        pass
    return 0


def create_team(owner_username: str, team_name: str) -> int | None:
    """Create a team and add owner as member with 'owner' role."""
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            # Validate owner exists in users table
            owner_exists = conn.execute(text(
                "SELECT 1 FROM users WHERE username = :u"
            ), {"u": owner_username}).fetchone()
            if not owner_exists:
                return None
            # Check owner doesn't already own a team
            existing_team = conn.execute(text(
                "SELECT 1 FROM teams WHERE owner_username = :u"
            ), {"u": owner_username}).fetchone()
            if existing_team:
                return None
            result = conn.execute(text("""
                INSERT INTO teams (team_name, owner_username)
                VALUES (:name, :owner) RETURNING id
            """), {"name": team_name, "owner": owner_username})
            team_id = result.scalar()
            conn.execute(text("""
                INSERT INTO team_members (team_id, username, role)
                VALUES (:team_id, :username, 'owner')
            """), {"team_id": team_id, "username": owner_username})
            conn.commit()
            return team_id
    except Exception:
        return None


def add_team_member(team_id: int, username: str, role: str = "member") -> bool:
    """Add a user to a team. Validates user exists."""
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            user_exists = conn.execute(text(
                "SELECT 1 FROM users WHERE username = :u"
            ), {"u": username}).fetchone()
            if not user_exists:
                return False
            conn.execute(text("""
                INSERT INTO team_members (team_id, username, role)
                VALUES (:team_id, :username, :role)
                ON CONFLICT (team_id, username) DO NOTHING
            """), {"team_id": team_id, "username": username, "role": role})
            conn.commit()
        return True
    except Exception:
        return False


def remove_team_member(team_id: int, username: str) -> bool:
    """Remove a user from a team (cannot remove owner). Returns True if removed."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            result = conn.execute(text(
                "DELETE FROM team_members WHERE team_id = :tid AND username = :u AND role != 'owner'"
            ), {"tid": team_id, "u": username})
            conn.commit()
            return result.rowcount > 0
    except Exception:
        return False


def get_team_watchlist_brands(team_id: int) -> list:
    """Get the team owner's brand watchlist (shared with all members)."""
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            owner_row = conn.execute(text(
                "SELECT owner_username FROM teams WHERE id = :tid"
            ), {"tid": team_id}).fetchone()
            if not owner_row:
                return []
            result = conn.execute(text(
                "SELECT brand_name FROM brand_watchlist WHERE username = :u ORDER BY created_at"
            ), {"u": owner_row[0]})
            return [row[0] for row in result.fetchall()]
    except Exception:
        return []


def get_team_watchlist_topics(team_id: int) -> list:
    """Get the team owner's topic watchlist (shared with all members)."""
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            owner_row = conn.execute(text(
                "SELECT owner_username FROM teams WHERE id = :tid"
            ), {"tid": team_id}).fetchone()
            if not owner_row:
                return []
            result = conn.execute(text(
                "SELECT topic_name, is_category FROM topic_watchlist WHERE username = :u ORDER BY created_at"
            ), {"u": owner_row[0]})
            return [(row[0], bool(row[1])) for row in result.fetchall()]
    except Exception:
        return []


def invite_team_member(team_id: int, email: str, name: str, owner_username: str) -> tuple[bool, str]:
    """Invite a new user to a team. Creates user account if needed. Checks capacity."""
    import secrets as _secrets
    import bcrypt as _bcrypt
    import re as _re

    remaining = get_team_capacity(owner_username)
    if remaining <= 0:
        return False, "No remaining team seats. Upgrade your plan for more seats."

    engine = get_db_engine()
    clean_email = email.strip().lower()
    clean_name = name.strip() if name.strip() else clean_email.split("@")[0]
    # Sanitize username: only keep alphanumeric, underscores, hyphens
    new_username = _re.sub(r'[^a-z0-9_-]', '_', clean_name.lower().replace(" ", "_"))[:50]

    try:
        with engine.connect() as conn:
            existing = conn.execute(text(
                "SELECT username FROM users WHERE email = :email"
            ), {"email": clean_email}).fetchone()

            if existing:
                # Check if already a team member
                already_member = conn.execute(text(
                    "SELECT 1 FROM team_members WHERE team_id = :tid AND username = :u"
                ), {"tid": team_id, "u": existing[0]}).fetchone()
                if already_member:
                    return False, f"{existing[0]} is already a member of this team"
                conn.execute(text("""
                    INSERT INTO team_members (team_id, username, role)
                    VALUES (:team_id, :username, 'member')
                    ON CONFLICT (team_id, username) DO NOTHING
                """), {"team_id": team_id, "username": existing[0]})
                conn.commit()
                return True, f"Added existing user {existing[0]} to team"

            temp_password = _secrets.token_urlsafe(12)
            password_hash = _bcrypt.hashpw(temp_password.encode(), _bcrypt.gensalt()).decode()

            base_username = new_username
            suffix = 0
            while True:
                check = conn.execute(text(
                    "SELECT 1 FROM users WHERE username = :u"
                ), {"u": new_username}).fetchone()
                if not check:
                    break
                suffix += 1
                new_username = f"{base_username}_{suffix}"

            owner_tier = conn.execute(text(
                "SELECT tier FROM users WHERE username = :u"
            ), {"u": owner_username}).fetchone()
            tier = owner_tier[0] if owner_tier else "monthly"

            # Create user and add to team in same transaction
            conn.execute(text("""
                INSERT INTO users (username, email, password_hash, tier)
                VALUES (:username, :email, :hash, :tier)
            """), {
                "username": new_username, "email": clean_email,
                "hash": password_hash, "tier": tier,
            })
            conn.execute(text("""
                INSERT INTO team_members (team_id, username, role)
                VALUES (:team_id, :username, 'member')
            """), {"team_id": team_id, "username": new_username})
            conn.commit()

        return True, f"Created user **{new_username}** with temporary password: `{temp_password}` — share this securely with the user"

    except Exception as e:
        return False, f"Failed to invite: {e}"
