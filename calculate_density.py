#!/usr/bin/env python
"""
calculate_density.py
Calculates concentration/depth of topic discussions.

Density = how crowded/saturated the conversation is around a topic.
Components: volume share, source diversity, geographic spread, coverage depth.

Reads from PostgreSQL (social_scored + news_scored tables).
Saves results to topic_density table + CSV fallback.
"""

import os
import sys
import math
import pandas as pd
from datetime import datetime, timedelta, timezone
from collections import Counter
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
            CREATE TABLE IF NOT EXISTS topic_density (
                topic VARCHAR(200) PRIMARY KEY,
                density_score FLOAT,
                primary_region VARCHAR(100),
                geo_diversity FLOAT,
                primary_platform VARCHAR(100),
                conversation_depth VARCHAR(50),
                depth_score FLOAT,
                post_count INTEGER,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.commit()


# ── Geographic mapping — expanded to match actual RSS feed source names ──

GEO_MAPPING = {
    # North America
    'cnn': 'North America', 'fox_news': 'North America', 'fox_business': 'North America',
    'abc_news': 'North America', 'cbs_news': 'North America', 'nbc': 'North America',
    'npr': 'North America', 'usa_today': 'North America', 'washington_post': 'North America',
    'new_york_times': 'North America', 'nyt': 'North America', 'ny_post': 'North America',
    'politico': 'North America', 'ap_news': 'North America', 'associated_press': 'North America',
    'wall_street_journal': 'North America', 'wsj': 'North America',
    'bloomberg': 'North America', 'cnbc': 'North America', 'marketwatch': 'North America',
    'yahoo': 'North America', 'huffpost': 'North America', 'buzzfeed': 'North America',
    'vice': 'North America', 'vox': 'North America', 'slate': 'North America',
    'the_atlantic': 'North America', 'newsweek': 'North America', 'axios': 'North America',
    'the_verge': 'North America', 'techcrunch': 'North America', 'ars_technica': 'North America',
    'wired': 'North America', 'engadget': 'North America', 'venturebeat': 'North America',
    'seeking_alpha': 'North America', 'benzinga': 'North America', 'motley_fool': 'North America',
    'the_hill': 'North America', 'daily_beast': 'North America',
    # UK/Europe
    'bbc': 'UK/Europe', 'guardian': 'UK/Europe', 'telegraph': 'UK/Europe',
    'independent': 'UK/Europe', 'sky_news': 'UK/Europe', 'reuters': 'UK/Europe',
    'financial_times': 'UK/Europe', 'economist': 'UK/Europe', 'ft_': 'UK/Europe',
    'euronews': 'UK/Europe', 'dw_': 'UK/Europe', 'france24': 'UK/Europe',
    'der_spiegel': 'UK/Europe', 'le_monde': 'UK/Europe', 'daily_mail': 'UK/Europe',
    'mirror': 'UK/Europe', 'metro_uk': 'UK/Europe',
    # Middle East
    'al_jazeera': 'Middle East', 'middle_east': 'Middle East',
    'jerusalem_post': 'Middle East', 'haaretz': 'Middle East',
    'arab_news': 'Middle East', 'gulf_news': 'Middle East', 'times_of_israel': 'Middle East',
    # Asia
    'japan_times': 'Asia', 'korea_herald': 'Asia', 'korea_times': 'Asia',
    'times_of_india': 'Asia', 'indian_express': 'Asia', 'hindustan': 'Asia',
    'south_china': 'Asia', 'scmp': 'Asia', 'nikkei': 'Asia',
    'strait_times': 'Asia', 'bangkok_post': 'Asia', 'channel_news_asia': 'Asia',
    # Latin America
    'brazil': 'Latin America', 'mexico': 'Latin America', 'buenos_aires': 'Latin America',
    # Africa
    'africa': 'Africa', 'daily_nation': 'Africa', 'nation_africa': 'Africa',
    # Global / Social
    'x': 'Global', 'reddit': 'Global', 'google_news': 'Global',
}


def get_geographic_density(topic_df):
    """Which regions are discussing this topic?"""
    regions = []
    for source in topic_df['source'].astype(str):
        source_lower = source.lower()
        matched = False
        for key, region in GEO_MAPPING.items():
            if key in source_lower:
                regions.append(region)
                matched = True
                break
        if not matched:
            regions.append('Other')

    if not regions:
        return {'diversity': 0, 'primary_region': 'Unknown'}

    region_counts = Counter(regions)
    # Don't count "Other" as a meaningful region for diversity
    meaningful = {k: v for k, v in region_counts.items() if k != 'Other'}
    total_possible = 6  # NA, UK/Europe, Middle East, Asia, Latin America, Africa
    diversity = len(meaningful) / total_possible if meaningful else 0

    primary = region_counts.most_common(1)[0][0]
    # If primary is "Other" but we have meaningful regions, use the top meaningful one
    if primary == 'Other' and meaningful:
        primary = max(meaningful, key=meaningful.get)

    return {
        'diversity': min(diversity, 1.0),
        'primary_region': primary,
    }


def get_platform_density(topic_df):
    """Which platforms are discussing this topic?"""
    platforms = []
    for source in topic_df['source'].astype(str):
        source_lower = source.lower()
        if 'reddit' in source_lower:
            platforms.append('Social (Reddit)')
        elif source_lower == 'x':
            platforms.append('Social (X)')
        else:
            platforms.append('News Media')

    platform_counts = Counter(platforms)
    diversity = len(platform_counts) / 3.0
    primary = platform_counts.most_common(1)[0][0]

    return {
        'diversity': diversity,
        'primary_platform': primary,
    }


def get_conversation_depth(topic_df):
    """How deep are the discussions?

    For social posts: reply/like ratio.
    For news: articles-per-source concentration and time span.
    Blends all available signals.
    """
    signals = []

    # Social depth: reply-to-like ratio
    if 'reply_count' in topic_df.columns and 'like_count' in topic_df.columns:
        social = topic_df[topic_df['source'].astype(str) == 'x'] if 'source' in topic_df.columns else pd.DataFrame()
        if not social.empty:
            total_replies = social['reply_count'].sum()
            total_likes = social['like_count'].sum()
            if total_likes > 0:
                signals.append(min(total_replies / total_likes / 0.3, 1.0))

    # News depth: articles per source (multiple articles from same outlet = deeper coverage)
    if 'source' in topic_df.columns:
        news = topic_df[topic_df['source'].astype(str) != 'x']
        if not news.empty and len(news) > 1:
            unique_sources = news['source'].nunique()
            articles_per_source = len(news) / max(unique_sources, 1)
            # 3+ articles per source = deep, sustained coverage
            signals.append(min(articles_per_source / 3.0, 1.0))

    # Time depth: how many days does this topic appear?
    if 'created_at' in topic_df.columns:
        dates = pd.to_datetime(topic_df['created_at'], errors='coerce').dt.date
        unique_days = dates.nunique()
        if unique_days >= 1:
            # 5+ days = deep/sustained
            signals.append(min(unique_days / 5.0, 1.0))

    if not signals:
        depth_score = 0.3
    else:
        depth_score = sum(signals) / len(signals)

    if depth_score < 0.3:
        category = 'Surface (shares only)'
    elif depth_score < 0.6:
        category = 'Medium (some discussion)'
    else:
        category = 'Deep (active debate)'

    return {'depth_score': depth_score, 'depth_category': category}


# ── Main density calculation ──

def calculate_density_score(topic_df, total_posts):
    """Overall density score (0-1).

    Density = how crowded/saturated the conversation is.
    Components:
    - Volume share (35%): post count relative to total (log-scaled)
    - Source diversity (25%): unique sources covering this topic
    - Geographic spread (20%): regional diversity
    - Coverage depth (20%): articles-per-source, time span, engagement depth
    """
    post_count = len(topic_df)

    # Volume: log-scaled share of total posts
    if total_posts > 0 and post_count > 0:
        share = post_count / total_posts
        volume = min(math.log1p(share * 100) / math.log1p(100), 1.0)
    else:
        volume = 0.0

    # Source diversity
    if 'source' in topic_df.columns:
        unique_sources = topic_df['source'].nunique()
        source_score = min(unique_sources / 15.0, 1.0)  # 15+ sources = max
    else:
        source_score = 0.0

    # Geographic spread
    geo = get_geographic_density(topic_df)
    geo_score = geo['diversity']

    # Coverage depth
    depth = get_conversation_depth(topic_df)
    depth_score = depth['depth_score']

    density = volume * 0.35 + source_score * 0.25 + geo_score * 0.20 + depth_score * 0.20

    platform = get_platform_density(topic_df)

    return density, geo, platform, depth


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


def analyze_all_densities(engine=None):
    """Analyze density for all topics."""
    df_all = _load_data(engine)
    if df_all.empty:
        print("No data available.")
        return pd.DataFrame()

    if 'created_at' in df_all.columns:
        df_all['created_at'] = pd.to_datetime(df_all['created_at'], errors='coerce', utc=True)

    total_posts = len(df_all)
    results = []

    for topic in df_all['topic'].unique():
        if pd.isna(topic):
            continue
        topic_df = df_all[df_all['topic'] == topic]
        density, geo, platform, depth = calculate_density_score(topic_df, total_posts)

        results.append({
            'topic': topic,
            'density_score': round(density, 4),
            'primary_region': geo['primary_region'],
            'geo_diversity': round(geo['diversity'], 4),
            'primary_platform': platform['primary_platform'],
            'conversation_depth': depth['depth_category'],
            'depth_score': round(depth['depth_score'], 4),
            'post_count': len(topic_df),
        })

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('density_score', ascending=False)
    return results_df


def _save_to_db(results_df, engine):
    """Upsert results into topic_density table."""
    from sqlalchemy import text
    _ensure_table(engine)
    with engine.connect() as conn:
        for _, row in results_df.iterrows():
            conn.execute(text("""
                INSERT INTO topic_density (topic, density_score, primary_region, geo_diversity,
                    primary_platform, conversation_depth, depth_score, post_count, updated_at)
                VALUES (:topic, :density, :region, :geo_div, :platform, :depth_cat, :depth, :posts, NOW())
                ON CONFLICT (topic) DO UPDATE SET
                    density_score = EXCLUDED.density_score,
                    primary_region = EXCLUDED.primary_region,
                    geo_diversity = EXCLUDED.geo_diversity,
                    primary_platform = EXCLUDED.primary_platform,
                    conversation_depth = EXCLUDED.conversation_depth,
                    depth_score = EXCLUDED.depth_score,
                    post_count = EXCLUDED.post_count,
                    updated_at = NOW()
            """), {
                "topic": row['topic'],
                "density": row['density_score'],
                "region": row['primary_region'],
                "geo_div": row['geo_diversity'],
                "platform": row['primary_platform'],
                "depth_cat": row['conversation_depth'],
                "depth": row['depth_score'],
                "posts": int(row['post_count']),
            })
        conn.commit()
    print(f"  Saved {len(results_df)} topics to DB")


if __name__ == "__main__":
    print("Calculating topic density...\n")

    engine = _get_engine()
    results = analyze_all_densities(engine)

    if results.empty:
        print("No topics to analyze.")
        sys.exit(0)

    print(f"\nTopics by Density (High = Concentrated & Deep):")
    print("=" * 100)
    print(results.head(15).to_string(index=False))

    # Save to DB
    if engine:
        try:
            _save_to_db(results, engine)
        except Exception as e:
            print(f"  DB save failed: {e}")

    # Save CSV as fallback
    results.to_csv('topic_density.csv', index=False)
    print(f"\n✓ Saved {len(results)} topics to topic_density.csv")
