"""
theme_detector.py
Detects recurring societal themes across 14 days of high-empathy headlines.

Uses Haiku to tag headlines with societal themes (loneliness epidemic, trust erosion,
career vertigo, etc.), clusters and scores them, and persists multi-week arcs in DB.
Feeds into generate_radar.py's context builder.
"""

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone, timedelta

import pandas as pd
from anthropic import Anthropic
from sqlalchemy import text as sql_text

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ---------------------------------------------------------------------------
# DB table
# ---------------------------------------------------------------------------

def ensure_themes_table(engine):
    """Create detected_themes table if it doesn't exist."""
    with engine.connect() as conn:
        conn.execute(sql_text("""
            CREATE TABLE IF NOT EXISTS detected_themes (
                id SERIAL PRIMARY KEY,
                detection_date DATE NOT NULL,
                theme_name VARCHAR(200) NOT NULL,
                theme_slug VARCHAR(200) NOT NULL,
                story_count INTEGER NOT NULL DEFAULT 0,
                topic_diversity INTEGER NOT NULL DEFAULT 0,
                avg_empathy FLOAT,
                growth_rate FLOAT,
                recent_count INTEGER DEFAULT 0,
                prior_count INTEGER DEFAULT 0,
                top_emotions TEXT,
                evidence_headlines TEXT,
                first_seen DATE,
                consecutive_days INTEGER DEFAULT 1,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(detection_date, theme_slug)
            )
        """))
        conn.commit()


# ---------------------------------------------------------------------------
# 1. Fetch high-empathy headlines
# ---------------------------------------------------------------------------

def _fetch_high_empathy_headlines(engine, lookback_days=14):
    """Fetch high-empathy headlines from news and social for theme detection."""
    headlines = []

    # News headlines
    try:
        news_df = pd.read_sql(sql_text("""
            SELECT text, topic, empathy_score, emotion_top_1, created_at
            FROM news_scored
            WHERE created_at >= NOW() - INTERVAL :days
              AND empathy_score > 0.06
              AND text IS NOT NULL
            ORDER BY empathy_score DESC
            LIMIT 500
        """), engine, params={"days": f"{lookback_days} days"})
        for _, row in news_df.iterrows():
            headlines.append({
                "text": row["text"][:300],
                "topic": row.get("topic", ""),
                "empathy_score": float(row.get("empathy_score", 0) or 0),
                "emotion": row.get("emotion_top_1", ""),
                "created_at": row["created_at"],
                "source_type": "news",
            })
    except Exception as e:
        print(f"  News headlines fetch failed: {e}")

    # Social posts
    try:
        social_df = pd.read_sql(sql_text("""
            SELECT text, topic, empathy_score, emotion_top_1, created_at
            FROM social_scored
            WHERE created_at >= NOW() - INTERVAL :days
              AND empathy_score > 0.06
              AND text IS NOT NULL
            ORDER BY empathy_score DESC
            LIMIT 500
        """), engine, params={"days": f"{lookback_days} days"})
        for _, row in social_df.iterrows():
            headlines.append({
                "text": row["text"][:300],
                "topic": row.get("topic", ""),
                "empathy_score": float(row.get("empathy_score", 0) or 0),
                "emotion": row.get("emotion_top_1", ""),
                "created_at": row["created_at"],
                "source_type": "social",
            })
    except Exception as e:
        print(f"  Social headlines fetch failed: {e}")

    print(f"  Fetched {len(headlines)} high-empathy headlines")
    return headlines


# ---------------------------------------------------------------------------
# 2. Haiku theme tagging
# ---------------------------------------------------------------------------

THEME_TAG_PROMPT = """You are a societal pattern detector. Given a batch of headlines, identify which ones reflect SOCIETAL-LEVEL themes — not individual events, but recurring patterns about how people are living, working, connecting, coping, or breaking down.

Examples of societal themes:
- THE LONELINESS EPIDEMIC (isolation, social disconnection, vanishing third places, remote work loneliness, elderly isolation, "loneliness crisis", friendship decline, seeking connection online, introverts debating office vs remote, community breakdown, people reaching out to strangers for guidance or companionship, AI chatbots vs human connection, senior isolation programs). This theme is BROAD — any story about people struggling to connect, feeling alone, or the systems meant to address isolation counts.
- TRUST EROSION (institutional distrust, vaccine hesitancy, media skepticism, government credibility)
- CAREER VERTIGO (job market anxiety, AI displacement fear, identity-work decoupling, feeling lost professionally)
- THE NESTING ECONOMY (retreat into private spaces, home improvement as coping, domestic consumption)
- CRISIS FATIGUE (emotional numbness, news avoidance, gratitude as survival mechanism)
- FINANCIAL SHAME (debt stigma, cost-of-living stress, generational money trauma, gambling addiction)
- THE CARE CRISIS (caregiver burnout, aging infrastructure, healthcare access, mental health gaps)
- DIGITAL DISCONNECTION (screen fatigue, AI anxiety, nostalgia for analog, choosing simpler tech)
- COMMUNITY FRACTURE (political division, neighborhood decline, belonging crisis)
- IDENTITY RENEGOTIATION (gender roles shifting, cultural identity, purpose-seeking)

Rules:
- Only tag headlines that CLEARLY reflect a societal pattern. Not every headline has one.
- A single headline can reflect multiple themes. Someone posting about feeling isolated while working remotely = both THE LONELINESS EPIDEMIC and CAREER VERTIGO.
- Use consistent theme names. Prefer the examples above when they fit. Invent new ones only when needed.
- Each headline gets 0-2 themes. Most get 0.
- Return ONLY a JSON array. No explanation.

Format: [{"idx": 0, "themes": ["THE LONELINESS EPIDEMIC"]}, {"idx": 1, "themes": []}, ...]"""


def _tag_themes_batch(headlines_batch):
    """Tag a batch of headlines with societal themes via Haiku."""
    numbered = "\n".join(
        f"{i}. {h['text'][:250]}" for i, h in enumerate(headlines_batch)
    )
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": f"{THEME_TAG_PROMPT}\n\nHeadlines:\n{numbered}",
            }],
        )
        text = response.content[0].text.strip()
        # Handle markdown code blocks
        if "```" in text:
            match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text, re.DOTALL)
            if match:
                text = match.group(1)
        results = json.loads(text)
        if isinstance(results, list):
            return results
    except Exception as e:
        print(f"  Haiku theme tagging failed: {e}")
    return []


def _slugify(theme_name):
    """Convert theme name to a stable slug for DB matching."""
    slug = theme_name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s]', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    return slug


# ---------------------------------------------------------------------------
# 3. Cluster and score themes
# ---------------------------------------------------------------------------

def _cluster_and_score_themes(headlines, tag_results):
    """Group tagged headlines by theme and compute scores."""
    # Build theme → headlines mapping
    theme_headlines = {}
    for result in tag_results:
        idx = result.get("idx", -1)
        themes = result.get("themes", [])
        if idx < 0 or idx >= len(headlines):
            continue
        headline = headlines[idx]
        for theme_name in themes:
            if not theme_name or not isinstance(theme_name, str):
                continue
            theme_name = theme_name.strip().upper()
            slug = _slugify(theme_name)
            if slug not in theme_headlines:
                theme_headlines[slug] = {"name": theme_name, "headlines": []}
            theme_headlines[slug]["headlines"].append(headline)

    # Score each theme
    now = datetime.now(timezone.utc)
    cutoff_3d = now - timedelta(days=3)
    themes = []

    for slug, data in theme_headlines.items():
        hl_list = data["headlines"]
        story_count = len(hl_list)
        topics = set(h["topic"] for h in hl_list if h.get("topic"))
        topic_diversity = len(topics)

        # Minimum thresholds
        if story_count < 5 or topic_diversity < 2:
            continue

        avg_empathy = sum(h["empathy_score"] for h in hl_list) / story_count
        emotions = Counter(h["emotion"] for h in hl_list if h.get("emotion"))
        top_emotions = [e for e, _ in emotions.most_common(3)]

        # Growth: last 3 days vs prior 11 days
        recent = [h for h in hl_list if h["created_at"] >= cutoff_3d]
        prior = [h for h in hl_list if h["created_at"] < cutoff_3d]
        recent_count = len(recent)
        prior_count = len(prior)

        if prior_count == 0:
            growth_rate = 10.0 if recent_count > 0 else 1.0
        else:
            growth_rate = (recent_count / 3) / (prior_count / 11)

        # Evidence: top headlines by empathy
        evidence = sorted(hl_list, key=lambda h: h["empathy_score"], reverse=True)[:8]
        evidence_texts = [h["text"][:200] for h in evidence]

        # Composite score — floor growth at 0.3 so persistent themes don't get zeroed out
        # A steady 14-day theme (growth ~0.3) is still valuable
        effective_growth = max(growth_rate, 0.3)
        composite = story_count * topic_diversity * avg_empathy * effective_growth

        themes.append({
            "name": data["name"],
            "slug": slug,
            "story_count": story_count,
            "topic_diversity": topic_diversity,
            "avg_empathy": avg_empathy,
            "growth_rate": growth_rate,
            "recent_count": recent_count,
            "prior_count": prior_count,
            "top_emotions": top_emotions,
            "evidence_headlines": evidence_texts,
            "composite": composite,
        })

    themes.sort(key=lambda t: t["composite"], reverse=True)
    return themes


# ---------------------------------------------------------------------------
# 3b. Recency suppression (never repeat themes)
# ---------------------------------------------------------------------------

def _get_recent_radar_themes(engine, lookback_days=7):
    """Get theme slugs that appeared in recent Radar outputs."""
    try:
        df = pd.read_sql(sql_text("""
            SELECT topic AS theme_slug, output_date
            FROM output_topic_history
            WHERE output_type = 'radar_theme'
              AND output_date >= CURRENT_DATE - INTERVAL :days
            ORDER BY output_date DESC
        """), engine, params={"days": f"{lookback_days} days"})
        if df.empty:
            return {}
        # Build slug -> days_since_last_appearance
        today = datetime.now(timezone.utc).date()
        recency = {}
        for _, row in df.iterrows():
            slug = row["theme_slug"]
            days_ago = (today - row["output_date"]).days if hasattr(row["output_date"], "days") else (today - pd.Timestamp(row["output_date"]).date()).days
            if slug not in recency or days_ago < recency[slug]:
                recency[slug] = days_ago
        return recency
    except Exception:
        return {}


def _apply_recency_penalty(themes, recent_themes):
    """Penalize themes that appeared in recent Radar outputs.

    - Appeared yesterday (0-1 days ago): 0.05x (almost killed)
    - Appeared 2-3 days ago: 0.15x (heavy penalty)
    - Appeared 4-5 days ago: 0.4x (moderate penalty)
    - Appeared 6-7 days ago: 0.7x (light penalty)
    - Not seen in 7+ days: no penalty (1.0x)
    """
    if not recent_themes:
        return themes

    for theme in themes:
        slug = theme["slug"]
        if slug in recent_themes:
            days_ago = recent_themes[slug]
            if days_ago <= 1:
                penalty = 0.05
            elif days_ago <= 3:
                penalty = 0.15
            elif days_ago <= 5:
                penalty = 0.4
            elif days_ago <= 7:
                penalty = 0.7
            else:
                penalty = 1.0
            theme["composite"] *= penalty
            theme["suppressed"] = True
            theme["days_since_featured"] = days_ago
        else:
            theme["suppressed"] = False

    # Re-sort after penalties
    themes.sort(key=lambda t: t["composite"], reverse=True)
    return themes


def log_radar_themes(engine, theme_slugs):
    """Log which themes appeared in today's Radar output."""
    from topic_intelligence import ensure_output_history_table
    ensure_output_history_table(engine)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with engine.connect() as conn:
        for slug in theme_slugs:
            conn.execute(sql_text("""
                INSERT INTO output_topic_history (output_type, output_date, topic, section)
                VALUES ('radar_theme', :date, :slug, 'theme')
            """), {"date": today, "slug": slug})
        conn.commit()


# ---------------------------------------------------------------------------
# 4. Arc metadata (multi-week tracking)
# ---------------------------------------------------------------------------

def _compute_arc_metadata(engine, themes):
    """Compute first_seen and consecutive_days for each theme."""
    today = datetime.now(timezone.utc).date()

    for theme in themes:
        slug = theme["slug"]
        try:
            # Find earliest occurrence
            result = pd.read_sql(sql_text("""
                SELECT MIN(detection_date) AS first_seen
                FROM detected_themes
                WHERE theme_slug = :slug
            """), engine, params={"slug": slug})
            if not result.empty and pd.notna(result.iloc[0]["first_seen"]):
                theme["first_seen"] = result.iloc[0]["first_seen"]
            else:
                theme["first_seen"] = today

            # Count consecutive days backward from yesterday
            hist = pd.read_sql(sql_text("""
                SELECT DISTINCT detection_date
                FROM detected_themes
                WHERE theme_slug = :slug
                ORDER BY detection_date DESC
                LIMIT 30
            """), engine, params={"slug": slug})
            consecutive = 0
            check_date = today - timedelta(days=1)
            if not hist.empty:
                dates = set(hist["detection_date"].tolist())
                while check_date in dates:
                    consecutive += 1
                    check_date -= timedelta(days=1)
            theme["consecutive_days"] = consecutive + 1  # +1 for today
        except Exception as e:
            theme["first_seen"] = today
            theme["consecutive_days"] = 1
            print(f"  Arc metadata failed for {slug}: {e}")


# ---------------------------------------------------------------------------
# 5. Persist themes
# ---------------------------------------------------------------------------

def _persist_themes(engine, themes):
    """Upsert top themes into detected_themes table."""
    today = datetime.now(timezone.utc).date()
    with engine.connect() as conn:
        for theme in themes[:15]:
            conn.execute(sql_text("""
                INSERT INTO detected_themes
                    (detection_date, theme_name, theme_slug, story_count, topic_diversity,
                     avg_empathy, growth_rate, recent_count, prior_count,
                     top_emotions, evidence_headlines, first_seen, consecutive_days)
                VALUES
                    (:date, :name, :slug, :story_count, :topic_diversity,
                     :avg_empathy, :growth_rate, :recent_count, :prior_count,
                     :top_emotions, :evidence, :first_seen, :consecutive_days)
                ON CONFLICT (detection_date, theme_slug) DO UPDATE SET
                    story_count = EXCLUDED.story_count,
                    topic_diversity = EXCLUDED.topic_diversity,
                    avg_empathy = EXCLUDED.avg_empathy,
                    growth_rate = EXCLUDED.growth_rate,
                    recent_count = EXCLUDED.recent_count,
                    prior_count = EXCLUDED.prior_count,
                    top_emotions = EXCLUDED.top_emotions,
                    evidence_headlines = EXCLUDED.evidence_headlines,
                    consecutive_days = EXCLUDED.consecutive_days
            """), {
                "date": today,
                "name": theme["name"],
                "slug": theme["slug"],
                "story_count": theme["story_count"],
                "topic_diversity": theme["topic_diversity"],
                "avg_empathy": theme["avg_empathy"],
                "growth_rate": theme["growth_rate"],
                "recent_count": theme["recent_count"],
                "prior_count": theme["prior_count"],
                "top_emotions": json.dumps(theme["top_emotions"]),
                "evidence": json.dumps(theme["evidence_headlines"]),
                "first_seen": theme.get("first_seen", today),
                "consecutive_days": theme.get("consecutive_days", 1),
            })
        conn.commit()


# ---------------------------------------------------------------------------
# 6. Main orchestrator
# ---------------------------------------------------------------------------

def detect_and_persist_themes(engine):
    """Detect societal themes, persist to DB, return ranked list."""
    ensure_themes_table(engine)

    # Fetch headlines
    headlines = _fetch_high_empathy_headlines(engine)
    if not headlines:
        print("  No headlines found for theme detection")
        return []

    # Tag in batches of 75
    batch_size = 75
    all_tags = []
    offset = 0
    for i in range(0, len(headlines), batch_size):
        batch = headlines[i:i + batch_size]
        print(f"  Tagging batch {i // batch_size + 1}/{(len(headlines) + batch_size - 1) // batch_size}...")
        batch_tags = _tag_themes_batch(batch)
        # Offset indices to match global headline list
        for tag in batch_tags:
            tag["idx"] = tag.get("idx", 0) + i
        all_tags.extend(batch_tags)

    # Cluster and score
    themes = _cluster_and_score_themes(headlines, all_tags)
    print(f"  Detected {len(themes)} themes above threshold")

    if not themes:
        return []

    # Compute arc metadata
    _compute_arc_metadata(engine, themes)

    # Apply recency penalty — suppress themes featured in recent Radars
    recent = _get_recent_radar_themes(engine, lookback_days=7)
    if recent:
        themes = _apply_recency_penalty(themes, recent)
        suppressed = [t["name"] for t in themes if t.get("suppressed")]
        if suppressed:
            print(f"  Suppressed {len(suppressed)} recently-featured themes: {', '.join(suppressed)}")

    # Persist (all themes, not just unsuppressed — for arc tracking)
    _persist_themes(engine, themes)
    print(f"  Persisted {min(len(themes), 15)} themes to DB")

    return themes


# ---------------------------------------------------------------------------
# 7. Read-only accessor for persistent themes
# ---------------------------------------------------------------------------

def get_active_themes(engine, min_days=2, limit=10):
    """Get themes that have appeared on multiple recent days (proven persistent)."""
    try:
        df = pd.read_sql(sql_text("""
            SELECT theme_name, theme_slug, story_count, topic_diversity,
                   avg_empathy, growth_rate, consecutive_days, first_seen,
                   top_emotions, evidence_headlines
            FROM detected_themes
            WHERE detection_date = CURRENT_DATE
              AND consecutive_days >= :min_days
            ORDER BY story_count * topic_diversity * avg_empathy * growth_rate DESC
            LIMIT :limit
        """), engine, params={"min_days": min_days, "limit": limit})
        if df.empty:
            return []
        themes = []
        for _, row in df.iterrows():
            themes.append({
                "name": row["theme_name"],
                "slug": row["theme_slug"],
                "story_count": row["story_count"],
                "topic_diversity": row["topic_diversity"],
                "avg_empathy": row["avg_empathy"],
                "growth_rate": row["growth_rate"],
                "consecutive_days": row["consecutive_days"],
                "first_seen": row["first_seen"],
                "top_emotions": json.loads(row["top_emotions"]) if row["top_emotions"] else [],
                "evidence_headlines": json.loads(row["evidence_headlines"]) if row["evidence_headlines"] else [],
            })
        return themes
    except Exception as e:
        print(f"  get_active_themes failed: {e}")
        return []


# ---------------------------------------------------------------------------
# 8. Format for Claude prompt
# ---------------------------------------------------------------------------

def format_themes_context(themes, top_n=5):
    """Format detected themes into context string for Radar prompt."""
    if not themes:
        return ""

    # Count strong themes (composite > 50 after penalties)
    strong = [t for t in themes[:top_n] if t.get("composite", 0) > 50]
    if len(strong) < 2:
        lines = ["SOCIETAL THEMES (SLOW DAY — fewer strong patterns detected)"]
        lines.append("=" * 50)
        lines.append("  NOTE TO WRITER: Only 0-1 strong themes today. Go DEEP on what exists")
        lines.append("  rather than forcing 3 topics. One rich, deeply-reported story is better")
        lines.append("  than three thin ones. Use the 'quiet but deeply felt' stories below")
        lines.append("  to find something nobody else is covering.")
    else:
        lines = ["RECURRING SOCIETAL THEMES (patterns detected across 14 days of data)"]
        lines.append("=" * 50)

    for theme in themes[:top_n]:
        days = theme.get("consecutive_days", 1)
        growth = theme.get("growth_rate", 1.0)

        if days >= 7:
            arc_label = f"persistent, {days} days running"
        elif growth > 2.0:
            arc_label = "accelerating fast"
        elif days >= 3:
            arc_label = f"building, {days} days"
        else:
            arc_label = "emerging"

        lines.append(f"\n  {theme['name']} [{arc_label}]")
        lines.append(
            f"    Stories: {theme['story_count']} across {theme['topic_diversity']} topics | "
            f"Avg empathy: {theme.get('avg_empathy', 0):.4f} | "
            f"Growth: {growth:.1f}x"
        )

        emotions = theme.get("top_emotions", [])
        if emotions:
            lines.append(f"    Top emotions: {', '.join(emotions)}")

        evidence = theme.get("evidence_headlines", [])
        if evidence:
            lines.append("    Evidence:")
            for headline in evidence[:5]:
                lines.append(f"      - \"{headline}\"")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI for standalone testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        print("DATABASE_URL not set")
        exit(1)

    from sqlalchemy import create_engine
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(db_url)

    print("=" * 60)
    print("Theme Detector — Standalone Run")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    themes = detect_and_persist_themes(engine)

    print(f"\n{'=' * 60}")
    print(f"Detected {len(themes)} themes:\n")
    for t in themes[:10]:
        print(f"  {t['name']}")
        print(f"    stories={t['story_count']}, topics={t['topic_diversity']}, "
              f"empathy={t['avg_empathy']:.4f}, growth={t['growth_rate']:.1f}x, "
              f"days={t.get('consecutive_days', 1)}")
        print()

    print("\nFormatted context:")
    print(format_themes_context(themes))
