"""
Data loading service - fetches news/social data from database or CSV fallback.
Port of load_data() from app.py with async support.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from pathlib import Path

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import NewsItem
from app.utils.constants import empathy_label_from_score, clean_source_name, SPAM_KEYWORDS

settings = get_settings()

# Path to CSV files (fallback)
DATA_DIR = Path(__file__).parent.parent.parent.parent  # moodlight root


async def load_data_from_db(
    db: AsyncSession,
    days: int = 30,
    source_filter: Optional[str] = None
) -> pd.DataFrame:
    """
    Load scored data from database.
    Queries both news_scored and social_scored tables (v1 schema).

    Args:
        db: Database session
        days: Number of days to look back
        source_filter: Optional filter for specific source (x, news, etc.)

    Returns:
        DataFrame with scored items
    """
    print(f"[data_loader] Loading data for {days} days", flush=True)

    # Ensure clean transaction state
    try:
        await db.rollback()
    except Exception:
        pass

    # Query each table separately to avoid UNION type mismatch issues
    # Cast all columns to text to handle schema differences
    base_columns = """
        id::text as id, text, created_at::text as created_at, link, source, topic,
        COALESCE(engagement::text, '0') as engagement, country, intensity::text as intensity,
        empathy_score::text as empathy_score, empathy_label,
        emotion_top_1, emotion_top_2, emotion_top_3
    """

    source_clause = ""
    params = {}
    if source_filter:
        source_clause = "WHERE source = :source"
        params["source"] = source_filter

    columns = ["id", "text", "created_at", "link", "source", "topic",
               "engagement", "country", "intensity", "empathy_score",
               "empathy_label", "emotion_top_1", "emotion_top_2", "emotion_top_3"]

    all_rows = []

    # Query news_scored
    news_rows = []
    try:
        sql_news = text(f"SELECT {base_columns} FROM news_scored {source_clause} ORDER BY created_at DESC LIMIT 500")
        print(f"[data_loader] Querying news_scored...", flush=True)
        result = await db.execute(sql_news, params)
        news_rows = result.fetchall()
        print(f"[data_loader] Got {len(news_rows)} rows from news_scored", flush=True)
    except Exception as e:
        print(f"[data_loader] Error querying news_scored: {e}", flush=True)
        try:
            await db.rollback()
        except Exception:
            pass

    # Query social_scored - need fresh connection state
    social_rows = []
    try:
        # Commit any pending state to reset transaction
        try:
            await db.commit()
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass

        sql_social = text(f"SELECT {base_columns} FROM social_scored {source_clause} ORDER BY created_at DESC LIMIT 500")
        print(f"[data_loader] Querying social_scored...", flush=True)
        result = await db.execute(sql_social, params)
        social_rows = result.fetchall()
        print(f"[data_loader] Got {len(social_rows)} rows from social_scored", flush=True)
    except Exception as e:
        print(f"[data_loader] Error querying social_scored: {e}", flush=True)
        try:
            await db.rollback()
        except Exception:
            pass

    all_rows = list(news_rows) + list(social_rows)

    if not all_rows:
        print("[data_loader] No rows returned from either table", flush=True)
        return pd.DataFrame()

    print(f"[data_loader] Total rows: {len(all_rows)}", flush=True)

    # Convert to DataFrame
    data = [dict(zip(columns, row)) for row in all_rows]
    df = pd.DataFrame(data)

    # Convert types
    df["engagement"] = pd.to_numeric(df["engagement"], errors="coerce").fillna(0)
    df["intensity"] = pd.to_numeric(df["intensity"], errors="coerce")
    df["empathy_score"] = pd.to_numeric(df["empathy_score"], errors="coerce")

    # Filter by date in pandas
    if "created_at" in df.columns and len(df) > 0:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        df = df[df["created_at"] >= cutoff]
        print(f"[data_loader] After date filter: {len(df)} rows", flush=True)

    # Sort by created_at
    df = df.sort_values("created_at", ascending=False)

    return df


def load_data_from_csv(days: int = 30) -> pd.DataFrame:
    """
    Load scored data from CSV files (fallback).

    Args:
        days: Number of days to look back

    Returns:
        DataFrame with scored items
    """
    frames = []
    csv_files = [
        ("social_scored.csv", None),
        ("news_scored.csv", None),
    ]

    for filename, default_source in csv_files:
        filepath = DATA_DIR / filename
        if not filepath.exists():
            continue

        try:
            df = pd.read_csv(filepath)
            if df.empty:
                continue

            # Filter out pypi entries
            if "source" in df.columns:
                df = df[~df["source"].str.contains("pypi", case=False, na=False)]

            # Validate required columns
            required_cols = ["empathy_score", "created_at", "text"]
            missing = [col for col in required_cols if col not in df.columns]
            if missing:
                continue

            # Convert created_at to datetime
            df["created_at"] = pd.to_datetime(df["created_at"], format="mixed", utc=True)

            # Set default source if needed
            if default_source and "source" in df.columns:
                df.loc[df["source"].isna() | (df["source"] == ""), "source"] = default_source

            frames.append(df)

        except Exception as e:
            print(f"Error loading {filename}: {e}")
            continue

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    # Filter by date
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    df = df[df["created_at"] >= cutoff]

    return df


async def load_data(
    db: Optional[AsyncSession] = None,
    days: int = 30,
    source_filter: Optional[str] = None,
    use_db: bool = True
) -> pd.DataFrame:
    """
    Load scored data - tries database first, falls back to CSV.

    Args:
        db: Optional database session
        days: Number of days to look back
        source_filter: Optional filter for specific source
        use_db: Whether to try database first

    Returns:
        Processed DataFrame with all required columns
    """
    df = pd.DataFrame()

    # Try database first
    if use_db and db and settings.database_url:
        try:
            df = await load_data_from_db(db, days, source_filter)
            if not df.empty:
                print(f"Loaded {len(df)} items from database")
        except Exception as e:
            print(f"Database load failed: {e}")
            df = pd.DataFrame()

    # Fall back to CSV
    if df.empty:
        df = load_data_from_csv(days)
        if not df.empty:
            print(f"Loaded {len(df)} items from CSV")

    if df.empty:
        return df

    # Process empathy scores
    if "empathy_score" in df.columns:
        df["empathy_score"] = pd.to_numeric(df["empathy_score"], errors="coerce")
        df["empathy_label"] = df["empathy_score"].apply(empathy_label_from_score)

    # Drop rows with invalid dates
    if "created_at" in df.columns:
        df = df.dropna(subset=["created_at"])

    # Process engagement
    if "engagement" in df.columns:
        df["engagement"] = pd.to_numeric(df["engagement"], errors="coerce").fillna(0)

    # Add readable source names
    if "source" in df.columns:
        df["source_display"] = df["source"].apply(clean_source_name)

    return df


def compute_world_mood(df: pd.DataFrame) -> dict:
    """
    Calculate world mood score from empathy data.
    Normalizes GoEmotions output to 0-100 scale.

    Args:
        df: DataFrame with empathy_score column

    Returns:
        Dict with score, label, emoji, and raw average
    """
    if df.empty or "empathy_score" not in df.columns or df["empathy_score"].isna().all():
        return {
            "score": None,
            "label": "No Data",
            "emoji": "❓",
            "raw_avg": None
        }

    avg = df["empathy_score"].mean()

    # Normalize for GoEmotions output (median ~0.036, 95th ~0.33)
    # Map: 0.0->0, 0.04->50, 0.10->65, 0.30->85, 1.0->100
    if avg <= 0.04:
        score = int(round(avg / 0.04 * 50))
    elif avg <= 0.10:
        score = int(round(50 + (avg - 0.04) / 0.06 * 15))
    elif avg <= 0.30:
        score = int(round(65 + (avg - 0.10) / 0.20 * 20))
    else:
        score = int(round(85 + (avg - 0.30) / 0.70 * 15))

    score = min(100, max(0, score))

    # Determine label and emoji
    if score < 35:
        label = "Very Cold / Hostile"
        emoji = "cold"
    elif score < 50:
        label = "Detached / Neutral"
        emoji = "neutral"
    elif score < 70:
        label = "Warm / Supportive"
        emoji = "warm"
    else:
        label = "Highly Empathetic"
        emoji = "heart"

    return {
        "score": score,
        "label": label,
        "emoji": emoji,
        "raw_avg": round(avg, 4)
    }


def get_emotion_distribution(df: pd.DataFrame, top_n: int = 8) -> list[dict]:
    """
    Get distribution of top emotions.

    Args:
        df: DataFrame with emotion_top_1 column
        top_n: Number of top emotions to return

    Returns:
        List of dicts with emotion, count, percentage
    """
    if df.empty or "emotion_top_1" not in df.columns:
        return []

    emotion_counts = df["emotion_top_1"].value_counts()
    total = len(df)

    result = []
    for emotion, count in emotion_counts.head(top_n).items():
        if pd.isna(emotion):
            continue
        result.append({
            "emotion": emotion,
            "count": int(count),
            "percentage": round((count / total) * 100, 1)
        })

    return result


def get_topic_distribution(df: pd.DataFrame, top_n: int = 10) -> list[dict]:
    """
    Get distribution of topics.

    Args:
        df: DataFrame with topic column
        top_n: Number of top topics to return

    Returns:
        List of dicts with topic, count, percentage
    """
    if df.empty or "topic" not in df.columns:
        return []

    topic_counts = df["topic"].value_counts()
    total = len(df)

    result = []
    for topic, count in topic_counts.head(top_n).items():
        if pd.isna(topic):
            continue
        result.append({
            "topic": topic,
            "count": int(count),
            "percentage": round((count / total) * 100, 1)
        })

    return result


def get_source_distribution(df: pd.DataFrame) -> list[dict]:
    """
    Get distribution of sources.

    Args:
        df: DataFrame with source column

    Returns:
        List of dicts with source, display_name, count, percentage
    """
    if df.empty or "source" not in df.columns:
        return []

    source_counts = df["source"].value_counts()
    total = len(df)

    result = []
    for source, count in source_counts.items():
        if pd.isna(source):
            continue
        result.append({
            "source": source,
            "display_name": clean_source_name(source),
            "count": int(count),
            "percentage": round((count / total) * 100, 1)
        })

    return result


def get_trending_headlines(
    df: pd.DataFrame,
    limit: int = 10,
    filter_spam: bool = True
) -> list[dict]:
    """
    Get trending headlines sorted by engagement.

    Args:
        df: DataFrame with text, engagement, etc.
        limit: Maximum number of headlines
        filter_spam: Whether to filter spam keywords

    Returns:
        List of headline dicts
    """
    if df.empty or "text" not in df.columns:
        return []

    # Filter spam
    if filter_spam:
        mask = ~df["text"].str.lower().str.contains(
            "|".join(SPAM_KEYWORDS),
            regex=True,
            na=False
        )
        df = df[mask]

    # Sort by engagement if available
    if "engagement" in df.columns:
        df = df.sort_values("engagement", ascending=False)

    # Take top N
    df = df.head(limit)

    result = []
    for _, row in df.iterrows():
        result.append({
            "id": row.get("id", ""),
            "text": row["text"],
            "source": row.get("source", ""),
            "source_display": row.get("source_display", clean_source_name(row.get("source", ""))),
            "created_at": row["created_at"].isoformat() if pd.notna(row.get("created_at")) else None,
            "link": row.get("link", ""),
            "engagement": int(row.get("engagement", 0)),
            "emotion": row.get("emotion_top_1", ""),
            "topic": row.get("topic", ""),
            "empathy_score": round(row.get("empathy_score", 0), 3) if pd.notna(row.get("empathy_score")) else None,
        })

    return result


def get_mood_history(df: pd.DataFrame, days: int = 7) -> list[dict]:
    """
    Get daily mood scores for trend chart.

    Args:
        df: DataFrame with empathy_score and created_at
        days: Number of days to include

    Returns:
        List of dicts with date and score
    """
    if df.empty or "empathy_score" not in df.columns or "created_at" not in df.columns:
        return []

    # Group by date
    df = df.copy()
    df["date"] = df["created_at"].dt.date

    daily = df.groupby("date")["empathy_score"].mean().reset_index()
    daily = daily.sort_values("date").tail(days)

    result = []
    for _, row in daily.iterrows():
        avg = row["empathy_score"]
        # Normalize score
        if avg <= 0.04:
            score = int(round(avg / 0.04 * 50))
        elif avg <= 0.10:
            score = int(round(50 + (avg - 0.04) / 0.06 * 15))
        elif avg <= 0.30:
            score = int(round(65 + (avg - 0.10) / 0.20 * 20))
        else:
            score = int(round(85 + (avg - 0.30) / 0.70 * 15))
        score = min(100, max(0, score))

        result.append({
            "date": row["date"].isoformat(),
            "score": score,
            "raw_avg": round(avg, 4)
        })

    return result


def get_geographic_distribution(df: pd.DataFrame, top_n: int = 10) -> list[dict]:
    """
    Get distribution by country.

    Args:
        df: DataFrame with country column
        top_n: Number of top countries

    Returns:
        List of dicts with country, count, avg_empathy
    """
    if df.empty or "country" not in df.columns:
        return []

    # Filter out empty countries
    df = df[df["country"].notna() & (df["country"] != "")]

    if df.empty:
        return []

    grouped = df.groupby("country").agg({
        "id": "count",
        "empathy_score": "mean"
    }).reset_index()

    grouped.columns = ["country", "count", "avg_empathy"]
    grouped = grouped.sort_values("count", ascending=False).head(top_n)

    result = []
    for _, row in grouped.iterrows():
        result.append({
            "country": row["country"],
            "count": int(row["count"]),
            "avg_empathy": round(row["avg_empathy"], 3) if pd.notna(row["avg_empathy"]) else None
        })

    return result
