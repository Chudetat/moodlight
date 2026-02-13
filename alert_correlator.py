#!/usr/bin/env python
"""
alert_correlator.py
Detects when multiple alerts from the same pipeline run are related
and generates unified "Situation Reports" that connect the dots.
"""

import os
import json
from datetime import datetime, timezone
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Known causal relationships between alert types.
# Each pair maps to a bonus relatedness score.
CAUSAL_PATTERNS = {
    ("geopolitical_risk_escalation", "market_mood_divergence"): 2,
    ("geopolitical_risk_escalation", "brand_sentiment_shift"): 2,
    ("regulatory_policy_spike", "brand_sentiment_shift"): 2,
    ("regulatory_policy_spike", "market_mood_divergence"): 2,
    ("breaking_signal", "brand_crisis"): 2,
    ("breaking_signal", "brand_mention_surge"): 2,
    ("mood_shift", "market_mood_divergence"): 2,
    ("brand_crisis", "brand_sentiment_shift"): 2,
    ("topic_emergence", "breaking_signal"): 2,
    ("topic_emergence", "brand_mention_surge"): 2,
    ("intensity_cluster", "breaking_signal"): 2,
    ("intensity_cluster", "brand_crisis"): 2,
}

# Minimum relatedness score to consider two alerts correlated
CORRELATION_THRESHOLD = 3


def _compute_relatedness(alert_a, alert_b):
    """Score how related two alerts are (0 = unrelated, higher = more related).

    Scoring:
    - Same brand: +3
    - Same or related topic/data overlap: +2
    - Known causal pattern: +2
    - Same data source overlap: +1
    """
    score = 0

    # Same brand
    brand_a = (alert_a.get("brand") or "").lower()
    brand_b = (alert_b.get("brand") or "").lower()
    if brand_a and brand_b and brand_a == brand_b:
        score += 3

    # Known causal pattern
    type_a = alert_a.get("alert_type", "")
    type_b = alert_b.get("alert_type", "")
    pair = (type_a, type_b)
    pair_rev = (type_b, type_a)
    if pair in CAUSAL_PATTERNS:
        score += CAUSAL_PATTERNS[pair]
    elif pair_rev in CAUSAL_PATTERNS:
        score += CAUSAL_PATTERNS[pair_rev]

    # Topic overlap — check if titles/summaries share key terms
    title_a = (alert_a.get("title") or "").lower()
    title_b = (alert_b.get("title") or "").lower()
    summary_a = (alert_a.get("summary") or "").lower()
    summary_b = (alert_b.get("summary") or "").lower()

    text_a = title_a + " " + summary_a
    text_b = title_b + " " + summary_b

    _stopwords = frozenset({
        "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to",
        "for", "of", "and", "or", "but", "with", "from", "by", "this", "that",
        "it", "not", "be", "has", "had", "have", "will", "would", "could",
        "should", "may", "can", "do", "did", "been", "being", "their", "there",
        "than", "more", "less", "alert", "detected", "spike", "surge", "shift",
    })

    words_a = {w for w in text_a.split() if len(w) > 3 and w not in _stopwords}
    words_b = {w for w in text_b.split() if len(w) > 3 and w not in _stopwords}

    if words_a and words_b:
        overlap = len(words_a & words_b)
        if overlap >= 3:
            score += 2
        elif overlap >= 1:
            score += 1

    return score


def _find_clusters(alerts, scores):
    """Group correlated alerts into clusters using union-find.

    Args:
        alerts: list of alert dicts
        scores: dict mapping (i, j) index pairs to relatedness scores

    Returns:
        list of clusters, where each cluster is a list of alert dicts
    """
    n = len(alerts)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Union alerts that are correlated
    for (i, j), score in scores.items():
        if score >= CORRELATION_THRESHOLD:
            union(i, j)

    # Group by root
    groups = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)

    # Return clusters with 2+ alerts
    clusters = []
    for indices in groups.values():
        if len(indices) >= 2:
            clusters.append([alerts[i] for i in indices])

    return clusters


def correlate_alerts(alerts):
    """Find clusters of related alerts from a pipeline run.

    Args:
        alerts: list of alert dicts from the current pipeline run

    Returns:
        list of clusters (each cluster is a list of related alert dicts)
    """
    if len(alerts) < 2:
        return []

    # Compute pairwise relatedness
    scores = {}
    for i in range(len(alerts)):
        for j in range(i + 1, len(alerts)):
            score = _compute_relatedness(alerts[i], alerts[j])
            if score > 0:
                scores[(i, j)] = score

    # Find connected clusters
    clusters = _find_clusters(alerts, scores)

    return clusters


def generate_situation_report(cluster, engine=None, df_news=None, df_social=None):
    """Generate a unified situation report for a cluster of correlated alerts.

    Args:
        cluster: list of related alert dicts
        engine: SQLAlchemy engine (optional, for historical context)
        df_news: news DataFrame (optional)
        df_social: social DataFrame (optional)

    Returns:
        A special alert dict with alert_type="situation_report"
    """
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Build context from correlated alerts
    alert_summaries = []
    alert_types = set()
    brands = set()
    for i, alert in enumerate(cluster, 1):
        alert_types.add(alert.get("alert_type", "unknown"))
        if alert.get("brand"):
            brands.add(alert["brand"])

        alert_summaries.append(
            f"{i}. [{alert.get('severity', 'info').upper()}] "
            f"{alert.get('alert_type', 'unknown')}: {alert.get('title', 'Untitled')}\n"
            f"   Summary: {alert.get('summary', 'No summary')}"
        )

    context = (
        f"CORRELATED ALERTS ({len(cluster)} signals detected simultaneously):\n\n"
        + "\n\n".join(alert_summaries)
    )

    if brands:
        context += f"\n\nBrands involved: {', '.join(brands)}"
    context += f"\nAlert types: {', '.join(alert_types)}"

    prompt = f"""You are a senior intelligence analyst. Multiple alert signals have fired simultaneously
in our monitoring system. Your job is to determine HOW these signals are connected and what the
unified situation means strategically.

{context}

Analyze these correlated signals and produce a SITUATION REPORT:

1. CONNECTION: How are these signals related? What is the common thread or causal chain?
2. UNIFIED ASSESSMENT: What is the overall situation when you connect these dots?
3. SEVERITY: Is the combined situation more serious than any individual alert suggests?
4. STRATEGIC IMPLICATION: What does this mean for decision-makers?
5. RECOMMENDED ACTION: What should be done NOW given the full picture?

Be direct and specific. Connect the dots between signals — that's the entire point.
Target 200-400 words."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1000,
            system=(
                "You are a senior intelligence analyst specializing in connecting "
                "disparate signals into unified situational awareness. You focus on "
                "causal chains, compound risks, and actionable synthesis."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        investigation = response.content[0].text
    except Exception as e:
        investigation = f"Situation report generation failed: {e}"

    # Build the situation report alert
    title_parts = []
    for alert in cluster[:3]:
        alert_type = alert.get("alert_type", "").replace("_", " ").title()
        title_parts.append(alert_type)
    title = "Situation Report: " + " + ".join(title_parts)
    if len(cluster) > 3:
        title += f" (+{len(cluster) - 3} more)"

    summary_parts = [
        f"{len(cluster)} correlated signals detected:",
    ]
    for alert in cluster:
        summary_parts.append(
            f"- [{alert.get('severity', 'info')}] {alert.get('title', 'Untitled')}"
        )

    # Store correlated alert details in data
    correlated_data = {
        "correlated_alerts": [
            {
                "alert_type": a.get("alert_type"),
                "severity": a.get("severity"),
                "title": a.get("title"),
                "brand": a.get("brand"),
                "summary": a.get("summary", "")[:200],
            }
            for a in cluster
        ],
        "alert_types": list(alert_types),
        "brands": list(brands),
    }

    return {
        "alert_type": "situation_report",
        "severity": "critical",
        "title": title,
        "summary": "\n".join(summary_parts),
        "investigation": investigation,
        "data": json.dumps(correlated_data),
        "brand": ", ".join(brands) if brands else None,
        "username": cluster[0].get("username"),
    }
