#!/usr/bin/env python
"""
generate_radar.py
Generates "Radar by Moodlight" — a daily consumer intelligence email.

Each topic hits three beats: What's happening? Why it matters to me? What's my move?
Uses VLDS deltas, empathy shifts, prediction markets, and staleness scoring
to surface only what's genuinely new and interesting.
"""

import os
import sys
import pandas as pd
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _get_engine():
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        print("DATABASE_URL not set")
        sys.exit(1)
    from sqlalchemy import create_engine
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url)


def build_radar_context(engine):
    """Build context from all signal sources for Radar generation."""
    from sqlalchemy import text as sql_text
    now = datetime.now(timezone.utc)
    cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_48h = (now - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
    sections = []

    # ── 1. Topic Intelligence (the core — what's interesting and why) ──
    try:
        from topic_intelligence import compute_topic_intelligence, format_intelligence_context
        topics = compute_topic_intelligence(engine, output_type="radar")
        if topics:
            sections.append(format_intelligence_context(topics, top_n=15))
    except Exception as e:
        print(f"  Topic intelligence failed: {e}")

    # ── 2. Fresh headlines (24h only — must be genuinely new) ──
    try:
        news_df = pd.read_sql(sql_text("""
            SELECT text, topic, intensity, created_at, country
            FROM news_scored
            WHERE created_at >= :cutoff AND intensity >= 3
            ORDER BY intensity DESC, created_at DESC
            LIMIT 20
        """), engine, params={"cutoff": cutoff_24h})
        if not news_df.empty:
            lines = ["FRESH HEADLINES (last 24h, high intensity only)"]
            lines.append("=" * 50)
            for _, row in news_df.iterrows():
                lines.append(f"  [{row.get('topic', '?')}] {row['text'][:250]}")
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Headlines failed: {e}")

    # ── 3. Social emotional temperature ──
    try:
        emo_df = pd.read_sql(sql_text("""
            SELECT emotion_top_1 AS emotion, COUNT(*) AS cnt
            FROM news_scored
            WHERE created_at >= :cutoff AND emotion_top_1 IS NOT NULL
            GROUP BY emotion_top_1
            ORDER BY cnt DESC
            LIMIT 10
        """), engine, params={"cutoff": cutoff_24h})
        emp_df = pd.read_sql(sql_text("""
            SELECT AVG(empathy_score) AS avg_empathy, COUNT(*) AS total
            FROM news_scored
            WHERE created_at >= :cutoff AND empathy_score IS NOT NULL
        """), engine, params={"cutoff": cutoff_24h})

        if not emo_df.empty:
            total = emo_df['cnt'].sum()
            lines = ["EMOTIONAL TEMPERATURE (last 24h)"]
            lines.append("=" * 50)
            for _, row in emo_df.head(5).iterrows():
                pct = row['cnt'] / total * 100
                lines.append(f"  {row['emotion']}: {pct:.1f}%")
            if not emp_df.empty:
                avg_emp = emp_df.iloc[0]['avg_empathy']
                lines.append(f"  Average empathy: {avg_emp:.4f} (0.04=neutral, 0.10=warm, 0.30+=highly empathetic)")
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Emotions failed: {e}")

    # ── 4. Market indices ──
    try:
        mkt_df = pd.read_sql(sql_text("""
            SELECT symbol, name, price, change_percent, market_sentiment
            FROM markets
            WHERE timestamp::timestamptz >= NOW() - INTERVAL '24 hours'
            ORDER BY timestamp DESC
        """), engine)
        if not mkt_df.empty:
            latest = mkt_df.drop_duplicates(subset=['symbol'], keep='first')
            lines = ["MARKETS (last 24h)"]
            lines.append("=" * 50)
            for _, row in latest.iterrows():
                chg = row.get('change_percent', 0) or 0
                lines.append(f"  {row['name']}: {'up' if chg > 0 else 'down'} {abs(chg):.2f}%")
            avg_sent = latest['market_sentiment'].mean()
            lines.append(f"  Overall mood: {'bullish' if avg_sent > 0.55 else 'bearish' if avg_sent < 0.45 else 'neutral'} ({avg_sent:.2f})")
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Markets failed: {e}")

    # ── 5. Commodity prices ──
    try:
        from db_helper import load_commodity_data
        comm_df = load_commodity_data(days=3)
        if not comm_df.empty:
            price_df = comm_df[comm_df["metric_name"] == "price"]
            if not price_df.empty:
                latest = price_df.sort_values("snapshot_date").groupby("scope_name").last().reset_index()
                lines = ["COMMODITY PRICES"]
                lines.append("=" * 50)
                for _, row in latest.iterrows():
                    lines.append(f"  {row['scope_name']}: ${row['metric_value']:.2f}")
                sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Commodities failed: {e}")

    # ── 6. Economic indicators ──
    try:
        from db_helper import load_economic_data
        econ_df = load_economic_data(days=7)
        if not econ_df.empty:
            latest = econ_df.sort_values("snapshot_date").groupby("metric_name").last().reset_index()
            lines = ["ECONOMIC INDICATORS"]
            lines.append("=" * 50)
            for _, row in latest.iterrows():
                lines.append(f"  {row['metric_name']}: {row['metric_value']:.2f}")
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Economic indicators failed: {e}")

    # ── 7. Prediction markets ──
    try:
        from polymarket_helper import fetch_polymarket_markets
        markets = fetch_polymarket_markets(limit=10, min_volume=50000)
        if markets:
            lines = ["PREDICTION MARKETS (Polymarket — real money bets)"]
            lines.append("=" * 50)
            for m in markets[:8]:
                lines.append(f"  \"{m['question']}\" — {m['yes_odds']:.0f}% YES (${m['volume']:,.0f} wagered)")
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Polymarket failed: {e}")

    # ── 8. Predictive signals ──
    try:
        pred_df = pd.read_sql(sql_text("""
            SELECT alert_type, title, summary, brand, topic
            FROM alerts
            WHERE alert_type LIKE 'predictive_%%' AND timestamp >= :cutoff
            ORDER BY timestamp DESC LIMIT 10
        """), engine, params={"cutoff": cutoff_48h})
        if not pred_df.empty:
            lines = ["MOODLIGHT SIGNALS (last 48h)"]
            lines.append("=" * 50)
            for _, row in pred_df.iterrows():
                scope = row.get('brand') or row.get('topic') or ''
                lines.append(f"  [{scope}] {row['title']}")
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Signals failed: {e}")

    # ── 9. Brand stocks ──
    try:
        brand_df = pd.read_sql(sql_text("""
            SELECT scope_name, metric_name, metric_value, snapshot_date
            FROM metric_snapshots
            WHERE scope = 'brand' AND snapshot_date >= CURRENT_DATE - INTERVAL '3 days'
            ORDER BY snapshot_date DESC
        """), engine)
        if not brand_df.empty:
            price_df = brand_df[brand_df["metric_name"] == "stock_price"]
            chg_df = brand_df[brand_df["metric_name"] == "stock_change_pct"]
            if not price_df.empty:
                latest = price_df.drop_duplicates(subset=["scope_name"], keep="first")
                chg_map = {}
                if not chg_df.empty:
                    chg_latest = chg_df.drop_duplicates(subset=["scope_name"], keep="first")
                    chg_map = dict(zip(chg_latest["scope_name"], chg_latest["metric_value"]))
                lines = ["BRAND STOCKS (watchlist companies)"]
                lines.append("=" * 50)
                for _, row in latest.iterrows():
                    chg = chg_map.get(row["scope_name"], 0)
                    lines.append(f"  {row['scope_name']}: ${row['metric_value']:.2f} ({chg:+.2f}%)")
                sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Brand stocks failed: {e}")

    # ── 10. Signal track record ──
    try:
        sig_df = pd.read_sql(sql_text("""
            SELECT alert_type,
                   COUNT(*) AS total_signals,
                   COUNT(spy_change_1d) AS has_1d,
                   AVG(spy_change_1d) AS avg_spy_1d,
                   SUM(CASE WHEN spy_change_1d > 0 THEN 1 ELSE 0 END)::float
                       / NULLIF(COUNT(spy_change_1d), 0) AS up_rate_1d
            FROM signal_log
            GROUP BY alert_type
            ORDER BY total_signals DESC
        """), engine)
        if not sig_df.empty:
            lines = ["MOODLIGHT SIGNAL TRACK RECORD"]
            lines.append("=" * 50)
            for _, row in sig_df.iterrows():
                up_rate = f"{row['up_rate_1d']*100:.0f}%" if pd.notna(row.get("up_rate_1d")) else "N/A"
                avg_1d = f"{row['avg_spy_1d']:+.2f}%" if pd.notna(row.get("avg_spy_1d")) else "N/A"
                lines.append(
                    f"  {row['alert_type']}: {int(row['total_signals'])} signals, "
                    f"SPY up rate: {up_rate}, avg 1d move: {avg_1d}"
                )
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Signal track record failed: {e}")

    return "\n\n".join(sections)


RADAR_SYSTEM_PROMPT = """You write "Radar by Moodlight" — a daily email that tells people what they need to know about the world today, written like a brilliant friend who happens to have access to 9 real-time data feeds that nobody else can see.

Your voice: Direct. Warm. Occasionally funny. Never dry. Never corporate. Never "analyst." You're the friend who texts someone "hey, fill your tank today, gas is about to spike" — not the friend who says "commodity indicators suggest upward pressure on refined petroleum products."

STRUCTURE (follow exactly):

Start with a greeting: "Good morning. Here's what your radar is picking up."

Then 3-4 TOPICS — chosen by what's GENUINELY INTERESTING TODAY, not what's been in the news for weeks. Each topic gets:
1. A bold headline that's conversational (not a news headline)
2. A paragraph explaining what's happening in plain language
3. "Why this matters to you:" — connect it to the reader's daily life, money, career, or decisions
4. "Your move:" — one specific, actionable thing to do or avoid

Then: "THE THING NOBODY SEES YET" — one item from the high-scarcity/white-space data or a prediction market signal that contradicts conventional wisdom. This is the section that makes people forward the email.

Then: "THE VIBE" — one short paragraph about the emotional temperature of the internet right now. What are people feeling? What kind of content/messaging will cut through vs. get ignored?

Then: "ONE SIGNAL" — one prediction from Moodlight's signal data, framed as a pattern worth watching. Not financial advice.

End with: "Your radar updates every morning at 6am."

CRITICAL RULES:
- NEVER show scores, percentages from internal systems, or jargon. No "VLDS", no "density 0.86", no "empathy 0.04". Translate EVERYTHING into plain human language.
- NEVER lead with the biggest headline of the day. That's what every other newsletter does. Lead with the thing that's interesting, counterintuitive, or about to matter.
- Topics marked STALE in the data MUST be skipped unless you can point to a specific data change.
- Every topic must pass the "so what?" test — if the reader can't do something with this information, cut it.
- When prediction markets disagree with social sentiment, that divergence IS the story.
- Cross-reference signals: commodity price + social empathy + market move = a story nobody else can tell.
- Target 500-700 words. Tight. Every sentence earns its place.

DATA DISCIPLINE:
Only reference a data source when it is directly and obviously relevant to the story you're telling. Never force a metric into an insight just to prove the data exists. If prediction markets, brand stocks, signal track record, or commodity prices don't connect to today's topics — leave them out entirely. A tight email with 3 data sources beats a bloated one with 12.

TRAINING DATA BAN:
Your ONLY sources of truth are the data provided. Do NOT inject facts, events, or claims from training data. If the data doesn't cover something, skip it — never fill gaps with training knowledge."""


def generate_radar_email(context):
    """Generate the Radar email via Claude."""
    prompt = f"""Write today's Radar email based on these signals:

{context}
"""
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        system=RADAR_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def radar_to_html(radar_md):
    """Convert Radar markdown to styled HTML email."""
    import re

    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # Basic markdown → HTML
    html_body = radar_md

    # Bold
    html_body = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_body)

    # Section headers (lines that are all caps or start with specific phrases)
    for header in ["THE THING NOBODY SEES YET", "THE VIBE", "ONE SIGNAL",
                    "ON YOUR RADAR", "WHAT NOBODY SEES", "THE THING NOBODY",
                    "YOUR RADAR"]:
        html_body = html_body.replace(
            header,
            f'<div style="margin-top: 25px; margin-bottom: 8px;">'
            f'<span style="background: #F97316; color: white; padding: 4px 12px; border-radius: 4px; '
            f'font-size: 11px; font-weight: bold; letter-spacing: 1px;">{header}</span></div>'
        )

    # "Why this matters to you:" and "Your move:" labels
    html_body = re.sub(
        r'(Why this matters to you:)',
        r'<strong style="color: #F97316;">\1</strong>',
        html_body
    )
    html_body = re.sub(
        r'(Your move:)',
        r'<strong style="color: #22C55E;">\1</strong>',
        html_body
    )

    # Paragraphs
    html_body = re.sub(r'\n\s*\n', '</p><p style="margin: 12px 0; line-height: 1.6;">', html_body)
    html_body = html_body.replace("\n", "<br>")

    return f"""
    <html>
      <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    max-width: 600px; margin: 0 auto; padding: 20px; background: #0f0f0f; color: #e0e0e0;">
        <div style="text-align: center; padding: 20px 0; border-bottom: 1px solid #333;">
          <h1 style="color: #F97316; font-size: 28px; margin: 0; letter-spacing: 2px;">RADAR</h1>
          <p style="color: #666; font-size: 12px; margin: 5px 0;">by Moodlight &mdash; {date_str}</p>
        </div>

        <div style="padding: 20px 0;">
          <p style="margin: 12px 0; line-height: 1.6; color: #ccc; font-size: 15px;">
            {html_body}
          </p>
        </div>

        <hr style="border: none; border-top: 1px solid #333; margin: 25px 0;">
        <p style="color: #555; font-size: 12px; text-align: center;">
          Your radar updates every morning at 6am.<br>
          <a href="https://moodlight.app" style="color: #F97316;">moodlight.app</a>
        </p>
      </body>
    </html>
    """


def send_radar_email(radar_md):
    """Send Radar email."""
    sender = os.getenv("EMAIL_ADDRESS")
    recipient = os.getenv("EMAIL_RECIPIENT", "")
    password = os.getenv("EMAIL_PASSWORD")

    if not all([sender, password, recipient]):
        print("Email credentials not configured. Skipping.")
        return False

    html = radar_to_html(radar_md)
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'Your Radar — {date_str}'
    msg['From'] = sender
    msg['To'] = recipient.split(",")[0].strip()
    msg.attach(MIMEText(html, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            for addr in [r.strip() for r in recipient.split(",") if r.strip()]:
                msg.replace_header('To', addr)
                server.send_message(msg)
                print(f"  Radar sent to {addr}")
        return True
    except Exception as e:
        print(f"  Email failed: {e}")
        return False


def main():
    print("=" * 60)
    print("RADAR by Moodlight — Daily Intelligence")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    engine = _get_engine()

    # Build context from all sources
    print("\n[1/4] Building signal context...")
    context = build_radar_context(engine)
    print(f"  Context length: {len(context)} chars")

    # Generate email
    print("\n[2/4] Generating Radar via Claude Opus...")
    radar_md = generate_radar_email(context)
    print(f"  Radar length: {len(radar_md)} chars")

    # Log topics for staleness tracking
    print("\n[3/4] Logging output topics...")
    try:
        from topic_intelligence import log_output_topics
        known_topics = ["economics", "technology & ai", "sports", "entertainment",
                        "media & journalism", "labor & work", "government",
                        "healthcare & wellbeing", "war", "energy", "climate"]
        mentioned = [t for t in known_topics if t.lower() in radar_md.lower()]
        if mentioned:
            log_output_topics(engine, "radar", mentioned)
            print(f"  Logged {len(mentioned)} topics")
    except Exception as e:
        print(f"  Topic logging failed (non-fatal): {e}")

    # Send email
    print("\n[4/4] Sending email...")
    send_radar_email(radar_md)

    # Print to stdout
    print("\n" + "=" * 60)
    print("GENERATED RADAR:")
    print("=" * 60)
    print(radar_md)
    print("\nDone.")


if __name__ == "__main__":
    main()
