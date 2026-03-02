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

    # Gate on reasoning chain recommendation: only email act_now.
    # monitor, investigate_further, and likely_false_positive are dashboard-only.
    # Alerts without a recommendation (single-turn investigation or no investigation)
    # pass through — they're already filtered by severity above.
    # Situation reports (alert_type=situation_report) are always passed through.
    _EMAIL_RECOMMENDATIONS = {"act_now"}
    pre_gate = len(emailable)
    emailable = [
        a for a in emailable
        if a.get("alert_type") == "situation_report"
        or _get_recommendation(a) is None
        or _get_recommendation(a) in _EMAIL_RECOMMENDATIONS
    ]
    gated = pre_gate - len(emailable)
    if gated:
        print(f"  Suppressed {gated} alert email(s) (low-confidence recommendation)")
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
    WHY THIS MATTERS, KEY EVIDENCE). Single-turn alerts keep the legacy
    compact format.
    """
    severity_colors = {
        "critical": "#DC143C",
        "warning": "#FFB300",
        "info": "#1976D2",
    }
    color = severity_colors.get(alert.get("severity", "info"), "#1976D2")
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

    # --- Single-turn / legacy format (already concise) ---
    investigation_html = ""
    if inv:
        sections = []
        if inv.get("analysis"):
            sections.append(f"<p><strong>Analysis:</strong> {inv['analysis']}</p>")
        if inv.get("implications"):
            sections.append(f"<p><strong>Implications:</strong> {inv['implications']}</p>")
        if inv.get("watch_items"):
            sections.append(f"<p><strong>Watch:</strong><br>{inv['watch_items']}</p>")
        if sections:
            investigation_html = (
                '<div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 15px 0;">'
                + "".join(sections)
                + "</div>"
            )

    brand_badge = ""
    if alert.get("brand"):
        brand_badge = (
            f'<span style="background: #E3F2FD; color: #1565C0; padding: 2px 8px; '
            f'border-radius: 4px; font-size: 12px; margin-left: 8px;">'
            f'{alert["brand"]}</span>'
        )

    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
        <div style="border-left: 4px solid {color}; padding-left: 15px; margin-bottom: 20px;">
          <span style="background: {color}; color: white; padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: bold;">
            {severity}
          </span>
          {brand_badge}
          <h2 style="margin: 10px 0 5px 0; color: #333;">{alert.get('title', 'Alert')}</h2>
          <p style="color: #666; margin: 0;">
            {datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")}
          </p>
        </div>
        <p style="font-size: 15px; color: #333; line-height: 1.6;">
          {alert.get('summary', '')}
        </p>
        {investigation_html}
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">
          Moodlight Intelligence Platform<br>
          <a href="https://moodlight.up.railway.app" style="color: #1976D2;">View Dashboard</a>
        </p>
      </body>
    </html>
    """


def _build_chain_email_html(alert, inv, color, severity):
    """Build executive briefing HTML for multi-step reasoning chain alerts."""
    oc = inv.get("overall_confidence", 0)
    rec = inv.get("recommendation", "monitor")
    rec_labels = {"act_now": "Act Now", "monitor": "Monitor", "investigate_further": "Investigate"}

    # Confidence bar color
    if oc >= 75:
        conf_color = "#2E7D32"
    elif oc >= 40:
        conf_color = "#F9A825"
    else:
        conf_color = "#C62828"

    # Extract structured data from chain steps
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

    brand_label = alert.get("brand", "")
    brand_line = f'<span style="color: #555; font-size: 14px; font-weight: 600;">{brand_label}</span><br>' if brand_label else ""

    # Bottom line: summary + first recommended action for act_now
    bottom_line = alert.get("summary", "")
    if rec == "act_now" and why_items:
        bottom_line += f" {why_items[0]}"

    # Build bullet lists
    why_html = ""
    if why_items:
        bullets = "".join(
            f'<li style="margin: 4px 0; color: #333; font-size: 14px; line-height: 1.5;">{item}</li>'
            for item in why_items
        )
        why_html = f"""
        <div style="margin: 0 0 20px 0;">
          <p style="margin: 0 0 8px 0; font-size: 11px; font-weight: 700; color: #888; letter-spacing: 1px;">WHY THIS MATTERS</p>
          <ul style="margin: 0; padding-left: 18px;">{bullets}</ul>
        </div>"""

    evidence_html = ""
    if evidence_items:
        bullets = "".join(
            f'<li style="margin: 4px 0; color: #333; font-size: 14px; line-height: 1.5;">{item}</li>'
            for item in evidence_items
        )
        evidence_html = f"""
        <div style="margin: 0 0 20px 0;">
          <p style="margin: 0 0 8px 0; font-size: 11px; font-weight: 700; color: #888; letter-spacing: 1px;">KEY EVIDENCE</p>
          <ul style="margin: 0; padding-left: 18px;">{bullets}</ul>
        </div>"""

    # Confidence bar (visual)
    filled = max(1, int(oc / 100 * 16))
    bar = "█" * filled + "░" * (16 - filled)

    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
        <!-- Header -->
        <div style="border-bottom: 2px solid {color}; padding-bottom: 12px; margin-bottom: 20px;">
          <span style="background: {color}; color: white; padding: 3px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;">
            {severity}
          </span>
          <h2 style="margin: 10px 0 4px 0; color: #222; font-size: 20px;">{alert.get('title', 'Alert')}</h2>
          {brand_line}
          <span style="color: #999; font-size: 12px;">{datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")}</span>
        </div>

        <!-- Bottom Line -->
        <div style="background: #f8f9fa; border-left: 4px solid {color}; padding: 14px 16px; margin: 0 0 16px 0; border-radius: 0 6px 6px 0;">
          <p style="margin: 0 0 6px 0; font-size: 11px; font-weight: 700; color: #888; letter-spacing: 1px;">BOTTOM LINE</p>
          <p style="margin: 0; font-size: 15px; line-height: 1.5; color: #222;">{bottom_line}</p>
        </div>

        <!-- Confidence -->
        <div style="margin: 0 0 20px 0; padding: 0 2px;">
          <span style="font-size: 13px; color: #555;">Confidence: <strong style="color: {conf_color};">{oc}/100</strong></span>
          <span style="margin-left: 12px; font-size: 13px; color: #555;">| {rec_labels.get(rec, rec)}</span>
          <br>
          <span style="font-family: monospace; font-size: 12px; color: {conf_color}; letter-spacing: 1px;">{bar}</span>
        </div>

        {why_html}
        {evidence_html}

        <!-- Footer -->
        <div style="border-top: 1px solid #eee; padding-top: 16px; margin-top: 8px; text-align: center;">
          <a href="https://moodlight.up.railway.app" style="display: inline-block; background: #1976D2; color: white; padding: 10px 24px; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: 600;">View Full Analysis</a>
          <p style="color: #aaa; font-size: 11px; margin-top: 12px;">Moodlight Intelligence Platform</p>
        </div>
      </body>
    </html>
    """
