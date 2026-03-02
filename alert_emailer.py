#!/usr/bin/env python
"""
Email alert delivery for Moodlight.
Sends proactive alerts to subscribers via Gmail SMTP.
Reuses patterns from generate_brief.py.
"""

import os
import json
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

MAX_EMAILS_PER_DAY = 5


def get_subscriber_emails():
    """Get all active subscriber emails from the users table.
    Returns dict of {username: email} for active subscribers."""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return {}
    try:
        from sqlalchemy import create_engine, text
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        if "sslmode" not in db_url:
            sep = "&" if "?" in db_url else "?"
            db_url = db_url + sep + "sslmode=require"
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT u.username, u.email FROM users u
                LEFT JOIN user_preferences p ON u.username = p.username
                WHERE u.email IS NOT NULL AND u.email != ''
                  AND COALESCE(p.alert_emails, TRUE) = TRUE
            """))
            return {row[0]: row[1] for row in result.fetchall()}
    except Exception as e:
        print(f"  Could not query subscribers: {e}")
        return {}


def get_cancelled_emails():
    """Get emails of cancelled subscribers to exclude."""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return set()
    try:
        from sqlalchemy import create_engine, text
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        if "sslmode" not in db_url:
            sep = "&" if "?" in db_url else "?"
            db_url = db_url + sep + "sslmode=require"
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT email FROM users
                WHERE tier NOT IN ('monthly', 'annually', 'professional', 'enterprise')
                  AND username != 'admin'
            """))
            return {row[0].lower() for row in result.fetchall()}
    except Exception as e:
        print(f"WARNING: get_cancelled_emails failed: {e}")
        return set()


def check_email_rate_limit(engine, email, cutoff_hours=24):
    """Check if a subscriber has hit the email rate limit."""
    try:
        from sqlalchemy import text
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=cutoff_hours)).isoformat()
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM alerts WHERE emailed = true AND timestamp > :cutoff"),
                {"cutoff": cutoff},
            )
            count = result.scalar()
            return count >= MAX_EMAILS_PER_DAY
    except Exception as e:
        print(f"WARNING: check_email_rate_limit failed: {e}")
        return False


def _get_user_disabled_alert_types():
    """Get alert types each user has disabled. Returns {username: set(alert_type)}."""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return {}
    try:
        from sqlalchemy import create_engine, text
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        if "sslmode" not in db_url:
            sep = "&" if "?" in db_url else "?"
            db_url = db_url + sep + "sslmode=require"
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT username, alert_type FROM user_alert_preferences WHERE enabled = FALSE"
            ))
            disabled = {}
            for row in result.fetchall():
                disabled.setdefault(row[0], set()).add(row[1])
            return disabled
    except Exception as e:
        print(f"WARNING: _get_user_disabled_alert_types failed: {e}")
        return {}


def _get_alert_opted_out_emails():
    """Get emails of users who have explicitly set alert_emails=FALSE.
    Used to filter env var recipients who would otherwise bypass preference checks."""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return set()
    try:
        from sqlalchemy import create_engine, text
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        if "sslmode" not in db_url:
            sep = "&" if "?" in db_url else "?"
            db_url = db_url + sep + "sslmode=require"
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT u.email FROM users u
                JOIN user_preferences p ON u.username = p.username
                WHERE p.alert_emails = FALSE
                  AND u.email IS NOT NULL AND u.email != ''
            """))
            return {row[0].lower() for row in result.fetchall()}
    except Exception as e:
        print(f"WARNING: _get_alert_opted_out_emails failed: {e}")
        return set()


def _get_recommendation(alert):
    """Extract reasoning chain recommendation from an alert's investigation field.
    Returns 'act_now', 'monitor', 'investigate_further', 'likely_false_positive', or None."""
    investigation = alert.get("investigation", "")
    if not investigation:
        return None
    if isinstance(investigation, str):
        try:
            inv = json.loads(investigation)
        except (json.JSONDecodeError, TypeError):
            return None
    else:
        inv = investigation
    return inv.get("recommendation")


def _get_confidence(alert):
    """Extract overall confidence from alert's investigation field."""
    investigation = alert.get("investigation", "")
    if not investigation:
        return None
    if isinstance(investigation, str):
        try:
            inv = json.loads(investigation)
        except (json.JSONDecodeError, TypeError):
            return None
    else:
        inv = investigation
    return inv.get("overall_confidence")


def send_alert_emails(alerts, engine=None):
    """Send email alerts to appropriate subscribers.

    Global alerts (brand=None) → all active subscribers
    Brand alerts (brand set) → only the subscriber who watches that brand
    Only sends for critical and warning severity.
    Respects user alert type preferences.
    """
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    recipients_str = os.getenv("EMAIL_RECIPIENT", "")

    if not all([sender, password]):
        print("  Email credentials not configured — skipping email alerts")
        return 0

    # Get subscriber mapping from DB (for both global and brand routing)
    subscriber_map = get_subscriber_emails()  # {username: email}
    cancelled = get_cancelled_emails()

    # Build global recipient list: DB subscribers + env var recipients, deduplicated.
    # Env var recipients are checked against the users table — if they have a matching
    # account with alert_emails=FALSE, they are excluded (same as DB subscribers).
    env_recipients = [r.strip() for r in recipients_str.split(",") if r.strip()]
    opted_out_emails = _get_alert_opted_out_emails()
    env_filtered = [e for e in env_recipients if e.lower() not in opted_out_emails]
    if len(env_filtered) < len(env_recipients):
        print(f"  Filtered {len(env_recipients) - len(env_filtered)} env recipient(s) who opted out of alert emails")
    all_emails = set(e.lower() for e in env_filtered)
    all_emails.update(e.lower() for e in subscriber_map.values() if e)
    if not all_emails:
        print("  No recipients found (DB or env var) — skipping email alerts")
        return 0

    # Filter out cancelled
    active_recipients = [e for e in all_emails if e not in cancelled]
    if not active_recipients:
        print("  All recipients are cancelled — skipping email alerts")
        return 0
    print(f"  Active recipients: {len(active_recipients)} ({len(subscriber_map)} from DB, {len(env_recipients)} from env)")

    # Load user alert preferences (disabled alert types)
    disabled_types = _get_user_disabled_alert_types()
    # Reverse subscriber map: email → username for preference lookup
    email_to_user = {email.lower(): uname for uname, email in subscriber_map.items()}

    # Filter to only critical/warning alerts, prioritize critical first
    emailable = [a for a in alerts if a.get("severity") in ("critical", "warning")]
    emailable.sort(key=lambda a: 0 if a.get("severity") == "critical" else 1)

    # Gate on reasoning chain recommendation + confidence floor.
    # Only email act_now with confidence >= 65. Single-turn alerts
    # (no recommendation) pass through unchanged.
    _EMAIL_RECOMMENDATIONS = {"act_now"}
    _MIN_EMAIL_CONFIDENCE = 65
    pre_gate = len(emailable)
    emailable = [
        a for a in emailable
        if _get_recommendation(a) is None  # single-turn, pass through
        or (
            _get_recommendation(a) in _EMAIL_RECOMMENDATIONS
            and (_get_confidence(a) or 0) >= _MIN_EMAIL_CONFIDENCE
        )
    ]
    gated = pre_gate - len(emailable)
    if gated:
        print(f"  Suppressed {gated} alert email(s) (recommendation/confidence gate)")
    if not emailable:
        print("  No critical/warning alerts to email")
        return 0

    # Rate limit check
    if engine and check_email_rate_limit(engine, "global"):
        print(f"  Rate limit reached ({MAX_EMAILS_PER_DAY}/day) — skipping emails")
        return 0

    sent_count = 0
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)

            for alert in emailable:
                # Determine recipients for this alert
                if alert.get("brand") and alert.get("username"):
                    # Brand-specific: send to that subscriber only
                    target_email = subscriber_map.get(alert["username"])
                    if not target_email or target_email.lower() in cancelled:
                        continue
                    targets = [target_email]
                else:
                    # Global: send to all active
                    targets = active_recipients

                html = _build_email_html(alert)
                subject = _build_subject(alert)

                alert_type = alert.get("alert_type", "")
                for recipient in targets:
                    # Check if this user has disabled this alert type
                    _rcpt_user = email_to_user.get(recipient.lower())
                    if _rcpt_user and alert_type and alert_type in disabled_types.get(_rcpt_user, set()):
                        continue
                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = subject
                    msg["From"] = sender
                    msg["To"] = recipient
                    msg.attach(MIMEText(html, "html"))

                    try:
                        server.send_message(msg)
                        print(f"  Email sent to {recipient}: {alert['title']}")
                        sent_count += 1
                    except Exception as e:
                        print(f"  Email failed for {recipient}: {e}")

    except Exception as e:
        print(f"  Email connection failed: {e}")

    return sent_count


def _build_subject(alert):
    """Build email subject line with severity emoji."""
    severity_emoji = {
        "critical": "🔴",
        "warning": "🟡",
        "info": "🔵",
    }
    emoji = severity_emoji.get(alert.get("severity", "info"), "🔵")
    brand = f" [{alert['brand']}]" if alert.get("brand") else ""
    return f"[Moodlight Alert] {emoji}{brand} {alert.get('title', 'Alert')}"


def _build_email_html(alert):
    """Build HTML email body for an alert.

    Multi-step chain alerts get an executive briefing format (BOTTOM LINE,
    WHY THIS MATTERS, KEY EVIDENCE). Single-turn alerts get structured
    sections. Both use the unified design from email_templates.
    """
    import re as _re
    from email_templates import (
        SEVERITY_COLORS, render_email, render_section,
        render_confidence_bar, markdown_to_html, parse_and_render_sections,
    )

    color = SEVERITY_COLORS.get(alert.get("severity", "info"), "#1976D2")
    severity = alert.get("severity", "info").upper()

    investigation = alert.get("investigation", "")
    inv = None
    if investigation:
        if isinstance(investigation, str):
            try:
                inv = json.loads(investigation)
            except (json.JSONDecodeError, TypeError):
                inv = {"analysis": investigation}
        else:
            inv = investigation

    # --- Multi-step chain: executive briefing format ---
    if inv and inv.get("steps"):
        return _build_chain_email_html(alert, inv, color, severity)

    # --- Single-turn / situation report format ---
    brand_badge_html = ""
    if alert.get("brand"):
        brand_badge_html = (
            f'<span style="background: #E3F2FD; color: #1565C0; padding: 2px 8px; '
            f'border-radius: 4px; font-size: 12px; margin-left: 8px;">'
            f'{alert["brand"]}</span>'
        )

    body_parts = []

    # Summary
    summary = alert.get("summary", "")
    if summary:
        body_parts.append(
            f'<p style="font-size: 15px; color: #333; line-height: 1.6;">{summary}</p>'
        )

    # Investigation sections
    if inv:
        analysis = inv.get("analysis", "")

        # Situation reports with ALL-CAPS sections → parse into colored sections
        if (isinstance(analysis, str)
                and _re.search(r'^[A-Z][A-Z &\-/]+:?\s*$', analysis, _re.MULTILINE)):
            body_parts.append(parse_and_render_sections(analysis))
        else:
            # Single-turn alert with separate fields
            if analysis:
                body_parts.append(
                    render_section("ANALYSIS", markdown_to_html(str(analysis)), "#1976D2")
                )
            if inv.get("implications"):
                body_parts.append(
                    render_section("IMPLICATIONS", markdown_to_html(str(inv["implications"])), "#FFB300")
                )
            if inv.get("watch_items"):
                body_parts.append(
                    render_section("WATCH ITEMS", markdown_to_html(str(inv["watch_items"])), "#2E7D32")
                )

        # Confidence bar for alerts with confidence/recommendation
        if inv.get("overall_confidence") is not None and inv.get("recommendation"):
            body_parts.append(
                render_confidence_bar(inv["overall_confidence"], inv["recommendation"])
            )

    body_html = "\n".join(body_parts)

    return render_email(
        badge_text=severity,
        badge_color=color,
        title=alert.get("title", "Alert"),
        body_html=body_html,
        extra_badges_html=brand_badge_html,
    )


def _build_chain_email_html(alert, inv, color, severity):
    """Build executive briefing HTML for multi-step reasoning chain alerts."""
    from email_templates import (
        render_email, render_section, render_confidence_bar, markdown_to_html,
    )

    oc = inv.get("overall_confidence", 0)
    rec = inv.get("recommendation", "monitor")

    # Extract structured data from chain steps (logic unchanged)
    why_items = []
    evidence_items = []
    for step in inv.get("steps", []):
        step_name = step.get("step", "")
        if step_name == "strategic" and step.get("recommended_actions"):
            why_items = [a for a in step["recommended_actions"][:3]]
        if step_name == "causal" and step.get("likely_causes"):
            evidence_items = [c for c in step["likely_causes"][:2]]

    # Fallback: extract from causal step content if no structured likely_causes
    if not evidence_items:
        for step in inv.get("steps", []):
            if step.get("step") == "causal" and step.get("content"):
                sentences = [s.strip() for s in step["content"].split(".") if len(s.strip()) > 20]
                evidence_items = sentences[:2]
                break

    # Fallback: extract from strategic step content if no structured recommended_actions
    if not why_items:
        for step in inv.get("steps", []):
            if step.get("step") == "strategic" and step.get("content"):
                sentences = [s.strip() for s in step["content"].split(".") if len(s.strip()) > 20]
                why_items = sentences[:2]
                break

    # Build brand badge
    brand_badge_html = ""
    if alert.get("brand"):
        brand_badge_html = (
            f'<span style="background: #E3F2FD; color: #1565C0; padding: 2px 8px; '
            f'border-radius: 4px; font-size: 12px; margin-left: 8px;">'
            f'{alert["brand"]}</span>'
        )

    # Bottom line: summary + first recommended action for act_now
    bottom_line = alert.get("summary", "")
    if rec == "act_now" and why_items:
        bottom_line += f" {why_items[0]}"

    # Build body sections
    body_parts = []
    body_parts.append(render_section("BOTTOM LINE", markdown_to_html(bottom_line), color))
    body_parts.append(render_confidence_bar(oc, rec))

    if why_items:
        bullets_html = "".join(
            f'<div style="margin: 4px 0; padding-left: 12px;">'
            f'<span style="color: #999;">&#8226;</span> {item}</div>'
            for item in why_items
        )
        body_parts.append(render_section("WHY THIS MATTERS", bullets_html, "#FFB300"))

    if evidence_items:
        bullets_html = "".join(
            f'<div style="margin: 4px 0; padding-left: 12px;">'
            f'<span style="color: #999;">&#8226;</span> {item}</div>'
            for item in evidence_items
        )
        body_parts.append(render_section("KEY EVIDENCE", bullets_html, "#1976D2"))

    body_html = "\n".join(body_parts)

    return render_email(
        badge_text=severity,
        badge_color=color,
        title=alert.get("title", "Alert"),
        body_html=body_html,
        extra_badges_html=brand_badge_html,
    )
