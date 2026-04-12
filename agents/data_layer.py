"""
agents/data_layer.py
Shared data-fetching layer for all Moodlight agents.
Extracts and consolidates data loading from generate_strategic_brief.py
so all agents pull from the same real-time intelligence.
"""

import os
import json
import pandas as pd
from datetime import datetime, timezone, timedelta
from sqlalchemy import text as sql_text
from db_helper import get_engine


def load_combined_data(days=7):
    """Load combined news + social scored data."""
    engine = get_engine()
    if not engine:
        return pd.DataFrame()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    frames = []
    for table in ("news_scored", "social_scored"):
        try:
            df = pd.read_sql(
                sql_text(f"SELECT * FROM {table} WHERE created_at >= :cutoff"),
                engine,
                params={"cutoff": cutoff},
            )
            frames.append(df)
        except Exception:
            pass
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build_intelligence_snapshot(df):
    """Build summary stats from combined data."""
    snapshot = {}
    snapshot["top_topics"] = (
        df["topic"].value_counts().head(10).to_string()
        if "topic" in df.columns else "No topic data"
    )
    snapshot["top_emotions"] = (
        df["emotion_top_1"].value_counts().head(10).to_string()
        if "emotion_top_1" in df.columns else "No emotion data"
    )
    snapshot["empathy_dist"] = (
        df["empathy_label"].value_counts().to_string()
        if "empathy_label" in df.columns else "No empathy data"
    )
    snapshot["avg_empathy"] = (
        f"{df['empathy_score'].mean():.1f}/100"
        if "empathy_score" in df.columns else "N/A"
    )
    snapshot["geo_dist"] = (
        df["country"].value_counts().head(10).to_string()
        if "country" in df.columns else "No geographic data"
    )
    snapshot["source_dist"] = (
        df["source"].value_counts().head(10).to_string()
        if "source" in df.columns else "No source data"
    )
    snapshot["total_posts"] = len(df)
    return snapshot


def load_headlines(df, recent_count=15, viral_count=10):
    """Extract recent and high-engagement headlines."""
    recent = ""
    viral = ""
    if "text" not in df.columns:
        return recent, viral

    cols = ["text", "topic", "source", "engagement", "empathy_label", "emotion_top_1"]
    available = [c for c in cols if c in df.columns]

    if "created_at" in df.columns:
        top = df.nlargest(recent_count, "created_at")[available].drop_duplicates("text")
        recent = "\n".join([
            f"- [{row.get('topic', 'N/A')}] {row['text'][:150]} | Source: {row.get('source', 'N/A')} | Empathy: {row.get('empathy_label', 'N/A')} | Emotion: {row.get('emotion_top_1', 'N/A')}"
            for _, row in top.iterrows()
        ])

    if "engagement" in df.columns:
        top = df.nlargest(viral_count, "engagement")[available].drop_duplicates("text")
        viral = "\n".join([
            f"- [{row.get('topic', 'N/A')}] {row['text'][:150]} | Engagement: {int(row.get('engagement', 0))} | Source: {row.get('source', 'N/A')} | Emotion: {row.get('emotion_top_1', 'N/A')}"
            for _, row in top.iterrows()
        ])

    return recent, viral


def load_vlds_tables():
    """Load velocity, density, scarcity tables."""
    engine = get_engine()
    if not engine:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    velocity_df = density_df = scarcity_df = pd.DataFrame()
    try:
        velocity_df = pd.read_sql(
            sql_text("SELECT topic, velocity_score, longevity_score FROM topic_longevity"), engine
        )
    except Exception:
        pass
    try:
        density_df = pd.read_sql(
            sql_text("SELECT topic, density_score, post_count, primary_platform FROM topic_density"), engine
        )
    except Exception:
        pass
    try:
        scarcity_df = pd.read_sql(
            sql_text("SELECT topic, scarcity_score, mention_count, opportunity FROM topic_scarcity"), engine
        )
    except Exception:
        pass

    return velocity_df, density_df, scarcity_df


def build_creative_opportunity_map(velocity_df, density_df, scarcity_df):
    """Build opportunity map: scarcity * velocity / density."""
    try:
        if density_df.empty or "density_score" not in density_df.columns:
            return "No opportunity map available"

        opp_df = density_df[["topic", "density_score"]].copy()

        if not velocity_df.empty and "velocity_score" in velocity_df.columns:
            vel_map = dict(zip(velocity_df["topic"], velocity_df["velocity_score"]))
            opp_df["velocity"] = opp_df["topic"].map(vel_map).fillna(0)
        else:
            opp_df["velocity"] = 0

        if not scarcity_df.empty and "scarcity_score" in scarcity_df.columns:
            scar_map = dict(zip(scarcity_df["topic"], scarcity_df["scarcity_score"]))
            opp_df["scarcity"] = opp_df["topic"].map(scar_map).fillna(0)
        else:
            opp_df["scarcity"] = 0

        opp_df["opp_score"] = (
            opp_df["scarcity"] * opp_df["velocity"] / opp_df["density_score"].clip(lower=0.1)
        )
        opp_df["label"] = opp_df.apply(
            lambda r: "SATURATED" if r["density_score"] > 0.8
            else ("OPPORTUNITY" if r["scarcity"] > 0.5 else ""),
            axis=1,
        )
        opp_df = opp_df.sort_values("opp_score", ascending=False)

        lines = []
        for _, r in opp_df.head(10).iterrows():
            tag = f" [{r['label']}]" if r["label"] else ""
            sc_l = "high opportunity" if r["scarcity"] > 0.6 else "moderate" if r["scarcity"] > 0.3 else "low"
            v_l = "accelerating" if r["velocity"] > 0.6 else "building" if r["velocity"] > 0.3 else "quiet"
            d_l = "saturated" if r["density_score"] > 0.6 else "moderate" if r["density_score"] > 0.3 else "uncrowded"
            lines.append(
                f"  {r['topic']}{tag}: scarcity: {sc_l}, velocity: {v_l}, density: {d_l} "
                f"[raw: opp={r['opp_score']:.2f}, sc={r['scarcity']:.2f}, v={r['velocity']:.2f}, d={r['density_score']:.2f}]"
            )
        return "\n".join(lines)
    except Exception:
        return "No opportunity map available"


def load_market_context():
    """Load market indices, economic indicators, commodities, brand stocks, signal track record."""
    engine = get_engine()
    if not engine:
        return {}

    sections = {}

    # Market indices
    try:
        mkt_df = pd.read_sql(sql_text("""
            SELECT symbol, name, price, change_percent, market_sentiment
            FROM markets
            WHERE timestamp::timestamptz >= NOW() - INTERVAL '24 hours'
            ORDER BY timestamp DESC
        """), engine)
        if not mkt_df.empty:
            latest = mkt_df.drop_duplicates(subset=["symbol"], keep="first")
            lines = ["MARKET INDICES (last 24h):"]
            for _, row in latest.iterrows():
                chg = row.get("change_percent", 0) or 0
                try:
                    chg = float(chg)
                except (ValueError, TypeError):
                    chg = 0
                lines.append(f"  {row['name']}: {'up' if chg > 0 else 'down'} {abs(chg):.2f}%")
            sections["markets"] = "\n".join(lines)
    except Exception:
        pass

    # Economic indicators
    try:
        from db_helper import load_economic_data
        econ_df = load_economic_data(days=730)
        if not econ_df.empty:
            latest_econ = econ_df.sort_values("snapshot_date").groupby("metric_name").last().reset_index()
            lines = ["ECONOMIC INDICATORS:"]
            for _, row in latest_econ.iterrows():
                lines.append(f"  {row['metric_name']}: {row['metric_value']:.2f}")
            sections["economic"] = "\n".join(lines)
    except Exception:
        pass

    # Commodities
    try:
        from db_helper import load_commodity_data
        comm_df = load_commodity_data(days=14)
        if not comm_df.empty:
            price_df = comm_df[comm_df["metric_name"] == "price"]
            if not price_df.empty:
                latest_comm = price_df.sort_values("snapshot_date").groupby("scope_name").last().reset_index()
                lines = ["COMMODITY PRICES:"]
                for _, row in latest_comm.iterrows():
                    lines.append(f"  {row['scope_name']}: ${row['metric_value']:.2f}")
                sections["commodities"] = "\n".join(lines)
    except Exception:
        pass

    # Brand stocks
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
                latest_date = pd.to_datetime(price_df["snapshot_date"]).max()
                if latest_date < (datetime.now(timezone.utc) - timedelta(days=5)):
                    price_df = pd.DataFrame()
            if not price_df.empty:
                latest_brands = price_df.sort_values("snapshot_date").groupby("scope_name").last().reset_index()
                chg_map = {}
                if not chg_df.empty:
                    chg_latest = chg_df.sort_values("snapshot_date").groupby("scope_name").last().reset_index()
                    chg_map = dict(zip(chg_latest["scope_name"], chg_latest["metric_value"]))
                lines = ["BRAND STOCKS:"]
                for _, row in latest_brands.iterrows():
                    chg = chg_map.get(row["scope_name"], 0)
                    lines.append(f"  {row['scope_name']}: ${row['metric_value']:.2f} ({chg:+.2f}%)")
                sections["brand_stocks"] = "\n".join(lines)
    except Exception:
        pass

    # Signal track record
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
            lines = ["MOODLIGHT SIGNAL TRACK RECORD:"]
            for _, row in sig_df.iterrows():
                up_rate = f"{row['up_rate_1d']*100:.0f}%" if pd.notna(row.get("up_rate_1d")) else "N/A"
                avg_1d = f"{row['avg_spy_1d']:+.2f}%" if pd.notna(row.get("avg_spy_1d")) else "N/A"
                lines.append(
                    f"  {row['alert_type']}: {int(row['total_signals'])} signals, "
                    f"SPY up rate: {up_rate}, avg 1d move: {avg_1d}"
                )
            sections["signal_track"] = "\n".join(lines)
    except Exception:
        pass

    return sections


def load_polymarket_data(limit=8, min_volume=50000):
    """Load Polymarket prediction market data."""
    try:
        from polymarket_helper import fetch_polymarket_markets
        markets = fetch_polymarket_markets(limit=limit, min_volume=min_volume)
        if markets:
            lines = ["PREDICTION MARKETS (Polymarket — real money bets):"]
            for m in markets[:6]:
                lines.append(
                    f"  \"{m['question']}\" — {m['yes_odds']:.0f}% YES (${m['volume']:,.0f} wagered)"
                )
            return "\n".join(lines)
    except Exception:
        pass
    return ""


def load_campaign_precedents(user_need, df):
    """Load and score campaign precedents against current cultural moment."""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "campaign_database.json")
    try:
        with open(db_path) as f:
            campaigns = json.load(f)
    except Exception:
        return ""

    if not campaigns:
        return ""

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

    # Generic topics that match too many campaigns — skip for scoring
    _generic_topics = {
        "entertainment", "technology", "politics", "sports", "media",
        "health", "science", "business", "economy", "education",
        "environment", "culture", "society", "world", "social",
        "technology & ai", "media & journalism", "labor & work",
    }

    def score_campaign(camp):
        score = 0
        tension = camp.get("cultural_tension", "").lower()
        insight = camp.get("insight", "").lower()
        why = camp.get("why_it_worked", "").lower()
        tags = [t.lower() for t in camp.get("category_tags", [])]
        emo_reg = camp.get("emotional_register", "").lower()
        category = camp.get("brand", "").lower()

        # User need is the PRIMARY signal — heavily weighted
        need_words = [w for w in user_need_lower.split() if len(w) > 4]
        for w in need_words:
            if w in tension or w in insight or w in why:
                score += 3
            if w in category:
                score += 2

        # Topic matching — only for specific topics, not generic categories
        for topic in topics:
            t = topic.lower()
            if t in _generic_topics:
                continue
            if t in tension or t in insight:
                score += 2

        # Emotion matching
        for emo in emotions:
            if emo.lower() in emo_reg:
                score += 1.5

        # Headline overlap — capped to prevent common-word campaigns dominating
        tension_words = [w for w in tension.split() if len(w) > 8]
        headline_hits = sum(1 for w in tension_words if w in headline_text)
        score += min(headline_hits * 0.2, 1.0)  # Cap at 1 point

        # Tag bonuses only when the tag connects to user input or current signals
        tag_bonuses = {
            "empathy": 1.5, "social impact": 1, "revelation": 1,
            "cultural moment": 1.5, "crisis response": 1, "subversion": 0.5,
            "provocation": 0.5, "reframe": 1, "authenticity": 0.5,
            "brand platform": 0.5, "long-running": 0.5,
        }
        relevance_words = set(user_need_lower.split()) | {e.lower() for e in emotions}
        for tag in tags:
            bonus = tag_bonuses.get(tag, 0)
            if bonus and any(w in tag or tag in w for w in relevance_words if len(w) > 3):
                score += bonus
        return score

    scored = [(c, score_campaign(c)) for c in campaigns]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:5]

    if top[0][1] < 3:
        return ""

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


def build_enrichment(username, user_need, df):
    """Build brand/topic enrichment context (VLDS, competitive, alerts).

    For logged-in users (username set): full three-layer matching via watchlists.
    For marketplace users (no username): compute VLDS directly from user_need.
    """
    engine = get_engine()
    if not engine:
        return ""

    if username:
        from generate_strategic_brief import _build_enrichment
        return _build_enrichment(engine, username, user_need, df)

    # Marketplace path: extract brand/product from user_need, compute VLDS directly
    return _build_marketplace_enrichment(user_need, df)


def _build_marketplace_enrichment(user_need, df):
    """Compute VLDS enrichment for marketplace users using their product input."""
    from vlds_helper import calculate_brand_vlds

    if df.empty or "text" not in df.columns:
        return ""

    # Extract likely brand/product keywords from user_need
    # Take the first meaningful phrase (before "targeting", "in", "with the challenge")
    brand_phrase = user_need
    for splitter in ["targeting ", " in ", " with the challenge"]:
        brand_phrase = brand_phrase.split(splitter)[0]
    # Remove "launch/promote " prefix from _build_marketplace_input
    brand_phrase = brand_phrase.replace("launch/promote ", "").strip()

    if not brand_phrase or len(brand_phrase) < 2:
        return ""

    # Search news/social data for mentions
    search_terms = [t.strip().lower() for t in brand_phrase.split() if len(t.strip()) > 2]
    if not search_terms:
        return ""

    # Try full phrase first, fall back to individual keywords
    text_lower = df["text"].str.lower()
    brand_df = df[text_lower.str.contains(brand_phrase.lower(), na=False)].copy()

    # If too few results with full phrase, try the longest keyword
    if len(brand_df) < 5 and search_terms:
        longest_term = max(search_terms, key=len)
        if len(longest_term) >= 4:
            brand_df = df[text_lower.str.contains(longest_term, na=False)].copy()

    if len(brand_df) < 5:
        return ""

    if "created_at" in brand_df.columns:
        brand_df = brand_df.dropna(subset=["created_at"])

    vlds = calculate_brand_vlds(brand_df)
    if not vlds:
        return ""

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

    top_emo = vlds.get("top_emotions_detailed", [])
    emo_str = ", ".join(
        f"{e['emotion']} ({e['percentage']}%)" for e in top_emo[:3]
    ) if top_emo else "N/A"

    mention_count = len(brand_df)

    return (
        f"BRAND INTELLIGENCE — {brand_phrase.upper()} ({mention_count} mentions in data):\n"
        f"---\n"
        f"  Velocity: {v_label} [raw: {v:.2f}] — {v_insight}\n"
        f"  Longevity: {l_label} [raw: {l:.2f}] — {l_insight}\n"
        f"  Density: {d_label} [raw: {d:.2f}] — {d_insight}\n"
        f"  Scarcity: {sc_label} [raw: {sc:.2f}]\n"
        f"  Top Emotions: {emo_str}\n"
        f"  Empathy: {emp_label}\n"
        f"---"
    )


def assemble_full_context(df, snapshot, headlines, vlds_data=None,
                          opp_map=None, market_ctx=None, polymarket=None,
                          brand_context=None, campaign_precedents=None):
    """Assemble the full intelligence context string for agent prompts."""
    recent_headlines, viral_headlines = headlines

    velocity_df, density_df, scarcity_df = vlds_data or (pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

    velocity_data = (
        velocity_df[["topic", "velocity_score", "longevity_score"]].head(10).to_string()
        if not velocity_df.empty else "No velocity/longevity data available"
    )
    density_data = (
        density_df[["topic", "density_score", "post_count", "primary_platform"]].head(10).to_string()
        if not density_df.empty else "No density data available"
    )
    scarcity_data = (
        scarcity_df[["topic", "scarcity_score", "mention_count", "opportunity"]].head(10).to_string()
        if not scarcity_df.empty else "No scarcity data available"
    )

    context = f"""
MOODLIGHT INTELLIGENCE SNAPSHOT
================================
TOP TOPICS (by mention volume):
{snapshot['top_topics']}

EMOTIONAL CLIMATE (top emotions detected):
{snapshot['top_emotions']}

EMPATHY DISTRIBUTION:
{snapshot['empathy_dist']}
Average Empathy Score: {snapshot['avg_empathy']}

GEOGRAPHIC HOTSPOTS:
{snapshot['geo_dist']}

SOURCE DISTRIBUTION (which publications/platforms are driving conversation):
{snapshot['source_dist']}

VELOCITY & LONGEVITY (Which topics are rising fast vs. enduring):
{velocity_data}

DENSITY (Topic saturation - high means crowded, low means opportunity):
{density_data}

SCARCITY (Underserved topics - high scarcity = white space opportunity):
{scarcity_data}

CREATIVE OPPORTUNITY MAP (Ranked by opportunity score = scarcity * velocity / density):
Topics marked [SATURATED] have density > 0.8 — avoid anchoring creative ideas here.
Topics marked [OPPORTUNITY] have scarcity > 0.5 — underserved creative white space.
{opp_map or 'No opportunity map available'}

RECENT HEADLINES (What just happened - with source, empathy, emotion):
{recent_headlines or 'No recent headlines available'}

HIGH-ENGAGEMENT CONTENT (What's resonating now - with engagement scores):
{viral_headlines or 'No engagement data available'}

{brand_context or ''}
"""

    if polymarket:
        context += polymarket + "\n\n"

    if market_ctx:
        for section in market_ctx.values():
            context += section + "\n\n"

    context += f"Total Posts Analyzed: {snapshot['total_posts']}\n"

    return context
