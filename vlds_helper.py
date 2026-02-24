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
        daily_counts = df_copy.groupby("date").size().sort_index()
        n_days = len(daily_counts)

        if n_days >= 3:
            # Multi-window velocity: blend spike + trend detection
            # Window 1 (40%): 1-day vs up to 3-day baseline (spike detection)
            r1_recent = float(daily_counts.iloc[-1])
            r1_base = float(
                daily_counts.iloc[max(0, n_days - 4):(n_days - 1)].mean()
            )
            r1 = (r1_recent / r1_base) if r1_base > 0 else 1.0

            # Window 2 (60%): 2-day vs up to 5-day baseline (trend detection)
            r2_recent = float(daily_counts.iloc[-2:].mean())
            r2_base_slice = daily_counts.iloc[max(0, n_days - 7):(n_days - 2)]
            r2_base = (
                float(r2_base_slice.mean()) if len(r2_base_slice) > 0 else r1_base
            )
            r2 = (r2_recent / r2_base) if r2_base > 0 else 1.0

            velocity_raw = 0.4 * r1 + 0.6 * r2
            # Sigmoid centered at 1.0: no change=0.5, ~1.6x→0.7, ~2x→0.82
            velocity_score = 1.0 / (1.0 + math.exp(-1.5 * (velocity_raw - 1.0)))
        elif n_days == 2:
            ratio = (
                float(daily_counts.iloc[-1] / daily_counts.iloc[0])
                if daily_counts.iloc[0] > 0 else 1.0
            )
            velocity_score = 1.0 / (1.0 + math.exp(-1.5 * (ratio - 1.0)))
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
        unique_dates = sorted(df_copy["date"].unique())
        unique_days = len(unique_dates)

        if unique_days >= 2:
            ref_date = unique_dates[-1]
            span_days = (unique_dates[-1] - unique_dates[0]).days + 1

            # Continuity (50%): fraction of span with activity, scaled by span
            # A 2-day run shouldn't score 1.0 just because it's fully dense
            continuity = (unique_days / span_days) * min(span_days / 7.0, 1.0)

            # Recency (40%): exponential decay with 7-day half-life
            total_weight = sum(
                math.exp(-0.693 * (ref_date - d).days / 7.0)
                for d in unique_dates
            )
            max_weight = sum(
                math.exp(-0.693 * i / 7.0) for i in range(span_days)
            )
            recency_score = (
                total_weight / max_weight if max_weight > 0 else 0.5
            )

            # Extended reach bonus (10%): log-scaled for spans beyond 7 days
            extended_raw = min(
                math.log1p(max(0, span_days - 7)) / math.log1p(23), 1.0
            )

            longevity_score = min(
                0.50 * continuity + 0.40 * recency_score
                + 0.10 * extended_raw,
                1.0,
            )
        else:
            span_days = 1
            longevity_score = 0.1

        results["longevity"] = round(longevity_score, 2)
        results["longevity_label"] = (
            "Sustained"
            if longevity_score > 0.7
            else "Moderate" if longevity_score > 0.4 else "Flash"
        )
        results["longevity_insight"] = (
            f"Coverage spans {span_days} day{'s' if span_days != 1 else ''}"
            f" with {unique_days} active — "
            f"{'a lasting narrative' if longevity_score > 0.7 else 'moderate staying power' if longevity_score > 0.4 else 'likely a short-term spike'}"
        )

    if "source" in df.columns:
        source_counts_series = df["source"].value_counts()
        source_count = len(source_counts_series)
        post_count = len(df)

        # Volume (70%): log-scaled post count
        volume_score = min(math.log1p(post_count) / 8.0, 1.0)

        # Source diversity (30%): inverted Herfindahl-Hirschman Index (unnormalized)
        # Unnormalized so few sources naturally score low regardless of balance
        if source_count >= 2:
            shares = source_counts_series.values / post_count
            hhi = float((shares ** 2).sum())
            source_diversity = 1.0 - hhi
        else:
            source_diversity = 0.0

        density_score = 0.7 * volume_score + 0.3 * source_diversity

        # Sentiment quality modifier: +/- 20% based on discourse health
        if "emotion_top_1" in df.columns and "empathy_score" in df.columns:
            sent_em_counts = df["emotion_top_1"].value_counts()
            if len(sent_em_counts) >= 2:
                sent_probs = sent_em_counts.values / post_count
                sent_entropy = -sum(
                    p * math.log2(p) for p in sent_probs if p > 0
                )
                sent_max_ent = math.log2(len(sent_em_counts))
                emotion_div = (
                    sent_entropy / sent_max_ent if sent_max_ent > 0 else 0.0
                )
            else:
                emotion_div = 0.0

            neg_emotions = {
                "anger", "sadness", "fear", "disgust", "annoyance",
                "disappointment", "grief", "embarrassment",
                "nervousness", "remorse",
            }
            neg_count = int(df["emotion_top_1"].isin(neg_emotions).sum())
            neg_ratio = neg_count / post_count if post_count > 0 else 0.0

            empathy_norm = min(
                float(df["empathy_score"].mean()) / 0.15, 1.0
            )

            sentiment_quality = (
                0.4 * emotion_div
                + 0.3 * (1.0 - neg_ratio)
                + 0.3 * empathy_norm
            )
            sentiment_multiplier = 0.8 + 0.4 * sentiment_quality
            density_score = min(density_score * sentiment_multiplier, 1.0)

        results["density"] = round(density_score, 2)
        results["source_diversity"] = round(source_diversity, 2)
        results["source_count"] = source_count
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

        # Genuine Scarcity: topic concentration + source gap + emotion uniformity
        # Topic concentration (40%): Gini coefficient
        if len(topic_counts) >= 2:
            counts_arr = sorted(topic_counts.values)
            n_topics = len(counts_arr)
            tc_total = sum(counts_arr)
            gini = (
                sum(
                    (2 * (i + 1) - n_topics - 1) * counts_arr[i]
                    for i in range(n_topics)
                ) / (n_topics * tc_total)
                if tc_total > 0 else 0.0
            )
        else:
            gini = 1.0

        # Source coverage gap (30%): log-scaled breadth
        sc = results.get("source_count", 1)
        source_gap = 1.0 - min(math.log1p(sc) / math.log1p(20), 1.0)

        # Emotion uniformity (30%): 1 - normalized Shannon entropy
        if "emotion_top_1" in df.columns:
            em_counts = df["emotion_top_1"].value_counts()
            if len(em_counts) >= 2:
                em_probs = em_counts.values / total_posts
                em_entropy = -sum(
                    p * math.log2(p) for p in em_probs if p > 0
                )
                em_max_ent = math.log2(len(em_counts))
                emotion_uniformity = (
                    1.0 - (em_entropy / em_max_ent)
                    if em_max_ent > 0 else 1.0
                )
            else:
                emotion_uniformity = 1.0
        else:
            emotion_uniformity = 0.5

        scarcity_score = (
            0.4 * gini + 0.3 * source_gap + 0.3 * emotion_uniformity
        )
        results["scarcity"] = round(scarcity_score, 2)
        results["scarcity_label"] = (
            "High Opportunity"
            if scarcity_score > 0.7
            else "Some Opportunity" if scarcity_score > 0.4 else "Crowded"
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

    results["_vlds_version"] = 2
    results["total_posts"] = total_posts

    return results
