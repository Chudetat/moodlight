#!/usr/bin/env python
"""
Anomaly detection engine for Moodlight.
Part A: 4 global detectors (mood shift, market-mood divergence, intensity cluster, topic emergence)
Part B: 7 brand-specific detectors per watchlist brand (VLDS + mentions + sentiment)
"""

import json
import pandas as pd
from datetime import datetime, timezone, timedelta
from vlds_helper import calculate_brand_vlds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_alert(alert_type, severity, title, summary, data,
                brand=None, username=None):
    """Standard alert dict."""
    return {
        "alert_type": alert_type,
        "severity": severity,
        "title": title,
        "summary": summary,
        "data": json.dumps(data) if isinstance(data, dict) else str(data),
        "brand": brand,
        "username": username,
    }


# ---------------------------------------------------------------------------
# PART A — Global Detectors
# ---------------------------------------------------------------------------

def detect_mood_shift(df_news, df_social):
    """Detect >15-point swing in average empathy_score day-over-day."""
    alerts = []
    for label, df in [("news", df_news), ("social", df_social)]:
        if df.empty or "empathy_score" not in df.columns or "created_at" not in df.columns:
            continue
        df_c = df.copy()
        df_c["date"] = df_c["created_at"].dt.date
        daily = df_c.groupby("date")["empathy_score"].mean().sort_index()
        if len(daily) < 2:
            continue
        prev_day = daily.iloc[-2]
        curr_day = daily.iloc[-1]
        # Convert to 0-100 scale for comparison
        prev_pct = prev_day * 100
        curr_pct = curr_day * 100
        shift = curr_pct - prev_pct
        if abs(shift) > 15:
            direction = "surged" if shift > 0 else "dropped"
            severity = "critical" if abs(shift) > 25 else "warning"
            alerts.append(_make_alert(
                alert_type="mood_shift",
                severity=severity,
                title=f"Mood {direction} {abs(shift):.0f}pts in {label}",
                summary=(
                    f"Average {label} empathy score {direction} from "
                    f"{prev_pct:.0f} to {curr_pct:.0f} "
                    f"({shift:+.0f}pts day-over-day)."
                ),
                data={
                    "source": label,
                    "prev_day": str(daily.index[-2]),
                    "curr_day": str(daily.index[-1]),
                    "prev_score": round(prev_pct, 1),
                    "curr_score": round(curr_pct, 1),
                    "shift": round(shift, 1),
                },
            ))
    return alerts


def detect_market_mood_divergence(df_social, df_markets):
    """Detect >25-point gap between market sentiment and social mood."""
    alerts = []
    if df_social.empty or df_markets.empty:
        return alerts
    if "empathy_score" not in df_social.columns or "market_sentiment" not in df_markets.columns:
        return alerts

    social_score = df_social["empathy_score"].mean() * 100
    market_score = df_markets["market_sentiment"].mean() * 100
    gap = abs(social_score - market_score)

    if gap > 25:
        social_dir = "positive" if social_score > market_score else "negative"
        market_dir = "bullish" if market_score > social_score else "bearish"
        severity = "critical" if gap > 40 else "warning"
        alerts.append(_make_alert(
            alert_type="market_mood_divergence",
            severity=severity,
            title=f"Market-mood divergence: {gap:.0f}pt gap",
            summary=(
                f"Social mood ({social_score:.0f}) and market sentiment "
                f"({market_score:.0f}) are diverging by {gap:.0f} points. "
                f"Social is {social_dir} while markets are {market_dir}."
            ),
            data={
                "social_score": round(social_score, 1),
                "market_score": round(market_score, 1),
                "gap": round(gap, 1),
            },
        ))
    return alerts


def detect_intensity_cluster(df_news, df_social):
    """Detect when >40% of articles have empathy_score > 0.7."""
    alerts = []
    for label, df in [("news", df_news), ("social", df_social)]:
        if df.empty or "empathy_score" not in df.columns:
            continue
        total = len(df)
        high_emotion = len(df[df["empathy_score"] > 0.7])
        ratio = high_emotion / total if total > 0 else 0
        if ratio > 0.4:
            severity = "critical" if ratio > 0.6 else "warning"
            alerts.append(_make_alert(
                alert_type="intensity_cluster",
                severity=severity,
                title=f"High-emotion spike in {label}: {ratio:.0%} intense",
                summary=(
                    f"{high_emotion} of {total} {label} items ({ratio:.0%}) "
                    f"have empathy scores above 0.7, indicating an unusual "
                    f"cluster of emotionally charged content."
                ),
                data={
                    "source": label,
                    "high_emotion_count": high_emotion,
                    "total": total,
                    "ratio": round(ratio, 3),
                },
            ))
    return alerts


def detect_topic_emergence(df_news):
    """Detect a topic absent from prior 3 days now appearing in >20% of articles."""
    alerts = []
    if df_news.empty or "topic" not in df_news.columns or "created_at" not in df_news.columns:
        return alerts

    df_c = df_news.copy()
    df_c["date"] = df_c["created_at"].dt.date
    dates = sorted(df_c["date"].unique())
    if len(dates) < 2:
        return alerts

    latest_date = dates[-1]
    prior_dates = dates[:-1][-3:]  # up to 3 prior days

    today_df = df_c[df_c["date"] == latest_date]
    prior_df = df_c[df_c["date"].isin(prior_dates)]

    today_topics = today_df["topic"].value_counts()
    prior_topics = set(prior_df["topic"].unique()) if not prior_df.empty else set()
    total_today = len(today_df)

    for topic, count in today_topics.items():
        pct = count / total_today if total_today > 0 else 0
        if pct > 0.20 and topic not in prior_topics:
            if topic.lower() in ("other",):
                continue
            alerts.append(_make_alert(
                alert_type="topic_emergence",
                severity="critical",
                title=f"Emerging topic: {topic}",
                summary=(
                    f'"{topic}" appeared in {count} articles ({pct:.0%} of today\'s coverage) '
                    f"but was absent from the prior {len(prior_dates)} day(s). "
                    f"This may signal a breaking development."
                ),
                data={
                    "topic": topic,
                    "count": count,
                    "percentage": round(pct * 100, 1),
                    "prior_days_checked": len(prior_dates),
                },
            ))
    return alerts


# ---------------------------------------------------------------------------
# PART B — Brand-Specific Detectors
# ---------------------------------------------------------------------------

def _filter_by_brand(df, brand_name):
    """Filter a dataframe to rows mentioning a brand in title or text."""
    if df.empty:
        return pd.DataFrame()
    brand_lower = brand_name.lower()
    mask = pd.Series(False, index=df.index)
    for col in ["title", "text", "source"]:
        if col in df.columns:
            mask = mask | df[col].str.contains(brand_lower, case=False, na=False)
    return df[mask]


def detect_brand_vlds_alerts(df_news, df_social, brand_name, username,
                             prev_vlds=None):
    """Run VLDS analysis on brand-filtered data and detect opportunities."""
    alerts = []
    brand_df = pd.concat([
        _filter_by_brand(df_news, brand_name),
        _filter_by_brand(df_social, brand_name),
    ], ignore_index=True)

    if brand_df.empty or len(brand_df) < 5:
        return alerts, None

    vlds = calculate_brand_vlds(brand_df)
    if not vlds:
        return alerts, None

    # White Space Found
    scarcity = vlds.get("scarcity", 0)
    if scarcity > 0.7:
        alerts.append(_make_alert(
            alert_type="brand_white_space",
            severity="critical",
            title=f"White space opportunity for {brand_name}",
            summary=(
                f"{brand_name} has a scarcity score of {scarcity:.2f} — "
                f"low coverage density means first-mover advantage. "
                f"Only {vlds.get('total_posts', 0)} posts found across sources."
            ),
            data={"brand": brand_name, "scarcity": scarcity, "vlds": vlds},
            brand=brand_name,
            username=username,
        ))

    # Velocity Spike
    velocity = vlds.get("velocity", 0.5)
    if velocity > 0.7:
        alerts.append(_make_alert(
            alert_type="brand_velocity_spike",
            severity="critical",
            title=f"Velocity spike for {brand_name}",
            summary=(
                f"Conversation about {brand_name} is accelerating "
                f"(velocity: {velocity:.2f}). Recent coverage is "
                f"outpacing earlier periods significantly."
            ),
            data={"brand": brand_name, "velocity": velocity, "vlds": vlds},
            brand=brand_name,
            username=username,
        ))

    # Narrative Fading (requires previous VLDS to compare)
    if prev_vlds:
        prev_longevity = prev_vlds.get("longevity", 0)
        curr_longevity = vlds.get("longevity", 0)
        if prev_longevity > 0.6 and curr_longevity < 0.3:
            alerts.append(_make_alert(
                alert_type="brand_narrative_fading",
                severity="warning",
                title=f"Narrative fading for {brand_name}",
                summary=(
                    f"{brand_name} longevity dropped from {prev_longevity:.2f} "
                    f"to {curr_longevity:.2f}. The conversation window may be "
                    f"closing — act now or miss the moment."
                ),
                data={
                    "brand": brand_name,
                    "prev_longevity": prev_longevity,
                    "curr_longevity": curr_longevity,
                },
                brand=brand_name,
                username=username,
            ))

    # Saturation Warning
    density = vlds.get("density", 0)
    if density > 0.7:
        alerts.append(_make_alert(
            alert_type="brand_saturation",
            severity="warning",
            title=f"Market saturated for {brand_name}",
            summary=(
                f"{brand_name} has a density score of {density:.2f} — "
                f"the conversation space is crowded. Consider differentiating "
                f"or finding adjacent white space."
            ),
            data={"brand": brand_name, "density": density, "vlds": vlds},
            brand=brand_name,
            username=username,
        ))

    return alerts, vlds


def detect_brand_mention_surge(df_news, df_social, brand_name, username):
    """Detect sudden spikes in news or social mentions of a brand."""
    alerts = []

    for label, df in [("news", df_news), ("social", df_social)]:
        brand_df = _filter_by_brand(df, brand_name)
        if brand_df.empty or "created_at" not in brand_df.columns:
            continue

        brand_df = brand_df.copy()
        brand_df["date"] = brand_df["created_at"].dt.date
        daily = brand_df.groupby("date").size().sort_index()

        if len(daily) < 2:
            continue

        today_count = daily.iloc[-1]
        baseline = daily.iloc[:-1].mean()

        # Surge: >3x normal, or >5 when baseline was <2
        is_surge = (
            (baseline >= 2 and today_count > baseline * 3) or
            (baseline < 2 and today_count >= 5)
        )
        if is_surge:
            alert_type = "brand_news_surge" if label == "news" else "brand_social_buzz"
            alerts.append(_make_alert(
                alert_type=alert_type,
                severity="critical",
                title=f"{label.title()} mention surge for {brand_name}",
                summary=(
                    f"{brand_name} appeared in {today_count} {label} items today "
                    f"vs a baseline of {baseline:.1f}/day. "
                    f"This is a {today_count/max(baseline,0.1):.1f}x spike."
                ),
                data={
                    "brand": brand_name,
                    "source": label,
                    "today_count": int(today_count),
                    "baseline": round(float(baseline), 1),
                    "multiplier": round(today_count / max(baseline, 0.1), 1),
                },
                brand=brand_name,
                username=username,
            ))
    return alerts


def detect_brand_sentiment_shift(df_news, df_social, brand_name, username):
    """Detect significant shifts in brand sentiment (empathy_score)."""
    alerts = []
    brand_df = pd.concat([
        _filter_by_brand(df_news, brand_name),
        _filter_by_brand(df_social, brand_name),
    ], ignore_index=True)

    if brand_df.empty or "empathy_score" not in brand_df.columns:
        return alerts
    if "created_at" not in brand_df.columns:
        return alerts

    brand_df = brand_df.copy()
    brand_df["date"] = brand_df["created_at"].dt.date
    daily_sentiment = brand_df.groupby("date")["empathy_score"].mean().sort_index()

    if len(daily_sentiment) < 3:
        return alerts

    rolling_avg = daily_sentiment.iloc[:-1].mean()
    current = daily_sentiment.iloc[-1]
    shift = current - rolling_avg

    if abs(shift) > 0.15:
        direction = "improved" if shift > 0 else "declined"
        alerts.append(_make_alert(
            alert_type="brand_sentiment_shift",
            severity="warning",
            title=f"Sentiment {direction} for {brand_name}",
            summary=(
                f"Brand sentiment for {brand_name} {direction} from "
                f"{rolling_avg:.3f} (7-day avg) to {current:.3f} "
                f"(shift: {shift:+.3f}). This signals a meaningful change "
                f"in how audiences perceive the brand."
            ),
            data={
                "brand": brand_name,
                "rolling_avg": round(float(rolling_avg), 3),
                "current": round(float(current), 3),
                "shift": round(float(shift), 3),
            },
            brand=brand_name,
            username=username,
        ))
    return alerts


# ---------------------------------------------------------------------------
# Run all detectors
# ---------------------------------------------------------------------------

def run_global_detectors(df_news, df_social, df_markets):
    """Run all 4 global detectors and return a list of alerts."""
    alerts = []
    alerts.extend(detect_mood_shift(df_news, df_social))
    alerts.extend(detect_market_mood_divergence(df_social, df_markets))
    alerts.extend(detect_intensity_cluster(df_news, df_social))
    alerts.extend(detect_topic_emergence(df_news))
    return alerts


def run_brand_detectors(df_news, df_social, brand_name, username,
                        prev_vlds=None):
    """Run all 7 brand detectors and return alerts + current VLDS."""
    alerts = []
    vlds_alerts, current_vlds = detect_brand_vlds_alerts(
        df_news, df_social, brand_name, username, prev_vlds
    )
    alerts.extend(vlds_alerts)
    alerts.extend(detect_brand_mention_surge(df_news, df_social, brand_name, username))
    alerts.extend(detect_brand_sentiment_shift(df_news, df_social, brand_name, username))
    return alerts, current_vlds
