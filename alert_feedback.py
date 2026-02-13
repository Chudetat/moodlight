#!/usr/bin/env python
"""
Alert engagement tracking and feedback for Moodlight.
Records user interactions (expand, thumbs up/down) and computes engagement scores.
"""

from datetime import datetime, timezone, timedelta


def ensure_feedback_table(engine):
    """Create the alert_feedback table if it doesn't exist."""
    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS alert_feedback (
                id SERIAL PRIMARY KEY,
                alert_id INTEGER,
                username VARCHAR(100) NOT NULL,
                action VARCHAR(20) NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(alert_id, username, action)
            )
        """))
        conn.commit()


def record_feedback(engine, alert_id, username, action):
    """Record a user interaction with an alert.
    action: 'expanded', 'thumbs_up', or 'thumbs_down'
    Uses ON CONFLICT DO NOTHING to avoid duplicates.
    """
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO alert_feedback (alert_id, username, action)
                    VALUES (:alert_id, :username, :action)
                    ON CONFLICT (alert_id, username, action) DO NOTHING
                """),
                {"alert_id": alert_id, "username": username, "action": action},
            )
            conn.commit()
    except Exception as e:
        print(f"  Feedback recording failed: {e}")


def get_feedback_summary(engine, days=30) -> dict:
    """Aggregate feedback data per alert_type for threshold tuning.

    Returns: {
        alert_type: {
            total_alerts: N,
            expanded_count: N,
            thumbs_up: N,
            thumbs_down: N,
            engagement_rate: float,
            approval_rate: float,
        }
    }
    """
    from sqlalchemy import text

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    try:
        with engine.connect() as conn:
            # Get total alerts per type in the period
            totals = conn.execute(
                text("""
                    SELECT alert_type, COUNT(*) as cnt
                    FROM alerts
                    WHERE timestamp > :cutoff
                    GROUP BY alert_type
                """),
                {"cutoff": cutoff},
            )
            type_totals = {row[0]: row[1] for row in totals.fetchall()}

            # Get feedback counts per alert_type and action
            feedback = conn.execute(
                text("""
                    SELECT a.alert_type, f.action, COUNT(*) as cnt
                    FROM alert_feedback f
                    JOIN alerts a ON a.id = f.alert_id
                    WHERE f.created_at > :cutoff
                    GROUP BY a.alert_type, f.action
                """),
                {"cutoff": cutoff},
            )

            # Build summary
            summary = {}
            for row in feedback.fetchall():
                alert_type, action, count = row
                if alert_type not in summary:
                    summary[alert_type] = {
                        "total_alerts": type_totals.get(alert_type, 0),
                        "expanded_count": 0,
                        "thumbs_up": 0,
                        "thumbs_down": 0,
                    }
                if action == "expanded":
                    summary[alert_type]["expanded_count"] = count
                elif action == "thumbs_up":
                    summary[alert_type]["thumbs_up"] = count
                elif action == "thumbs_down":
                    summary[alert_type]["thumbs_down"] = count

            # Calculate rates
            for alert_type, stats in summary.items():
                total = stats["total_alerts"]
                stats["engagement_rate"] = (
                    stats["expanded_count"] / total if total > 0 else 0
                )
                voted = stats["thumbs_up"] + stats["thumbs_down"]
                stats["approval_rate"] = (
                    stats["thumbs_up"] / voted if voted > 0 else 0.5
                )

            return summary

    except Exception as e:
        print(f"  Could not load feedback summary: {e}")
        return {}


def compute_engagement_score(engine, alert_id) -> float:
    """Compute engagement score for a single alert (0-1 scale).
    - Expanded: +0.3
    - Thumbs up: +0.5
    - Thumbs down: -0.3
    - No interaction: 0.0
    Normalized to [0, 1].
    """
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT action FROM alert_feedback WHERE alert_id = :id"),
                {"id": alert_id},
            )
            actions = {row[0] for row in result.fetchall()}

        raw_score = 0.0
        if "expanded" in actions:
            raw_score += 0.3
        if "thumbs_up" in actions:
            raw_score += 0.5
        if "thumbs_down" in actions:
            raw_score -= 0.3

        # Normalize from [-0.3, 0.8] to [0, 1]
        return max(0.0, min(1.0, (raw_score + 0.3) / 1.1))

    except Exception:
        return 0.5  # neutral default
