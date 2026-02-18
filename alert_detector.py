#!/usr/bin/env python
"""
Anomaly detection engine for Moodlight.
Part A: 7 global detectors (mood shift, market-mood divergence, intensity cluster, topic emergence,
         regulatory/policy spike, breaking signal, geopolitical risk escalation)
Part B: 8 brand-specific detectors per watchlist brand (VLDS + mentions + sentiment + crisis)
Part C: 3 competitive detectors (competitor momentum, SOV shift, competitive white space)

All thresholds are configurable via the `thresholds` parameter (loaded from DB).
Falls back to hardcoded defaults if not provided.
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from vlds_helper import calculate_brand_vlds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _NumpyEncoder(json.JSONEncoder):
    """Handle numpy types that aren't natively JSON serializable."""
    def default(self, obj):
        if isinstance(obj, (np.bool_, np.integer)):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def _make_alert(alert_type, severity, title, summary, data,
                brand=None, username=None):
    """Standard alert dict."""
    return {
        "alert_type": alert_type,
        "severity": severity,
        "title": title,
        "summary": summary,
        "data": json.dumps(data, cls=_NumpyEncoder) if isinstance(data, dict) else str(data),
        "brand": brand,
        "username": username,
    }


def _t(thresholds, key, default):
    """Get a threshold value with fallback."""
    if thresholds and key in thresholds:
        return thresholds[key]
    return default


# ---------------------------------------------------------------------------
# PART A — Global Detectors
# ---------------------------------------------------------------------------

def detect_mood_shift(df_news, df_social, thresholds=None):
    """Detect significant swing in average empathy_score day-over-day."""
    warn = _t(thresholds, "warning", 15)
    crit = _t(thresholds, "critical", 25)
    alerts = []
    for label, df in [("news", df_news), ("social", df_social)]:
        if df.empty or "empathy_score" not in df.columns or "created_at" not in df.columns:
            continue
        df_c = df.copy()
        df_c["date"] = df_c["created_at"].dt.date
        daily = df_c.groupby("date")["empathy_score"].mean().sort_index()
        if len(daily) < 2:
            continue
        prev_pct = daily.iloc[-2] * 100
        curr_pct = daily.iloc[-1] * 100
        shift = curr_pct - prev_pct
        if abs(shift) > warn:
            direction = "surged" if shift > 0 else "dropped"
            severity = "critical" if abs(shift) > crit else "warning"
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


def detect_market_mood_divergence(df_social, df_markets, thresholds=None):
    """Detect significant gap between market sentiment and social mood."""
    warn = _t(thresholds, "warning", 25)
    crit = _t(thresholds, "critical", 40)
    alerts = []
    if df_social.empty or df_markets.empty:
        return alerts
    if "empathy_score" not in df_social.columns or "market_sentiment" not in df_markets.columns:
        return alerts

    social_score = df_social["empathy_score"].mean() * 100
    market_score = df_markets["market_sentiment"].mean() * 100
    gap = abs(social_score - market_score)

    if gap > warn:
        social_dir = "positive" if social_score > market_score else "negative"
        market_dir = "bullish" if market_score > social_score else "bearish"
        severity = "critical" if gap > crit else "warning"
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


def detect_intensity_cluster(df_news, df_social, thresholds=None):
    """Detect when a high percentage of articles have empathy_score > 0.7."""
    warn = _t(thresholds, "warning", 0.4)
    crit = _t(thresholds, "critical", 0.6)
    alerts = []
    for label, df in [("news", df_news), ("social", df_social)]:
        if df.empty or "empathy_score" not in df.columns:
            continue
        total = len(df)
        high_emotion = len(df[df["empathy_score"] > 0.7])
        ratio = high_emotion / total if total > 0 else 0
        if ratio > warn:
            severity = "critical" if ratio > crit else "warning"
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


def detect_topic_emergence(df_news, thresholds=None):
    """Detect a topic absent from prior 3 days now appearing in a significant share of articles."""
    pct_threshold = _t(thresholds, "critical", 0.20)
    alerts = []
    if df_news.empty or "topic" not in df_news.columns or "created_at" not in df_news.columns:
        return alerts

    df_c = df_news.copy()
    df_c["date"] = df_c["created_at"].dt.date
    dates = sorted(df_c["date"].unique())
    if len(dates) < 2:
        return alerts

    latest_date = dates[-1]
    prior_dates = dates[:-1][-3:]

    today_df = df_c[df_c["date"] == latest_date]
    prior_df = df_c[df_c["date"].isin(prior_dates)]

    today_topics = today_df["topic"].value_counts()
    prior_topics = set(prior_df["topic"].unique()) if not prior_df.empty else set()
    total_today = len(today_df)

    for topic, count in today_topics.items():
        pct = count / total_today if total_today > 0 else 0
        if pct > pct_threshold and topic not in prior_topics:
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


def detect_regulatory_policy_spike(df_news, thresholds=None):
    """Detect high-intensity spikes in regulatory/policy topics."""
    t = thresholds or {}
    count_thresh = _t(t, "warning", 5)
    intensity_thresh = _t(t, "critical", 4.0)
    alerts = []

    if df_news.empty:
        return alerts
    if not all(c in df_news.columns for c in ["topic", "intensity", "created_at"]):
        return alerts

    regulatory_topics = {"government", "economics", "politics"}
    cutoff_24h = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=24)

    reg_df = df_news[
        (df_news["topic"].isin(regulatory_topics))
        & (df_news["created_at"] >= cutoff_24h)
    ]

    if reg_df.empty or len(reg_df) < count_thresh:
        return alerts

    avg_intensity = reg_df["intensity"].mean()
    if avg_intensity >= intensity_thresh:
        top_topics = reg_df["topic"].value_counts().head(3)
        alerts.append(_make_alert(
            alert_type="regulatory_policy_spike",
            severity="warning",
            title=f"Regulatory/policy intensity spike: avg {avg_intensity:.1f}",
            summary=(
                f"{len(reg_df)} articles in regulatory topics in the last 24h "
                f"with average intensity {avg_intensity:.1f}/5. "
                f"Top areas: {', '.join(f'{t} ({c})' for t, c in top_topics.items())}. "
                f"This may signal significant policy or regulatory developments."
            ),
            data={
                "article_count": len(reg_df),
                "avg_intensity": round(float(avg_intensity), 2),
                "topic_breakdown": top_topics.to_dict(),
            },
        ))
    return alerts


# Simple stopwords for title overlap detection
_STOPWORDS = frozenset([
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to",
    "for", "of", "and", "or", "but", "with", "by", "from", "as", "it", "its",
    "this", "that", "has", "have", "had", "be", "been", "will", "not", "no",
    "up", "out", "over", "after", "new", "says", "said",
])


def _has_story_overlap(titles, min_pairs=2, threshold=0.3):
    """Check if titles share enough words to indicate same story."""
    if len(titles) < 2:
        return False
    word_sets = []
    for t in titles[:15]:
        words = set(t.lower().split()) - _STOPWORDS
        if words:
            word_sets.append(words)

    overlap_count = 0
    for i in range(len(word_sets)):
        for j in range(i + 1, len(word_sets)):
            inter = len(word_sets[i] & word_sets[j])
            union = len(word_sets[i] | word_sets[j])
            if union > 0 and inter / union > threshold:
                overlap_count += 1
                if overlap_count >= min_pairs:
                    return True
    return False


def detect_breaking_signal(df_news, thresholds=None):
    """Detect high-intensity stories spreading across multiple sources within 6 hours."""
    alerts = []
    if df_news.empty:
        return alerts
    if not all(c in df_news.columns for c in ["created_at", "intensity", "source", "topic"]):
        return alerts

    cutoff_6h = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=6)
    recent = df_news[
        (df_news["created_at"] >= cutoff_6h)
        & (df_news["intensity"] >= 4)
    ]

    if recent.empty:
        return alerts

    for topic, group in recent.groupby("topic"):
        source_count = group["source"].nunique()
        if source_count < 3:
            continue

        # Verify same story via title overlap
        if "title" in group.columns:
            titles = group["title"].dropna().tolist()
        elif "text" in group.columns:
            titles = group["text"].dropna().str[:80].tolist()
        else:
            continue

        if not _has_story_overlap(titles):
            continue

        alerts.append(_make_alert(
            alert_type="breaking_signal",
            severity="critical",
            title=f"Breaking: {topic} across {source_count} sources",
            summary=(
                f"High-intensity ({topic}) story detected across {source_count} "
                f"sources in the last 6 hours ({len(group)} articles). "
                f"Average intensity: {group['intensity'].mean():.1f}/5. "
                f"This appears to be a breaking development."
            ),
            data={
                "topic": topic,
                "source_count": source_count,
                "article_count": len(group),
                "avg_intensity": round(float(group["intensity"].mean()), 2),
                "sources": group["source"].unique().tolist()[:10],
            },
        ))
    return alerts


def detect_geopolitical_risk_escalation(df_news, engine=None, thresholds=None):
    """Detect accelerating intensity in geopolitical/conflict topics."""
    alerts = []
    if df_news.empty:
        return alerts
    if not all(c in df_news.columns for c in ["topic", "intensity", "created_at"]):
        return alerts

    geopolitical_topics = {"war & foreign policy", "immigration", "crime & safety"}

    geo_df = df_news[df_news["topic"].isin(geopolitical_topics)]
    if geo_df.empty or len(geo_df) < 5:
        return alerts

    avg_intensity = geo_df["intensity"].mean()
    if avg_intensity < 3.5:
        return alerts

    # Check momentum via predictive_detector if engine available
    momentum = None
    if engine:
        try:
            from predictive_detector import compute_momentum
            momentum = compute_momentum(engine, "global", None, "avg_intensity_geopolitical")
        except Exception as e:
            print(f"WARNING: compute_momentum for geopolitical risk failed: {e}")

    is_rapid = avg_intensity >= 4.5
    is_accelerating = momentum and momentum.get("direction") == "accelerating"

    if is_rapid or is_accelerating:
        severity = "critical" if is_rapid else "warning"
        direction_note = ""
        if momentum:
            direction_note = f" Momentum: {momentum['direction']} ({momentum['magnitude']})."

        topic_breakdown = geo_df["topic"].value_counts()
        alerts.append(_make_alert(
            alert_type="geopolitical_risk_escalation",
            severity=severity,
            title=f"Geopolitical risk {'surge' if is_rapid else 'escalation'}: intensity {avg_intensity:.1f}",
            summary=(
                f"Geopolitical topics show {'rapid escalation' if is_rapid else 'sustained escalation'} "
                f"with average intensity {avg_intensity:.1f}/5 across {len(geo_df)} articles. "
                f"Breakdown: {', '.join(f'{t} ({c})' for t, c in topic_breakdown.items())}.{direction_note}"
            ),
            data={
                "avg_intensity": round(float(avg_intensity), 2),
                "article_count": len(geo_df),
                "topic_breakdown": topic_breakdown.to_dict(),
                "momentum": momentum,
                "rapid_escalation": is_rapid,
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
                             prev_vlds=None, thresholds=None):
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

    t_ws = thresholds.get("brand_white_space", {}) if thresholds else {}
    t_vs = thresholds.get("brand_velocity_spike", {}) if thresholds else {}
    t_nf = thresholds.get("brand_narrative_fading", {}) if thresholds else {}
    t_sat = thresholds.get("brand_saturation", {}) if thresholds else {}

    # White Space Found
    scarcity = vlds.get("scarcity", 0)
    ws_threshold = t_ws.get("critical", 0.7)
    if ws_threshold and scarcity > ws_threshold:
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
    vs_threshold = t_vs.get("critical", 0.7)
    if vs_threshold and velocity > vs_threshold:
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

    # Narrative Fading
    if prev_vlds:
        prev_longevity = prev_vlds.get("longevity", 0)
        curr_longevity = vlds.get("longevity", 0)
        nf_from = t_nf.get("warning", 0.6)
        nf_to = t_nf.get("critical", 0.3)
        if nf_from and nf_to and prev_longevity > nf_from and curr_longevity < nf_to:
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
    sat_threshold = t_sat.get("warning", 0.7)
    if sat_threshold and density > sat_threshold:
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


def detect_brand_mention_surge(df_news, df_social, brand_name, username,
                               thresholds=None):
    """Detect sudden spikes in news or social mentions of a brand."""
    t_surge = thresholds.get("brand_mention_surge", {}) if thresholds else {}
    multiplier = t_surge.get("critical", 3.0)
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

        is_surge = (
            (baseline >= 2 and today_count > baseline * multiplier) or
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


def detect_brand_sentiment_shift(df_news, df_social, brand_name, username,
                                 thresholds=None):
    """Detect significant shifts in brand sentiment (empathy_score)."""
    t_sent = thresholds.get("brand_sentiment_shift", {}) if thresholds else {}
    shift_threshold = t_sent.get("warning", 0.15)
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

    if abs(shift) > shift_threshold:
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


def detect_brand_crisis(df_news, df_social, brand_name, username, thresholds=None):
    """Detect PR crisis: high volume + low empathy + negative emotions simultaneously."""
    alerts = []
    brand_df = pd.concat([
        _filter_by_brand(df_news, brand_name),
        _filter_by_brand(df_social, brand_name),
    ], ignore_index=True)

    if brand_df.empty or len(brand_df) < 5:
        return alerts

    if "created_at" not in brand_df.columns or "empathy_score" not in brand_df.columns:
        return alerts

    # Check volume: need day-over-day baseline
    brand_df_c = brand_df.copy()
    brand_df_c["date"] = brand_df_c["created_at"].dt.date
    daily = brand_df_c.groupby("date").size().sort_index()
    if len(daily) < 2:
        return alerts

    today_count = daily.iloc[-1]
    baseline = daily.iloc[:-1].mean()
    volume_surge = today_count > max(baseline * 2, 5)

    # Check empathy
    avg_empathy = brand_df["empathy_score"].mean()
    low_empathy = avg_empathy < 0.15

    # Check negative emotions
    negative_emotions = {"anger", "annoyance", "disapproval", "disgust"}
    negative_ratio = 0
    if "emotion_top_1" in brand_df.columns:
        neg_count = brand_df["emotion_top_1"].str.lower().isin(negative_emotions).sum()
        negative_ratio = neg_count / len(brand_df)
    negative_dominant = negative_ratio > 0.5

    # All three conditions must be true
    if volume_surge and low_empathy and negative_dominant:
        alerts.append(_make_alert(
            alert_type="brand_crisis",
            severity="critical",
            title=f"PR crisis signal for {brand_name}",
            summary=(
                f"{brand_name} shows crisis indicators: {today_count} mentions today "
                f"({today_count / max(baseline, 0.1):.1f}x baseline), "
                f"avg empathy {avg_empathy:.3f} (very low), "
                f"and {negative_ratio:.0%} negative emotions dominating. "
                f"This combination signals a potential PR crisis."
            ),
            data={
                "brand": brand_name,
                "today_count": int(today_count),
                "baseline": round(float(baseline), 1),
                "avg_empathy": round(float(avg_empathy), 3),
                "negative_ratio": round(float(negative_ratio), 3),
            },
            brand=brand_name,
            username=username,
        ))
    return alerts


# ---------------------------------------------------------------------------
# PART C — Competitive Detectors
# ---------------------------------------------------------------------------

def detect_competitor_momentum(snapshot, brand_name, username, thresholds=None):
    """Detect when a competitor's velocity exceeds the watched brand's."""
    t = thresholds.get("competitor_momentum", {}) if thresholds else {}
    min_velocity = t.get("critical", 0.5)
    alerts = []

    brand_data = snapshot.get(brand_name, {})
    brand_vlds = brand_data.get("vlds") or {}
    brand_velocity = brand_vlds.get("velocity", 0.5)

    for comp_name, comp_data in snapshot.items():
        if comp_name in (brand_name, "share_of_voice", "competitive_gaps"):
            continue
        comp_vlds = comp_data.get("vlds") or {}
        comp_velocity = comp_vlds.get("velocity", 0)
        if comp_velocity > brand_velocity and comp_velocity > min_velocity:
            alerts.append(_make_alert(
                alert_type="competitor_momentum",
                severity="warning",
                title=f"{comp_name} gaining momentum vs {brand_name}",
                summary=(
                    f"{comp_name} has higher conversation velocity ({comp_velocity:.2f}) "
                    f"than {brand_name} ({brand_velocity:.2f}). "
                    f"Competitor is accelerating in the conversation space."
                ),
                data={
                    "brand": brand_name,
                    "competitor": comp_name,
                    "brand_velocity": brand_velocity,
                    "competitor_velocity": comp_velocity,
                },
                brand=brand_name,
                username=username,
            ))
    return alerts


def detect_share_of_voice_shift(current_snapshot, previous_snapshot,
                                brand_name, username, thresholds=None):
    """Detect when a competitor's share of voice overtakes the brand's."""
    alerts = []
    if not previous_snapshot:
        return alerts

    curr_sov = current_snapshot.get("share_of_voice", {})
    prev_sov = previous_snapshot.get("share_of_voice", {})

    brand_curr = curr_sov.get(brand_name, 0)
    brand_prev = prev_sov.get(brand_name, 0)

    for comp_name in curr_sov:
        if comp_name == brand_name:
            continue
        comp_curr = curr_sov.get(comp_name, 0)
        comp_prev = prev_sov.get(comp_name, 0)

        # Competitor was below brand, now above
        if comp_prev < brand_prev and comp_curr >= brand_curr and comp_curr > 0:
            alerts.append(_make_alert(
                alert_type="share_of_voice_shift",
                severity="critical",
                title=f"{comp_name} overtook {brand_name} in share of voice",
                summary=(
                    f"{comp_name} now has {comp_curr:.0f}% share of voice "
                    f"vs {brand_name} at {brand_curr:.0f}%. "
                    f"Previously {comp_name} was at {comp_prev:.0f}% "
                    f"while {brand_name} was at {brand_prev:.0f}%."
                ),
                data={
                    "brand": brand_name,
                    "competitor": comp_name,
                    "brand_sov": brand_curr,
                    "competitor_sov": comp_curr,
                    "brand_prev_sov": brand_prev,
                    "competitor_prev_sov": comp_prev,
                },
                brand=brand_name,
                username=username,
            ))
    return alerts


def detect_competitive_white_space(snapshot, brand_name, username,
                                   thresholds=None):
    """Detect density gaps between brand and competitors indicating opportunity."""
    t = thresholds.get("competitive_white_space", {}) if thresholds else {}
    brand_density_max = t.get("warning", 0.3)
    comp_density_min = t.get("critical", 0.5)
    alerts = []

    brand_data = snapshot.get(brand_name, {})
    brand_vlds = brand_data.get("vlds") or {}
    brand_density = brand_vlds.get("density", 0)

    comp_densities = []
    for comp_name, comp_data in snapshot.items():
        if comp_name in (brand_name, "share_of_voice", "competitive_gaps"):
            continue
        comp_vlds = comp_data.get("vlds") or {}
        comp_density = comp_vlds.get("density", 0)
        comp_densities.append((comp_name, comp_density))

    if not comp_densities:
        return alerts

    avg_comp_density = sum(d for _, d in comp_densities) / len(comp_densities)

    if brand_density < brand_density_max and avg_comp_density > comp_density_min:
        top_comp = max(comp_densities, key=lambda x: x[1])
        alerts.append(_make_alert(
            alert_type="competitive_white_space",
            severity="critical",
            title=f"Competitive white space for {brand_name}",
            summary=(
                f"{brand_name} has low density ({brand_density:.2f}) while "
                f"competitors average {avg_comp_density:.2f}. "
                f"{top_comp[0]} leads at {top_comp[1]:.2f}. "
                f"This gap represents a strategic opportunity."
            ),
            data={
                "brand": brand_name,
                "brand_density": brand_density,
                "avg_competitor_density": round(avg_comp_density, 2),
                "top_competitor": top_comp[0],
                "top_competitor_density": top_comp[1],
            },
            brand=brand_name,
            username=username,
        ))
    return alerts


def run_competitive_detectors(brand_name, username, current_snapshot,
                              previous_snapshot=None, thresholds=None):
    """Run all 3 competitive detectors. Returns list of alerts."""
    alerts = []
    alerts.extend(detect_competitor_momentum(
        current_snapshot, brand_name, username, thresholds
    ))
    alerts.extend(detect_share_of_voice_shift(
        current_snapshot, previous_snapshot, brand_name, username, thresholds
    ))
    alerts.extend(detect_competitive_white_space(
        current_snapshot, brand_name, username, thresholds
    ))
    return alerts


# ---------------------------------------------------------------------------
# Run all detectors
# ---------------------------------------------------------------------------

def run_global_detectors(df_news, df_social, df_markets, thresholds=None,
                         engine=None):
    """Run all 7 global detectors and return a list of alerts."""
    t = thresholds or {}
    alerts = []
    alerts.extend(detect_mood_shift(df_news, df_social, t.get("mood_shift")))
    alerts.extend(detect_market_mood_divergence(df_social, df_markets, t.get("market_mood_divergence")))
    alerts.extend(detect_intensity_cluster(df_news, df_social, t.get("intensity_cluster")))
    alerts.extend(detect_topic_emergence(df_news, t.get("topic_emergence")))
    alerts.extend(detect_regulatory_policy_spike(df_news, t.get("regulatory_policy_spike")))
    alerts.extend(detect_breaking_signal(df_news, t.get("breaking_signal")))
    alerts.extend(detect_geopolitical_risk_escalation(df_news, engine=engine, thresholds=t.get("geopolitical_risk_escalation")))
    return alerts


def run_brand_detectors(df_news, df_social, brand_name, username,
                        prev_vlds=None, thresholds=None):
    """Run all 8 brand detectors and return alerts + current VLDS."""
    alerts = []
    vlds_alerts, current_vlds = detect_brand_vlds_alerts(
        df_news, df_social, brand_name, username, prev_vlds, thresholds
    )
    alerts.extend(vlds_alerts)
    alerts.extend(detect_brand_mention_surge(
        df_news, df_social, brand_name, username, thresholds
    ))
    alerts.extend(detect_brand_sentiment_shift(
        df_news, df_social, brand_name, username, thresholds
    ))
    alerts.extend(detect_brand_crisis(
        df_news, df_social, brand_name, username, thresholds
    ))
    return alerts, current_vlds


# ---------------------------------------------------------------------------
# Topic filtering helper
# ---------------------------------------------------------------------------

def _filter_by_topic(df, topic_name, is_category=False):
    """Filter a dataframe to rows matching a topic.

    For built-in categories (is_category=True): exact match on topic column.
    For custom keywords (is_category=False): text search in title/text.
    """
    if df.empty:
        return pd.DataFrame()

    if is_category and "topic" in df.columns:
        return df[df["topic"].str.lower() == topic_name.lower()]

    # Custom keyword: text search (same pattern as _filter_by_brand)
    topic_lower = topic_name.lower()
    mask = pd.Series(False, index=df.index)
    for col in ["title", "text"]:
        if col in df.columns:
            mask = mask | df[col].str.contains(topic_lower, case=False, na=False)
    return df[mask]


# ---------------------------------------------------------------------------
# PART D — Topic-Specific Detectors
# ---------------------------------------------------------------------------

def detect_topic_mention_surge(df_news, df_social, topic_name, is_category,
                                username, thresholds=None):
    """Detect sudden volume spike for a watched topic."""
    t_surge = thresholds.get("topic_mention_surge", {}) if thresholds else {}
    multiplier = t_surge.get("critical", 3.0)
    alerts = []

    for label, df in [("news", df_news), ("social", df_social)]:
        topic_df = _filter_by_topic(df, topic_name, is_category)
        if topic_df.empty or "created_at" not in topic_df.columns:
            continue

        topic_df = topic_df.copy()
        topic_df["date"] = topic_df["created_at"].dt.date
        daily = topic_df.groupby("date").size().sort_index()

        if len(daily) < 2:
            continue

        today_count = daily.iloc[-1]
        baseline = daily.iloc[:-1].mean()

        is_surge = (
            (baseline >= 2 and today_count > baseline * multiplier)
            or (baseline < 2 and today_count >= 8)
        )
        if is_surge:
            alerts.append(_make_alert(
                alert_type="topic_mention_surge",
                severity="critical",
                title=f"Topic surge: {topic_name} in {label}",
                summary=(
                    f'"{topic_name}" appeared in {today_count} {label} items today '
                    f'vs a baseline of {baseline:.1f}/day. '
                    f'This is a {today_count / max(baseline, 0.1):.1f}x spike.'
                ),
                data={
                    "topic": topic_name,
                    "source": label,
                    "today_count": int(today_count),
                    "baseline": round(float(baseline), 1),
                },
                username=username,
            ))
            alerts[-1]["topic"] = topic_name
    return alerts


def detect_topic_sentiment_shift(df_news, df_social, topic_name, is_category,
                                  username, thresholds=None):
    """Detect significant empathy score shift for a watched topic."""
    t_sent = thresholds.get("topic_sentiment_shift", {}) if thresholds else {}
    shift_threshold = t_sent.get("warning", 0.15)
    alerts = []

    topic_df = pd.concat([
        _filter_by_topic(df_news, topic_name, is_category),
        _filter_by_topic(df_social, topic_name, is_category),
    ], ignore_index=True)

    if topic_df.empty or "empathy_score" not in topic_df.columns:
        return alerts
    if "created_at" not in topic_df.columns:
        return alerts

    topic_df = topic_df.copy()
    topic_df["date"] = topic_df["created_at"].dt.date
    daily_sentiment = topic_df.groupby("date")["empathy_score"].mean().sort_index()

    if len(daily_sentiment) < 3:
        return alerts

    rolling_avg = daily_sentiment.iloc[:-1].mean()
    current = daily_sentiment.iloc[-1]
    shift = current - rolling_avg

    if abs(shift) > shift_threshold:
        direction = "warmed" if shift > 0 else "cooled"
        alerts.append(_make_alert(
            alert_type="topic_sentiment_shift",
            severity="warning",
            title=f"Sentiment {direction} for {topic_name}",
            summary=(
                f'Sentiment around "{topic_name}" {direction} from '
                f'{rolling_avg:.3f} (rolling avg) to {current:.3f} '
                f'(shift: {shift:+.3f}).'
            ),
            data={
                "topic": topic_name,
                "rolling_avg": round(float(rolling_avg), 3),
                "current": round(float(current), 3),
                "shift": round(float(shift), 3),
            },
            username=username,
        ))
        alerts[-1]["topic"] = topic_name
    return alerts


def detect_topic_intensity_spike(df_news, df_social, topic_name, is_category,
                                  username, thresholds=None):
    """Detect rising average intensity for a watched topic."""
    t_int = thresholds.get("topic_intensity_spike", {}) if thresholds else {}
    intensity_threshold = t_int.get("warning", 3.5)
    alerts = []

    topic_df = pd.concat([
        _filter_by_topic(df_news, topic_name, is_category),
        _filter_by_topic(df_social, topic_name, is_category),
    ], ignore_index=True)

    if topic_df.empty or "intensity" not in topic_df.columns:
        return alerts
    if len(topic_df) < 5:
        return alerts

    avg_intensity = topic_df["intensity"].mean()
    if avg_intensity >= intensity_threshold:
        alerts.append(_make_alert(
            alert_type="topic_intensity_spike",
            severity="warning",
            title=f"Intensity spike for {topic_name}: {avg_intensity:.1f}",
            summary=(
                f'"{topic_name}" shows elevated intensity at {avg_intensity:.1f}/5 '
                f'across {len(topic_df)} posts.'
            ),
            data={
                "topic": topic_name,
                "avg_intensity": round(float(avg_intensity), 2),
                "post_count": len(topic_df),
            },
            username=username,
        ))
        alerts[-1]["topic"] = topic_name
    return alerts


def detect_topic_vlds_alerts(df_news, df_social, topic_name, is_category,
                              username, thresholds=None):
    """Run VLDS on topic-filtered data and detect velocity/saturation thresholds."""
    alerts = []
    topic_df = pd.concat([
        _filter_by_topic(df_news, topic_name, is_category),
        _filter_by_topic(df_social, topic_name, is_category),
    ], ignore_index=True)

    if topic_df.empty or len(topic_df) < 5:
        return alerts, None

    from vlds_helper import calculate_brand_vlds
    vlds = calculate_brand_vlds(topic_df)
    if not vlds:
        return alerts, None

    t_vs = thresholds.get("topic_velocity_spike", {}) if thresholds else {}
    t_sat = thresholds.get("topic_saturation", {}) if thresholds else {}

    # Velocity spike
    velocity = vlds.get("velocity", 0.5)
    vs_threshold = t_vs.get("critical", 0.7)
    if vs_threshold and velocity > vs_threshold:
        alerts.append(_make_alert(
            alert_type="topic_velocity_spike",
            severity="critical",
            title=f"Velocity spike for {topic_name}",
            summary=(
                f'Conversation about "{topic_name}" is accelerating '
                f'(velocity: {velocity:.2f}).'
            ),
            data={"topic": topic_name, "velocity": velocity},
            username=username,
        ))
        alerts[-1]["topic"] = topic_name

    # Saturation warning
    density = vlds.get("density", 0)
    sat_threshold = t_sat.get("warning", 0.7)
    if sat_threshold and density > sat_threshold:
        alerts.append(_make_alert(
            alert_type="topic_saturation",
            severity="warning",
            title=f"Topic saturated: {topic_name}",
            summary=(
                f'"{topic_name}" has a density score of {density:.2f} — '
                f'the space is crowded with {vlds.get("total_posts", 0)} posts.'
            ),
            data={"topic": topic_name, "density": density},
            username=username,
        ))
        alerts[-1]["topic"] = topic_name

    return alerts, vlds


def run_topic_detectors(df_news, df_social, topic_name, is_category, username,
                         thresholds=None):
    """Run all topic detectors and return alerts + current VLDS."""
    alerts = []
    alerts.extend(detect_topic_mention_surge(
        df_news, df_social, topic_name, is_category, username, thresholds
    ))
    alerts.extend(detect_topic_sentiment_shift(
        df_news, df_social, topic_name, is_category, username, thresholds
    ))
    alerts.extend(detect_topic_intensity_spike(
        df_news, df_social, topic_name, is_category, username, thresholds
    ))
    vlds_alerts, current_vlds = detect_topic_vlds_alerts(
        df_news, df_social, topic_name, is_category, username, thresholds
    )
    alerts.extend(vlds_alerts)
    return alerts, current_vlds


# =====================================================================
# Part E: Economic Detectors
# =====================================================================

def detect_economic_stress(engine, thresholds=None):
    """Score economic stress from multiple indicators.

    Stress signals (each +1 point):
      - Treasury yield > 5%
      - Unemployment > 4.5%
      - CPI > 3.5%
      - Nonfarm payroll < 100 (thousands)
      - Federal funds rate > 5.5%

    Fires at warning (2) or critical (3).
    """
    from sqlalchemy import text as sql_text

    alerts = []
    if not engine:
        return alerts

    t_conf = (thresholds or {}).get("economic_stress", {})
    warning_threshold = t_conf.get("warning", 2)
    critical_threshold = t_conf.get("critical", 3)

    try:
        with engine.connect() as conn:
            result = conn.execute(sql_text("""
                SELECT metric_name, metric_value
                FROM metric_snapshots
                WHERE scope = 'economic'
                  AND snapshot_date = (
                      SELECT MAX(snapshot_date) FROM metric_snapshots
                      WHERE scope = 'economic' AND metric_name = metric_snapshots.metric_name
                  )
            """))
            latest = {row[0]: row[1] for row in result.fetchall()}
    except Exception as e:
        print(f"  Economic stress query failed: {e}")
        return alerts

    if not latest:
        return alerts

    score = 0
    signals = []

    treasury = latest.get("treasury_yield_10y")
    if treasury is not None and treasury > 5.0:
        score += 1
        signals.append(f"Treasury yield {treasury:.2f}%")

    unemployment = latest.get("unemployment_rate")
    if unemployment is not None and unemployment > 4.5:
        score += 1
        signals.append(f"Unemployment {unemployment:.1f}%")

    cpi = latest.get("cpi_yoy")
    if cpi is not None and cpi > 3.5:
        score += 1
        signals.append(f"CPI {cpi:.1f}%")

    nonfarm = latest.get("nonfarm_payroll")
    if nonfarm is not None and nonfarm < 100:
        score += 1
        signals.append(f"Nonfarm payroll {nonfarm:.0f}K")

    fed_funds = latest.get("federal_funds_rate")
    if fed_funds is not None and fed_funds > 5.5:
        score += 1
        signals.append(f"Fed funds rate {fed_funds:.2f}%")

    if critical_threshold and score >= critical_threshold:
        severity = "critical"
    elif warning_threshold and score >= warning_threshold:
        severity = "warning"
    else:
        return alerts

    alerts.append(_make_alert(
        alert_type="economic_stress",
        severity=severity,
        title=f"Economic stress score: {score}/5",
        summary=f"Multiple economic indicators signal stress: {'; '.join(signals)}.",
        data={"score": score, "signals": signals, "latest": latest},
    ))
    return alerts


def detect_economic_threshold_crossing(engine, thresholds=None):
    """Fire when an individual economic indicator crosses a significant level.

    Checks current vs previous value to detect actual crossings,
    not just levels above threshold.
    """
    from sqlalchemy import text as sql_text

    alerts = []
    if not engine:
        return alerts

    # Significant thresholds for each indicator
    crossings = {
        "unemployment_rate": [(5.0, "Unemployment crossed 5%"), (4.0, "Unemployment dropped below 4%")],
        "treasury_yield_10y": [(5.0, "10-year Treasury yield crossed 5%"), (4.0, "10-year Treasury yield crossed 4%")],
        "cpi_yoy": [(3.0, "CPI crossed 3%"), (4.0, "CPI crossed 4%")],
        "federal_funds_rate": [(5.0, "Fed funds rate crossed 5%"), (5.5, "Fed funds rate crossed 5.5%")],
    }

    try:
        with engine.connect() as conn:
            for metric_name, thresholds_list in crossings.items():
                result = conn.execute(sql_text("""
                    SELECT snapshot_date, metric_value
                    FROM metric_snapshots
                    WHERE scope = 'economic' AND metric_name = :metric
                    ORDER BY snapshot_date DESC LIMIT 2
                """), {"metric": metric_name})
                rows = result.fetchall()

                if len(rows) < 2:
                    continue

                current_val = rows[0][1]
                previous_val = rows[1][1]

                for level, description in thresholds_list:
                    # Check if threshold was crossed between previous and current
                    crossed_up = previous_val < level <= current_val
                    crossed_down = previous_val > level >= current_val
                    if crossed_up or crossed_down:
                        direction = "rose above" if crossed_up else "fell below"
                        alerts.append(_make_alert(
                            alert_type="economic_threshold_crossing",
                            severity="warning",
                            title=description,
                            summary=(
                                f"{metric_name.replace('_', ' ').title()} {direction} {level} "
                                f"(previous: {previous_val:.2f}, current: {current_val:.2f})."
                            ),
                            data={
                                "metric": metric_name,
                                "level": level,
                                "previous": previous_val,
                                "current": current_val,
                                "direction": "up" if crossed_up else "down",
                            },
                        ))
    except Exception as e:
        print(f"  Economic threshold crossing check failed: {e}")

    return alerts


def run_economic_detectors(engine, thresholds=None):
    """Run all economic detectors. Returns list of alerts."""
    alerts = []
    alerts.extend(detect_economic_stress(engine, thresholds))
    alerts.extend(detect_economic_threshold_crossing(engine, thresholds))
    return alerts
