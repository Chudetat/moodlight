#!/usr/bin/env python
"""
generate_brief.py
Generates an executive intelligence brief using Claude AI
"""

import os
import pandas as pd
from datetime import datetime, timezone
from anthropic import Anthropic
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_cancelled_subscriber_emails():
    """Get emails of users who cancelled their subscription.
    Only these emails will be excluded from the daily brief.
    Active tiers (monthly, annually) always pass through regardless of Stripe status."""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return None  # No database — send to full EMAIL_RECIPIENT list
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
            emails = {row[0].lower() for row in result.fetchall()}
            print(f"Cancelled/inactive subscribers (will be excluded): {emails}")
            return emails
    except Exception as e:
        print(f"Could not query subscriber status: {e}")
        return None  # Send to full EMAIL_RECIPIENT list

def _build_brief_html(brief_text):
    """Convert brief plain text to styled HTML matching alert email format."""
    import re

    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

    # Parse sections from the brief text
    sections_html = []
    current_section = None
    current_lines = []

    for line in brief_text.split("\n"):
        # Detect section headers (ALL CAPS lines, optionally with colons)
        stripped = line.strip()
        if (stripped and re.match(r'^[A-Z][A-Z &\-/]+:?\s*$', stripped)
                and len(stripped) > 3 and stripped not in ("DATA:", "FORMAT:")):
            # Save previous section
            if current_section:
                sections_html.append(_format_brief_section(current_section, current_lines))
            current_section = stripped.rstrip(":")
            current_lines = []
        elif stripped.startswith("DAILY INTELLIGENCE BRIEF"):
            # Skip the title line — we render our own header
            continue
        elif stripped.startswith("===") or stripped.startswith("---"):
            continue
        else:
            current_lines.append(line)

    # Save last section
    if current_section:
        sections_html.append(_format_brief_section(current_section, current_lines))
    elif current_lines:
        # No sections detected — render as single block
        content = "\n".join(current_lines).strip()
        content_html = _markdown_to_html(content)
        sections_html.append(
            f'<div style="margin: 15px 0;">'
            f'<p style="font-size: 15px; color: #333; line-height: 1.6;">{content_html}</p>'
            f'</div>'
        )

    body = "\n".join(sections_html)

    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
        <div style="border-left: 4px solid #1976D2; padding-left: 15px; margin-bottom: 20px;">
          <span style="background: #1976D2; color: white; padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: bold;">
            INTELLIGENCE BRIEF
          </span>
          <h2 style="margin: 10px 0 5px 0; color: #333;">Daily Intelligence Brief</h2>
          <p style="color: #666; margin: 0;">{date_str}</p>
        </div>

        {body}

        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">
          Moodlight Intelligence Platform — Executive Brief<br>
          <a href="https://moodlight.up.railway.app" style="color: #1976D2;">View Dashboard</a>
        </p>
      </body>
    </html>
    """


def _format_brief_section(title, lines):
    """Format a single section of the brief as styled HTML."""
    content = "\n".join(lines).strip()
    if not content:
        return ""

    # Section color coding
    section_colors = {
        "KEY THREATS": "#DC143C",
        "WATCH LIST": "#FFB300",
        "EMERGING PATTERNS": "#1976D2",
        "RECOMMENDED ACTIONS": "#2E7D32",
    }
    color = section_colors.get(title, "#1976D2")

    content_html = _markdown_to_html(content)

    return (
        f'<div style="margin: 20px 0;">'
        f'<div style="border-left: 3px solid {color}; padding-left: 12px; margin-bottom: 8px;">'
        f'<h3 style="margin: 0; color: {color}; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;">{title}</h3>'
        f'</div>'
        f'<div style="background: #fafafa; padding: 12px 15px; border-radius: 8px;">'
        f'<div style="font-size: 15px; color: #333; line-height: 1.6;">{content_html}</div>'
        f'</div>'
        f'</div>'
    )


def _markdown_to_html(text):
    """Convert basic markdown patterns to HTML for email rendering."""
    import re

    # Bold: **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    # Numbered list items: "1. text" → styled list
    text = re.sub(
        r'^(\d+)\.\s+(.+)$',
        r'<div style="margin: 6px 0; padding-left: 8px;">'
        r'<span style="color: #999; font-size: 13px;">\1.</span> \2</div>',
        text,
        flags=re.MULTILINE,
    )

    # Bullet items: "- text" → styled bullets
    text = re.sub(
        r'^[-•]\s+(.+)$',
        r'<div style="margin: 4px 0; padding-left: 12px;">'
        r'<span style="color: #999;">&#8226;</span> \1</div>',
        text,
        flags=re.MULTILINE,
    )

    # Tags: [NEW], [ONGOING], [HIGH CONFIDENCE], etc.
    def _style_tag(m):
        tag = m.group(1)
        if tag in ("NEW",):
            return f'<span style="background: #E8F5E9; color: #2E7D32; padding: 1px 6px; border-radius: 3px; font-size: 11px; font-weight: bold;">{tag}</span>'
        elif tag in ("ONGOING",):
            return f'<span style="background: #FFF3E0; color: #E65100; padding: 1px 6px; border-radius: 3px; font-size: 11px; font-weight: bold;">{tag}</span>'
        elif "CONFIDENCE" in tag:
            return f'<span style="background: #E3F2FD; color: #1565C0; padding: 1px 6px; border-radius: 3px; font-size: 11px;">{tag}</span>'
        elif tag in ("IMMEDIATE", "SHORT-TERM", "MONITOR"):
            return f'<span style="background: #F3E5F5; color: #7B1FA2; padding: 1px 6px; border-radius: 3px; font-size: 11px; font-weight: bold;">{tag}</span>'
        return f'<span style="background: #ECEFF1; color: #546E7A; padding: 1px 6px; border-radius: 3px; font-size: 11px;">{tag}</span>'

    text = re.sub(r'\[([A-Z][A-Z \-]+?)\]', _style_tag, text)

    # Arrows
    text = text.replace("↑", '<span style="color: #DC143C;">&#8593;</span>')
    text = text.replace("↓", '<span style="color: #2E7D32;">&#8595;</span>')

    # Preserve paragraph breaks
    text = re.sub(r'\n\s*\n', '</p><p style="margin: 8px 0;">', text)
    text = text.replace("\n", "<br>")

    return text


def _get_subscriber_emails_for_brief():
    """Get all subscriber emails from the users table for brief delivery."""
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
                  AND COALESCE(p.digest_daily, TRUE) = TRUE
            """))
            return [row[0] for row in result.fetchall()]
    except Exception as e:
        print(f"Could not query subscriber emails: {e}")
        return []


def send_email_brief(brief_text):
    """Send intelligence brief via email to each recipient individually.
    Cancelled subscribers are filtered out; everyone else passes through."""
    sender = os.getenv("EMAIL_ADDRESS")
    recipients_str = os.getenv("EMAIL_RECIPIENT", "")
    password = os.getenv("EMAIL_PASSWORD")

    if not all([sender, password]):
        print("Email credentials not configured. Skipping email.")
        return False

    # Build recipient list: DB subscribers + env var, deduplicated
    env_recipients = [r.strip() for r in recipients_str.split(",") if r.strip()]
    db_subscribers = _get_subscriber_emails_for_brief()
    all_emails = set(e.lower() for e in env_recipients)
    all_emails.update(e.lower() for e in db_subscribers if e)

    if not all_emails:
        print("No recipients found (DB or env var). Skipping email.")
        return False

    # Remove cancelled subscribers
    cancelled_emails = get_cancelled_subscriber_emails()
    if cancelled_emails:
        all_emails -= cancelled_emails

    recipients = list(all_emails)
    if not recipients:
        print("All recipients are cancelled. Skipping email.")
        return False

    print(f"Sending brief to {len(recipients)} active recipient(s)")

    # Convert brief text to styled HTML matching alert email format
    html = _build_brief_html(brief_text)

    success_count = 0
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)

            for recipient in recipients:
                # Create fresh message for each recipient
                msg = MIMEMultipart('alternative')
                msg['Subject'] = f'[Moodlight Brief] \U0001f4ca Daily Intelligence Brief — {datetime.now(timezone.utc).strftime("%B %d, %Y")}'
                msg['From'] = sender
                msg['To'] = recipient  # Only this recipient visible
                msg.attach(MIMEText(html, 'html'))

                try:
                    server.send_message(msg)
                    print(f"✅ Email sent to {recipient}")
                    success_count += 1
                except Exception as e:
                    print(f"❌ Email failed for {recipient}: {e}")

        return success_count > 0
    except Exception as e:
        print(f"❌ Email connection failed: {e}")
        return False

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def load_recent_data():
    """Load last 24 hours of intelligence data"""
    # Try PostgreSQL first
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        try:
            from sqlalchemy import create_engine
            db_url = db_url.replace("postgres://", "postgresql://", 1)
            engine = create_engine(db_url)
            df = pd.read_sql("SELECT * FROM news_scored", engine)
            if not df.empty:
                print(f"✅ Loaded {len(df)} rows from PostgreSQL")
                df['created_at'] = pd.to_datetime(df['created_at'], utc=True, errors='coerce')
                cutoff = datetime.now(timezone.utc) - pd.Timedelta(days=7)
                return df[df['created_at'] >= cutoff]
        except Exception as e:
            print(f"DB error: {e}")
    # Fallback to CSV
    df = pd.read_csv("news_scored.csv")
    df['created_at'] = pd.to_datetime(df['created_at'], utc=True, errors='coerce')

    # Last 7 days
    cutoff = datetime.now(timezone.utc) - pd.Timedelta(days=7)
    recent = df[df['created_at'] >= cutoff]

    return recent


def load_social_data():
    """Load social media data for sentiment analysis"""
    cutoff = datetime.now(timezone.utc) - pd.Timedelta(days=7)
    # Try PostgreSQL first
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        try:
            from sqlalchemy import create_engine
            db_url = db_url.replace("postgres://", "postgresql://", 1)
            engine = create_engine(db_url)
            df = pd.read_sql("SELECT * FROM social_scored", engine)
            if not df.empty:
                df['created_at'] = pd.to_datetime(df['created_at'], utc=True, errors='coerce')
                recent = df[df['created_at'] >= cutoff]
                if not recent.empty:
                    print(f"✅ Loaded {len(recent)} social posts from PostgreSQL")
                    return recent
        except Exception as e:
            print(f"Social DB error: {e}")
    # Fallback to CSV
    if os.path.exists("social_scored.csv"):
        try:
            df = pd.read_csv("social_scored.csv")
            df['created_at'] = pd.to_datetime(df['created_at'], utc=True, errors='coerce')
            recent = df[df['created_at'] >= cutoff]
            if not recent.empty:
                print(f"✅ Loaded {len(recent)} social posts from CSV")
                return recent
        except Exception as e:
            print(f"Social CSV error: {e}")
    print("⚠️ No social data available")
    return pd.DataFrame()

def prepare_intelligence_context(news_df, social_df=None):
    """Prepare context for AI briefing"""

    # Top topics by volume
    topic_counts = news_df['topic'].value_counts().head(5)

    # High intensity articles (4-5 severity)
    critical = news_df[news_df['intensity'] >= 4]

    # Geographic distribution
    country_counts = news_df['country'].value_counts().head(5)

    # Average intensity by topic
    topic_intensity = news_df.groupby('topic')['intensity'].mean().sort_values(ascending=False).head(5)

    context = f"""
INTELLIGENCE DATA SUMMARY (Last 7 Days)
==========================================

TOP TOPICS BY VOLUME:
{topic_counts.to_string()}

HIGHEST INTENSITY TOPICS:
{topic_intensity.round(2).to_string()}

CRITICAL SEVERITY ARTICLES ({len(critical)} total):
{critical[['text', 'country', 'intensity']].head(10).to_string()}

GEOGRAPHIC DISTRIBUTION:
{country_counts.to_string()}

Total Articles Analyzed: {len(news_df)}
"""

    # Add social data if available
    if social_df is not None and not social_df.empty:
        # Top social topics
        social_topics = social_df['topic'].value_counts().head(5)

        # Emotional sentiment distribution
        emotion_dist = social_df['emotion_top_1'].value_counts().head(5)

        # Empathy score distribution
        empathy_dist = social_df['empathy_label'].value_counts()

        # High engagement posts (top by engagement score)
        if 'engagement' in social_df.columns:
            top_engagement = social_df.nlargest(5, 'engagement')[['text', 'engagement', 'emotion_top_1', 'source']]
        else:
            top_engagement = social_df.head(5)[['text', 'emotion_top_1', 'source']]

        # Average empathy by topic (cultural temperature)
        topic_empathy = social_df.groupby('topic')['empathy_score'].mean().sort_values(ascending=False).head(5)

        context += f"""

SOCIAL PULSE & CULTURAL MOMENTUM
==========================================

TRENDING SOCIAL TOPICS:
{social_topics.to_string()}

DOMINANT EMOTIONS:
{emotion_dist.to_string()}

EMPATHY TEMPERATURE:
{empathy_dist.to_string()}

CULTURAL HEAT BY TOPIC (Empathy Score):
{topic_empathy.round(2).to_string()}

HIGH-ENGAGEMENT CONTENT:
{top_engagement.to_string()}

Total Social Posts Analyzed: {len(social_df)}
"""

    return context

def generate_brief(context):
    """Generate executive brief using Claude AI"""

    prompt = f"""You are an intelligence analyst preparing a daily intelligence brief.

Based on the following intelligence data, create a concise executive summary.

IMPORTANT GUIDELINES:
- Consolidate related stories: If multiple articles cover the same event (e.g., Venezuela), group them into ONE threat entry, not separate items
- Prioritize by RECENCY + INTENSITY: Recent high-intensity events outrank older high-intensity events
- For each threat, include the "SO WHAT?" - why it matters, not just what happened
- Flag each threat as [NEW] (first appeared in last 48h) or [ONGOING] (continuing situation)
- Add confidence indicator based on data volume: [HIGH CONFIDENCE] = 10+ sources, [MODERATE] = 3-9 sources, [LIMITED] = 1-2 sources

Format as:
DAILY INTELLIGENCE BRIEF - {datetime.now(timezone.utc).strftime("%B %d, %Y")}

KEY THREATS:
1. [NEW/ONGOING] **Threat Title** - [CONFIDENCE LEVEL]
   What: [One sentence on what happened]
   So What: [Why this matters / implications]

WATCH LIST:
[Lower priority items worth monitoring - not urgent but could escalate]

EMERGING PATTERNS:
[Group related signals. Note if each pattern is ACCELERATING ↑ or DECELERATING ↓]

RECOMMENDED ACTIONS:
- IMMEDIATE (24h): [...]
- SHORT-TERM (this week): [...]
- MONITOR: [...]

Target 600-800 words. Use clear, direct language. No fluff.

DATA:
{context}
"""

    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=2000,
        system="You are a senior intelligence analyst. You consolidate noise into signal, distinguish new developments from ongoing situations, and always explain WHY something matters - not just WHAT happened.",
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.content[0].text

def main():
    print("=" * 60)
    print("GENERATING EXECUTIVE INTELLIGENCE BRIEF")
    print("=" * 60)
    print()

    news_df = load_recent_data()
    social_df = load_social_data()

    if len(news_df) == 0 and len(social_df) == 0:
        print("No recent data available for briefing.")
        return

    print(f"Analyzing {len(news_df)} news articles + {len(social_df)} social posts...")
    print()

    context = prepare_intelligence_context(news_df, social_df)
    brief = generate_brief(context)
    
    print(brief)
    print()
    print("=" * 60)
    
    # Save to file
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"intel_brief_{timestamp}.txt"
    
    with open(filename, 'w') as f:
        f.write(brief)
    
    print(f"Brief saved to: {filename}")

    # Send email
    send_email_brief(brief)

if __name__ == "__main__":
    main()
