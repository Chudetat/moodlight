#!/usr/bin/env python
"""
generate_radar.py
Generates "Radar by Moodlight" — a daily email that surfaces societal patterns
hiding in plain sight.

Uses empathy scoring, emotion clustering, and cross-topic pattern detection
to find the human stories that reveal where we are as a society.
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
    """Build empathy-weighted, pattern-clustered context for Radar."""
    from sqlalchemy import text as sql_text
    sections = []

    # ── 1. Emotional patterns by topic (clustered signals, not individual stories) ──
    try:
        pattern_df = pd.read_sql(sql_text("""
            SELECT topic, emotion_top_1,
                   COUNT(*) AS story_count,
                   AVG(empathy_score) AS avg_empathy,
                   MAX(empathy_score) AS peak_empathy,
                   AVG(intensity) AS avg_intensity
            FROM news_scored
            WHERE created_at >= NOW() - INTERVAL '72 hours'
              AND empathy_score IS NOT NULL
              AND emotion_top_1 IS NOT NULL
            GROUP BY topic, emotion_top_1
            HAVING COUNT(*) >= 3
            ORDER BY avg_empathy DESC
            LIMIT 20
        """), engine)
        if not pattern_df.empty:
            lines = ["EMOTIONAL PATTERNS BY TOPIC (clustered signals, not individual stories)"]
            lines.append("=" * 50)
            for _, row in pattern_df.iterrows():
                lines.append(
                    f"  [{row['topic']}] emotion: {row['emotion_top_1']}, "
                    f"stories: {int(row['story_count'])}, "
                    f"avg empathy: {row['avg_empathy']:.4f}, "
                    f"peak: {row['peak_empathy']:.4f}"
                )
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Emotional patterns failed: {e}")

    # ── 2. High-empathy stories (the headlines behind the patterns) ──
    try:
        top_stories = pd.read_sql(sql_text("""
            SELECT text, topic, empathy_score, emotion_top_1, intensity, created_at
            FROM news_scored
            WHERE created_at >= NOW() - INTERVAL '72 hours'
              AND empathy_score > 0.08
            ORDER BY empathy_score DESC
            LIMIT 40
        """), engine)
        if not top_stories.empty:
            lines = ["HIGH-EMPATHY STORIES (the headlines behind the patterns)"]
            lines.append("=" * 50)
            for _, row in top_stories.iterrows():
                lines.append(
                    f"  [{row['topic']}] [{row.get('emotion_top_1', '?')}] "
                    f"[empathy: {row['empathy_score']:.4f}] "
                    f"{row['text'][:300]}"
                )
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"  High-empathy stories failed: {e}")

    # ── 3. Social posts ranked by empathy (what people are processing) ──
    try:
        social_df = pd.read_sql(sql_text("""
            SELECT text, topic, source, emotion_top_1, empathy_score
            FROM social_scored
            WHERE created_at >= NOW() - INTERVAL '48 hours'
              AND empathy_score IS NOT NULL
            ORDER BY empathy_score DESC
            LIMIT 25
        """), engine)
        if not social_df.empty:
            lines = ["SOCIAL — WHAT PEOPLE ARE PROCESSING"]
            lines.append("=" * 50)
            for _, row in social_df.iterrows():
                lines.append(
                    f"  [{row.get('topic', '?')}] [{row.get('emotion_top_1', '?')}] "
                    f"[{row.get('source', '?')}] "
                    f"\"{row['text'][:250]}\""
                )
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Social posts failed: {e}")

    # ── 4. Emotion shifts (what changed in 24h vs prior 24h) ──
    try:
        shift_df = pd.read_sql(sql_text("""
            WITH recent AS (
                SELECT emotion_top_1, COUNT(*) AS cnt
                FROM news_scored
                WHERE created_at >= NOW() - INTERVAL '24 hours' AND emotion_top_1 IS NOT NULL
                GROUP BY emotion_top_1
            ),
            prior AS (
                SELECT emotion_top_1, COUNT(*) AS cnt
                FROM news_scored
                WHERE created_at >= NOW() - INTERVAL '48 hours'
                  AND created_at < NOW() - INTERVAL '24 hours'
                  AND emotion_top_1 IS NOT NULL
                GROUP BY emotion_top_1
            )
            SELECT COALESCE(r.emotion_top_1, p.emotion_top_1) AS emotion,
                   COALESCE(r.cnt, 0) AS recent_count,
                   COALESCE(p.cnt, 0) AS prior_count,
                   COALESCE(r.cnt, 0) - COALESCE(p.cnt, 0) AS shift
            FROM recent r
            FULL OUTER JOIN prior p ON r.emotion_top_1 = p.emotion_top_1
            ORDER BY ABS(COALESCE(r.cnt, 0) - COALESCE(p.cnt, 0)) DESC
        """), engine)
        if not shift_df.empty:
            lines = ["EMOTION SHIFTS (last 24h vs prior 24h — what changed)"]
            lines.append("=" * 50)
            for _, row in shift_df.iterrows():
                direction = "UP" if row['shift'] > 0 else "DOWN" if row['shift'] < 0 else "FLAT"
                lines.append(
                    f"  {row['emotion']}: {direction} "
                    f"({row['prior_count']} -> {row['recent_count']}, shift: {row['shift']:+d})"
                )
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Emotion shifts failed: {e}")

    # ── 5. Empathy outliers (outsized emotional response vs topic average) ──
    try:
        outlier_df = pd.read_sql(sql_text("""
            WITH topic_avg AS (
                SELECT topic, AVG(empathy_score) AS avg_emp
                FROM news_scored
                WHERE created_at >= NOW() - INTERVAL '72 hours' AND empathy_score IS NOT NULL
                GROUP BY topic
            )
            SELECT n.text, n.topic, n.empathy_score, n.emotion_top_1,
                   n.empathy_score - t.avg_emp AS empathy_above_avg
            FROM news_scored n
            JOIN topic_avg t ON n.topic = t.topic
            WHERE n.created_at >= NOW() - INTERVAL '72 hours'
              AND n.empathy_score IS NOT NULL
            ORDER BY empathy_above_avg DESC
            LIMIT 10
        """), engine)
        if not outlier_df.empty:
            lines = ["EMPATHY OUTLIERS (outsized emotional response vs topic average)"]
            lines.append("=" * 50)
            for _, row in outlier_df.iterrows():
                above = row.get('empathy_above_avg', 0) or 0
                lines.append(
                    f"  [+{above:.4f} above avg] [{row.get('emotion_top_1', '?')}] "
                    f"{row['text'][:300]}"
                )
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Empathy outliers failed: {e}")

    # ── 6. Quiet but deeply felt (high empathy, low news intensity) ──
    try:
        quiet_df = pd.read_sql(sql_text("""
            SELECT text, topic, empathy_score, emotion_top_1, intensity
            FROM news_scored
            WHERE created_at >= NOW() - INTERVAL '72 hours'
              AND empathy_score > 0.10
              AND intensity <= 3
            ORDER BY empathy_score DESC
            LIMIT 10
        """), engine)
        if not quiet_df.empty:
            lines = ["QUIET BUT DEEPLY FELT (high empathy, low news intensity)"]
            lines.append("=" * 50)
            for _, row in quiet_df.iterrows():
                lines.append(
                    f"  [empathy: {row['empathy_score']:.4f}] "
                    f"[{row.get('emotion_top_1', '?')}] "
                    f"{row['text'][:300]}"
                )
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Quiet stories failed: {e}")

    # ── 7. Recurring societal themes (multi-week arcs via Haiku) ──
    try:
        from theme_detector import detect_and_persist_themes, format_themes_context
        themes = detect_and_persist_themes(engine)
        if themes:
            sections.append(format_themes_context(themes, top_n=5))
    except Exception as e:
        print(f"  Theme detection failed (non-fatal): {e}")

    # ── 7b. Topic intelligence (freshness/staleness context) ──
    try:
        from topic_intelligence import compute_topic_intelligence, format_intelligence_context
        topics = compute_topic_intelligence(engine, output_type="radar")
        if topics:
            sections.append(format_intelligence_context(topics, top_n=10))
    except Exception as e:
        print(f"  Topic intelligence failed: {e}")

    # ── 8. Light economic/market context (forces underneath the human stories) ──
    try:
        mkt_df = pd.read_sql(sql_text("""
            SELECT symbol, name, price, change_percent
            FROM markets
            WHERE timestamp::timestamptz >= NOW() - INTERVAL '24 hours'
            ORDER BY timestamp DESC
        """), engine)
        if not mkt_df.empty:
            latest = mkt_df.drop_duplicates(subset=['symbol'], keep='first')
            lines = ["BACKGROUND: ECONOMIC FORCES (use only when they explain a human pattern)"]
            lines.append("=" * 50)
            for _, row in latest.iterrows():
                try:
                    chg = float(row.get('change_percent', 0) or 0)
                except (ValueError, TypeError):
                    chg = 0
                lines.append(f"  {row['name']}: {'up' if chg > 0 else 'down'} {abs(chg):.2f}%")
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Markets failed: {e}")

    try:
        from db_helper import load_commodity_data
        comm_df = load_commodity_data(days=14)
        if not comm_df.empty:
            price_df = comm_df[comm_df["metric_name"] == "price"]
            if not price_df.empty:
                latest = price_df.sort_values("snapshot_date").groupby("scope_name").last().reset_index()
                lines = ["BACKGROUND: COMMODITY PRICES"]
                lines.append("=" * 50)
                for _, row in latest.iterrows():
                    lines.append(f"  {row['scope_name']}: ${row['metric_value']:.2f}")
                sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Commodities failed: {e}")

    try:
        from db_helper import load_economic_data
        econ_df = load_economic_data(days=730)
        if not econ_df.empty:
            latest = econ_df.sort_values("snapshot_date").groupby("metric_name").last().reset_index()
            lines = ["BACKGROUND: ECONOMIC INDICATORS"]
            lines.append("=" * 50)
            for _, row in latest.iterrows():
                lines.append(f"  {row['metric_name']}: {row['metric_value']:.2f}")
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"  Economic indicators failed: {e}")

    return "\n\n".join(sections)


RADAR_SYSTEM_PROMPT = """You write "Radar by Moodlight" — a daily email that surfaces the societal patterns hiding in plain sight.

Not individual feel-good stories. Not LinkedIn inspiration. Not news roundups. You find the SOCIETAL-LEVEL shifts that reveal something true about how we're living right now — and you tell them as human stories, not data reports.

The loneliness epidemic. The erosion of institutional trust. A generation's broken relationship with money. Crisis fatigue rewiring how people process information. Remote work reshaping what "community" means. These are the stories you find — the tectonic plates moving underneath daily life.

Your voice: Clear-eyed. Warm but never sentimental. You write like a great magazine feature compressed into a paragraph — the kind of piece someone reads and then sits with for an hour. You never exploit pain. You never moralize. You observe, you connect, you illuminate.

Your reader is smart. Many work in branding, communications, or strategy — but this is NOT a branding newsletter. You never say "brands should..." or "this means for marketers..." You just tell the human story so well that anyone who communicates with humans for a living can't help but rethink their assumptions.

STRUCTURE:

Open with 1-2 sentences that name the pattern you're seeing today. Not a feeling — a PATTERN. "Something is shifting in how people talk about money." or "There's a trust fracture running through three completely unrelated stories today."

Then 2-3 STORIES — each one is a window into a SOCIETAL PATTERN, not an individual anecdote. Each gets:
1. A topic label on its own line — just the pattern name in ALL CAPS, like "THE LONELINESS EPIDEMIC" or "THE NESTING ECONOMY" or "CAREER VERTIGO". No numbers, no markdown headers, no "###". Just the label.
2. A subtitle in bold — one sentence that captures the pattern.
3. The evidence — multiple data points that reveal the pattern (cluster of headlines, emotion shifts, social signals). Not one story — a PATTERN of stories.
4. "What this is really about:" — the deeper societal shift underneath. Loneliness, trust, identity, security, belonging, exhaustion.
5. One sentence connecting this pattern to another one in today's edition, if a connection exists.

FORMAT RULES:
- Do NOT use markdown headers (no #, ##, ###). Use ALL CAPS labels for topic names.
- Do NOT number the topics (no "1.", "2.", "3."). Each topic label speaks for itself.
- Use --- between sections for visual separation.

Then: "THE UNDERCURRENT" — the single deepest thread connecting today's patterns. What does today's data say about where we are as a society? This is the paragraph people screenshot and send to someone.

End with: "Your radar updates every morning at 6am."

CRITICAL RULES:
- PATTERNS over anecdotes. Always. If you can't point to multiple signals confirming a societal trend, don't include it.
- Individual stories are EVIDENCE of patterns, not the point themselves. A house fire is not a story. A house fire + a spike in grief-related social posts + declining community safety metrics = a story about fraying social infrastructure.
- NEVER mention scores, system metrics, VLDS, or any internal jargon.
- NEVER give branding advice. Never say "brands should" or "marketers need to." The reader will connect those dots themselves.
- High-empathy + low-volume signals are more interesting than high-volume stories everyone already knows.
- Emotion SHIFTS matter more than absolute levels. What CHANGED tells you more than what IS.
- Target 500-700 words. Dense with meaning, not words.
- Do NOT inject facts from training data. Only use what the data provides.

RECURRING THEMES:
When societal themes data is provided, PREFER patterns that have been building over multiple days. A theme that has persisted for 7+ days across multiple topics is more significant than a brand-new spike. Use growth rate to spot which patterns are accelerating vs plateauing. You don't need to use every theme — pick the 2-3 most resonant and weave them into your stories. Evidence headlines under each theme are your raw material.

FRESHNESS RULE:
Every edition of Radar MUST feature different themes than recent editions. Never repeat the same theme two days in a row. If the data marks themes as suppressed or recently featured, find something new — there is always a pattern hiding in the data that hasn't been told yet.

SLOW DAYS:
If the data says it's a slow day with fewer strong themes, do NOT pad with weak stories. Instead: go DEEP on 1-2 stories. One rich, deeply-reported pattern with layered evidence is better than three thin ones. Use "quiet but deeply felt" stories — high empathy, low coverage — as your raw material on slow days. These are often the best editions.

DATA DISCIPLINE:
Only reference a data source when directly and obviously relevant. Never force economic data into an insight just to prove it exists. Markets and commodities are BACKGROUND FORCES that explain human patterns — never lead with them. If they don't connect to a human story, leave them out entirely."""


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

    html_body = radar_md

    # Remove markdown headers (###, ##, #) — we use ALL CAPS labels instead
    html_body = re.sub(r'^#{1,3}\s+', '', html_body, flags=re.MULTILINE)

    # Bold
    html_body = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_body)

    # Topic labels: ALL CAPS lines (3+ words, all uppercase/spaces/punctuation)
    # These become large styled visual blocks with left orange border
    html_body = re.sub(
        r'^([A-Z][A-Z\s\'\'\-&,]{6,})$',
        r'<div style="margin-top: 35px; margin-bottom: 14px; padding: 14px 18px; '
        r'border-left: 4px solid #F97316; background: #1a1a1a;">'
        r'<span style="color: #F97316; font-size: 20px; font-weight: bold; '
        r'letter-spacing: 2px;">\1</span></div>',
        html_body,
        flags=re.MULTILINE
    )

    # Special section: THE UNDERCURRENT (distinct styling — full orange background)
    for header in ["THE UNDERCURRENT", "THE THREAD"]:
        styled = (
            f'<div style="margin-top: 40px; margin-bottom: 14px; padding: 14px 18px; '
            f'background: #F97316; border-radius: 4px;">'
            f'<span style="color: white; font-size: 18px; font-weight: bold; '
            f'letter-spacing: 2px;">{header}</span></div>'
        )
        html_body = html_body.replace(
            f'<div style="margin-top: 35px; margin-bottom: 14px; padding: 14px 18px; '
            f'border-left: 4px solid #F97316; background: #1a1a1a;">'
            f'<span style="color: #F97316; font-size: 20px; font-weight: bold; '
            f'letter-spacing: 2px;">{header}</span></div>',
            styled
        )

    # Inline labels
    html_body = re.sub(
        r'(What this is really about:)',
        r'<strong style="color: #F97316;">\1</strong>',
        html_body
    )
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

    # Horizontal rules
    html_body = html_body.replace('---', '<hr style="border: none; border-top: 1px solid #333; margin: 20px 0;">')

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
    print("RADAR by Moodlight — Societal Patterns")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    engine = _get_engine()

    # Build context from empathy-weighted sources
    print("\n[1/4] Building empathy-weighted context...")
    context = build_radar_context(engine)
    print(f"  Context length: {len(context)} chars")

    # Generate email
    print("\n[2/4] Generating Radar via Claude Opus...")
    radar_md = generate_radar_email(context)
    print(f"  Radar length: {len(radar_md)} chars")

    # Log themes for recency suppression (prevents repeats)
    print("\n[3/4] Logging featured themes...")
    try:
        from theme_detector import log_radar_themes
        # Detect which theme labels appeared in the output by matching ALL CAPS lines
        import re
        featured_slugs = []
        for line in radar_md.split("\n"):
            line = line.strip()
            # Match ALL CAPS lines that look like theme labels
            if re.match(r'^[A-Z][A-Z\s\'\'\-&,]{6,}$', line):
                slug = re.sub(r'[^a-z0-9\s]', '', line.lower().strip())
                slug = re.sub(r'\s+', '-', slug)
                if slug and slug not in ["the-undercurrent", "the-thread", "radar-by-moodlight"]:
                    featured_slugs.append(slug)
        if featured_slugs:
            log_radar_themes(engine, featured_slugs)
            print(f"  Logged {len(featured_slugs)} themes: {', '.join(featured_slugs)}")
        else:
            print("  No themes detected in output")
    except Exception as e:
        print(f"  Theme logging failed (non-fatal): {e}")

    # Also log traditional topics for staleness tracking
    try:
        from topic_intelligence import log_output_topics
        known_topics = ["economics", "technology & ai", "sports", "entertainment",
                        "media & journalism", "labor & work", "government",
                        "healthcare & wellbeing", "war", "energy", "climate"]
        mentioned = [t for t in known_topics if t.lower() in radar_md.lower()]
        if mentioned:
            log_output_topics(engine, "radar", mentioned)
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
