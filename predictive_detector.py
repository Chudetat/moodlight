#!/usr/bin/env python
"""
Predictive pattern matching for Moodlight.
Detects metrics trending toward thresholds before they're crossed,
tracks acceleration/deceleration, and identifies compound signals
where multiple weak indicators align.

All computation is pure statistics (numpy) — no ML models, no API calls.
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from alert_detector import _make_alert, _filter_by_brand
from vlds_helper import calculate_brand_vlds


# ---------------------------------------------------------------------------
# Table setup
# ---------------------------------------------------------------------------

def ensure_metric_snapshots_table(engine):
    """Create the metric_snapshots table if it doesn't exist."""
    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS metric_snapshots (
                id SERIAL PRIMARY KEY,
                snapshot_date DATE NOT NULL,
                scope VARCHAR(20) NOT NULL,
                scope_name VARCHAR(200),
                metric_name VARCHAR(100) NOT NULL,
                metric_value FLOAT NOT NULL,
                sample_size INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(snapshot_date, scope, scope_name, metric_name)
            )
        """))
        conn.commit()


# ---------------------------------------------------------------------------
# Metric snapshot capture
# ---------------------------------------------------------------------------

def capture_metric_snapshots(engine, df_news, df_social, df_markets, watchlist):
    """Compute and store today's metric values for trend analysis.

    Called once per pipeline run, after data is loaded.
    Uses ON CONFLICT DO UPDATE for idempotent re-runs.
    """
    from sqlalchemy import text

    today = datetime.now(timezone.utc).date().isoformat()
    metrics = []

    # Global metrics
    if not df_news.empty and "empathy_score" in df_news.columns:
        avg = float(df_news["empathy_score"].mean())
        metrics.append(("global", None, "avg_empathy_news", avg, len(df_news)))
        high = len(df_news[df_news["empathy_score"] > 0.7])
        ratio = high / len(df_news) if len(df_news) > 0 else 0
        metrics.append(("global", None, "high_emotion_ratio_news", ratio, len(df_news)))
        metrics.append(("global", None, "total_news_count", float(len(df_news)), len(df_news)))

    if not df_social.empty and "empathy_score" in df_social.columns:
        avg = float(df_social["empathy_score"].mean())
        metrics.append(("global", None, "avg_empathy_social", avg, len(df_social)))
        high = len(df_social[df_social["empathy_score"] > 0.7])
        ratio = high / len(df_social) if len(df_social) > 0 else 0
        metrics.append(("global", None, "high_emotion_ratio_social", ratio, len(df_social)))
        metrics.append(("global", None, "total_social_count", float(len(df_social)), len(df_social)))

    if not df_markets.empty and "market_sentiment" in df_markets.columns:
        avg = float(df_markets["market_sentiment"].mean())
        metrics.append(("global", None, "market_sentiment", avg, len(df_markets)))

    # Per-brand metrics
    for username, brands in (watchlist or {}).items():
        for brand_name in brands:
            news_brand = _filter_by_brand(df_news, brand_name)
            social_brand = _filter_by_brand(df_social, brand_name)

            metrics.append(("brand", brand_name, "mention_count_news",
                            float(len(news_brand)), len(news_brand)))
            metrics.append(("brand", brand_name, "mention_count_social",
                            float(len(social_brand)), len(social_brand)))

            combined = pd.concat([news_brand, social_brand], ignore_index=True)
            if not combined.empty and "empathy_score" in combined.columns:
                metrics.append(("brand", brand_name, "avg_empathy",
                                float(combined["empathy_score"].mean()), len(combined)))

            if not combined.empty and len(combined) >= 3:
                vlds = calculate_brand_vlds(combined)
                if vlds:
                    for key in ("velocity", "longevity", "density", "scarcity"):
                        if key in vlds:
                            metrics.append(("brand", brand_name, key,
                                            float(vlds[key]), len(combined)))

    # Store all metrics
    if not metrics:
        return

    try:
        with engine.connect() as conn:
            for scope, scope_name, metric_name, value, sample_size in metrics:
                conn.execute(
                    text("""
                        INSERT INTO metric_snapshots
                            (snapshot_date, scope, scope_name, metric_name, metric_value, sample_size)
                        VALUES (:date, :scope, :scope_name, :metric, :value, :sample)
                        ON CONFLICT (snapshot_date, scope, scope_name, metric_name)
                        DO UPDATE SET metric_value = EXCLUDED.metric_value,
                                      sample_size = EXCLUDED.sample_size,
                                      created_at = NOW()
                    """),
                    {
                        "date": today,
                        "scope": scope,
                        "scope_name": scope_name,
                        "metric": metric_name,
                        "value": value,
                        "sample": sample_size,
                    },
                )
            conn.commit()
        print(f"  Captured {len(metrics)} metric snapshots")
    except Exception as e:
        print(f"  Metric snapshot storage failed: {e}")


# ---------------------------------------------------------------------------
# Trend computation
# ---------------------------------------------------------------------------

def compute_trend(engine, scope, scope_name, metric_name, lookback_days=7):
    """Load historical snapshots and compute linear regression.

    Returns dict with {slope, r_squared, current_value, data_points, values}
    or None if fewer than 3 data points exist.
    """
    from sqlalchemy import text

    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).date().isoformat()

    try:
        with engine.connect() as conn:
            if scope_name:
                result = conn.execute(
                    text("""
                        SELECT snapshot_date, metric_value FROM metric_snapshots
                        WHERE scope = :scope AND scope_name = :name
                          AND metric_name = :metric AND snapshot_date >= :cutoff
                        ORDER BY snapshot_date
                    """),
                    {"scope": scope, "name": scope_name, "metric": metric_name, "cutoff": cutoff},
                )
            else:
                result = conn.execute(
                    text("""
                        SELECT snapshot_date, metric_value FROM metric_snapshots
                        WHERE scope = :scope AND scope_name IS NULL
                          AND metric_name = :metric AND snapshot_date >= :cutoff
                        ORDER BY snapshot_date
                    """),
                    {"scope": scope, "metric": metric_name, "cutoff": cutoff},
                )
            rows = result.fetchall()
    except Exception:
        return None

    if len(rows) < 3:
        return None

    values = [(str(row[0]), float(row[1])) for row in rows]
    y = np.array([v[1] for v in values])
    x = np.arange(len(y), dtype=float)

    # Linear regression
    coeffs = np.polyfit(x, y, 1)
    slope = float(coeffs[0])

    # R-squared
    y_pred = np.polyval(coeffs, x)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    return {
        "slope": slope,
        "r_squared": r_squared,
        "current_value": float(y[-1]),
        "data_points": len(y),
        "values": values,
    }


def predict_threshold_crossing(trend, threshold_value, max_days=7):
    """Predict when a metric will cross a threshold at current rate.

    Returns dict with {days_to_crossing, predicted_value, confidence}
    or None if no crossing within max_days.
    """
    if trend is None or threshold_value is None:
        return None

    slope = trend["slope"]
    current = trend["current_value"]

    # Already past threshold
    if (slope > 0 and current >= threshold_value) or (slope < 0 and current <= threshold_value):
        return None

    # Not moving toward threshold
    if slope == 0:
        return None
    if slope > 0 and threshold_value < current:
        return None
    if slope < 0 and threshold_value > current:
        return None

    days_to_crossing = (threshold_value - current) / slope
    if days_to_crossing <= 0 or days_to_crossing > max_days:
        return None

    # Confidence based on R-squared
    r_sq = trend.get("r_squared", 0)
    if r_sq > 0.7:
        confidence = "high"
    elif r_sq > 0.4:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "days_to_crossing": round(days_to_crossing, 1),
        "predicted_value": round(threshold_value, 4),
        "confidence": confidence,
    }


def compute_momentum(engine, scope, scope_name, metric_name, lookback_days=7):
    """Track acceleration/deceleration of a metric (second derivative).

    Returns dict with {velocity, acceleration, direction, magnitude}
    or None if fewer than 3 data points.
    """
    trend = compute_trend(engine, scope, scope_name, metric_name, lookback_days)
    if trend is None or trend["data_points"] < 3:
        return None

    values = [v[1] for v in trend["values"]]

    # First derivatives (daily changes)
    first_derivs = [values[i] - values[i - 1] for i in range(1, len(values))]

    # Latest velocity (most recent daily change)
    velocity = first_derivs[-1]

    # Acceleration (change in velocity) — need at least 2 derivatives
    if len(first_derivs) >= 2:
        acceleration = first_derivs[-1] - first_derivs[-2]
    else:
        acceleration = 0.0

    # Direction
    if abs(acceleration) < 0.001:
        direction = "steady"
    elif acceleration > 0:
        direction = "accelerating"
    else:
        direction = "decelerating"

    # Magnitude based on acceleration relative to current value
    current = trend["current_value"]
    if current != 0:
        rel_accel = abs(acceleration / current)
    else:
        rel_accel = abs(acceleration)

    if rel_accel > 0.1:
        magnitude = "strong"
    elif rel_accel > 0.03:
        magnitude = "moderate"
    else:
        magnitude = "weak"

    return {
        "velocity": round(velocity, 4),
        "acceleration": round(acceleration, 4),
        "direction": direction,
        "magnitude": magnitude,
    }


# ---------------------------------------------------------------------------
# Compound signal detection
# ---------------------------------------------------------------------------

# Mapping of metric names to the alert thresholds they approach
METRIC_THRESHOLD_MAP = {
    # Global metrics → alert_type threshold keys
    "avg_empathy_news": ("mood_shift", "critical", 0.25, "above"),
    "avg_empathy_social": ("mood_shift", "critical", 0.25, "above"),
    "high_emotion_ratio_news": ("intensity_cluster", "critical", None, "above"),
    "high_emotion_ratio_social": ("intensity_cluster", "critical", None, "above"),
    # Brand metrics
    "velocity": ("brand_velocity_spike", "critical", None, "above"),
    "density": ("brand_saturation", "warning", None, "above"),
    "mention_count_news": ("brand_mention_surge", "critical", None, "above"),
    "mention_count_social": ("brand_mention_surge", "critical", None, "above"),
}


def detect_compound_signals(engine, scope, scope_name, trends, thresholds):
    """Detect when multiple weak signals align.

    Scoring:
    - Each metric within 80% of threshold: +1 point
    - Each metric accelerating toward threshold: +1 point
    - Compound score >= 3: generate alert

    Returns list of alert dicts.
    """
    alerts = []
    score = 0
    signals = []

    for metric_name, trend in trends.items():
        if trend is None:
            continue

        mapping = METRIC_THRESHOLD_MAP.get(metric_name)
        if not mapping:
            continue

        alert_type, level, default_val, direction = mapping

        # Get threshold value
        t_config = thresholds.get(alert_type, {}) if thresholds else {}
        threshold_val = t_config.get(level, default_val)
        if threshold_val is None:
            continue

        current = trend["current_value"]

        # Check if within 80% of threshold
        if direction == "above":
            progress = current / threshold_val if threshold_val > 0 else 0
            if progress >= 0.8 and progress < 1.0:
                score += 1
                signals.append(f"{metric_name} at {progress:.0%} of threshold")
        else:
            progress = threshold_val / current if current > 0 else 0
            if progress >= 0.8 and progress < 1.0:
                score += 1
                signals.append(f"{metric_name} approaching lower threshold")

        # Check acceleration toward threshold
        momentum = compute_momentum(engine, scope, scope_name, metric_name)
        if momentum:
            if direction == "above" and momentum["direction"] == "accelerating":
                score += 1
                signals.append(f"{metric_name} accelerating ({momentum['magnitude']})")
            elif direction == "below" and momentum["direction"] == "decelerating":
                score += 1
                signals.append(f"{metric_name} decelerating toward threshold")

    if score >= 3:
        brand = scope_name if scope == "brand" else None
        alerts.append(_make_alert(
            alert_type="predictive_compound_signal",
            severity="info",
            title=f"Compound signal detected" + (f" for {brand}" if brand else ""),
            summary=(
                f"{score} converging signals detected: "
                + "; ".join(signals[:4])
                + ". Multiple metrics are approaching thresholds simultaneously."
            ),
            data={
                "score": score,
                "signals": signals,
                "scope": scope,
                "scope_name": scope_name,
            },
            brand=brand,
        ))

    return alerts


# ---------------------------------------------------------------------------
# Predictive cooldown
# ---------------------------------------------------------------------------

def build_predictive_cooldown_key(alert, metric_name=None):
    """Build a cooldown key for predictive alerts.

    Adds metric_name to avoid one predictive alert type suppressing
    alerts about different metrics.
    """
    parts = [alert.get("alert_type", "")]
    if metric_name:
        parts.append(metric_name)
    if alert.get("brand"):
        parts.append(alert["brand"])
    if alert.get("username"):
        parts.append(alert["username"])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parts.append(today)
    return ":".join(parts)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

# Which global metrics to check for threshold approach
GLOBAL_METRIC_THRESHOLDS = {
    "avg_empathy_news": ("mood_shift", "warning"),
    "avg_empathy_social": ("mood_shift", "warning"),
    "high_emotion_ratio_news": ("intensity_cluster", "warning"),
    "high_emotion_ratio_social": ("intensity_cluster", "warning"),
    "market_sentiment": ("market_mood_divergence", "warning"),
}

# Which brand metrics to check
BRAND_METRIC_THRESHOLDS = {
    "velocity": ("brand_velocity_spike", "critical"),
    "density": ("brand_saturation", "warning"),
    "scarcity": ("brand_white_space", "critical"),
}


def run_predictive_detectors(engine, df_news, df_social, df_markets,
                              watchlist, thresholds):
    """Run all predictive detection logic.

    Returns list of alert dicts (severity='info').
    """
    alerts = []

    # 1. Compute trends for global metrics
    global_trends = {}
    for metric_name in GLOBAL_METRIC_THRESHOLDS:
        trend = compute_trend(engine, "global", None, metric_name)
        if trend:
            global_trends[metric_name] = trend

    # 2. Check global threshold approaches
    for metric_name, (alert_type, level) in GLOBAL_METRIC_THRESHOLDS.items():
        trend = global_trends.get(metric_name)
        if not trend:
            continue

        t_config = thresholds.get(alert_type, {}) if thresholds else {}
        threshold_val = t_config.get(level)
        if threshold_val is None:
            continue

        crossing = predict_threshold_crossing(trend, threshold_val)
        if crossing and crossing["confidence"] in ("high", "medium"):
            momentum = compute_momentum(engine, "global", None, metric_name)
            direction_note = ""
            if momentum and momentum["direction"] != "steady":
                direction_note = f" and {momentum['direction']} ({momentum['magnitude']})"

            alerts.append(_make_alert(
                alert_type=f"predictive_{alert_type}",
                severity="info",
                title=f"Trending toward {alert_type.replace('_', ' ')} threshold",
                summary=(
                    f"{metric_name.replace('_', ' ').title()} is trending toward "
                    f"the {level} threshold ({threshold_val}). "
                    f"At current rate, crossing in ~{crossing['days_to_crossing']} days"
                    f"{direction_note}. "
                    f"Confidence: {crossing['confidence']}."
                ),
                data={
                    "metric": metric_name,
                    "trend": {
                        "slope": trend["slope"],
                        "r_squared": trend["r_squared"],
                        "current_value": trend["current_value"],
                    },
                    "crossing": crossing,
                    "momentum": momentum,
                },
            ))

    # 3. Check global compound signals
    alerts.extend(detect_compound_signals(
        engine, "global", None, global_trends, thresholds
    ))

    # 4. Per-brand predictive analysis
    for username, brands in (watchlist or {}).items():
        for brand_name in brands:
            brand_trends = {}
            for metric_name in BRAND_METRIC_THRESHOLDS:
                trend = compute_trend(engine, "brand", brand_name, metric_name)
                if trend:
                    brand_trends[metric_name] = trend

            # Also include mention counts
            for extra in ("mention_count_news", "mention_count_social", "avg_empathy"):
                trend = compute_trend(engine, "brand", brand_name, extra)
                if trend:
                    brand_trends[extra] = trend

            # Check brand threshold approaches
            for metric_name, (alert_type, level) in BRAND_METRIC_THRESHOLDS.items():
                trend = brand_trends.get(metric_name)
                if not trend:
                    continue

                t_config = thresholds.get(alert_type, {}) if thresholds else {}
                threshold_val = t_config.get(level)
                if threshold_val is None:
                    continue

                crossing = predict_threshold_crossing(trend, threshold_val)
                if crossing and crossing["confidence"] in ("high", "medium"):
                    momentum = compute_momentum(
                        engine, "brand", brand_name, metric_name
                    )
                    direction_note = ""
                    if momentum and momentum["direction"] != "steady":
                        direction_note = f" and {momentum['direction']}"

                    alerts.append(_make_alert(
                        alert_type=f"predictive_{alert_type}",
                        severity="info",
                        title=f"{brand_name}: trending toward {alert_type.replace('_', ' ')}",
                        summary=(
                            f"{metric_name.title()} for {brand_name} is trending toward "
                            f"the {level} threshold ({threshold_val}). "
                            f"Crossing in ~{crossing['days_to_crossing']} days"
                            f"{direction_note}. "
                            f"Confidence: {crossing['confidence']}."
                        ),
                        data={
                            "metric": metric_name,
                            "brand": brand_name,
                            "trend": {
                                "slope": trend["slope"],
                                "r_squared": trend["r_squared"],
                                "current_value": trend["current_value"],
                            },
                            "crossing": crossing,
                            "momentum": momentum,
                        },
                        brand=brand_name,
                        username=username,
                    ))

            # Check brand compound signals
            alerts.extend(detect_compound_signals(
                engine, "brand", brand_name, brand_trends, thresholds
            ))

    return alerts
