#!/usr/bin/env python
"""
calculate_scarcity.py
Identifies topic gaps and white-space opportunities.

Scarcity = inverse of coverage. High scarcity = underserved topic = opportunity.
Uses continuous log-scaled scoring instead of fixed buckets.

Reads from PostgreSQL (social_scored + news_scored tables).
Saves results to topic_scarcity table + CSV fallback.
"""

import os
import sys
import math
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


def _get_engine():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return None
    from sqlalchemy import create_engine
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    if "sslmode" not in db_url:
        sep = "&" if "?" in db_url else "?"
        db_url = db_url + sep + "sslmode=require"
    return create_engine(db_url, pool_pre_ping=True, pool_size=1, max_overflow=0)


def _ensure_table(engine):
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS topic_scarcity (
                topic VARCHAR(200) PRIMARY KEY,
                scarcity_score FLOAT,
                mention_count INTEGER,
                coverage_level VARCHAR(50),
                opportunity VARCHAR(10),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.commit()


# Expected important topics — keyword lists for detection
EXPECTED_TOPICS = {
    'AI regulation & ethics': ['ai regulation', 'ai ethics', 'ai safety', 'ai governance', 'ai policy'],
    'Climate action': ['climate action', 'renewable energy', 'carbon emissions', 'sustainability', 'green energy'],
    'Mental health': ['mental health', 'therapy', 'wellbeing', 'anxiety', 'depression', 'burnout'],
    'Remote work': ['remote work', 'hybrid work', 'work from home', 'digital nomad', 'return to office'],
    'Inflation & cost of living': ['inflation', 'cost of living', 'prices', 'affordability', 'consumer prices'],
    'Cybersecurity': ['cybersecurity', 'data breach', 'privacy', 'hacking', 'ransomware', 'cyber attack'],
    'Healthcare access': ['healthcare access', 'medical costs', 'insurance', 'hospital', 'health equity'],
    'Education reform': ['education reform', 'student debt', 'online learning', 'teachers', 'higher education'],
    'Housing affordability': ['housing crisis', 'rent', 'mortgage', 'homelessness', 'housing market'],
    'Social media regulation': ['social media regulation', 'content moderation', 'platform accountability', 'online safety'],
    'Crypto regulation': ['crypto regulation', 'bitcoin regulation', 'defi', 'digital currency', 'stablecoin'],
    'Space exploration': ['space exploration', 'mars', 'spacex', 'nasa', 'satellite', 'lunar'],
    'EV adoption': ['electric vehicles', 'ev charging', 'tesla', 'charging infrastructure', 'ev market'],
    'Aging population': ['aging', 'elderly care', 'retirement', 'social security', 'senior care'],
    'Food security': ['food security', 'supply chain', 'agriculture', 'farming', 'food prices'],
    'AI agents & automation': ['ai agent', 'autonomous agent', 'agentic ai', 'workflow automation', 'ai assistant'],
    'Loneliness & social isolation': ['loneliness', 'social isolation', 'community', 'belonging', 'disconnection'],
    'Disinformation': ['disinformation', 'misinformation', 'deepfake', 'fake news', 'media literacy'],
}


def _calculate_scarcity_score(mention_count, max_mentions):
    """Continuous log-scaled scarcity score (0-1).

    0 mentions → 1.0 (max scarcity)
    max mentions → ~0.0 (no scarcity)
    Smooth curve between these extremes.
    """
    if mention_count == 0:
        return 1.0
    if max_mentions <= 0:
        return 0.5
    # Log-scaled inverse: more mentions = less scarce
    log_ratio = math.log1p(mention_count) / math.log1p(max_mentions)
    return round(max(1.0 - log_ratio, 0.0), 4)


def _coverage_level(scarcity):
    """Human-readable coverage label."""
    if scarcity >= 0.9:
        return 'Zero coverage'
    elif scarcity >= 0.75:
        return 'Minimal coverage'
    elif scarcity >= 0.55:
        return 'Low coverage'
    elif scarcity >= 0.35:
        return 'Moderate coverage'
    elif scarcity >= 0.15:
        return 'Good coverage'
    else:
        return 'Saturated'


def _opportunity_level(scarcity):
    """Opportunity classification."""
    if scarcity > 0.6:
        return 'HIGH'
    elif scarcity > 0.35:
        return 'MEDIUM'
    else:
        return 'LOW'


# ── Data loading ──

def _load_data(engine=None):
    """Load scored data from DB, fall back to CSV."""
    frames = []
    if engine:
        from sqlalchemy import text
        for table in ("social_scored", "news_scored"):
            try:
                df = pd.read_sql(f"SELECT * FROM {table}", engine)
                if not df.empty:
                    print(f"  Loaded {len(df)} rows from DB: {table}")
                    frames.append(df)
                    continue
            except Exception:
                pass
    # CSV fallback
    for csv in ("social_scored.csv", "news_scored.csv"):
        if len(frames) < 2:
            try:
                df = pd.read_csv(csv)
                print(f"  Loaded {len(df)} rows from CSV: {csv}")
                frames.append(df)
            except FileNotFoundError:
                pass
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def check_topic_coverage(df_all):
    """Check which expected topics are underrepresented using continuous scoring."""
    all_text = ' '.join(df_all['text'].dropna().astype(str).str.lower())

    # Count mentions for each expected topic
    raw_counts = {}
    for topic_name, keywords in EXPECTED_TOPICS.items():
        mentions = sum(all_text.count(kw) for kw in keywords)
        raw_counts[topic_name] = mentions

    # Find max mentions for log scaling
    max_mentions = max(raw_counts.values()) if raw_counts else 1

    coverage = []
    for topic_name, mentions in raw_counts.items():
        scarcity = _calculate_scarcity_score(mentions, max_mentions)
        coverage.append({
            'topic': topic_name,
            'scarcity_score': scarcity,
            'mention_count': mentions,
            'coverage_level': _coverage_level(scarcity),
            'opportunity': _opportunity_level(scarcity),
        })

    return pd.DataFrame(coverage).sort_values('scarcity_score', ascending=False)


def find_topic_gaps(engine=None):
    """Find gaps between what exists and what's expected."""
    df_all = _load_data(engine)
    if df_all.empty:
        print("No data available.")
        return pd.DataFrame()

    print("Analyzing topic coverage...\n")

    # Existing topic distribution
    existing_topics = df_all['topic'].value_counts()
    print("Current Topic Distribution:")
    print("=" * 80)
    print(existing_topics.head(10).to_string())

    # Expected topic scarcity
    print("\n\nExpected Topic Scarcity Analysis:")
    print("=" * 80)
    coverage_df = check_topic_coverage(df_all)
    print(coverage_df.to_string(index=False))

    return coverage_df


def _save_to_db(results_df, engine):
    """Upsert results into topic_scarcity table."""
    from sqlalchemy import text
    _ensure_table(engine)
    with engine.connect() as conn:
        for _, row in results_df.iterrows():
            conn.execute(text("""
                INSERT INTO topic_scarcity (topic, scarcity_score, mention_count, coverage_level, opportunity, updated_at)
                VALUES (:topic, :scarcity, :mentions, :coverage, :opportunity, NOW())
                ON CONFLICT (topic) DO UPDATE SET
                    scarcity_score = EXCLUDED.scarcity_score,
                    mention_count = EXCLUDED.mention_count,
                    coverage_level = EXCLUDED.coverage_level,
                    opportunity = EXCLUDED.opportunity,
                    updated_at = NOW()
            """), {
                "topic": row['topic'],
                "scarcity": row['scarcity_score'],
                "mentions": int(row['mention_count']),
                "coverage": row['coverage_level'],
                "opportunity": row['opportunity'],
            })
        conn.commit()
    print(f"  Saved {len(results_df)} topics to DB")


if __name__ == "__main__":
    print("Calculating topic scarcity...\n")

    engine = _get_engine()
    results = find_topic_gaps(engine)

    if results.empty:
        print("No topics to analyze.")
        sys.exit(0)

    # Strategic opportunities summary
    print(f"\nStrategic Opportunities:")
    print("=" * 80)
    high_opp = results[results['opportunity'] == 'HIGH']
    if len(high_opp) > 0:
        print("\nHIGH OPPORTUNITY (First-mover advantage):")
        for _, row in high_opp.iterrows():
            print(f"  {row['topic']} (scarcity: {row['scarcity_score']:.2f}, {row['mention_count']} mentions)")

    medium_opp = results[results['opportunity'] == 'MEDIUM']
    if len(medium_opp) > 0:
        print("\nMEDIUM OPPORTUNITY (Differentiation possible):")
        for _, row in medium_opp.iterrows():
            print(f"  {row['topic']} (scarcity: {row['scarcity_score']:.2f}, {row['mention_count']} mentions)")

    # Save to DB
    if engine:
        try:
            _save_to_db(results, engine)
        except Exception as e:
            print(f"  DB save failed: {e}")

    # Save CSV as fallback
    results.to_csv('topic_scarcity.csv', index=False)
    print(f"\n✓ Saved {len(results)} topics to topic_scarcity.csv")
