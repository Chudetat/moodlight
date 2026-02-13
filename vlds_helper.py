#!/usr/bin/env python
"""
Shared VLDS (Velocity, Longevity, Density, Scarcity) calculation.
Used by both app.py (dashboard) and alert_detector.py (pipeline).
"""

import math
import pandas as pd

EMPATHY_LEVELS = [
    "Cold / Hostile",
    "Detached / Neutral",
    "Warm / Supportive",
    "Highly Empathetic",
]


def empathy_label_from_score(score: float) -> str | None:
    if score is None or math.isnan(score):
        return None
    score = max(0.0, min(1.0, float(score)))
    if score < 0.04:
        return EMPATHY_LEVELS[0]
    if score < 0.10:
        return EMPATHY_LEVELS[1]
    if score < 0.30:
        return EMPATHY_LEVELS[2]
    return EMPATHY_LEVELS[3]


def calculate_brand_vlds(df: pd.DataFrame) -> dict | None:
    """Calculate VLDS metrics for a filtered brand dataset."""

    if df.empty or len(df) < 5:
        return None

    results = {}
    total_posts = len(df)

    if "created_at" in df.columns:
        df_copy = df.copy()
        df_copy["date"] = df_copy["created_at"].dt.date
        daily_counts = df_copy.groupby("date").size()

        if len(daily_counts) >= 2:
            recent = daily_counts.tail(2).mean()
            older = daily_counts.head(max(1, len(daily_counts) - 2)).mean()
            velocity = (recent / older) if older > 0 else 1.0
            velocity_score = min(velocity / 2.0, 1.0)
        else:
            velocity_score = 0.5
        results["velocity"] = round(velocity_score, 2)
        results["velocity_label"] = (
            "Rising Fast"
            if velocity_score > 0.7
            else "Stable" if velocity_score > 0.4 else "Declining"
        )
        results["velocity_insight"] = (
            f"Conversation is "
            f"{'accelerating' if velocity_score > 0.7 else 'steady' if velocity_score > 0.4 else 'slowing down'}"
            f" compared to earlier periods"
        )

    if "created_at" in df.columns:
        unique_days = df_copy["date"].nunique()
        longevity_score = min(unique_days / 7.0, 1.0)
        results["longevity"] = round(longevity_score, 2)
        results["longevity_label"] = (
            "Sustained"
            if longevity_score > 0.7
            else "Moderate" if longevity_score > 0.4 else "Flash"
        )
        results["longevity_insight"] = (
            f"Coverage spans {unique_days} day{'s' if unique_days != 1 else ''} — "
            f"{'a lasting narrative' if longevity_score > 0.7 else 'moderate staying power' if longevity_score > 0.4 else 'likely a short-term spike'}"
        )

    if "source" in df.columns:
        source_count = df["source"].nunique()
        post_count = len(df)
        density_score = min(post_count / 100.0, 1.0)
        results["density"] = round(density_score, 2)
        results["density_label"] = (
            "Saturated"
            if density_score > 0.7
            else "Moderate" if density_score > 0.3 else "White Space"
        )
        results["density_insight"] = (
            f"{post_count} posts across {source_count} sources — "
            f"{'crowded, hard to break through' if density_score > 0.7 else 'room to grow presence' if density_score > 0.3 else 'wide open for thought leadership'}"
        )

    if "topic" in df.columns:
        topic_counts = df["topic"].value_counts()

        top_topics_detailed = []
        for topic, count in topic_counts.head(5).items():
            pct = (count / total_posts) * 100
            top_topics_detailed.append(
                {"topic": topic, "count": count, "percentage": round(pct, 1)}
            )
        results["top_topics_detailed"] = top_topics_detailed

        irrelevant_topics = [
            "other",
            "religion & values",
            "race & ethnicity",
            "gender & sexuality",
        ]
        scarce_topics_detailed = []
        for topic, count in topic_counts.items():
            pct = (count / total_posts) * 100
            if pct < 10 and topic.lower() not in irrelevant_topics:
                scarce_topics_detailed.append(
                    {"topic": topic, "count": count, "percentage": round(pct, 1)}
                )
        results["scarce_topics_detailed"] = scarce_topics_detailed[:5]

        results["scarcity"] = round(1.0 - results.get("density", 0.5), 2)
        results["scarcity_label"] = (
            "High Opportunity"
            if results["scarcity"] > 0.7
            else "Some Opportunity" if results["scarcity"] > 0.4 else "Crowded"
        )

    if "emotion_top_1" in df.columns:
        emotion_counts = df["emotion_top_1"].value_counts()
        top_emotions_detailed = []
        for emotion, count in emotion_counts.head(5).items():
            pct = (count / total_posts) * 100
            top_emotions_detailed.append(
                {"emotion": emotion, "count": count, "percentage": round(pct, 1)}
            )
        results["top_emotions_detailed"] = top_emotions_detailed

        if top_emotions_detailed:
            dominant = top_emotions_detailed[0]
            results["emotion_insight"] = (
                f"The dominant emotional tone is {dominant['emotion']}"
                f" ({dominant['percentage']}% of coverage)"
            )

    if "empathy_score" in df.columns:
        avg_empathy = df["empathy_score"].mean()
        results["empathy_score"] = round(avg_empathy, 3)
        results["empathy_label"] = empathy_label_from_score(avg_empathy)

    results["total_posts"] = total_posts

    return results
