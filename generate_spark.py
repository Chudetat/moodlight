#!/usr/bin/env python
"""
generate_spark.py
Generates "Spark" — a daily creative intelligence email.

Sharp cultural observations backed by real-time data. 90-second read.
For anyone who wants to feel smarter about the world.

Usage:
    python generate_spark.py
    python generate_spark.py --skip-email
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


def load_spark_data(engine):
    """Load data for Spark — prioritizes gaps and edges, not just top stories."""
    from sqlalchemy import text as sql_text

    now = datetime.now(timezone.utc)
    data = {}

    # 1. Top 15 news stories by intensity (24h) — raw material
    try:
        cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        headlines = pd.read_sql(
            sql_text("""
                SELECT text, topic, intensity, empathy_score, emotion_top_1,
                       source, created_at
                FROM news_scored
                WHERE created_at >= :cutoff
                ORDER BY intensity DESC
                LIMIT 15
            """),
            engine,
            params={"cutoff": cutoff_24h},
        )
        data["headlines"] = headlines
    except Exception as e:
        print(f"  Could not load headlines: {e}")
        data["headlines"] = pd.DataFrame()

    # 2. High-scarcity topics — underserved areas
    try:
        scarcity = pd.read_csv("topic_scarcity.csv")
        data["scarcity"] = scarcity
    except Exception as e:
        print(f"  Could not load scarcity data: {e}")
        data["scarcity"] = pd.DataFrame()

    # 3. VLDS snapshot per topic — velocity, density, scarcity scores
    try:
        density = pd.read_csv("topic_density.csv")
        data["density"] = density
    except Exception as e:
        print(f"  Could not load density data: {e}")
        data["density"] = pd.DataFrame()

    try:
        longevity = pd.read_csv("topic_longevity.csv")
        data["longevity"] = longevity
    except Exception as e:
        print(f"  Could not load longevity data: {e}")
        data["longevity"] = pd.DataFrame()

    # 4. Top social posts (24h) — lighter, more culturally varied material
    try:
        social = pd.read_sql(
            sql_text("""
                SELECT text, topic, intensity, empathy_score, emotion_top_1,
                       source, created_at
                FROM social_scored
                WHERE created_at >= :cutoff
                ORDER BY intensity DESC
                LIMIT 10
            """),
            engine,
            params={"cutoff": cutoff_24h},
        )
        data["social"] = social
    except Exception as e:
        print(f"  Could not load social data: {e}")
        data["social"] = pd.DataFrame()

    # 5. Emotion distribution (3d, top 5)
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

    # 5. Contrarian signals: merge density + longevity to find
    #    low-density + high-velocity topics (accelerating but not crowded)
    #    This is computed in build_spark_context from density + longevity data.

    return data


# ---------------------------------------------------------------------------
# 2. Context Building
# ---------------------------------------------------------------------------

def build_spark_context(data):
    """Build structured context for the Spark prompt."""
    sections = []

    now = datetime.now(timezone.utc)
    sections.append(f"SPARK DATA CONTEXT — {now.strftime('%B %d, %Y')}")
    sections.append("=" * 50)

    # RAW MATERIAL — top headlines
    hdl = data.get("headlines", pd.DataFrame())
    if not hdl.empty:
        lines = ["RAW MATERIAL (Top stories by intensity, last 24h):"]
        for _, row in hdl.iterrows():
            topic = row.get("topic", "N/A")
            emotion = row.get("emotion_top_1", "N/A")
            intensity = row.get("intensity", 0)
            text = str(row.get("text", ""))[:200]
            lines.append(f"  - [{topic}] {text} | emotion: {emotion} | intensity: {intensity:.1f}")
        sections.append("\n".join(lines))

    # SOCIAL PULSE — what people are actually talking about
    social = data.get("social", pd.DataFrame())
    if not social.empty:
        lines = ["SOCIAL PULSE (Top social posts by intensity, last 24h):"]
        for _, row in social.iterrows():
            topic = row.get("topic", "N/A")
            emotion = row.get("emotion_top_1", "N/A")
            intensity = row.get("intensity", 0)
            text = str(row.get("text", ""))[:200]
            lines.append(f"  - [{topic}] {text} | emotion: {emotion} | intensity: {intensity:.1f}")
        sections.append("\n".join(lines))

    # Build merged VLDS data for opportunity analysis
    density_df = data.get("density", pd.DataFrame())
    longevity_df = data.get("longevity", pd.DataFrame())
    scarcity_df = data.get("scarcity", pd.DataFrame())

    merged = None
    if not density_df.empty and "topic" in density_df.columns:
        merged = density_df[["topic"]].copy()
        if "density_score" in density_df.columns:
            merged["density"] = density_df["density_score"]
        if not longevity_df.empty and "topic" in longevity_df.columns and "velocity_score" in longevity_df.columns:
            vel_map = dict(zip(longevity_df["topic"], longevity_df["velocity_score"]))
            merged["velocity"] = merged["topic"].map(vel_map)
        if not scarcity_df.empty and "topic" in scarcity_df.columns and "scarcity_score" in scarcity_df.columns:
            scar_map = dict(zip(scarcity_df["topic"], scarcity_df["scarcity_score"]))
            merged["scarcity"] = merged["topic"].map(scar_map)

    # OPPORTUNITY ZONES — high scarcity + low density
    if merged is not None and "scarcity" in merged.columns and "density" in merged.columns:
        opp = merged.dropna(subset=["scarcity", "density"])
        opp = opp[(opp["scarcity"] > 0.5) & (opp["density"] < 0.5)].sort_values(
            "scarcity", ascending=False
        )
        if not opp.empty:
            lines = ["OPPORTUNITY ZONES (High scarcity + low density — gaps nobody's filling):"]
            for _, row in opp.head(5).iterrows():
                lines.append(
                    f"  - {row['topic']}: scarcity={row['scarcity']:.2f}, density={row['density']:.2f}"
                )
            sections.append("\n".join(lines))

    # RISING EDGES — high velocity + low density
    if merged is not None and "velocity" in merged.columns and "density" in merged.columns:
        edges = merged.dropna(subset=["velocity", "density"])
        edges = edges[(edges["velocity"] > 0.5) & (edges["density"] < 0.5)].sort_values(
            "velocity", ascending=False
        )
        if not edges.empty:
            lines = ["RISING EDGES (High velocity + low density — emerging, not crowded):"]
            for _, row in edges.head(5).iterrows():
                lines.append(
                    f"  - {row['topic']}: velocity={row['velocity']:.2f}, density={row['density']:.2f}"
                )
            sections.append("\n".join(lines))

    # SATURATED (AVOID)
    if merged is not None and "density" in merged.columns:
        sat = merged[merged["density"] > 0.7].sort_values("density", ascending=False)
        if not sat.empty:
            lines = ["SATURATED — AVOID (High density — everyone's already here):"]
            for _, row in sat.head(5).iterrows():
                vel_str = f", velocity={row['velocity']:.2f}" if pd.notna(row.get("velocity")) else ""
                lines.append(f"  - {row['topic']}: density={row['density']:.2f}{vel_str}")
            sections.append("\n".join(lines))

    # EMOTIONAL CLIMATE
    emo = data.get("emotions", pd.DataFrame())
    if not emo.empty:
        total = emo["cnt"].sum()
        lines = ["EMOTIONAL CLIMATE (Top emotions across all coverage, 3d):"]
        for _, row in emo.iterrows():
            pct = (row["cnt"] / total) * 100
            lines.append(f"  - {row['emotion_top_1']}: {pct:.0f}%")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# 3. Spark Generation (Claude)
# ---------------------------------------------------------------------------

SPARK_SYSTEM_PROMPT = """You are the writer behind Spark — a daily email that makes people feel smarter about the world in 90 seconds.

Your reader might be a strategist at an agency or a parent scrolling over coffee. Write for both. No jargon. No industry-speak. Just sharp observations about what's happening in culture right now — and why it matters to how people live, work, and think.

You are not a creative director. You are not pitching campaigns. You are a curious, observant person who reads everything and connects dots that other people miss. Your job is to make the reader say "huh, I never thought about it that way" at least once.

RULES:

1. EMPATHY FIRST, DATA SECOND. Lead with the most emotionally resonant human observation — how people are feeling, behaving, withdrawing, or surprising each other. Then connect it to the cultural, economic, or global forces driving it. The reader should feel something before they learn something. "Two-thirds of Americans stopped going to weddings" is a Spark lead. "Oil prices rose 4%" is not.

2. OBSERVATIONS, NOT IDEAS. Don't tell people what to make or build. Tell them what's interesting and why. If the reader walks away thinking differently about something they'll encounter today, you've won.

3. NO HYPOTHETICAL CAMPAIGNS. Never pitch a fake ad, brand concept, or content series for an imaginary company. That's not inspiring — it's fan fiction. Talk about what's real.

4. SKIP THE OBVIOUS. If everyone's talking about it, you don't need to explain it. Find what's underneath — the second-order effect, the weird contradiction, the thing hiding in plain sight.

5. BE CONCRETE. Reference the actual data — real numbers, real headlines, real shifts. But wear it lightly. You're not writing a report. One well-placed data point is worth more than five.

6. CONNECT THINGS THAT DON'T OBVIOUSLY CONNECT. The best observations sit at the intersection of two unrelated trends. A labor shift + an entertainment trend. An economic indicator + a change in how people talk online. Find those collisions.

7. TONE: Warm, sharp, curious. Like a smart friend who texts you something interesting they noticed. Conversational, not performative. Funny when it's natural, not when it's forced. Never snarky, never preachy, never breathless. If it sounds like a LinkedIn post or a TED talk, start over.

8. KEEP IT SHORT. The whole thing should take 90 seconds to read. Every sentence should earn its spot. If you can cut a sentence without losing meaning, cut it.

9. EVEN WHEN THE NEWS IS HEAVY, FIND THE HUMAN ANGLE. You're not ignoring hard things — you're finding the part of the story that's about how people actually respond, adapt, and surprise each other. That's where inspiration lives.

OUTPUT FORMAT — use this EXACT structure:

# SPARK
*[Full date]*

## [A sharp, specific headline — not clickbait, but something that earns curiosity]

[3-4 paragraphs. Lead with the most emotionally resonant human observation — how people are feeling, behaving, or being affected. Then connect it to the forces driving it. The reader should feel something before they learn something. End with the "huh" moment — the insight the reader will carry with them.]

---

## ALSO WORTH NOTICING

**[Short headline]**
[2-3 sentences. A different observation from a different part of the data. Brief, punchy, complete.]

**[Short headline]**
[2-3 sentences. Different topic, different angle.]

---

*Spark — daily from Moodlight*
"""


def generate_spark(context):
    """Generate the Spark newsletter via Claude Sonnet."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        system=SPARK_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Generate today's Spark using this data:\n\n{context}",
        }],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# 4. Email
# ---------------------------------------------------------------------------

def _spark_email_html(newsletter_md):
    """Convert Spark markdown to branded HTML email."""
    from mood_report_publisher import markdown_to_newsletter_html

    # Convert markdown body
    body_html = markdown_to_newsletter_html(newsletter_md)

    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    return f"""
    <html>
      <body style="margin: 0; padding: 0; background: #0f0f0f; font-family: 'Helvetica Neue', Arial, sans-serif;">
        <div style="max-width: 640px; margin: 0 auto; padding: 0;">

          <!-- Header -->
          <div style="background: #0f0f0f; padding: 32px 24px 20px 24px; text-align: center;">
            <h1 style="margin: 0; font-size: 36px; font-weight: 800; letter-spacing: 3px; color: #F97316;">
              SPARK
            </h1>
            <p style="margin: 6px 0 0 0; font-size: 13px; color: #888; letter-spacing: 1px;">
              {date_str} &middot; Daily Creative Intelligence
            </p>
          </div>

          <!-- Body -->
          <div style="background: #ffffff; padding: 28px 24px; border-radius: 0;">
            {body_html}
          </div>

          <!-- Footer -->
          <div style="background: #0f0f0f; padding: 20px 24px; text-align: center;">
            <p style="margin: 0; font-size: 12px; color: #666;">
              Spark &mdash; daily creative intelligence from Moodlight
            </p>
          </div>

        </div>
      </body>
    </html>
    """


def email_spark(newsletter_md):
    """Email the Spark newsletter."""
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    recipient = os.getenv("EMAIL_RECIPIENT", "")

    if not all([sender, password, recipient]):
        print("  Email credentials not configured. Skipping email.")
        return False

    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    html_body = _spark_email_html(newsletter_md)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Spark — {date_str}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"  Spark emailed to {recipient}")
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
    print("SPARK — Daily Creative Intelligence")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # 1. Connect
    engine = _get_engine()

    # 2. Load data
    print("\n[1/4] Loading spark data...")
    data = load_spark_data(engine)

    has_data = any(
        not df.empty for df in data.values() if isinstance(df, pd.DataFrame)
    )
    if not has_data:
        print("No data available. Cannot generate Spark.")
        return

    # 3. Build context
    print("[2/4] Building context...")
    context = build_spark_context(data)
    print(f"  Context length: {len(context)} chars")

    # 4. Generate
    print("[3/4] Generating Spark via Claude Sonnet...")
    spark_md = generate_spark(context)
    print(f"  Spark length: {len(spark_md)} chars")

    # 5. Email
    if skip_email:
        print("[4/4] Skipping email (--skip-email)")
    else:
        print("[4/4] Emailing Spark...")
        email_spark(spark_md)

    # Print to stdout
    print("\n" + "=" * 60)
    print("GENERATED SPARK:")
    print("=" * 60)
    print(spark_md)

    print("\nDone.")


if __name__ == "__main__":
    main()
