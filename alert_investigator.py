#!/usr/bin/env python
"""
AI-powered investigation module for Moodlight alerts.
Uses Claude to analyze anomalies and provide actionable intelligence.
"""

import os
import json
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


def investigate_alert(alert, df_news=None, df_social=None, df_markets=None):
    """
    Investigate an anomaly using Claude AI.

    Returns dict with {analysis, implications, watch_items} or None on failure.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set — skipping investigation")
        return None

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
    except Exception as e:
        print(f"  Could not initialize Anthropic client: {e}")
        return None

    context = _build_context(alert, df_news, df_social, df_markets)
    prompt = _build_prompt(alert, context)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        return _parse_investigation(text)
    except Exception as e:
        print(f"  Investigation API call failed: {e}")
        return None


def _build_context(alert, df_news, df_social, df_markets):
    """Gather supporting data for the investigation prompt."""
    parts = []
    alert_data = alert.get("data", "{}")
    if isinstance(alert_data, str):
        try:
            alert_data = json.loads(alert_data)
        except (json.JSONDecodeError, TypeError):
            alert_data = {}

    brand = alert.get("brand")

    # Recent headlines
    if df_news is not None and not df_news.empty:
        sample = df_news
        if brand:
            brand_lower = brand.lower()
            for col in ["title", "text"]:
                if col in sample.columns:
                    mask = sample[col].str.contains(brand_lower, case=False, na=False)
                    filtered = sample[mask]
                    if not filtered.empty:
                        sample = filtered
                        break
        if "title" in sample.columns:
            headlines = sample["title"].dropna().head(10).tolist()
            parts.append(f"Recent headlines:\n" + "\n".join(f"- {h}" for h in headlines))

    # Social posts
    if df_social is not None and not df_social.empty:
        sample = df_social
        if brand:
            brand_lower = brand.lower()
            for col in ["text", "title"]:
                if col in sample.columns:
                    mask = sample[col].str.contains(brand_lower, case=False, na=False)
                    filtered = sample[mask]
                    if not filtered.empty:
                        sample = filtered
                        break
        if "text" in sample.columns:
            posts = sample["text"].dropna().head(5).tolist()
            parts.append(f"Recent social posts:\n" + "\n".join(f"- {p[:200]}" for p in posts))

    # Market data
    if df_markets is not None and not df_markets.empty:
        if "market_sentiment" in df_markets.columns:
            avg_sentiment = df_markets["market_sentiment"].mean()
            parts.append(f"Current market sentiment: {avg_sentiment:.2f} (0=bearish, 1=bullish)")

    return "\n\n".join(parts) if parts else "No additional context available."


def _build_prompt(alert, context):
    """Build the investigation prompt for Claude."""
    brand_note = ""
    if alert.get("brand"):
        brand_note = f" This alert is specific to the brand: {alert['brand']}."

    return f"""You are Moodlight's intelligence analyst. An anomaly was detected that requires investigation.{brand_note}

ALERT:
- Type: {alert.get('alert_type', 'unknown')}
- Severity: {alert.get('severity', 'unknown')}
- Title: {alert.get('title', 'No title')}
- Summary: {alert.get('summary', 'No summary')}

SUPPORTING DATA:
{context}

Provide a concise investigation in exactly this format:

ANALYSIS: [2-3 sentences on what's happening and why]

IMPLICATIONS: [2-3 sentences on why this matters and what it means for strategy]

WATCH: [2-3 bullet points of what to monitor next]"""


def _parse_investigation(text):
    """Parse the structured investigation response."""
    result = {"analysis": "", "implications": "", "watch_items": ""}

    sections = {"ANALYSIS:": "analysis", "IMPLICATIONS:": "implications", "WATCH:": "watch_items"}
    current_key = None

    for line in text.split("\n"):
        stripped = line.strip()
        for marker, key in sections.items():
            if stripped.upper().startswith(marker):
                current_key = key
                content = stripped[len(marker):].strip()
                if content:
                    result[current_key] = content
                break
        else:
            if current_key and stripped:
                if result[current_key]:
                    result[current_key] += "\n" + stripped
                else:
                    result[current_key] = stripped

    return result
