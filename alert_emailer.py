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
                SELECT username, email FROM users
                WHERE email IS NOT NULL AND email != ''
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
                WHERE stripe_subscription_id IS NULL
                  AND tier != 'enterprise'
                  AND username != 'admin'
            """))
            return {row[0].lower() for row in result.fetchall()}
    except Exception:
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
    except Exception:
        return False


def send_alert_emails(alerts, engine=None):
    """Send email alerts to appropriate subscribers.

    Global alerts (brand=None) → all active subscribers
    Brand alerts (brand set) → only the subscriber who watches that brand
    Only sends for critical and warning severity.
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

    # Build global recipient list: DB subscribers + env var fallback, deduplicated
    env_recipients = [r.strip() for r in recipients_str.split(",") if r.strip()]
    all_emails = set(e.lower() for e in env_recipients)
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

    # Filter to only critical/warning alerts, prioritize critical first
    emailable = [a for a in alerts if a.get("severity") in ("critical", "warning")]
    emailable.sort(key=lambda a: 0 if a.get("severity") == "critical" else 1)
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

                for recipient in targets:
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
    """Build HTML email body for an alert."""
    severity_colors = {
        "critical": "#DC143C",
        "warning": "#FFB300",
        "info": "#1976D2",
    }
    color = severity_colors.get(alert.get("severity", "info"), "#1976D2")
    severity = alert.get("severity", "info").upper()

    investigation = alert.get("investigation", "")
    investigation_html = ""
    if investigation:
        if isinstance(investigation, str):
            try:
                inv = json.loads(investigation)
            except (json.JSONDecodeError, TypeError):
                inv = {"analysis": investigation}
        else:
            inv = investigation

        # Check for reasoning chain steps
        if inv.get("steps"):
            chain_parts = []
            oc = inv.get("overall_confidence", "?")
            rec = inv.get("recommendation", "monitor")
            rec_labels = {"act_now": "Act Now", "monitor": "Monitor", "investigate_further": "Investigate Further"}
            chain_parts.append(
                f'<p style="margin: 0 0 10px 0;"><strong>Confidence:</strong> {oc}/100 '
                f'| <strong>Recommendation:</strong> {rec_labels.get(rec, rec)}</p>'
            )
            for step_data in inv["steps"]:
                step_title = step_data.get("title", step_data.get("step", ""))
                step_content = step_data.get("content", "")
                step_conf = step_data.get("confidence", 0)
                conf_pct = f"{step_conf:.0%}" if isinstance(step_conf, float) and step_conf <= 1 else str(step_conf)
                chain_parts.append(
                    f'<div style="margin: 8px 0; padding: 8px 12px; '
                    f'border-left: 3px solid #1976D2; background: #fafafa;">'
                    f'<strong>{step_title}</strong> '
                    f'<span style="color: #999; font-size: 11px;">({conf_pct})</span>'
                    f'<p style="margin: 4px 0 0 0; font-size: 13px;">{step_content[:500]}</p>'
                    f'</div>'
                )
            investigation_html = (
                '<div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 15px 0;">'
                + "".join(chain_parts)
                + "</div>"
            )
        else:
            # Legacy single-turn format
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
          Moodlight Intelligence Platform — Autonomous Alert System<br>
          <a href="https://moodlight.up.railway.app" style="color: #1976D2;">View Dashboard</a>
        </p>
      </body>
    </html>
    """
