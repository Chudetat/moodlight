import json
import os
from datetime import datetime, timezone
from anthropic import Anthropic
import pandas as pd
from sqlalchemy import text as sql_text
from strategic_frameworks import select_frameworks, get_framework_prompt, STRATEGIC_FRAMEWORKS
from db_helper import get_engine
from vlds_helper import calculate_brand_vlds

# Shared regulatory guidance used by both Strategic Brief Generator and Ask Moodlight
REGULATORY_GUIDANCE = """HEALTHCARE / PHARMA / MEDICAL DEVICES:
- Flag emotional tones (fear, nervousness, anger, grief, sadness, disappointment) that may face Medical Legal Review (MLR) scrutiny
- Prioritize "safe white space" — culturally appropriate AND unlikely to trigger regulatory concerns
- Recommend messaging that builds trust and credibility over provocative hooks
- Note velocity spikes that could indicate emerging issues requiring compliance awareness
- Frame recommendations as "MLR-friendly" where appropriate
- Ensure fair balance when discussing benefits vs. risks

FINANCIAL SERVICES / BANKING / INVESTMENTS:
- Never promise or imply guaranteed returns
- Flag any claims that could be seen as misleading by SEC, FINRA, or CFPB
- Include appropriate risk disclosure language in recommendations
- Avoid superlatives ("best," "guaranteed," "risk-free") without substantiation
- Be cautious with testimonials — results not typical disclaimers required
- Fair lending language required — no discriminatory implications

ALCOHOL / SPIRITS / BEER / WINE:
- Never target or appeal to audiences under 21
- No health benefit claims whatsoever
- Include responsible drinking messaging considerations
- Avoid associating alcohol with success, social acceptance, or sexual prowess
- Cannot show excessive consumption or intoxication positively
- Platform restrictions: Meta/Google have strict alcohol ad policies

CANNABIS / CBD:
- Highly fragmented state-by-state regulations — recommend geo-specific strategies
- No medical or health claims unless FDA-approved
- Strict age-gating requirements in all messaging
- Major platform restrictions: Meta, Google, TikTok prohibit cannabis ads
- Recommend owned media and experiential strategies over paid social
- Cannot target or appeal to minors in any way

INSURANCE:
- No guaranteed savings claims without substantiation
- State DOI regulations vary — flag need for state-specific compliance review
- Required disclosures on coverage limitations
- Fair treatment language required — no discriminatory implications
- Testimonials require "results may vary" disclaimers
- Avoid fear-based messaging that could be seen as coercive

LEGAL SERVICES:
- No guarantees of case outcomes whatsoever
- State bar regulations vary — recommend jurisdiction-specific review
- Required disclaimers on attorney advertising
- Restrictions on client testimonials in many states
- Cannot create unjustified expectations
- Avoid comparative claims against other firms without substantiation

For all industries: Consider regulatory and reputational risk when recommending bold creative angles. When in doubt, recommend client consult with their legal/compliance team before execution."""


def _build_enrichment(engine, username: str, user_need: str, df: pd.DataFrame) -> str:
    """Build brand/topic enrichment context for the strategic brief.

    Three-layer matching:
      Layer 1 — Brand match: VLDS v2 + competitive snapshot + recent alerts
      Layer 2 — Topic match: recent alerts for matching topics
      Layer 3 — No match: returns empty string (graceful fallback)
    """
    user_need_lower = user_need.lower()

    # Load watchlist brands
    with engine.connect() as conn:
        rows = conn.execute(
            sql_text("SELECT brand_name FROM brand_watchlist WHERE username = :username"),
            {"username": username},
        ).fetchall()
    brands = [r[0] for r in rows]

    # Layer 1: Brand match
    matched_brand = None
    for brand in brands:
        if brand.lower() in user_need_lower:
            matched_brand = brand
            break

    if matched_brand:
        sections = []
        brand_lower = matched_brand.lower()

        # Compute VLDS v2 for matched brand
        if "text" in df.columns:
            brand_df = df[df["text"].str.lower().str.contains(brand_lower, na=False)].copy()
            if "created_at" in brand_df.columns:
                brand_df = brand_df.dropna(subset=["created_at"])
            if len(brand_df) >= 5:
                vlds = calculate_brand_vlds(brand_df)
                if vlds:
                    v = vlds.get("velocity", 0)
                    v_label = vlds.get("velocity_label", "")
                    v_insight = vlds.get("velocity_insight", "")
                    l = vlds.get("longevity", 0)
                    l_label = vlds.get("longevity_label", "")
                    l_insight = vlds.get("longevity_insight", "")
                    d = vlds.get("density", 0)
                    d_label = vlds.get("density_label", "")
                    d_insight = vlds.get("density_insight", "")
                    sc = vlds.get("scarcity", 0)
                    sc_label = vlds.get("scarcity_label", "")
                    emp_label = vlds.get("empathy_label", "N/A")

                    # Top emotions
                    top_emo = vlds.get("top_emotions_detailed", [])
                    emo_str = ", ".join(
                        f"{e['emotion']} ({e['percentage']}%)" for e in top_emo[:3]
                    ) if top_emo else "N/A"

                    sections.append(
                        f"BRAND INTELLIGENCE — {matched_brand.upper()}:\n"
                        f"---\n"
                        f"  Velocity: {v:.2f} ({v_label}) — {v_insight}\n"
                        f"  Longevity: {l:.2f} ({l_label}) — {l_insight}\n"
                        f"  Density: {d:.2f} ({d_label}) — {d_insight}\n"
                        f"  Scarcity: {sc:.2f} ({sc_label})\n"
                        f"  Top Emotions: {emo_str}\n"
                        f"  Empathy: {emp_label}\n"
                        f"---"
                    )

        # Load competitive snapshot
        with engine.connect() as conn:
            comp_row = conn.execute(
                sql_text(
                    "SELECT snapshot_data FROM competitive_snapshots "
                    "WHERE LOWER(brand_name) = :brand "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"brand": brand_lower},
            ).fetchone()

        if comp_row:
            snapshot = comp_row[0]
            if isinstance(snapshot, str):
                try:
                    snap = json.loads(snapshot)
                except (json.JSONDecodeError, TypeError):
                    snap = {}
            else:
                snap = snapshot or {}

            comp_lines = []
            sov = snap.get("share_of_voice", {})
            if sov:
                comp_lines.append("  Share of Voice:")
                for name, pct in sorted(sov.items(), key=lambda x: -x[1]):
                    comp_lines.append(f"    {name}: {pct:.1f}%")

            vlds_comp = snap.get("vlds_comparison", {})
            if vlds_comp:
                # Compute velocity/density gaps vs competitor average
                comp_velocities = []
                comp_densities = []
                for comp_name, metrics in vlds_comp.items():
                    if isinstance(metrics, dict) and comp_name.lower() != brand_lower:
                        if "velocity" in metrics:
                            comp_velocities.append(metrics["velocity"])
                        if "density" in metrics:
                            comp_densities.append(metrics["density"])

                brand_metrics = vlds_comp.get(matched_brand, {})
                if isinstance(brand_metrics, dict):
                    brand_v = brand_metrics.get("velocity")
                    brand_d = brand_metrics.get("density")
                    if brand_v is not None and comp_velocities:
                        avg_cv = sum(comp_velocities) / len(comp_velocities)
                        comp_lines.append(f"  Velocity gap: {brand_v - avg_cv:+.2f} ({'brand accelerating faster than competitor avg' if brand_v > avg_cv else 'competitors accelerating faster'})")
                    if brand_d is not None and comp_densities:
                        avg_cd = sum(comp_densities) / len(comp_densities)
                        comp_lines.append(f"  Density gap: {brand_d - avg_cd:+.2f} ({'brand has more coverage' if brand_d > avg_cd else 'competitors have slightly more coverage'})")

            if comp_lines:
                sections.append("COMPETITIVE LANDSCAPE:\n" + "\n".join(comp_lines))

        # Load recent alerts for this brand
        with engine.connect() as conn:
            alert_rows = conn.execute(
                sql_text(
                    "SELECT alert_type, severity, title, summary "
                    "FROM alerts "
                    "WHERE username = :username AND timestamp > NOW() - INTERVAL '7 days' "
                    "AND brand = :brand "
                    "ORDER BY timestamp DESC LIMIT 20"
                ),
                {"username": username, "brand": matched_brand},
            ).fetchall()

        if alert_rows:
            alert_lines = []
            for row in alert_rows:
                sev = (row[1] or "MEDIUM").upper()
                atype = row[0] or "unknown"
                summary = row[3] or row[2] or ""
                alert_lines.append(f"  - [{sev}] {atype}: {summary[:200]}")
            sections.append(
                "RECENT INTELLIGENCE ALERTS (Last 7 Days):\n" + "\n".join(alert_lines)
            )

        if sections:
            return "\n\n".join(sections)
        return ""

    # Layer 2: Topic match
    with engine.connect() as conn:
        topic_rows = conn.execute(
            sql_text("SELECT topic_name FROM topic_watchlist WHERE username = :username"),
            {"username": username},
        ).fetchall()
    user_topics = [r[0] for r in topic_rows]

    matched_topics = [t for t in user_topics if t.lower() in user_need_lower]

    if matched_topics:
        # Load recent alerts for matching topics
        with engine.connect() as conn:
            placeholders = ", ".join(f":t{i}" for i in range(len(matched_topics)))
            params = {"username": username}
            params.update({f"t{i}": t for i, t in enumerate(matched_topics)})
            alert_rows = conn.execute(
                sql_text(
                    f"SELECT alert_type, severity, title, summary, topic "
                    f"FROM alerts "
                    f"WHERE username = :username AND timestamp > NOW() - INTERVAL '7 days' "
                    f"AND topic IN ({placeholders}) "
                    f"ORDER BY timestamp DESC LIMIT 20"
                ),
                params,
            ).fetchall()

        if alert_rows:
            alert_lines = []
            for row in alert_rows:
                sev = (row[1] or "MEDIUM").upper()
                atype = row[0] or "unknown"
                summary = row[3] or row[2] or ""
                topic = row[4] or ""
                alert_lines.append(f"  - [{sev}] {atype}: {summary[:200]} (Topic: {topic})")
            return (
                "RELEVANT INTELLIGENCE ALERTS (Last 7 Days):\n"
                "---\n" + "\n".join(alert_lines) + "\n---"
            )

    # Layer 3: No match
    return ""


def generate_strategic_brief(user_need: str, df: pd.DataFrame, username: str = None) -> tuple:
    """Generate strategic campaign brief using AI and Moodlight data"""

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    top_topics = df['topic'].value_counts().head(10).to_string() if 'topic' in df.columns else "No topic data"
    empathy_dist = df['empathy_label'].value_counts().to_string() if 'empathy_label' in df.columns else "No empathy data"
    top_emotions = df['emotion_top_1'].value_counts().head(10).to_string() if 'emotion_top_1' in df.columns else "No emotion data"
    geo_dist = df['country'].value_counts().head(10).to_string() if 'country' in df.columns else "No geographic data"
    source_dist = df['source'].value_counts().head(10).to_string() if 'source' in df.columns else "No source data"
    avg_empathy = f"{df['empathy_score'].mean():.1f}/100" if 'empathy_score' in df.columns else "N/A"

    try:
        velocity_df = pd.read_csv('topic_longevity.csv')
        velocity_data = velocity_df[['topic', 'velocity_score', 'longevity_score']].head(10).to_string()
    except Exception:
        velocity_data = "No velocity/longevity data available"

    try:
        density_df = pd.read_csv('topic_density.csv')
        density_data = density_df[['topic', 'density_score', 'post_count', 'primary_platform']].head(10).to_string()
    except Exception:
        density_data = "No density data available"

    try:
        scarcity_df = pd.read_csv('topic_scarcity.csv')
        scarcity_data = scarcity_df[['topic', 'scarcity_score', 'mention_count', 'opportunity']].head(10).to_string()
    except Exception:
        scarcity_data = "No scarcity data available"

    # Get actual headlines for real-time grounding with full metadata
    recent_headlines = ""
    viral_headlines = ""
    if 'text' in df.columns:
        headline_cols = ['text', 'topic', 'source', 'engagement', 'empathy_label', 'emotion_top_1']
        available_cols = [c for c in headline_cols if c in df.columns]

        # Most recent headlines (what just happened)
        if 'created_at' in df.columns:
            recent = df.nlargest(15, 'created_at')[available_cols].drop_duplicates('text')
            recent_headlines = "\n".join([
                f"- [{row.get('topic', 'N/A')}] {row['text'][:150]} | Source: {row.get('source', 'N/A')} | Empathy: {row.get('empathy_label', 'N/A')} | Emotion: {row.get('emotion_top_1', 'N/A')}"
                for _, row in recent.iterrows()
            ])

        # Most viral/high-engagement (what's resonating)
        if 'engagement' in df.columns:
            viral = df.nlargest(10, 'engagement')[available_cols].drop_duplicates('text')
            viral_headlines = "\n".join([
                f"- [{row.get('topic', 'N/A')}] {row['text'][:150]} | Engagement: {int(row.get('engagement', 0))} | Source: {row.get('source', 'N/A')} | Emotion: {row.get('emotion_top_1', 'N/A')}"
                for _, row in viral.iterrows()
            ])

    # Build brand/topic enrichment if username provided
    brand_context = ""
    if username:
        try:
            engine = get_engine()
            if engine:
                brand_context = _build_enrichment(engine, username, user_need, df)
        except Exception:
            brand_context = ""

    context = f"""
MOODLIGHT INTELLIGENCE SNAPSHOT
================================
TOP TOPICS (by mention volume):
{top_topics}

EMOTIONAL CLIMATE (top emotions detected):
{top_emotions}

EMPATHY DISTRIBUTION:
{empathy_dist}
Average Empathy Score: {avg_empathy}

GEOGRAPHIC HOTSPOTS:
{geo_dist}

SOURCE DISTRIBUTION (which publications/platforms are driving conversation):
{source_dist}

VELOCITY & LONGEVITY (Which topics are rising fast vs. enduring):
{velocity_data}

DENSITY (Topic saturation - high means crowded, low means opportunity):
{density_data}

SCARCITY (Underserved topics - high scarcity = white space opportunity):
{scarcity_data}

RECENT HEADLINES (What just happened - with source, empathy, emotion):
{recent_headlines if recent_headlines else "No recent headlines available"}

HIGH-ENGAGEMENT CONTENT (What's resonating now - with engagement scores):
{viral_headlines if viral_headlines else "No engagement data available"}

{brand_context}
Total Posts Analyzed: {len(df)}
"""

    # Select best frameworks for this request
    selected_frameworks = select_frameworks(user_need)
    framework_guidance = get_framework_prompt(selected_frameworks)

    prompt = f"""You are a senior strategist who believes most brand strategy is cowardice dressed as caution. You've built your reputation on the ideas that made clients nervous before making them successful. You find the uncomfortable truth competitors are too polite to say. You never recommend what a competitor could also do - if it's obvious, it's worthless. Your best work comes from tension, not consensus.

A client has come to you with this request:
"{user_need}"

Based on the following real-time intelligence data from Moodlight (which tracks empathy, emotions, trends, and strategic metrics across news and social media), create a strategic brief.

{context}

{framework_guidance}

If BRAND INTELLIGENCE or RELEVANT INTELLIGENCE ALERTS data is included in the intelligence snapshot, weave those insights into your analysis: brand VLDS into territorial mapping (Section 1), competitive gaps into your unexpected angle (Section 4), and recent alerts as real-time triggers (Section 5). Do not repeat raw numbers — interpret them strategically.

KEY METRICS TO CONSIDER:
- VELOCITY: How fast a topic is accelerating (high = trending now)
- LONGEVITY: How long a topic sustains interest (high = lasting movement)
- DENSITY: How saturated/crowded a topic is (high = hard to break through)
- SCARCITY: How underserved a topic is (high = white space opportunity)


Create a brief using the Cultural Momentum Matrix (CMM)™ structure:

## 1. WHERE TO PLAY: Cultural Territory Mapping

Analyze the data and identify:
- **Hot Zones**: Dominant topics (>10K mentions) — lead with authority, expect competition
- **Active Zones**: Growing topics (2K-10K mentions) — engage strategically, build expertise
- **Opportunity Zones**: Emerging topics (<2K mentions) — early mover advantage, test and learn
- **Avoid Zones**: High conflict, high risk topics to steer clear of

End with: "Territory Recommendation: [specific territory] because [data-backed reason]"

## 2. WHEN TO MOVE: Momentum Timing

Based on the current Mood Score, identify the timing zone:
- **Strike Zone (60-80)**: Optimal engagement window — audiences receptive but not oversaturated. Recommendation: ENGAGE NOW
- **Caution Zone (40-59)**: Wait for positive shift or proceed with extra sensitivity
- **Storm Zone (<40)**: Defensive positioning only
- **Peak Zone (80+)**: High competition, premium content required

Factor in Velocity (how fast topics are moving) and Longevity (how long they'll last).

End with: "Timing Recommendation: [ENGAGE NOW / WAIT / PROCEED WITH CAUTION] because [data-backed reason]"

## 3. WHAT TO SAY: Message Architecture

Based on the empathy score and emotional climate:
- **Empathy Calibration**: Match message warmth to current cultural mood
- **Tone Recommendation**: Specific guidance on voice and approach
- **Message Hierarchy**: What to lead with, what to support with
- **Creative Thought-Starter**: One campaign idea or hook that fits this moment

End with: "Consider: '[specific campaign thought-starter]'"

## 4. ⚡ UNEXPECTED ANGLE: The Insight They Didn't See Coming

This is where you earn your fee. Include ALL of the following:

- **Contrarian Take**: One insight that challenges conventional thinking about this category. What would surprise the client? What do they NOT expect to hear but need to?

- **Data Tension**: Look for contradictions (what people say vs. what they engage with, stated values vs. actual behavior). Call out one paradox in the data.

- **Cultural Parallel**: Reference one analogy from another brand, category, or cultural moment that illuminates the current opportunity.

- **Competitor Blind Spot**: What is one thing competitors in this space are likely missing right now?

- **Creative Spark**: One bold campaign idea or hook that ONLY works in this specific cultural moment. Not generic. Not safe. Something that makes the client lean forward.

End with: "The non-obvious move: [one sentence summary of the unexpected angle]"

## 5. 🔥 WHY NOW: The Real-Time Trigger

This brief must feel URGENT and TIMELY. Use the RECENT HEADLINES and HIGH-ENGAGEMENT CONTENT sections above. Include:

- **This Week's Catalyst**: Quote or paraphrase 2-3 specific headlines from the data above that are DIRECTLY RELEVANT to the client's request. Skip unrelated headlines even if they're high-engagement. Be specific - "The [topic] story about [specifics]" not generic references.

- **The Window**: Why does this opportunity exist RIGHT NOW but might not in 30 days? What's the expiration date on this insight?

- **Cultural Collision**: What current events from the headlines are colliding to create this specific opening?

End with: "Act now because: [one sentence on why timing matters]"

## 6. 🎯 MAKE IT REAL: Tangible Outputs

Based on the above analysis, provide:

**Opening Hooks (3 options):**
- One that leads with tension
- One that leads with aspiration
- One that's provocative/contrarian

**Campaign Concept (1 paragraph):**
A single activatable idea—name it, describe it in 2-3 sentences, explain why it fits this cultural moment.

**Platform Play:**
Which platform (X, LinkedIn, TikTok, OOH, etc.) is best suited for this moment and why? One sentence.

**First 48 Hours:**
If the client said "go" right now, what's the single most important action in the next 48 hours? Be specific.

**Steal This Line:**
One sentence the client can use verbatim in a deck, ad, or pitch tomorrow.

End with: "This is your starting point, not your ceiling."

---

Be bold and specific. Reference actual data points. Make decisions, not suggestions.

IMPORTANT: Do NOT include obvious "avoid" recommendations that any brand strategist already knows (e.g., "avoid war & foreign policy for brand safety"). Only mention Avoid Zones if:
1. The client's specific product/challenge intersects with that topic, OR
2. There's a non-obvious risk the client might miss

Focus on actionable opportunities, not generic warnings.

QUALITY CHECK: Before finalizing, delete any sentence a competitor's strategist could also write. If an insight isn't specific to THIS data and THIS moment, cut it.

End the brief with: "---
Powered by Moodlight's Cultural Momentum Matrix™"

{REGULATORY_GUIDANCE}
"""

    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=4000,
        system="You are a senior strategist who combines data intelligence with creative intuition. You speak plainly and give bold recommendations.",
        messages=[{"role": "user", "content": prompt}]
    )

    # Get framework names for email
    framework_names = [STRATEGIC_FRAMEWORKS[f]["name"] for f in selected_frameworks]
    return response.content[0].text, framework_names


def send_strategic_brief_email(recipient_email: str, user_need: str, brief: str, frameworks: list = None) -> bool:
    """Send strategic brief via email"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")

    if not all([sender, password]):
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'Your Moodlight Strategic Brief'
    msg['From'] = sender
    msg['To'] = recipient_email

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #6B46C1;">🎯 Your Strategic Brief</h1>
        <p style="color: #666; font-size: 14px;"><strong>Your request:</strong> "{user_need}"</p>
        <p style="color: #666; font-size: 14px;"><strong>Frameworks applied:</strong> {", ".join(frameworks) if frameworks else "Custom analysis"}</p>
        <hr style="border: 1px solid #eee;">
        <pre style="white-space: pre-wrap; font-family: Georgia, serif; font-size: 15px; line-height: 1.6;">
{brief}
        </pre>
        <hr style="border: 1px solid #eee;">
        <p style="color: #666; font-size: 12px;">
          Generated by <strong>Moodlight Intelligence</strong><br>
          Empathy Analytics for the Age of Connection<br>
          {datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")}
        </p>
      </body>
    </html>
    """

    msg.attach(MIMEText(html, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False
