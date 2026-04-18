#!/usr/bin/env python
"""
generate_signal_newsletter.py
Generates "Signal" — a daily news intelligence newsletter for busy professionals.

Ranked by what actually mattered (intensity scoring), not what got the most clicks.
Tone: Morning Brew meets your smartest friend. Entertaining, punchy, informative.

Leverages existing Moodlight data pipeline with a dedicated prompt and minimal new code.
"""

import os
import sys
import pandas as pd
from datetime import datetime, timezone, timedelta
from anthropic import Anthropic
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ---------------------------------------------------------------------------
# 1. Data Loading
# ---------------------------------------------------------------------------

def _get_engine():
    from sqlalchemy import create_engine
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url)


def load_signal_data(engine):
    """Load data for the Signal newsletter — top stories by intensity."""
    from sqlalchemy import text as sql_text

    now = datetime.now(timezone.utc)
    data = {}

    # --- Top 20 news stories by intensity (24h) ---
    try:
        cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        stories = pd.read_sql(
            sql_text("""
                SELECT text, intensity, source, topic, emotion_top_1,
                       empathy_score, created_at
                FROM news_scored
                WHERE created_at >= :cutoff
                  AND intensity IS NOT NULL
                ORDER BY intensity DESC
                LIMIT 20
            """),
            engine,
            params={"cutoff": cutoff_24h},
        )
        data["stories"] = stories
    except Exception as e:
        print(f"  Could not load news stories: {e}")
        data["stories"] = pd.DataFrame()

    # --- Top 10 social posts by intensity (24h) ---
    try:
        cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        social = pd.read_sql(
            sql_text("""
                SELECT text, intensity, source, topic, emotion_top_1,
                       empathy_score, created_at
                FROM social_scored
                WHERE created_at >= :cutoff
                  AND intensity IS NOT NULL
                ORDER BY intensity DESC
                LIMIT 10
            """),
            engine,
            params={"cutoff": cutoff_24h},
        )
        data["social"] = social
    except Exception as e:
        print(f"  Could not load social posts: {e}")
        data["social"] = pd.DataFrame()

    # --- Emotion distribution (3d, top 5) ---
    try:
        cutoff_3d = (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        emotions = pd.read_sql(
            sql_text("""
                SELECT emotion_top_1, COUNT(*) AS cnt
                FROM news_scored
                WHERE created_at >= :cutoff
                  AND emotion_top_1 IS NOT NULL
                GROUP BY emotion_top_1
                ORDER BY cnt DESC
                LIMIT 5
            """),
            engine,
            params={"cutoff": cutoff_3d},
        )
        data["emotions"] = emotions
    except Exception as e:
        print(f"  Could not load emotions: {e}")
        data["emotions"] = pd.DataFrame()

    # --- Market snapshot (SPY, QQQ, DIA) ---
    try:
        markets = pd.read_sql(
            sql_text("""
                SELECT symbol, price, change, change_percent, latest_trading_day
                FROM markets
                WHERE symbol IN ('SPY', 'QQQ', 'DIA')
                ORDER BY timestamp DESC
            """),
            engine,
        )
        data["markets"] = markets.groupby("symbol").first().reset_index()
    except Exception as e:
        print(f"  Could not load market data: {e}")
        data["markets"] = pd.DataFrame()

    return data


# ---------------------------------------------------------------------------
# 2. Context Building
# ---------------------------------------------------------------------------

def build_signal_context(data):
    """Format data into a structured text block for Claude."""
    now = datetime.now(timezone.utc)
    sections = []

    sections.append(f"SIGNAL — DATA CONTEXT")
    sections.append(f"Generated: {now.strftime('%B %d, %Y at %H:%M UTC')}")
    sections.append("=" * 50)

    # Top stories
    stories = data.get("stories", pd.DataFrame())
    if not stories.empty:
        lines = ["TOP STORIES (ranked by intensity, last 24h):"]
        for i, (_, row) in enumerate(stories.iterrows(), 1):
            headline = str(row["text"])[:300]
            topic = row.get("topic", "unknown") or "unknown"
            emotion = row.get("emotion_top_1", "unknown") or "unknown"
            source = row.get("source", "unknown") or "unknown"
            intensity = row.get("intensity", 0) or 0
            lines.append(
                f"  {i}. [{topic}] (intensity: {intensity:.1f}, emotion: {emotion}, "
                f"source: {source})\n     {headline}"
            )
        sections.append("\n".join(lines))

    # Top social
    social = data.get("social", pd.DataFrame())
    if not social.empty:
        lines = ["TOP SOCIAL (ranked by intensity, last 24h):"]
        for i, (_, row) in enumerate(social.iterrows(), 1):
            text = str(row["text"])[:300]
            topic = row.get("topic", "unknown") or "unknown"
            emotion = row.get("emotion_top_1", "unknown") or "unknown"
            source = row.get("source", "unknown") or "unknown"
            intensity = row.get("intensity", 0) or 0
            lines.append(
                f"  {i}. [{topic}] (intensity: {intensity:.1f}, emotion: {emotion}, "
                f"source: {source})\n     {text}"
            )
        sections.append("\n".join(lines))

    # Emotion pulse
    emotions = data.get("emotions", pd.DataFrame())
    if not emotions.empty:
        lines = ["EMOTION PULSE (top 5 emotions, 3-day window):"]
        total = emotions["cnt"].sum()
        for _, row in emotions.iterrows():
            pct = (row["cnt"] / total) * 100
            lines.append(f"  {row['emotion_top_1']}: {row['cnt']} ({pct:.0f}%)")
        sections.append("\n".join(lines))

    # Market snapshot
    mkt = data.get("markets", pd.DataFrame())
    if not mkt.empty:
        lines = ["MARKET SNAPSHOT:"]
        for _, row in mkt.iterrows():
            chg = row.get("change", 0) or 0
            pct = row.get("change_percent", "0%")
            lines.append(f"  {row['symbol']}: ${row['price']:.2f} ({chg:+.2f}, {pct})")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# 3. Newsletter Generation (Claude)
# ---------------------------------------------------------------------------

SIGNAL_SYSTEM_PROMPT = """You are the writer behind Signal — a daily intelligence newsletter that cuts through the noise and tells busy professionals what actually mattered today.

Your voice: Morning Brew meets your smartest friend. Witty, direct, zero filler. You're the person at the dinner party who somehow knows everything interesting that happened today and explains it in a way that's genuinely fun to read.

RULES:
1. Pick 5-7 stories from the data. Rank by what's most important and interesting, NOT by intensity score alone. Use your judgment — a lower-intensity story with huge implications beats a high-intensity nothing-burger.
2. Every claim must come from the provided data. No training data. No made-up stats.
3. Open with a one-liner hook — something clever that sets the tone for the day. One sentence max.
4. Each story gets a punchy headline (bold) + 2-3 sentences on why it matters. Don't just summarize — tell the reader why they should care. Connect dots between stories when possible.
5. Close with "Mood of the Day" — one sentence capturing the emotional vibe from the emotion data.
6. Close with "Market Pulse" — one tight line on SPY/QQQ/DIA. Just the numbers and a quip.
7. Under 800 words total. This is a 2-minute read, max.
8. No corporate speak. No "in today's rapidly evolving landscape." No throat-clearing. Get to it.
9. Mix in social signals where they add color or contrast to a news story. Don't treat social as a separate section.
10. Group related stories or find a thread between them when possible. Don't just list items.

OUTPUT FORMAT — use this exact markdown structure:

# SIGNAL
*[Full date]*

[One-liner hook]

---

**[Story 1 Headline]**
[2-3 sentences. Why it matters.]

**[Story 2 Headline]**
[2-3 sentences. Why it matters.]

[...continue for 5-7 stories...]

---

**Mood of the Day:** [One sentence from emotion data — what's the vibe?]

**Market Pulse:** [SPY/QQQ/DIA one-liner with numbers]

---
*Signal is powered by Moodlight Intelligence. Ranked by what mattered, not what trended.*
"""


def generate_signal(context):
    """Generate the Signal newsletter via Claude Sonnet."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SIGNAL_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Generate today's Signal newsletter using this data:\n\n{context}",
        }],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# 4. Email Delivery
# ---------------------------------------------------------------------------

def email_signal(newsletter_md):
    """Email the Signal newsletter."""
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    recipient = os.getenv("EMAIL_RECIPIENT", "")

    if not all([sender, password, recipient]):
        print("  Email credentials not configured. Skipping email.")
        return False

    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    from mood_report_publisher import markdown_to_newsletter_html
    newsletter_html = markdown_to_newsletter_html(newsletter_md)

    html_body = f"""
    <html>
      <body style="font-family: 'Helvetica Neue', Arial, sans-serif; max-width: 640px; margin: 0 auto; padding: 20px; background: #fafafa;">
        <div style="background: #111827; color: white; padding: 24px 20px; border-radius: 8px 8px 0 0;">
          <h1 style="margin: 0; font-size: 28px; font-weight: 800; letter-spacing: 2px;">SIGNAL</h1>
          <p style="margin: 6px 0 0 0; color: #9CA3AF; font-size: 13px;">{date_str} &mdash; Daily Intelligence</p>
        </div>

        <div style="background: white; border: 1px solid #e5e7eb; border-top: none; padding: 24px 20px; border-radius: 0 0 8px 8px;">
          {newsletter_html}
        </div>

        <p style="color: #9CA3AF; font-size: 11px; text-align: center; margin-top: 16px;">
          Signal by Moodlight Intelligence &mdash; Ranked by what mattered, not what trended.
        </p>
      </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Signal — {date_str}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"  Signal emailed to {recipient}")
        return True
    except Exception as e:
        print(f"  Email failed: {e}")
        return False


# ---------------------------------------------------------------------------
# 5. Main
# ---------------------------------------------------------------------------

def main():
    skip_email = "--skip-email" in sys.argv

    print("=" * 60)
    print("SIGNAL — Daily News Intelligence Newsletter")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # 1. Connect
    engine = _get_engine()

    # 2. Load data
    print("\n[1/4] Loading signal data...")
    data = load_signal_data(engine)

    stories = data.get("stories", pd.DataFrame())
    social = data.get("social", pd.DataFrame())
    print(f"  News stories: {len(stories)}, Social posts: {len(social)}")

    if stories.empty and social.empty:
        print("No stories or social data available. Cannot generate newsletter.")
        return

    # 3. Build context
    print("[2/4] Building context...")
    context = build_signal_context(data)
    print(f"  Context length: {len(context)} chars")

    # 4. Generate newsletter
    print("[3/4] Generating Signal via Claude Sonnet...")
    newsletter_md = generate_signal(context)
    print(f"  Newsletter length: {len(newsletter_md)} chars")

    # 5. Email
    if skip_email:
        print("[4/4] Skipping email (--skip-email)")
    else:
        print("[4/4] Emailing Signal...")
        email_signal(newsletter_md)

    # Print to stdout
    print("\n" + "=" * 60)
    print("GENERATED NEWSLETTER:")
    print("=" * 60)
    print(newsletter_md)

    print("\nDone.")


if __name__ == "__main__":
    main()
