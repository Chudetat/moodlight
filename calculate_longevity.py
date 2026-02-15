#!/usr/bin/env python
"""
calculate_longevity.py
Calculates velocity and longevity scores for topics.

Velocity: volume acceleration — how fast is coverage growing? (recent vs older post rate)
Longevity: staying power — source diversity, conversation depth, time persistence, topic breadth

Reads from PostgreSQL (social_scored + news_scored tables).
Saves results to topic_longevity table + CSV fallback.
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta, timezone
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
            CREATE TABLE IF NOT EXISTS topic_longevity (
                topic VARCHAR(200) PRIMARY KEY,
                longevity_score FLOAT,
                velocity_score FLOAT,
                post_count INTEGER,
                source_count INTEGER,
                avg_engagement FLOAT,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.commit()


# ── Longevity components ──

def calculate_source_diversity(topic_df):
    """How many different sources discuss this topic?"""
    unique_sources = topic_df['source'].nunique()
    total_possible = 20
    return min(unique_sources / total_possible, 1.0)


def calculate_conversation_depth(topic_df):
    """Ratio of replies to likes — deeper discussion = higher longevity."""
    if 'reply_count' in topic_df.columns and 'like_count' in topic_df.columns:
        total_replies = topic_df['reply_count'].sum()
        total_likes = topic_df['like_count'].sum()
        if total_likes > 0:
            depth_ratio = total_replies / total_likes
            return min(depth_ratio / 0.3, 1.0)
    return 0.5


def calculate_time_persistence(topic_df):
    """How many days does this topic appear?"""
    if 'created_at' not in topic_df.columns:
        return 0.5
    dates = pd.to_datetime(topic_df['created_at'], errors='coerce').dt.date
    unique_days = dates.nunique()
    if unique_days <= 1:
        return 0.3
    elif unique_days >= 7:
        return 1.0
    else:
        return 0.3 + (unique_days - 1) * 0.7 / 6


def calculate_topic_breadth(topic_name):
    """Does this topic connect to fundamental themes?"""
    lasting_topics = {
        'war & foreign policy': 0.9,
        'economics': 0.85,
        'climate & environment': 0.85,
        'politics': 0.8,
        'healthcare & wellbeing': 0.8,
        'technology & ai': 0.75,
        'education': 0.7,
        'crime & safety': 0.6,
        'sports': 0.4,
        'entertainment': 0.3,
        'other': 0.5,
    }
    return lasting_topics.get(topic_name, 0.5)


def calculate_longevity_score(topic_name, topic_df):
    """Overall longevity score (0-1). Weights: source 30%, depth 20%, persistence 30%, breadth 20%."""
    source_div = calculate_source_diversity(topic_df)
    conv_depth = calculate_conversation_depth(topic_df)
    time_persist = calculate_time_persistence(topic_df)
    topic_broad = calculate_topic_breadth(topic_name)
    return source_div * 0.30 + conv_depth * 0.20 + time_persist * 0.30 + topic_broad * 0.20


# ── Velocity ──

def calculate_velocity(topic_df):
    """Volume acceleration: recent post rate vs older post rate.

    Compares last 48h daily rate against the preceding 5-day daily rate.
    Works for all sources (news + social) since it only needs timestamps.
    """
    if 'created_at' not in topic_df.columns or len(topic_df) < 2:
        return 0.0

    now = datetime.now(timezone.utc)
    cutoff_48h = now - timedelta(hours=48)
    cutoff_7d = now - timedelta(days=7)

    dates = pd.to_datetime(topic_df['created_at'], errors='coerce', utc=True)
    recent = (dates >= cutoff_48h).sum()
    older = ((dates >= cutoff_7d) & (dates < cutoff_48h)).sum()

    if older == 0:
        return 1.0 if recent > 0 else 0.0

    recent_rate = recent / 2.0   # posts per day (48h window)
    older_rate = older / 5.0     # posts per day (5-day window)

    if older_rate == 0:
        return 1.0 if recent_rate > 0 else 0.0

    ratio = recent_rate / older_rate
    return min(ratio / 2.0, 1.0)


def calculate_engagement_velocity(topic_df):
    """Engagement velocity from social posts only (boost signal)."""
    if 'engagement' not in topic_df.columns or 'source' not in topic_df.columns:
        return 0.0
    social = topic_df[topic_df['source'] == 'x']
    if social.empty or social['engagement'].sum() == 0:
        return 0.0
    dates = pd.to_datetime(social['created_at'], errors='coerce', utc=True)
    now = datetime.now(timezone.utc)
    age_hours = (now - dates).dt.total_seconds() / 3600
    age_hours = age_hours.clip(lower=0.1)
    eng_velocity = (social['engagement'] / age_hours).mean()
    # Normalize: 10+ engagement/hour = max
    return min(eng_velocity / 10.0, 1.0)


# ── Main analysis ──

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
        if not any(f is not None for f in frames) or len(frames) < 2:
            try:
                df = pd.read_csv(csv)
                print(f"  Loaded {len(df)} rows from CSV: {csv}")
                frames.append(df)
            except FileNotFoundError:
                pass
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def analyze_all_topics(engine=None):
    """Analyze velocity and longevity for all topics."""
    df_all = _load_data(engine)
    if df_all.empty:
        print("No data available.")
        return pd.DataFrame()

    df_all['created_at'] = pd.to_datetime(df_all['created_at'], errors='coerce', utc=True)

    results = []
    for topic in df_all['topic'].unique():
        if pd.isna(topic):
            continue
        topic_df = df_all[df_all['topic'] == topic]

        longevity = calculate_longevity_score(topic, topic_df)

        # Velocity: 60% volume acceleration + 40% engagement boost
        vol_velocity = calculate_velocity(topic_df)
        eng_velocity = calculate_engagement_velocity(topic_df)
        velocity = vol_velocity * 0.6 + eng_velocity * 0.4

        avg_engagement = 0.0
        if 'engagement' in topic_df.columns:
            avg_engagement = topic_df['engagement'].mean()

        results.append({
            'topic': topic,
            'longevity_score': round(longevity, 4),
            'velocity_score': round(velocity, 4),
            'post_count': len(topic_df),
            'source_count': topic_df['source'].nunique() if 'source' in topic_df.columns else 0,
            'avg_engagement': round(avg_engagement, 2),
        })

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('longevity_score', ascending=False)
    return results_df


def _save_to_db(results_df, engine):
    """Upsert results into topic_longevity table."""
    from sqlalchemy import text
    _ensure_table(engine)
    with engine.connect() as conn:
        for _, row in results_df.iterrows():
            conn.execute(text("""
                INSERT INTO topic_longevity (topic, longevity_score, velocity_score, post_count, source_count, avg_engagement, updated_at)
                VALUES (:topic, :longevity, :velocity, :posts, :sources, :engagement, NOW())
                ON CONFLICT (topic) DO UPDATE SET
                    longevity_score = EXCLUDED.longevity_score,
                    velocity_score = EXCLUDED.velocity_score,
                    post_count = EXCLUDED.post_count,
                    source_count = EXCLUDED.source_count,
                    avg_engagement = EXCLUDED.avg_engagement,
                    updated_at = NOW()
            """), {
                "topic": row['topic'],
                "longevity": row['longevity_score'],
                "velocity": row['velocity_score'],
                "posts": int(row['post_count']),
                "sources": int(row['source_count']),
                "engagement": row['avg_engagement'],
            })
        conn.commit()
    print(f"  Saved {len(results_df)} topics to DB")


if __name__ == "__main__":
    print("Calculating velocity & longevity scores...\n")

    engine = _get_engine()
    results = analyze_all_topics(engine)

    if results.empty:
        print("No topics to analyze.")
        sys.exit(0)

    print(f"\nTop 10 Topics by Longevity:")
    print("=" * 80)
    print(results.head(10).to_string(index=False))

    print(f"\nVelocity leaders:")
    print("=" * 80)
    print(results.sort_values('velocity_score', ascending=False).head(5).to_string(index=False))

    # Save to DB
    if engine:
        try:
            _save_to_db(results, engine)
        except Exception as e:
            print(f"  DB save failed: {e}")

    # Save CSV as fallback
    results.to_csv('topic_longevity.csv', index=False)
    print(f"\n✓ Saved {len(results)} topics to topic_longevity.csv")
