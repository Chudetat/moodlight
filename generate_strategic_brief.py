import json
import os
from datetime import datetime, timezone, timedelta
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
                        f"  Velocity: {v_label} [raw: {v:.2f}] — {v_insight}\n"
                        f"  Longevity: {l_label} [raw: {l:.2f}] — {l_insight}\n"
                        f"  Density: {d_label} [raw: {d:.2f}] — {d_insight}\n"
                        f"  Scarcity: {sc_label} [raw: {sc:.2f}]\n"
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


def _load_campaign_precedents(user_need: str, df: pd.DataFrame) -> str:
    """Retrieve the most relevant campaign precedents for the current cultural moment.

    Scores each campaign in the database by keyword overlap with today's headlines,
    topics, emotions, and the client's request. Returns formatted context for the
    top 5 matches.
    """
    db_path = os.path.join(os.path.dirname(__file__), "campaign_database.json")
    try:
        with open(db_path) as f:
            campaigns = json.load(f)
    except Exception:
        return ""

    if not campaigns:
        return ""

    # Build matching context from today's data
    headline_text = ""
    topics = []
    emotions = []
    if "text" in df.columns:
        headline_text = " ".join(df["text"].astype(str).tolist()).lower()
    if "topic" in df.columns:
        topics = df["topic"].value_counts().head(5).index.tolist()
    if "emotion_top_1" in df.columns:
        emotions = df["emotion_top_1"].value_counts().head(3).index.tolist()

    user_need_lower = user_need.lower()

    def score_campaign(camp):
        score = 0
        tension = camp.get("cultural_tension", "").lower()
        insight = camp.get("insight", "").lower()
        why = camp.get("why_it_worked", "").lower()
        tags = [t.lower() for t in camp.get("category_tags", [])]
        emo_reg = camp.get("emotional_register", "").lower()

        # Topic match
        for topic in topics:
            t = topic.lower()
            if t in tension or t in insight:
                score += 3

        # Emotion match
        for emo in emotions:
            if emo.lower() in emo_reg:
                score += 2

        # User need keyword match
        need_words = [w for w in user_need_lower.split() if len(w) > 4]
        for w in need_words:
            if w in tension or w in insight or w in why:
                score += 1.5

        # Headline keyword overlap
        tension_words = [w for w in tension.split() if len(w) > 5]
        for w in tension_words:
            if w in headline_text:
                score += 0.3

        # Tag bonuses for common strategic needs
        tag_bonuses = {
            "empathy": 2, "social impact": 1.5, "revelation": 1.5,
            "cultural moment": 2, "crisis response": 1.5, "subversion": 1,
            "provocation": 1, "reframe": 1.5, "authenticity": 1,
            "brand platform": 1, "long-running": 1,
        }
        for tag in tags:
            score += tag_bonuses.get(tag, 0)

        return score

    scored = [(c, score_campaign(c)) for c in campaigns]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:5]

    if top[0][1] < 3:
        return ""  # No strong matches

    lines = [
        "CREATIVE PRECEDENTS — Award-winning campaigns that worked in similar cultural conditions:\n"
    ]
    for i, (camp, _sc) in enumerate(top, 1):
        lines.append(f"PRECEDENT {i}: {camp['campaign']} ({camp['brand']}, {camp['year']})")
        lines.append(f"  Cultural tension: {camp['cultural_tension']}")
        lines.append(f"  Insight: {camp['insight']}")
        lines.append(f"  What they did: {camp['what_they_did']}")
        lines.append(f"  Why it worked: {camp['why_it_worked']}")
        lines.append(f"  Emotional register: {camp.get('emotional_register', 'N/A')}")
        lines.append(f"  Tags: {', '.join(camp.get('category_tags', []))}")
        lines.append("")

    return "\n".join(lines)


def generate_strategic_brief(user_need: str, df: pd.DataFrame, username: str = None) -> tuple:
    """Generate strategic campaign brief using AI and Moodlight data"""

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    top_topics = df['topic'].value_counts().head(10).to_string() if 'topic' in df.columns else "No topic data"
    empathy_dist = df['empathy_label'].value_counts().to_string() if 'empathy_label' in df.columns else "No empathy data"
    top_emotions = df['emotion_top_1'].value_counts().head(10).to_string() if 'emotion_top_1' in df.columns else "No emotion data"
    geo_dist = df['country'].value_counts().head(10).to_string() if 'country' in df.columns else "No geographic data"
    source_dist = df['source'].value_counts().head(10).to_string() if 'source' in df.columns else "No source data"
    avg_empathy = f"{df['empathy_score'].mean():.1f}/100" if 'empathy_score' in df.columns else "N/A"

    velocity_df = pd.DataFrame()
    density_df = pd.DataFrame()
    scarcity_df = pd.DataFrame()

    # Read VLDS from PostgreSQL (not CSVs — those don't exist on Railway)
    _sb_engine = get_engine()
    if _sb_engine:
        from sqlalchemy import text as _sb_text
        try:
            velocity_df = pd.read_sql(_sb_text("SELECT topic, velocity_score, longevity_score FROM topic_longevity"), _sb_engine)
            velocity_data = velocity_df[['topic', 'velocity_score', 'longevity_score']].head(10).to_string()
        except Exception:
            velocity_data = "No velocity/longevity data available"

        try:
            density_df = pd.read_sql(_sb_text("SELECT topic, density_score, post_count, primary_platform FROM topic_density"), _sb_engine)
            density_data = density_df[['topic', 'density_score', 'post_count', 'primary_platform']].head(10).to_string()
        except Exception:
            density_data = "No density data available"

        try:
            scarcity_df = pd.read_sql(_sb_text("SELECT topic, scarcity_score, mention_count, opportunity FROM topic_scarcity"), _sb_engine)
            scarcity_data = scarcity_df[['topic', 'scarcity_score', 'mention_count', 'opportunity']].head(10).to_string()
        except Exception:
            scarcity_data = "No scarcity data available"
    else:
        velocity_data = "No velocity/longevity data available"
        density_data = "No density data available"
        scarcity_data = "No scarcity data available"

    # Build Creative Opportunity Map — anti-repetition: deprioritize saturated topics
    creative_opp_map = "No opportunity map available"
    try:
        if not density_df.empty and 'density_score' in density_df.columns:
            opp_df = density_df[['topic', 'density_score']].copy()

            # Merge velocity
            if not velocity_df.empty and 'velocity_score' in velocity_df.columns:
                vel_map = dict(zip(velocity_df['topic'], velocity_df['velocity_score']))
                opp_df['velocity'] = opp_df['topic'].map(vel_map).fillna(0)
            else:
                opp_df['velocity'] = 0

            # Merge scarcity
            if not scarcity_df.empty and 'scarcity_score' in scarcity_df.columns:
                scar_map = dict(zip(scarcity_df['topic'], scarcity_df['scarcity_score']))
                opp_df['scarcity'] = opp_df['topic'].map(scar_map).fillna(0)
            else:
                opp_df['scarcity'] = 0

            # Opportunity score: scarcity * velocity / max(density, 0.1)
            opp_df['opp_score'] = (
                opp_df['scarcity'] * opp_df['velocity'] / opp_df['density_score'].clip(lower=0.1)
            )

            # Label saturated vs opportunity
            opp_df['label'] = opp_df.apply(
                lambda r: 'SATURATED' if r['density_score'] > 0.8
                else ('OPPORTUNITY' if r['scarcity'] > 0.5 else ''),
                axis=1,
            )

            opp_df = opp_df.sort_values('opp_score', ascending=False)
            lines = []
            for _, r in opp_df.head(10).iterrows():
                tag = f" [{r['label']}]" if r['label'] else ""
                sc_l = "high opportunity" if r['scarcity'] > 0.6 else "moderate" if r['scarcity'] > 0.3 else "low"
                v_l = "accelerating" if r['velocity'] > 0.6 else "building" if r['velocity'] > 0.3 else "quiet"
                d_l = "saturated" if r['density_score'] > 0.6 else "moderate" if r['density_score'] > 0.3 else "uncrowded"
                lines.append(
                    f"  {r['topic']}{tag}: scarcity: {sc_l}, velocity: {v_l}, density: {d_l} "
                    f"[raw: opp={r['opp_score']:.2f}, sc={r['scarcity']:.2f}, v={r['velocity']:.2f}, d={r['density_score']:.2f}]"
                )
            creative_opp_map = "\n".join(lines)
    except Exception:
        creative_opp_map = "No opportunity map available"

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

CREATIVE OPPORTUNITY MAP (Ranked by opportunity score = scarcity * velocity / density):
Topics marked [SATURATED] have density > 0.8 — avoid anchoring creative ideas here.
Topics marked [OPPORTUNITY] have scarcity > 0.5 — underserved creative white space.
{creative_opp_map}

RECENT HEADLINES (What just happened - with source, empathy, emotion):
{recent_headlines if recent_headlines else "No recent headlines available"}

HIGH-ENGAGEMENT CONTENT (What's resonating now - with engagement scores):
{viral_headlines if viral_headlines else "No engagement data available"}

{brand_context}
"""

    # Add Polymarket data
    try:
        from polymarket_helper import fetch_polymarket_markets
        poly_markets = fetch_polymarket_markets(limit=8, min_volume=50000)
        if poly_markets:
            poly_lines = ["PREDICTION MARKETS (Polymarket — real money bets):"]
            for m in poly_markets[:6]:
                poly_lines.append(
                    f"  \"{m['question']}\" — {m['yes_odds']:.0f}% YES (${m['volume']:,.0f} wagered)"
                )
            context += "\n".join(poly_lines) + "\n\n"
    except Exception as e:
        print(f"  Polymarket data failed (non-fatal): {e}")

    # Add market indices, economic indicators, commodities, brand stocks
    if _sb_engine:
        try:
            mkt_df = pd.read_sql(_sb_text("""
                SELECT symbol, name, price, change_percent, market_sentiment
                FROM markets
                WHERE timestamp::timestamptz >= NOW() - INTERVAL '24 hours'
                ORDER BY timestamp DESC
            """), _sb_engine)
            if not mkt_df.empty:
                latest = mkt_df.drop_duplicates(subset=['symbol'], keep='first')
                mkt_lines = ["MARKET INDICES (last 24h):"]
                for _, row in latest.iterrows():
                    chg = row.get('change_percent', 0) or 0
                    mkt_lines.append(f"  {row['name']}: {'up' if chg > 0 else 'down'} {abs(chg):.2f}%")
                context += "\n".join(mkt_lines) + "\n\n"
        except Exception as e:
            print(f"  Market indices failed (non-fatal): {e}")

        try:
            from db_helper import load_economic_data
            econ_df = load_economic_data(days=730)
            if not econ_df.empty:
                latest_econ = econ_df.sort_values("snapshot_date").groupby("metric_name").last().reset_index()
                econ_lines = ["ECONOMIC INDICATORS:"]
                for _, row in latest_econ.iterrows():
                    econ_lines.append(f"  {row['metric_name']}: {row['metric_value']:.2f}")
                context += "\n".join(econ_lines) + "\n\n"
        except Exception as e:
            print(f"  Economic indicators failed (non-fatal): {e}")

        try:
            from db_helper import load_commodity_data
            comm_df = load_commodity_data(days=14)
            if not comm_df.empty:
                price_df = comm_df[comm_df["metric_name"] == "price"]
                if not price_df.empty:
                    latest_comm = price_df.sort_values("snapshot_date").groupby("scope_name").last().reset_index()
                    comm_lines = ["COMMODITY PRICES:"]
                    for _, row in latest_comm.iterrows():
                        comm_lines.append(f"  {row['scope_name']}: ${row['metric_value']:.2f}")
                    context += "\n".join(comm_lines) + "\n\n"
        except Exception as e:
            print(f"  Commodities failed (non-fatal): {e}")

        try:
            brand_df = pd.read_sql(_sb_text("""
                SELECT scope_name, metric_name, metric_value, snapshot_date
                FROM metric_snapshots
                WHERE scope = 'brand' AND snapshot_date >= CURRENT_DATE - INTERVAL '3 days'
                ORDER BY snapshot_date DESC
            """), _sb_engine)
            if not brand_df.empty:
                price_df = brand_df[brand_df["metric_name"] == "stock_price"]
                chg_df = brand_df[brand_df["metric_name"] == "stock_change_pct"]
                if not price_df.empty:
                    # Staleness guard — skip if data is older than 5 days
                    latest_date = pd.to_datetime(price_df["snapshot_date"]).max()
                    if latest_date < (datetime.now(timezone.utc) - timedelta(days=5)):
                        print("  Brand stock data is stale (>5 days old) — skipping")
                        price_df = pd.DataFrame()
                if not price_df.empty:
                    latest_brands = price_df.sort_values("snapshot_date").groupby("scope_name").last().reset_index()
                    chg_map = {}
                    if not chg_df.empty:
                        chg_latest = chg_df.sort_values("snapshot_date").groupby("scope_name").last().reset_index()
                        chg_map = dict(zip(chg_latest["scope_name"], chg_latest["metric_value"]))
                    brand_lines = ["BRAND STOCKS:"]
                    for _, row in latest_brands.iterrows():
                        chg = chg_map.get(row["scope_name"], 0)
                        brand_lines.append(f"  {row['scope_name']}: ${row['metric_value']:.2f} ({chg:+.2f}%)")
                    context += "\n".join(brand_lines) + "\n\n"
        except Exception as e:
            print(f"  Brand stocks failed (non-fatal): {e}")

        # Signal track record
        try:
            sig_df = pd.read_sql(_sb_text("""
                SELECT alert_type,
                       COUNT(*) AS total_signals,
                       COUNT(spy_change_1d) AS has_1d,
                       AVG(spy_change_1d) AS avg_spy_1d,
                       SUM(CASE WHEN spy_change_1d > 0 THEN 1 ELSE 0 END)::float
                           / NULLIF(COUNT(spy_change_1d), 0) AS up_rate_1d
                FROM signal_log
                GROUP BY alert_type
                ORDER BY total_signals DESC
            """), _sb_engine)
            if not sig_df.empty:
                sig_lines = ["MOODLIGHT SIGNAL TRACK RECORD:"]
                for _, row in sig_df.iterrows():
                    up_rate = f"{row['up_rate_1d']*100:.0f}%" if pd.notna(row.get("up_rate_1d")) else "N/A"
                    avg_1d = f"{row['avg_spy_1d']:+.2f}%" if pd.notna(row.get("avg_spy_1d")) else "N/A"
                    sig_lines.append(
                        f"  {row['alert_type']}: {int(row['total_signals'])} signals, "
                        f"SPY up rate: {up_rate}, avg 1d move: {avg_1d}"
                    )
                context += "\n".join(sig_lines) + "\n\n"
        except Exception as e:
            print(f"  Signal track record failed (non-fatal): {e}")

    context += f"Total Posts Analyzed: {len(df)}\n"

    # Select best frameworks for this request
    selected_frameworks = select_frameworks(user_need)
    framework_guidance = get_framework_prompt(selected_frameworks)

    # Retrieve campaign precedents
    campaign_precedents = _load_campaign_precedents(user_need, df)

    prompt = f"""You are a senior strategist who believes most brand strategy is cowardice dressed as caution. You've built your reputation on the ideas that made clients nervous before making them successful. You find the uncomfortable truth competitors are too polite to say. You never recommend what a competitor could also do - if it's obvious, it's worthless. Your best work comes from tension, not consensus.

A client has come to you with this request:
"{user_need}"

TRAINING DATA BAN: Your ONLY sources of truth are the Moodlight intelligence data provided below. Do NOT inject facts, events, corporate actions, controversies, or narratives from your training data. Your training knowledge is stale — presenting it as current intelligence destroys credibility. If the data doesn't cover something, build your strategy from what IS there. Never fill gaps with training-data "knowledge."

Based on the following real-time intelligence data from Moodlight (which tracks empathy, emotions, trends, and strategic metrics across news and social media), create a strategic brief.

{context}

{framework_guidance}

{campaign_precedents}

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

Based on the empathy distribution and emotional climate in the data, identify the timing zone:
- **Warm / Highly Empathetic dominant**: Optimal engagement window — audiences are receptive and emotionally open. Recommendation: ENGAGE NOW
- **Detached / Neutral dominant**: Audiences are disengaged; wait for a positive emotional shift or proceed with extra sensitivity and compelling hooks
- **Cold / Hostile dominant**: Defensive positioning only — high negativity means campaigns risk backlash
- **Mixed with strong positive emotions (joy, hope, excitement)**: Good window despite mixed empathy — lean into the dominant positive emotion as your entry point

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

ANTI-STALENESS CHECK: Do NOT anchor your creative idea on the highest-velocity topic unless you can prove a genuinely novel angle that nobody else would find. The obvious trending topic is where lazy strategists go. Your job is to find the edge. If your idea could appear in any other strategic brief this week, it's not unexpected enough. Delete it and dig deeper. Use the CREATIVE OPPORTUNITY MAP above — topics marked [OPPORTUNITY] are your hunting ground; topics marked [SATURATED] are where you should NOT start.

End with: "The non-obvious move: [one sentence summary of the unexpected angle]"

## 4.5 🎓 CREATIVE PRECEDENT LENS

If CREATIVE PRECEDENTS are provided above, select the 3 most relevant to this brief and present them as follows. If no precedents are provided, skip this section entirely.

For each precedent:
- **[Campaign Name] ([Brand], [Year])** — [One sentence on the cultural tension it addressed]
  *Applies because:* [One sentence explaining the structural parallel to today's moment — NOT the surface similarity, but the underlying pattern]

After the 3 precedents, identify:
- **Structural pattern to steal:** [Name the underlying mechanic that connects the best precedents to this brief — e.g., "absence as message," "the audience convicts themselves," "give away your advantage to prove values," "reframe the weakness as mythology." This pattern should directly inform the Campaign Concept in Section 6.]

Do NOT recommend recreating any precedent campaign. The value is the THINKING behind them — the structural patterns, the emotional calibration, the way they attached to cultural tension. Use them to calibrate ambition and find analogies.

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
A single activatable idea—name it, describe it in 2-3 sentences, explain why it fits this cultural moment. The Campaign Concept must feel like it could ONLY exist this week. If you could run this campaign next month with no changes, it's not timely enough. If CREATIVE PRECEDENTS were provided, the concept should be informed by the structural pattern identified in Section 4.5 — not copying a precedent, but applying the same underlying mechanic to today's data.

**Platform Play:**
Which platform (X, LinkedIn, TikTok, OOH, etc.) is best suited for this moment and why? One sentence.

**First 48 Hours:**
If the client said "go" right now, what's the single most important action in the next 48 hours? Be specific.

**Steal This Line:**
One sentence the client can use verbatim in a deck, ad, or pitch tomorrow. It must make someone uncomfortable to say out loud. If it's safe, it's forgettable.

End with: "This is the starting point, not the ceiling."

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
        model="claude-opus-4-6",
        max_tokens=4000,
        system="You are a senior strategist who combines data intelligence with creative intuition. You speak plainly and give bold recommendations.",
        messages=[{"role": "user", "content": prompt}]
    )

    # Get framework names for email
    framework_names = [STRATEGIC_FRAMEWORKS[f]["name"] for f in selected_frameworks]
    return response.content[0].text, framework_names


_AGENT_CROSS_SELL = {
    "new-business-win": [
        ("The Brief Critic", "Pressure-test the pitch narrative before you walk into the room."),
        ("The Creative Technologist", "Stress-test the hero concept's build and timeline before you commit to it."),
    ],
    "outbound-discovery": [
        ("The Audience Profiler", "Go deeper on one of the 10 account archetypes before you send."),
        ("The Partnership Scout", "Find partners who already have relationships in the accounts you're hunting."),
    ],
    "gtm-researcher": [
        ("Outbound Discovery", "Turn this research brief into a full GTM motion with outbound lines you can send today."),
        ("The Audience Profiler", "Go deeper on the cultural read of the top archetype."),
    ],
    "cco": [
        ("The Copywriter", "Turn this brief into headlines, social posts, and ad copy."),
        ("The Comms Planner", "Get a channel-by-channel deployment plan for this campaign."),
    ],
    "cso": [
        ("The Chief Creative Officer", "Turn this strategy into campaign concepts."),
        ("The Comms Planner", "Map out where and when to deploy this positioning."),
    ],
    "comms-planner": [
        ("The Chief Creative Officer", "Build creative concepts for these channels."),
        ("The Copywriter", "Write the copy for each touchpoint in this plan."),
    ],
    "full-deploy": [
        ("The Copywriter", "Turn this battle plan into ready-to-run copy."),
        ("The Pitch Builder", "Package this into a client-ready pitch narrative."),
    ],
    "brand-auditor": [
        ("The Cultural Strategist", "Build a positioning strategy from this audit."),
        ("The Chief Creative Officer", "Create campaign concepts to close the gaps."),
    ],
    "brief-critic": [
        ("The Chief Creative Officer", "Rebuild the brief with these fixes applied."),
        ("The Cultural Strategist", "Rethink the strategy behind this brief."),
    ],
    "trend-forecaster": [
        ("The Cultural Strategist", "Build a positioning strategy around these trends."),
        ("The Chief Creative Officer", "Create campaigns that ride these shifts."),
    ],
    "copywriter": [
        ("The Comms Planner", "Plan where and when to deploy this copy."),
        ("The Content Strategist", "Build a full content strategy around this voice."),
    ],
    "crisis-advisor": [
        ("The Copywriter", "Draft the exact statements and social copy for this response."),
        ("The Comms Planner", "Map the channel-by-channel deployment of the crisis response."),
    ],
    "audience-profiler": [
        ("The Content Strategist", "Build content pillars for this audience."),
        ("The Chief Creative Officer", "Create campaigns that speak to who this audience really is."),
    ],
    "competitive-scout": [
        ("The Cultural Strategist", "Build a positioning strategy that exploits these gaps."),
        ("The Brand Auditor", "Run a full audit on the same brand to compare."),
    ],
    "pitch-builder": [
        ("The Copywriter", "Write the headlines and key copy for this pitch."),
        ("The Content Strategist", "Plan the content rollout if you win the pitch."),
    ],
    "content-strategist": [
        ("The Copywriter", "Write the first batch of content from these pillars."),
        ("The Audience Profiler", "Validate that this content strategy matches who's actually listening."),
    ],
    "culture-translator": [
        ("The Copywriter", "Write market-specific copy for each adaptation."),
        ("The Comms Planner", "Plan the channel deployment per market."),
    ],
    "seo-strategist": [
        ("The Content Strategist", "Build the full content strategy around these search opportunities."),
        ("The Copywriter", "Write the SEO content for the highest-priority keyword clusters."),
    ],
    "social-strategist": [
        ("The Copywriter", "Write the posts, hooks, and captions for this week's plan."),
        ("The Content Strategist", "Build a longer-term content ecosystem around these social insights."),
    ],
    "data-strategist": [
        ("The Audience Profiler", "Validate that who you're measuring against is who's actually showing up."),
        ("The Creative Technologist", "Figure out the instrumentation stack needed to capture these events."),
    ],
    "creative-technologist": [
        ("The Chief Creative Officer", "Make sure the concept this build is serving is still the right concept."),
        ("The Pitch Builder", "Turn this build plan into a client-ready pitch narrative."),
    ],
    "paid-media-strategist": [
        ("The Copywriter", "Write the ad creative for this channel mix."),
        ("The Experimentation Strategist", "Design incrementality tests to pressure-test platform-reported ROAS."),
    ],
    "funnel-doctor": [
        ("The Experimentation Strategist", "Design tests that prove the proposed fixes actually move the needle."),
        ("The Copywriter", "Rewrite the high-friction copy flagged in the audit."),
    ],
    "lifecycle-strategist": [
        ("The Content Strategist", "Build content pillars that feed each stage of this lifecycle."),
        ("The Copywriter", "Write the journey emails, SMS, and push copy for these sequences."),
    ],
    "experimentation-strategist": [
        ("The Funnel Doctor", "Find the next wave of leaks to test against."),
        ("The Data Strategist", "Instrument the events needed to measure these tests cleanly."),
    ],
    "referral-architect": [
        ("The Copywriter", "Write the share copy, incentive messaging, and landing experience."),
        ("The Lifecycle Strategist", "Embed referral triggers inside the lifecycle journey."),
    ],
    "partnership-scout": [
        ("The Pitch Builder", "Turn the top partnership candidate into a pitch narrative that earns the meeting."),
        ("The Chief Creative Officer", "Build the creative concept the partnership will actually live inside."),
    ],
    "creative-council": [
        ("The Brief Critic", "Tighten the case study before you submit — find what's thin against live data."),
        ("The Pitch Builder", "Turn this entry into the jury presentation narrative."),
    ],
    "focus-group": [
        ("The Audience Profiler", "Go deeper on who this audience actually is culturally before you retest."),
        ("The Brief Critic", "Stress-test the brief behind the creative before you spend on real research."),
    ],
}


# Reverse lookup from display name → agent slug so cross-sell email
# CTAs can deep-link directly to the target agent card on the
# marketplace. Must stay in sync with _AGENT_LABELS in
# ask_moodlight_api.py and with the display names used in
# _AGENT_CROSS_SELL above. Unknown names fall back to the marketplace
# root (no ?agent= param).
_AGENT_SLUG_BY_LABEL = {
    "New Business Win": "new-business-win",
    "Outbound Discovery": "outbound-discovery",
    "The Chief Creative Officer": "cco",
    "The Cultural Strategist": "cso",
    "The Comms Planner": "comms-planner",
    "Full Deploy": "full-deploy",
    "The Data Strategist": "data-strategist",
    "The Creative Technologist": "creative-technologist",
    "The Brand Auditor": "brand-auditor",
    "The Brief Critic": "brief-critic",
    "The Trend Forecaster": "trend-forecaster",
    "The Copywriter": "copywriter",
    "The Crisis Advisor": "crisis-advisor",
    "The Audience Profiler": "audience-profiler",
    "The Competitive Scout": "competitive-scout",
    "The Partnership Scout": "partnership-scout",
    "The Pitch Builder": "pitch-builder",
    "The Pitch Strategist": "pitch-strategist",
    "The Content Strategist": "content-strategist",
    "The Culture Translator": "culture-translator",
    "The Social Strategist": "social-strategist",
    "The GTM Researcher": "gtm-researcher",
    "The SEO Strategist": "seo-strategist",
    "The Paid Media Strategist": "paid-media-strategist",
    "The Funnel Doctor": "funnel-doctor",
    "The Lifecycle Strategist": "lifecycle-strategist",
    "The Experimentation Strategist": "experimentation-strategist",
    "The Referral Architect": "referral-architect",
    "The Global Creative Council": "creative-council",
    "The Focus Group": "focus-group",
}


def _build_cross_sell_html(agent_id: str) -> str:
    """Build cross-sell HTML for agent emails. Each suggestion is a
    deep-link to the marketplace with ?agent=<slug> so clicking the
    CTA opens the right agent card automatically."""
    suggestions = _AGENT_CROSS_SELL.get(agent_id, [])
    if not suggestions:
        return ""

    base_url = "https://www.moodlightintel.com"
    items = ""
    for agent_name, reason in suggestions:
        slug = _AGENT_SLUG_BY_LABEL.get(agent_name)
        href = f"{base_url}?agent={slug}" if slug else base_url
        items += (
            f'<a href="{href}" '
            f'style="display: block; margin: 6px 0; padding: 10px 14px; '
            f'background: #f9f7fd; border-radius: 8px; '
            f'border: 1px solid #ede8f5; text-decoration: none; '
            f'color: inherit;">'
            f'<strong style="color: #6B46C1;">{agent_name}</strong> '
            f'<span style="color: #555;">— {reason}</span>'
            f'</a>'
        )

    return (
        f'<div style="margin: 28px 0 0 0; padding: 20px; background: #fafafa; '
        f'border-radius: 10px; border: 1px solid #eee;">'
        f'<div style="font-size: 14px; font-weight: 600; color: #2D2D2D; margin-bottom: 10px;">'
        f'Keep going — run this through another agent</div>'
        f'{items}'
        f'<div style="margin-top: 12px; font-size: 13px; color: #888;">'
        f'Click an agent above, or visit '
        f'<a href="{base_url}" style="color: #6B46C1; text-decoration: none;">'
        f'moodlightintel.com</a> to run another.'
        f'</div>'
        f'</div>'
    )


def send_strategic_brief_email(recipient_email: str, user_need: str, brief: str, frameworks: list = None, agent_id: str = None) -> bool:
    """Send strategic brief via email"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email_templates import render_email, parse_and_render_sections

    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")

    if not all([sender, password]):
        return False

    # Agent-specific email titles
    agent_label = frameworks[0] if frameworks and len(frameworks) == 1 else None
    if agent_label:
        email_subject = f"{agent_label} Brief — Moodlight"
        email_title = f"{agent_label} Brief"
        badge_text = agent_label.upper()
    else:
        email_subject = "Moodlight Strategic Brief"
        email_title = "Strategic Brief"
        badge_text = "STRATEGIC BRIEF"

    msg = MIMEMultipart('alternative')
    msg['Subject'] = email_subject
    msg['From'] = sender
    msg['To'] = recipient_email

    # Metadata section before the main content
    frameworks_text = ", ".join(frameworks) if frameworks else "Custom analysis"
    meta_html = (
        f'<div style="margin: 0 0 20px 0; padding: 10px 15px; background: #f5f5f5; '
        f'border-radius: 8px; font-size: 14px; color: #555;">'
        f'<strong>Request:</strong> "{user_need}"<br>'
        f'<strong>Frameworks applied:</strong> {frameworks_text}'
        f'</div>'
    )

    body_html = meta_html + parse_and_render_sections(brief)

    # Add cross-sell for marketplace agent emails
    if agent_id:
        body_html += _build_cross_sell_html(agent_id)

    html = render_email(
        badge_text=badge_text,
        badge_color="#7B1FA2",
        title=email_title,
        body_html=body_html,
        footer_text=f"Moodlight Intelligence Platform — {email_title}",
    )

    msg.attach(MIMEText(html, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False
