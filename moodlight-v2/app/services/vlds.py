"""
VLDS (Velocity, Longevity, Density, Scarcity) calculation service.
Metrics for analyzing brand/topic performance in cultural conversations.
"""
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

# Geographic mapping based on source
GEO_MAPPING = {
    "bbc": "UK/Europe",
    "cnn": "North America",
    "guardian": "UK/Europe",
    "al_jazeera": "Middle East",
    "japan_times": "Asia",
    "korea_herald": "Asia",
    "times_of_india": "Asia",
    "indian_express": "Asia",
    "fox_news": "North America",
    "abc_news": "North America",
    "cbs_news": "North America",
    "nbc": "North America",
    "x": "Global",
    "reddit": "Global (English-speaking)",
}

# Irrelevant topics for scarcity calculation
IRRELEVANT_TOPICS = [
    "other", "sports", "entertainment", "religion & values",
    "race & ethnicity", "gender & sexuality"
]


def calculate_velocity(df: pd.DataFrame) -> dict:
    """
    Calculate conversation velocity - is momentum rising or falling?

    Returns score 0-1 where higher = accelerating conversation.
    """
    if df.empty or "created_at" not in df.columns:
        return {
            "score": 0.5,
            "label": "Unknown",
            "insight": "Insufficient data to calculate velocity"
        }

    df = df.copy()
    df["date"] = pd.to_datetime(df["created_at"]).dt.date
    daily_counts = df.groupby("date").size()

    if len(daily_counts) < 2:
        return {
            "score": 0.5,
            "label": "Stable",
            "insight": "Not enough history to measure velocity"
        }

    # Compare recent activity to older activity
    recent = daily_counts.tail(2).mean()
    older = daily_counts.head(max(1, len(daily_counts) - 2)).mean()

    velocity = (recent / older) if older > 0 else 1.0
    velocity_score = min(velocity / 2.0, 1.0)

    if velocity_score > 0.7:
        label = "Rising Fast"
        insight = "Conversation is accelerating compared to earlier periods"
    elif velocity_score > 0.4:
        label = "Stable"
        insight = "Conversation volume is steady"
    else:
        label = "Declining"
        insight = "Conversation is slowing down"

    return {
        "score": round(velocity_score, 2),
        "label": label,
        "insight": insight,
        "recent_avg": round(recent, 1),
        "older_avg": round(older, 1)
    }


def calculate_longevity(df: pd.DataFrame) -> dict:
    """
    Calculate conversation longevity - how long has this been discussed?

    Returns score 0-1 where higher = longer-lasting conversation.
    """
    if df.empty or "created_at" not in df.columns:
        return {
            "score": 0.5,
            "label": "Unknown",
            "insight": "Insufficient data to calculate longevity"
        }

    df = df.copy()
    df["date"] = pd.to_datetime(df["created_at"]).dt.date
    unique_days = df["date"].nunique()

    # Score based on 7-day window (0 = 0 days, 1 = 7+ days)
    longevity_score = min(unique_days / 7.0, 1.0)

    if longevity_score > 0.7:
        label = "Sustained"
        insight = f"Coverage spans {unique_days} days — a lasting narrative"
    elif longevity_score > 0.4:
        label = "Moderate"
        insight = f"Coverage spans {unique_days} days — moderate staying power"
    else:
        label = "Flash"
        insight = f"Coverage spans {unique_days} day(s) — likely a short-term spike"

    return {
        "score": round(longevity_score, 2),
        "label": label,
        "insight": insight,
        "unique_days": unique_days
    }


def calculate_density(df: pd.DataFrame) -> dict:
    """
    Calculate conversation density - how saturated is this space?

    Returns score 0-1 where higher = more crowded/saturated.
    """
    if df.empty or "source" not in df.columns:
        return {
            "score": 0.5,
            "label": "Unknown",
            "insight": "Insufficient data to calculate density"
        }

    source_count = df["source"].nunique()
    post_count = len(df)

    # Score based on volume (0 = 0 posts, 1 = 100+ posts)
    density_score = min(post_count / 100.0, 1.0)

    if density_score > 0.7:
        label = "Saturated"
        insight = f"{post_count} posts across {source_count} sources — crowded, hard to break through"
    elif density_score > 0.3:
        label = "Moderate"
        insight = f"{post_count} posts across {source_count} sources — room to grow presence"
    else:
        label = "White Space"
        insight = f"{post_count} posts across {source_count} sources — wide open for thought leadership"

    return {
        "score": round(density_score, 2),
        "label": label,
        "insight": insight,
        "post_count": post_count,
        "source_count": source_count
    }


def calculate_scarcity(df: pd.DataFrame) -> dict:
    """
    Calculate narrative scarcity - what angles are underrepresented?

    Returns inverse of density (high scarcity = low density = opportunity).
    """
    if df.empty or "topic" not in df.columns:
        return {
            "score": 0.5,
            "label": "Unknown",
            "insight": "Insufficient data to calculate scarcity",
            "scarce_topics": []
        }

    total_posts = len(df)
    topic_counts = df["topic"].value_counts()

    # Find underrepresented topics (<10% share, excluding irrelevant ones)
    scarce_topics = []
    for topic, count in topic_counts.items():
        pct = (count / total_posts) * 100
        if pct < 10 and str(topic).lower() not in IRRELEVANT_TOPICS:
            scarce_topics.append({
                "topic": topic,
                "count": int(count),
                "percentage": round(pct, 1)
            })

    # Scarcity is inverse of density
    density = calculate_density(df)
    scarcity_score = round(1.0 - density["score"], 2)

    if scarcity_score > 0.7:
        label = "High Opportunity"
        insight = "Low conversation density — significant white space for brand entry"
    elif scarcity_score > 0.4:
        label = "Some Opportunity"
        insight = "Moderate conversation density — selective opportunities exist"
    else:
        label = "Crowded"
        insight = "High conversation density — requires differentiation to stand out"

    return {
        "score": scarcity_score,
        "label": label,
        "insight": insight,
        "scarce_topics": scarce_topics[:5]
    }


def get_geographic_density(df: pd.DataFrame) -> dict:
    """
    Calculate geographic distribution of conversation.
    """
    if df.empty or "source" not in df.columns:
        return {
            "diversity": 0,
            "primary_region": "Unknown",
            "regions": {}
        }

    regions = []
    for source in df["source"]:
        source_lower = str(source).lower()
        matched = False
        for key, region in GEO_MAPPING.items():
            if key in source_lower:
                regions.append(region)
                matched = True
                break
        if not matched:
            regions.append("Other")

    if not regions:
        return {"diversity": 0, "primary_region": "Unknown", "regions": {}}

    region_counts = Counter(regions)
    total = len(regions)

    # Diversity score (0-1, higher = more geographically diverse)
    diversity = len(region_counts) / len(GEO_MAPPING)
    primary = region_counts.most_common(1)[0][0]
    distribution = {r: round(count / total, 3) for r, count in region_counts.items()}

    return {
        "diversity": round(diversity, 2),
        "primary_region": primary,
        "regions": distribution
    }


def get_platform_density(df: pd.DataFrame) -> dict:
    """
    Calculate platform distribution of conversation.
    """
    if df.empty or "source" not in df.columns:
        return {
            "diversity": 0,
            "primary_platform": "Unknown",
            "platforms": {}
        }

    platforms = []
    for source in df["source"]:
        source_lower = str(source).lower()
        if "reddit" in source_lower:
            platforms.append("Social Media (Reddit)")
        elif source_lower == "x":
            platforms.append("Social Media (X)")
        else:
            platforms.append("News Media")

    platform_counts = Counter(platforms)
    total = len(platforms)

    diversity = len(platform_counts) / 3  # Max 3 platform types
    primary = platform_counts.most_common(1)[0][0]
    distribution = {p: round(count / total, 3) for p, count in platform_counts.items()}

    return {
        "diversity": round(diversity, 2),
        "primary_platform": primary,
        "platforms": distribution
    }


def calculate_brand_vlds(df: pd.DataFrame) -> Optional[dict]:
    """
    Calculate full VLDS metrics for a brand/topic dataset.

    Args:
        df: DataFrame filtered for specific brand/topic

    Returns:
        Dict with all VLDS metrics or None if insufficient data
    """
    if df.empty or len(df) < 5:
        return None

    results = {
        "velocity": calculate_velocity(df),
        "longevity": calculate_longevity(df),
        "density": calculate_density(df),
        "scarcity": calculate_scarcity(df),
        "geographic": get_geographic_density(df),
        "platform": get_platform_density(df),
        "total_posts": len(df)
    }

    # Top topics with percentages
    if "topic" in df.columns:
        topic_counts = df["topic"].value_counts()
        total = len(df)
        results["top_topics"] = [
            {
                "topic": topic,
                "count": int(count),
                "percentage": round((count / total) * 100, 1)
            }
            for topic, count in topic_counts.head(5).items()
        ]

    # Top emotions with percentages
    if "emotion_top_1" in df.columns:
        emotion_counts = df["emotion_top_1"].value_counts()
        total = len(df)
        results["top_emotions"] = [
            {
                "emotion": emotion,
                "count": int(count),
                "percentage": round((count / total) * 100, 1)
            }
            for emotion, count in emotion_counts.head(5).items()
        ]

        # Dominant emotion insight
        if results["top_emotions"]:
            dominant = results["top_emotions"][0]
            results["emotion_insight"] = f"The dominant emotional tone is {dominant['emotion']} ({dominant['percentage']}% of coverage)"

    # Empathy score
    if "empathy_score" in df.columns:
        avg_empathy = df["empathy_score"].mean()
        results["empathy_score"] = round(avg_empathy, 3)

    return results


def get_vlds_summary(vlds: dict) -> str:
    """
    Get a text summary of VLDS metrics for display.
    """
    if not vlds:
        return "Insufficient data for VLDS analysis"

    lines = [
        f"**Velocity**: {vlds['velocity']['label']} ({vlds['velocity']['score']}) - {vlds['velocity']['insight']}",
        f"**Longevity**: {vlds['longevity']['label']} ({vlds['longevity']['score']}) - {vlds['longevity']['insight']}",
        f"**Density**: {vlds['density']['label']} ({vlds['density']['score']}) - {vlds['density']['insight']}",
        f"**Scarcity**: {vlds['scarcity']['label']} ({vlds['scarcity']['score']}) - {vlds['scarcity']['insight']}",
    ]

    return "\n".join(lines)
