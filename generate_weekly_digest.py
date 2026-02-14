#!/usr/bin/env python
"""
generate_weekly_digest.py
Generates a weekly strategic intelligence digest using Claude AI.
Covers: alert patterns, VLDS trends, competitive shifts, forward-looking assessment.
Runs once a week (Monday 7am PST) via GitHub Actions.
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime, timezone, timedelta
from anthropic import Anthropic
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def get_engine():
    """Create a SQLAlchemy engine."""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return None
    try:
        from sqlalchemy import create_engine
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        if "sslmode" not in db_url:
            sep = "&" if "?" in db_url else "?"
            db_url = db_url + sep + "sslmode=require"
        return create_engine(db_url, pool_pre_ping=True)
    except Exception as e:
        print(f"ERROR: Could not create DB engine: {e}")
        return None


def load_weekly_data(engine):
    """Load 7 days of alerts, metric snapshots, and competitive snapshots."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    alerts_df = pd.DataFrame()
    metrics_df = pd.DataFrame()
    competitive_df = pd.DataFrame()

    from sqlalchemy import text as sql_text

    try:
        alerts_df = pd.read_sql(
            sql_text("SELECT * FROM alerts WHERE timestamp >= :cutoff ORDER BY timestamp DESC"),
            engine, params={"cutoff": cutoff},
        )
        print(f"  Loaded {len(alerts_df)} alerts from past 7 days")
    except Exception as e:
        print(f"  Could not load alerts: {e}")

    try:
        metrics_df = pd.read_sql(
            sql_text("SELECT * FROM metric_snapshots WHERE snapshot_date >= :cutoff "
                     "ORDER BY snapshot_date, metric_name"),
            engine, params={"cutoff": cutoff[:10]},
        )
        print(f"  Loaded {len(metrics_df)} metric snapshots")
    except Exception as e:
        print(f"  Could not load metric snapshots: {e}")

    try:
        competitive_df = pd.read_sql(
            sql_text("SELECT * FROM competitive_snapshots WHERE created_at >= :cutoff "
                     "ORDER BY created_at DESC"),
            engine, params={"cutoff": cutoff},
        )
        print(f"  Loaded {len(competitive_df)} competitive snapshots")
    except Exception as e:
        print(f"  Could not load competitive snapshots: {e}")

    return alerts_df, metrics_df, competitive_df


def prepare_weekly_context(alerts_df, metrics_df, competitive_df):
    """Format weekly data as context for Claude."""
    week_start = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%B %d")
    week_end = datetime.now(timezone.utc).strftime("%B %d, %Y")

    context = f"WEEKLY INTELLIGENCE DATA ({week_start} - {week_end})\n"
    context += "=" * 60 + "\n\n"

    # Alert summary
    if not alerts_df.empty:
        context += "ALERTS SUMMARY:\n"
        context += f"Total alerts this week: {len(alerts_df)}\n"

        if "severity" in alerts_df.columns:
            severity_counts = alerts_df["severity"].value_counts()
            context += f"By severity: {severity_counts.to_dict()}\n"

        if "alert_type" in alerts_df.columns:
            type_counts = alerts_df["alert_type"].value_counts().head(10)
            context += f"\nTop alert types:\n{type_counts.to_string()}\n"

        if "brand" in alerts_df.columns:
            brand_alerts = alerts_df[alerts_df["brand"].notna()]
            if not brand_alerts.empty:
                brand_counts = brand_alerts["brand"].value_counts()
                context += f"\nAlerts by brand:\n{brand_counts.to_string()}\n"

        # Include critical alert summaries
        if "severity" in alerts_df.columns and "summary" in alerts_df.columns:
            critical = alerts_df[alerts_df["severity"] == "critical"]
            if not critical.empty:
                context += f"\nCRITICAL ALERTS ({len(critical)}):\n"
                for _, row in critical.head(10).iterrows():
                    title = row.get("title", "Untitled")
                    summary = row.get("summary", "")[:200]
                    context += f"- {title}: {summary}\n"

        # Predictive alerts
        if "alert_type" in alerts_df.columns:
            predictive = alerts_df[alerts_df["alert_type"].str.startswith("predictive_", na=False)]
            if not predictive.empty:
                context += f"\nPREDICTIVE SIGNALS ({len(predictive)}):\n"
                for _, row in predictive.head(5).iterrows():
                    context += f"- {row.get('title', '')}: {row.get('summary', '')[:150]}\n"
    else:
        context += "ALERTS: No alerts recorded this week.\n"

    context += "\n"

    # Metric trends
    if not metrics_df.empty:
        context += "METRIC TRENDS:\n"

        # Global metrics
        global_metrics = metrics_df[metrics_df["scope"] == "global"]
        if not global_metrics.empty:
            context += "\nGlobal Metrics (daily values):\n"
            for metric_name in global_metrics["metric_name"].unique():
                metric_data = global_metrics[global_metrics["metric_name"] == metric_name]
                if len(metric_data) >= 2:
                    first_val = metric_data.iloc[0]["metric_value"]
                    last_val = metric_data.iloc[-1]["metric_value"]
                    change = last_val - first_val
                    direction = "up" if change > 0 else "down" if change < 0 else "flat"
                    context += (
                        f"  {metric_name}: {first_val:.3f} -> {last_val:.3f} "
                        f"({direction}, {change:+.3f})\n"
                    )

        # Brand metrics
        brand_metrics = metrics_df[metrics_df["scope"] == "brand"]
        if not brand_metrics.empty:
            context += "\nBrand VLDS Trends:\n"
            for brand in brand_metrics["scope_name"].unique():
                brand_data = brand_metrics[brand_metrics["scope_name"] == brand]
                context += f"\n  {brand}:\n"
                for metric_name in ["velocity", "longevity", "density", "scarcity"]:
                    m = brand_data[brand_data["metric_name"] == metric_name]
                    if len(m) >= 2:
                        first_val = m.iloc[0]["metric_value"]
                        last_val = m.iloc[-1]["metric_value"]
                        change = last_val - first_val
                        context += f"    {metric_name}: {first_val:.2f} -> {last_val:.2f} ({change:+.2f})\n"
    else:
        context += "METRICS: No metric snapshots available.\n"

    context += "\n"

    # Competitive landscape
    if not competitive_df.empty:
        context += "COMPETITIVE LANDSCAPE:\n"
        for _, row in competitive_df.head(5).iterrows():
            brand = row.get("brand_name", "Unknown")
            snapshot = row.get("snapshot_data", "{}")
            if isinstance(snapshot, str):
                try:
                    snap = json.loads(snapshot)
                except (json.JSONDecodeError, TypeError):
                    snap = {}
            else:
                snap = snapshot

            sov = snap.get("share_of_voice", {})
            if sov:
                context += f"\n  {brand} Share of Voice:\n"
                for name, pct in sorted(sov.items(), key=lambda x: -x[1])[:5]:
                    context += f"    {name}: {pct:.1f}%\n"
    else:
        context += "COMPETITIVE: No competitive snapshots available.\n"

    return context


def generate_weekly_digest(context):
    """Generate weekly strategic digest using Claude AI."""
    week_start = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%B %d")
    week_end = datetime.now(timezone.utc).strftime("%B %d, %Y")

    prompt = f"""You are a senior strategic intelligence analyst preparing a weekly strategic digest
for business leaders.

Based on the following intelligence data from the past week, create a comprehensive strategic review.

IMPORTANT GUIDELINES:
- Focus on PATTERNS and TRENDS, not individual events
- Connect dots between different signals (alerts + metrics + competitive data)
- For each pattern, explain the STRATEGIC IMPLICATION — what it means for decision-making
- Flag patterns as ACCELERATING, STABLE, or DECELERATING
- Include a forward-looking section with anticipated developments for the coming week
- Be direct and actionable — business leaders need clear guidance, not hedging

Format as:

WEEKLY STRATEGIC DIGEST — {week_start} to {week_end}

EXECUTIVE SUMMARY:
[3-4 sentences capturing the week's most important intelligence themes]

TOP PATTERNS:
1. **Pattern Title** [ACCELERATING/STABLE/DECELERATING]
   What: [The pattern observed across multiple signals]
   Why It Matters: [Strategic implication]

VLDS TRENDS:
[Brand health trends — velocity, longevity, density, scarcity movements]
[Highlight any concerning or encouraging trends]

COMPETITIVE SHIFTS:
[Share of voice changes, competitor momentum, new competitive dynamics]
[Who is gaining, who is losing, and why]

FORWARD-LOOKING ASSESSMENT:
[What to watch for next week based on current trajectories]
[Potential inflection points or catalysts]

RECOMMENDED STRATEGIC ACTIONS:
- IMMEDIATE (this week): [...]
- MEDIUM-TERM (this month): [...]
- MONITOR: [...]

Target 800-1000 words. Use clear, direct language.

DATA:
{context}
"""

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2500,
        system=(
            "You are a senior strategic intelligence analyst. You synthesize weekly signals "
            "into actionable strategic insights. You focus on patterns, not noise, and always "
            "explain why something matters for business decision-making."
        ),
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def _get_subscriber_emails():
    """Get all subscriber emails from the users table."""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return []
    try:
        from sqlalchemy import create_engine, text
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT u.email FROM users u
                LEFT JOIN user_preferences p ON u.username = p.username
                WHERE u.email IS NOT NULL AND u.email != ''
                  AND COALESCE(p.digest_weekly, TRUE) = TRUE
            """))
            return [row[0] for row in result.fetchall()]
    except Exception as e:
        print(f"Could not query subscriber emails: {e}")
        return []


def _get_cancelled_emails():
    """Get emails of cancelled subscribers to exclude."""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return set()
    try:
        from sqlalchemy import create_engine, text
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT email FROM users
                WHERE tier NOT IN ('monthly', 'annually', 'professional', 'enterprise')
                  AND username != 'admin'
            """))
            return {row[0].lower() for row in result.fetchall()}
    except Exception:
        return set()


def send_weekly_digest(digest_text):
    """Send weekly digest via email to all active subscribers."""
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    recipients_str = os.getenv("EMAIL_RECIPIENT", "")

    if not all([sender, password]):
        print("Email credentials not configured. Skipping email.")
        return False

    # Build recipient list: DB subscribers + env var, deduplicated
    env_recipients = [r.strip() for r in recipients_str.split(",") if r.strip()]
    db_subscribers = _get_subscriber_emails()
    all_emails = set(e.lower() for e in env_recipients)
    all_emails.update(e.lower() for e in db_subscribers if e)

    if not all_emails:
        print("No recipients found. Skipping email.")
        return False

    # Remove cancelled subscribers
    cancelled = _get_cancelled_emails()
    if cancelled:
        all_emails -= cancelled

    recipients = list(all_emails)
    if not recipients:
        print("All recipients are cancelled. Skipping email.")
        return False

    print(f"Sending weekly digest to {len(recipients)} recipient(s)")

    # Build HTML using generate_brief.py formatting
    try:
        from generate_brief import _build_brief_html
        html = _build_brief_html(digest_text)
        # Replace the header badge text
        html = html.replace("INTELLIGENCE BRIEF", "WEEKLY DIGEST")
        html = html.replace("Daily Intelligence Brief", "Weekly Strategic Digest")
        html = html.replace("Executive Brief", "Weekly Strategic Digest")
    except ImportError:
        # Fallback: basic HTML
        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #1976D2;">Weekly Strategic Digest</h2>
            <pre style="white-space: pre-wrap; font-size: 14px;">{digest_text}</pre>
            <hr>
            <p style="color: #999; font-size: 12px;">
              Moodlight Intelligence Platform — Weekly Digest<br>
              <a href="https://moodlight.up.railway.app" style="color: #1976D2;">View Dashboard</a>
            </p>
          </body>
        </html>
        """

    week_end = datetime.now(timezone.utc).strftime("%B %d, %Y")
    subject = f"[Moodlight Digest] Weekly Strategic Intelligence — {week_end}"

    success_count = 0
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)

            for recipient in recipients:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = sender
                msg["To"] = recipient
                msg.attach(MIMEText(html, "html"))

                try:
                    server.send_message(msg)
                    print(f"  Weekly digest sent to {recipient}")
                    success_count += 1
                except Exception as e:
                    print(f"  Email failed for {recipient}: {e}")

        return success_count > 0
    except Exception as e:
        print(f"  Email connection failed: {e}")
        return False


def main():
    print("=" * 60)
    print("GENERATING WEEKLY STRATEGIC DIGEST")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    engine = get_engine()
    if not engine:
        print("ERROR: DATABASE_URL not set or invalid")
        sys.exit(0)

    print("\nLoading weekly data...")
    alerts_df, metrics_df, competitive_df = load_weekly_data(engine)

    if alerts_df.empty and metrics_df.empty:
        print("No data available for weekly digest.")
        sys.exit(0)

    context = prepare_weekly_context(alerts_df, metrics_df, competitive_df)

    print("\nGenerating digest with Claude...")
    digest = generate_weekly_digest(context)

    print("\n" + digest)
    print()

    # Save to file
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"weekly_digest_{timestamp}.txt"
    with open(filename, "w") as f:
        f.write(digest)
    print(f"Digest saved to: {filename}")

    # Send email
    send_weekly_digest(digest)

    print("\n" + "=" * 60)
    print("WEEKLY DIGEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
