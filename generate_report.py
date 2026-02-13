#!/usr/bin/env python
"""
generate_report.py
On-demand intelligence report generation for any brand or topic.
Called from the dashboard sidebar or Ask Moodlight chat.
"""

import os
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


def _get_engine():
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


def prepare_report_context(engine, subject, days=7, subject_type="brand"):
    """Load and format all relevant data for the report.

    Args:
        engine: SQLAlchemy engine
        subject: Brand name or topic string
        days: Number of days to look back
        subject_type: "brand" or "topic"

    Returns:
        Formatted context string for Claude
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%B %d")

    context = f"INTELLIGENCE REPORT DATA: {subject} ({start_date} - {end_date})\n"
    context += "=" * 60 + "\n\n"

    subject_lower = subject.lower()

    # --- News & Social Signal Data ---
    news_df = pd.DataFrame()
    social_df = pd.DataFrame()

    from sqlalchemy import text as sql_text

    try:
        if subject_type == "brand":
            news_df = pd.read_sql(
                sql_text("SELECT * FROM news_scored WHERE created_at >= :cutoff "
                         "AND LOWER(text) LIKE :pattern"),
                engine, params={"cutoff": cutoff_date, "pattern": f"%{subject_lower}%"},
            )
        else:
            news_df = pd.read_sql(
                sql_text("SELECT * FROM news_scored WHERE created_at >= :cutoff "
                         "AND LOWER(topic) LIKE :pattern"),
                engine, params={"cutoff": cutoff_date, "pattern": f"%{subject_lower}%"},
            )
    except Exception as e:
        print(f"  Could not load news data: {e}")

    try:
        if subject_type == "brand":
            social_df = pd.read_sql(
                sql_text("SELECT * FROM social_scored WHERE created_at >= :cutoff "
                         "AND LOWER(text) LIKE :pattern"),
                engine, params={"cutoff": cutoff_date, "pattern": f"%{subject_lower}%"},
            )
        else:
            social_df = pd.read_sql(
                sql_text("SELECT * FROM social_scored WHERE created_at >= :cutoff "
                         "AND LOWER(topic) LIKE :pattern"),
                engine, params={"cutoff": cutoff_date, "pattern": f"%{subject_lower}%"},
            )
    except Exception as e:
        print(f"  Could not load social data: {e}")

    context += "SIGNAL DATA:\n"
    context += f"  News articles mentioning '{subject}': {len(news_df)}\n"
    context += f"  Social posts mentioning '{subject}': {len(social_df)}\n"

    combined = pd.concat([news_df, social_df], ignore_index=True)
    if not combined.empty:
        if "empathy_score" in combined.columns:
            avg_empathy = combined["empathy_score"].mean()
            context += f"  Average empathy score: {avg_empathy:.3f}\n"

        if "intensity" in combined.columns:
            avg_intensity = combined["intensity"].mean()
            context += f"  Average intensity: {avg_intensity:.1f}/5\n"

        if "emotion_top_1" in combined.columns:
            top_emotions = combined["emotion_top_1"].value_counts().head(5)
            context += f"\n  Top emotions: {top_emotions.to_dict()}\n"

        if "topic" in combined.columns:
            top_topics = combined["topic"].value_counts().head(5)
            context += f"  Top topics: {top_topics.to_dict()}\n"

        # Sample recent headlines
        if "text" in combined.columns:
            context += "\n  Recent headlines:\n"
            if "created_at" in combined.columns:
                combined["created_at"] = pd.to_datetime(
                    combined["created_at"], utc=True, errors="coerce"
                )
                recent = combined.sort_values("created_at", ascending=False)
            else:
                recent = combined
            for _, row in recent.head(10).iterrows():
                text = str(row.get("text", ""))[:120]
                context += f"  - {text}\n"

        # VLDS computation
        try:
            from vlds_helper import calculate_brand_vlds
            if "created_at" in combined.columns:
                combined["created_at"] = pd.to_datetime(
                    combined["created_at"], utc=True, errors="coerce"
                )
            vlds = calculate_brand_vlds(combined)
            if vlds:
                context += "\n  VLDS SCORES:\n"
                for key in ["velocity", "longevity", "density", "scarcity"]:
                    if key in vlds:
                        label = vlds.get(f"{key}_label", "")
                        context += f"    {key.capitalize()}: {vlds[key]} ({label})\n"
                if "empathy_score" in vlds:
                    context += f"    Empathy: {vlds['empathy_score']} ({vlds.get('empathy_label', '')})\n"
        except Exception as e:
            print(f"  VLDS computation failed: {e}")

    context += "\n"

    # --- Alert History ---
    try:
        if subject_type == "brand":
            alerts_df = pd.read_sql(
                sql_text("SELECT alert_type, severity, title, summary, timestamp "
                         "FROM alerts WHERE timestamp >= :cutoff "
                         "AND (LOWER(brand) = :subject OR LOWER(title) LIKE :pattern) "
                         "ORDER BY timestamp DESC LIMIT 15"),
                engine, params={"cutoff": cutoff, "subject": subject_lower,
                                "pattern": f"%{subject_lower}%"},
            )
        else:
            alerts_df = pd.read_sql(
                sql_text("SELECT alert_type, severity, title, summary, timestamp "
                         "FROM alerts WHERE timestamp >= :cutoff "
                         "AND LOWER(title) LIKE :pattern "
                         "ORDER BY timestamp DESC LIMIT 15"),
                engine, params={"cutoff": cutoff, "pattern": f"%{subject_lower}%"},
            )

        if not alerts_df.empty:
            context += f"ALERT HISTORY ({len(alerts_df)} alerts):\n"
            if "severity" in alerts_df.columns:
                sev_counts = alerts_df["severity"].value_counts().to_dict()
                context += f"  By severity: {sev_counts}\n"
            if "alert_type" in alerts_df.columns:
                type_counts = alerts_df["alert_type"].value_counts().to_dict()
                context += f"  By type: {type_counts}\n"
            context += "\n  Recent alerts:\n"
            for _, row in alerts_df.head(10).iterrows():
                title = row.get("title", "Untitled")
                severity = row.get("severity", "info")
                summary = str(row.get("summary", ""))[:150]
                context += f"  - [{severity.upper()}] {title}: {summary}\n"
        else:
            context += "ALERT HISTORY: No alerts recorded for this subject.\n"
    except Exception as e:
        print(f"  Could not load alerts: {e}")
        context += "ALERT HISTORY: Could not load alert data.\n"

    context += "\n"

    # --- Metric Trends ---
    try:
        if subject_type == "brand":
            metrics_df = pd.read_sql(
                sql_text("SELECT * FROM metric_snapshots "
                         "WHERE snapshot_date >= :cutoff "
                         "AND scope = 'brand' AND LOWER(scope_name) = :subject "
                         "ORDER BY snapshot_date"),
                engine, params={"cutoff": cutoff_date, "subject": subject_lower},
            )
        else:
            metrics_df = pd.read_sql(
                sql_text("SELECT * FROM metric_snapshots "
                         "WHERE snapshot_date >= :cutoff AND scope = 'global' "
                         "ORDER BY snapshot_date"),
                engine, params={"cutoff": cutoff_date},
            )

        if not metrics_df.empty:
            context += "METRIC TRENDS:\n"
            for metric_name in metrics_df["metric_name"].unique():
                m = metrics_df[metrics_df["metric_name"] == metric_name]
                if len(m) >= 2:
                    first_val = m.iloc[0]["metric_value"]
                    last_val = m.iloc[-1]["metric_value"]
                    change = last_val - first_val
                    direction = "up" if change > 0 else "down" if change < 0 else "flat"
                    context += (
                        f"  {metric_name}: {first_val:.3f} -> {last_val:.3f} "
                        f"({direction}, {change:+.3f})\n"
                    )
        else:
            context += "METRIC TRENDS: No metric snapshots available.\n"
    except Exception as e:
        print(f"  Could not load metrics: {e}")
        context += "METRIC TRENDS: Could not load metric data.\n"

    context += "\n"

    # --- Competitive Intelligence (brand only) ---
    if subject_type == "brand":
        try:
            competitive_df = pd.read_sql(
                sql_text("SELECT * FROM competitive_snapshots "
                         "WHERE LOWER(brand_name) = :subject "
                         "ORDER BY created_at DESC LIMIT 1"),
                engine, params={"subject": subject_lower},
            )
            if not competitive_df.empty:
                row = competitive_df.iloc[0]
                snapshot = row.get("snapshot_data", "{}")
                if isinstance(snapshot, str):
                    try:
                        snap = json.loads(snapshot)
                    except (json.JSONDecodeError, TypeError):
                        snap = {}
                else:
                    snap = snapshot

                context += "COMPETITIVE LANDSCAPE:\n"
                sov = snap.get("share_of_voice", {})
                if sov:
                    context += "  Share of Voice:\n"
                    for name, pct in sorted(sov.items(), key=lambda x: -x[1]):
                        context += f"    {name}: {pct:.1f}%\n"

                vlds_comp = snap.get("vlds_comparison", {})
                if vlds_comp:
                    context += "  VLDS Comparison:\n"
                    for comp_name, metrics in vlds_comp.items():
                        if isinstance(metrics, dict):
                            context += f"    {comp_name}: "
                            parts = []
                            for k, v in metrics.items():
                                if isinstance(v, (int, float)):
                                    parts.append(f"{k}={v:.2f}")
                            context += ", ".join(parts) + "\n"
            else:
                context += "COMPETITIVE LANDSCAPE: No competitive data available.\n"
        except Exception as e:
            print(f"  Could not load competitive data: {e}")
            context += "COMPETITIVE LANDSCAPE: Could not load competitive data.\n"

    return context


def generate_intelligence_report(engine, subject, days=7, subject_type="brand"):
    """Generate a comprehensive intelligence report using Claude AI.

    Args:
        engine: SQLAlchemy engine (or None to create one)
        subject: Brand name or topic
        days: Number of days to analyze
        subject_type: "brand" or "topic"

    Returns:
        Report text string
    """
    if engine is None:
        engine = _get_engine()
    if engine is None:
        return "Error: Could not connect to database."

    context = prepare_report_context(engine, subject, days, subject_type)

    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%B %d")
    end_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
    date_range = f"{start_date} - {end_date}"

    prompt = f"""You are a senior strategic intelligence analyst preparing a comprehensive intelligence report.

Based on the following data, create a detailed intelligence report on "{subject}" covering the period {date_range}.

IMPORTANT GUIDELINES:
- Synthesize data across all sources (news, social, alerts, metrics, competitive)
- Focus on patterns and trends, not just individual data points
- For each finding, explain the STRATEGIC IMPLICATION
- Be direct and actionable — decision-makers need clear guidance
- If data is limited, say so honestly rather than speculating
- Use specific numbers from the data to support your analysis

Format as:

INTELLIGENCE REPORT: {subject}
Period: {date_range}

EXECUTIVE SUMMARY:
[3-4 sentences capturing the most important findings]

SIGNAL ANALYSIS:
[Volume trends, sentiment patterns, emotion distribution, intensity levels]
[How is the conversation evolving over the period?]

ALERT HISTORY:
[Summary of alerts fired for this subject]
[Any patterns in alert types or severity?]
[What has the detection system flagged?]

VLDS ASSESSMENT:
[Velocity — Is conversation momentum increasing or decreasing?]
[Longevity — How sustained is the coverage?]
[Density — How saturated is the space?]
[Scarcity — Where are the opportunities?]

{"COMPETITIVE POSITION:" if subject_type == "brand" else ""}
{"[Share of voice analysis, competitor comparison, gaps and opportunities]" if subject_type == "brand" else ""}

STRATEGIC OUTLOOK:
[Forward-looking assessment based on current trajectories]
[Key risks and opportunities]

RECOMMENDED ACTIONS:
- IMMEDIATE (this week): [...]
- MEDIUM-TERM (this month): [...]
- MONITOR: [...]

Target 800-1200 words. Use clear, direct language.

DATA:
{context}
"""

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=3000,
        system=(
            "You are a senior strategic intelligence analyst. You produce comprehensive, "
            "data-driven intelligence reports that synthesize multiple signal types into "
            "actionable strategic insights. You always support claims with specific data."
        ),
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def _build_report_html(report_text, subject, days):
    """Convert report text to styled HTML for email or display."""
    try:
        from generate_brief import _build_brief_html
        html = _build_brief_html(report_text)
        # Replace header badge and title
        html = html.replace("INTELLIGENCE BRIEF", "INTELLIGENCE REPORT")
        html = html.replace("Daily Intelligence Brief", f"Intelligence Report: {subject}")
        html = html.replace("Executive Brief", f"Intelligence Report — Last {days} days")
        return html
    except ImportError:
        # Fallback: basic HTML
        return f"""
        <html>
          <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #1976D2;">Intelligence Report: {subject}</h2>
            <p style="color: #666;">Last {days} days</p>
            <pre style="white-space: pre-wrap; font-size: 14px;">{report_text}</pre>
            <hr>
            <p style="color: #999; font-size: 12px;">
              Moodlight Intelligence Platform — On-Demand Report<br>
              <a href="https://moodlight.up.railway.app" style="color: #1976D2;">View Dashboard</a>
            </p>
          </body>
        </html>
        """


def email_report(report_text, subject, recipient_email, days=7):
    """Send a formatted report to a single recipient.

    Args:
        report_text: The report content
        subject: Brand/topic name (for subject line)
        recipient_email: Email address to send to
        days: Number of days covered (for subject line)

    Returns:
        True if sent successfully
    """
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")

    if not all([sender, password]):
        print("Email credentials not configured.")
        return False

    html = _build_report_html(report_text, subject, days)

    end_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
    email_subject = f"[Moodlight Report] {subject} — {end_date}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = email_subject
    msg["From"] = sender
    msg["To"] = recipient_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
            print(f"Report emailed to {recipient_email}")
            return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False
