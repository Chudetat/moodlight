#!/usr/bin/env python
"""
generate_special_edition.py
Generates a special edition of The Mood Report on any topic.

Usage:
  python generate_special_edition.py --topic "The Creative Industry" --context-file notes.txt
  python generate_special_edition.py --topic "Fashion Week" --context "Key points here..."
  python generate_special_edition.py --topic "AI Arms Race" --skip-email --skip-beehiiv

Pulls economic backdrop from DB, searches for topic-relevant articles,
and combines with user-provided context to generate a one-off newsletter.
"""

import argparse
import json
import os
import re
import sys
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import quote

import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Reuse from existing modules
from generate_mood_report import _get_engine, _quickchart_url
from mood_report_publisher import markdown_to_newsletter_html, publish_to_beehiiv


# ---------------------------------------------------------------------------
# Known DB topic categories (from fetch_news_rss.py TOPIC_KEYWORDS)
# ---------------------------------------------------------------------------

KNOWN_TOPICS = [
    "politics", "government", "economics", "education", "culture & identity",
    "branding & advertising", "creative & design", "technology & ai",
    "climate & environment", "healthcare & wellbeing", "immigration",
    "crime & safety", "war & foreign policy", "media & journalism",
    "race & ethnicity", "gender & sexuality", "business & corporate",
    "labor & work", "housing", "religion & values", "sports", "entertainment",
]


# ---------------------------------------------------------------------------
# 1. Topic Resolution
# ---------------------------------------------------------------------------

def _resolve_topic_filters(topic_str):
    """Map a user topic string to DB topic categories and search keywords."""
    topic_lower = topic_str.lower()

    # Direct match against known DB categories
    matching_categories = [
        t for t in KNOWN_TOPICS
        if t in topic_lower or topic_lower in t
    ]

    # Generate search keywords via Claude Haiku
    keywords = _generate_topic_keywords(topic_str)

    return matching_categories, keywords


def _generate_topic_keywords(topic_str):
    """Use Claude Haiku to generate search keywords for a topic."""
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"Generate 5-8 specific search keywords or short phrases for "
                    f"finding news articles about: {topic_str}\n"
                    f"Return ONLY the keywords, one per line. No numbering, no explanation."
                ),
            }],
        )
        return [kw.strip() for kw in response.content[0].text.strip().split("\n")
                if kw.strip()]
    except Exception as e:
        print(f"  Keyword generation failed: {e}")
        # Fallback: split topic into words
        return [w for w in topic_str.split() if len(w) > 3]


# ---------------------------------------------------------------------------
# 2. Data Loading
# ---------------------------------------------------------------------------

def load_special_edition_data(engine, topic, lookback_days=7):
    """Load economic backdrop + topic-specific data."""
    from sqlalchemy import text as sql_text

    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    data = {}

    # --- Economic backdrop (always loaded) ---

    # Markets
    try:
        markets = pd.read_sql(
            sql_text("""
                SELECT symbol, price, change, change_percent, latest_trading_day, timestamp
                FROM markets
                WHERE symbol IN ('SPY', 'QQQ', 'DIA')
                ORDER BY timestamp DESC
            """),
            engine,
        )
        data["markets"] = markets.groupby("symbol").first().reset_index()
    except Exception as e:
        print(f"  Could not load markets: {e}")
        data["markets"] = pd.DataFrame()

    # Commodities
    try:
        commodities = pd.read_sql(
            sql_text("""
                SELECT scope_name, metric_name, metric_value, snapshot_date
                FROM metric_snapshots
                WHERE scope = 'commodity'
                  AND metric_name = 'price'
                  AND snapshot_date >= :cutoff
                ORDER BY snapshot_date DESC
            """),
            engine,
            params={"cutoff": cutoff_30d},
        )
        if not commodities.empty:
            commodities["snapshot_date"] = pd.to_datetime(
                commodities["snapshot_date"]
            ).dt.tz_localize(None)
            latest = commodities.groupby("scope_name").first().reset_index()
            cutoff_7d_dt = pd.Timestamp(now.replace(tzinfo=None) - timedelta(days=7))
            week_ago = commodities[commodities["snapshot_date"] <= cutoff_7d_dt]
            if not week_ago.empty:
                prev = week_ago.groupby("scope_name").first().reset_index()
                latest = latest.merge(
                    prev[["scope_name", "metric_value"]],
                    on="scope_name", how="left", suffixes=("", "_7d_ago"),
                )
            data["commodities"] = latest
        else:
            data["commodities"] = pd.DataFrame()
    except Exception as e:
        print(f"  Could not load commodities: {e}")
        data["commodities"] = pd.DataFrame()

    # Economic indicators
    try:
        econ = pd.read_sql(
            sql_text("""
                SELECT metric_name, metric_value, snapshot_date
                FROM metric_snapshots
                WHERE scope = 'economic'
                ORDER BY snapshot_date DESC
            """),
            engine,
        )
        if not econ.empty:
            data["economic_indicators"] = econ.groupby("metric_name").first().reset_index()
        else:
            data["economic_indicators"] = pd.DataFrame()
    except Exception as e:
        print(f"  Could not load economic indicators: {e}")
        data["economic_indicators"] = pd.DataFrame()

    # Signal track record
    try:
        signal_log = pd.read_sql(
            sql_text("""
                SELECT alert_type,
                       COUNT(*) AS total_signals,
                       COUNT(spy_change_1d) AS has_1d,
                       AVG(spy_change_1d) AS avg_spy_1d,
                       SUM(CASE WHEN spy_change_1d > 0 THEN 1 ELSE 0 END)::float
                           / NULLIF(COUNT(spy_change_1d), 0) AS up_rate_1d
                FROM signal_log
                GROUP BY alert_type
                ORDER BY total_signals DESC
            """),
            engine,
        )
        data["signal_track_record"] = signal_log
    except Exception as e:
        print(f"  Could not load signal track record: {e}")
        data["signal_track_record"] = pd.DataFrame()

    # --- Topic-specific data (best-effort) ---

    print(f"  Resolving topic filters for: {topic}")
    matching_categories, keywords = _resolve_topic_filters(topic)
    print(f"  Matching categories: {matching_categories}")
    print(f"  Search keywords: {keywords}")

    # Build WHERE clause for topic matching
    topic_conditions = []
    topic_params = {"cutoff": cutoff}

    for i, cat in enumerate(matching_categories):
        key = f"cat_{i}"
        topic_conditions.append(f"topic = :{key}")
        topic_params[key] = cat

    for i, kw in enumerate(keywords):
        key = f"kw_{i}"
        topic_conditions.append(f"text ILIKE :{key}")
        topic_params[key] = f"%{kw}%"

    if not topic_conditions:
        print("  No topic filters resolved. Topic-specific data will be empty.")
        data["topic_news_sentiment"] = pd.DataFrame()
        data["topic_social_sentiment"] = pd.DataFrame()
        data["topic_headlines"] = pd.DataFrame()
        data["topic_emotions"] = pd.DataFrame()
        data["topic_alerts"] = pd.DataFrame()
        return data

    topic_where = f"({' OR '.join(topic_conditions)})"

    # Topic news sentiment
    try:
        topic_news = pd.read_sql(
            sql_text(f"""
                SELECT created_at::date AS day,
                       AVG(empathy_score) AS avg_empathy,
                       AVG(intensity) AS avg_intensity,
                       COUNT(*) AS article_count
                FROM news_scored
                WHERE {topic_where}
                  AND created_at >= :cutoff
                GROUP BY created_at::date
                ORDER BY day
            """),
            engine,
            params=topic_params,
        )
        data["topic_news_sentiment"] = topic_news
        print(f"  Topic news sentiment: {len(topic_news)} days")
    except Exception as e:
        print(f"  Could not load topic news sentiment: {e}")
        data["topic_news_sentiment"] = pd.DataFrame()

    # Topic social sentiment
    try:
        topic_social = pd.read_sql(
            sql_text(f"""
                SELECT created_at::date AS day,
                       AVG(empathy_score) AS avg_empathy,
                       AVG(intensity) AS avg_intensity,
                       COUNT(*) AS post_count
                FROM social_scored
                WHERE {topic_where}
                  AND created_at >= :cutoff
                GROUP BY created_at::date
                ORDER BY day
            """),
            engine,
            params=topic_params,
        )
        data["topic_social_sentiment"] = topic_social
        print(f"  Topic social sentiment: {len(topic_social)} days")
    except Exception as e:
        print(f"  Could not load topic social sentiment: {e}")
        data["topic_social_sentiment"] = pd.DataFrame()

    # Topic headlines
    try:
        topic_headlines = pd.read_sql(
            sql_text(f"""
                SELECT text, intensity, empathy_score, emotion_top_1, country, created_at
                FROM news_scored
                WHERE {topic_where}
                  AND created_at >= :cutoff
                ORDER BY intensity DESC
                LIMIT 15
            """),
            engine,
            params=topic_params,
        )
        data["topic_headlines"] = topic_headlines
        print(f"  Topic headlines: {len(topic_headlines)}")
    except Exception as e:
        print(f"  Could not load topic headlines: {e}")
        data["topic_headlines"] = pd.DataFrame()

    # Topic emotions
    try:
        topic_emotions = pd.read_sql(
            sql_text(f"""
                SELECT emotion_top_1, COUNT(*) AS cnt
                FROM news_scored
                WHERE {topic_where}
                  AND created_at >= :cutoff
                  AND emotion_top_1 IS NOT NULL
                GROUP BY emotion_top_1
                ORDER BY cnt DESC
                LIMIT 10
            """),
            engine,
            params=topic_params,
        )
        data["topic_emotions"] = topic_emotions
        print(f"  Topic emotions: {len(topic_emotions)} categories")
    except Exception as e:
        print(f"  Could not load topic emotions: {e}")
        data["topic_emotions"] = pd.DataFrame()

    # Topic alerts
    try:
        alert_conditions = []
        alert_params = {"cutoff": cutoff}
        for i, cat in enumerate(matching_categories):
            key = f"acat_{i}"
            alert_conditions.append(f"topic ILIKE :{key}")
            alert_params[key] = f"%{cat}%"
        for i, kw in enumerate(keywords[:5]):
            key = f"akw_{i}"
            alert_conditions.append(f"title ILIKE :{key}")
            alert_params[key] = f"%{kw}%"

        if alert_conditions:
            alert_where = f"({' OR '.join(alert_conditions)})"
            topic_alerts = pd.read_sql(
                sql_text(f"""
                    SELECT alert_type, severity, title, summary, brand, topic, timestamp
                    FROM alerts
                    WHERE {alert_where}
                      AND timestamp >= :cutoff
                    ORDER BY timestamp DESC
                    LIMIT 15
                """),
                engine,
                params=alert_params,
            )
            data["topic_alerts"] = topic_alerts
            print(f"  Topic alerts: {len(topic_alerts)}")
        else:
            data["topic_alerts"] = pd.DataFrame()
    except Exception as e:
        print(f"  Could not load topic alerts: {e}")
        data["topic_alerts"] = pd.DataFrame()

    return data


# ---------------------------------------------------------------------------
# 3. Context Building
# ---------------------------------------------------------------------------

def build_special_edition_context(topic, data, user_context=""):
    """Format all data into a structured text block for Claude."""
    now = datetime.now(timezone.utc)
    sections = []

    sections.append(f"THE MOOD REPORT: SPECIAL EDITION — {topic}")
    sections.append(f"Generated: {now.strftime('%B %d, %Y at %H:%M UTC')}")
    sections.append("=" * 50)

    # User-provided context (primary source)
    if user_context:
        sections.append(
            "USER-PROVIDED CONTEXT AND NOTES:\n"
            "=================================\n"
            f"{user_context}\n"
            "=================================\n"
            "This is the primary editorial source material. Build the newsletter around this."
        )

    # Topic news sentiment
    tns = data.get("topic_news_sentiment", pd.DataFrame())
    if not tns.empty:
        lines = [f"TOPIC SENTIMENT TREND — {topic.upper()} (news):"]
        for _, row in tns.iterrows():
            lines.append(
                f"  {row['day']}: empathy={row['avg_empathy']:.4f}, "
                f"intensity={row['avg_intensity']:.2f}, articles={row['article_count']}"
            )
        sections.append("\n".join(lines))

    # Topic social sentiment
    tss = data.get("topic_social_sentiment", pd.DataFrame())
    if not tss.empty:
        lines = [f"TOPIC SENTIMENT TREND — {topic.upper()} (social):"]
        for _, row in tss.iterrows():
            lines.append(
                f"  {row['day']}: empathy={row['avg_empathy']:.4f}, "
                f"intensity={row['avg_intensity']:.2f}, posts={row['post_count']}"
            )
        sections.append("\n".join(lines))

    # Topic headlines
    hdl = data.get("topic_headlines", pd.DataFrame())
    if not hdl.empty:
        lines = [f"TOP HEADLINES — {topic.upper()} (by intensity):"]
        for _, row in hdl.iterrows():
            ts = (pd.Timestamp(row["created_at"]).strftime("%m/%d")
                  if pd.notna(row.get("created_at")) else "?")
            lines.append(
                f"  [{ts}] (intensity: {row['intensity']}, empathy: {row['empathy_score']:.4f}) "
                f"{str(row['text'])[:250]}"
            )
        sections.append("\n".join(lines))

    # Topic emotions
    emo = data.get("topic_emotions", pd.DataFrame())
    if not emo.empty:
        lines = [f"DOMINANT EMOTIONS — {topic.upper()} COVERAGE:"]
        total = emo["cnt"].sum()
        for _, row in emo.iterrows():
            pct = (row["cnt"] / total) * 100
            lines.append(f"  {row['emotion_top_1']}: {row['cnt']} ({pct:.0f}%)")
        sections.append("\n".join(lines))

    # Topic alerts
    alerts = data.get("topic_alerts", pd.DataFrame())
    if not alerts.empty:
        lines = [f"INTELLIGENCE ALERTS — {topic.upper()}:"]
        for _, row in alerts.iterrows():
            sev = (row.get("severity") or "info").upper()
            scope = ""
            if row.get("brand"):
                scope = f" [{row['brand']}]"
            elif row.get("topic"):
                scope = f" [{row['topic']}]"
            lines.append(f"  [{sev}]{scope} {row['title']}")
            if row.get("summary"):
                lines.append(f"    {str(row['summary'])[:200]}")
        sections.append("\n".join(lines))

    # Economic backdrop
    sections.append("=" * 50)
    sections.append("ECONOMIC BACKDROP")

    # Markets
    mkt = data.get("markets", pd.DataFrame())
    if not mkt.empty:
        lines = ["MARKET DATA:"]
        for _, row in mkt.iterrows():
            chg = row.get("change", 0) or 0
            pct = row.get("change_percent", "0%")
            lines.append(f"  {row['symbol']}: ${row['price']:.2f} ({chg:+.2f}, {pct})")
        sections.append("\n".join(lines))

    # Commodities
    comm = data.get("commodities", pd.DataFrame())
    if not comm.empty:
        lines = ["COMMODITY PRICES:"]
        for _, row in comm.iterrows():
            delta_str = ""
            if "metric_value_7d_ago" in row and pd.notna(row.get("metric_value_7d_ago")):
                delta = row["metric_value"] - row["metric_value_7d_ago"]
                pct = (delta / row["metric_value_7d_ago"]) * 100
                delta_str = f" (7d: {delta:+.2f}, {pct:+.1f}%)"
            lines.append(f"  {row['scope_name']}: ${row['metric_value']:.2f}{delta_str}")
        sections.append("\n".join(lines))

    # Economic indicators
    econ = data.get("economic_indicators", pd.DataFrame())
    if not econ.empty:
        lines = ["ECONOMIC INDICATORS:"]
        for _, row in econ.iterrows():
            lines.append(
                f"  {row['metric_name']}: {row['metric_value']:.2f} "
                f"(as of {row['snapshot_date']})"
            )
        sections.append("\n".join(lines))

    # Signal track record
    sig = data.get("signal_track_record", pd.DataFrame())
    if not sig.empty:
        lines = ["SIGNAL TRACK RECORD (all-time):"]
        for _, row in sig.iterrows():
            up_rate = (f"{row['up_rate_1d']*100:.0f}%"
                       if pd.notna(row.get("up_rate_1d")) else "N/A")
            avg_1d = (f"{row['avg_spy_1d']:+.2f}%"
                      if pd.notna(row.get("avg_spy_1d")) else "N/A")
            lines.append(
                f"  {row['alert_type']}: {int(row['total_signals'])} signals, "
                f"1d outcomes: {int(row['has_1d'])} filled, "
                f"SPY up rate: {up_rate}, avg 1d move: {avg_1d}"
            )
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# 4. Chart Building
# ---------------------------------------------------------------------------

def build_special_edition_charts(data, topic):
    """Build QuickChart.io URLs for special edition visuals."""
    charts = {}

    # 1. Topic sentiment trend (line chart) — only if data exists
    tns = data.get("topic_news_sentiment", pd.DataFrame())
    tss = data.get("topic_social_sentiment", pd.DataFrame())
    if not tns.empty or not tss.empty:
        all_days = set()
        if not tns.empty:
            all_days.update(str(d) for d in tns["day"])
        if not tss.empty:
            all_days.update(str(d) for d in tss["day"])
        labels = sorted(all_days)

        formatted_labels = []
        for d in labels:
            try:
                formatted_labels.append(pd.Timestamp(d).strftime("%b %d"))
            except Exception:
                formatted_labels.append(d)

        datasets = []
        if not tns.empty:
            news_map = {str(r["day"]): round(float(r["avg_empathy"]), 4)
                        for _, r in tns.iterrows()}
            datasets.append({
                "label": "News",
                "data": [news_map.get(d) for d in labels],
                "borderColor": "#1976D2",
                "backgroundColor": "rgba(25,118,210,0.1)",
                "fill": True,
                "lineTension": 0.3,
                "pointRadius": 4,
            })
        if not tss.empty:
            social_map = {str(r["day"]): round(float(r["avg_empathy"]), 4)
                          for _, r in tss.iterrows()}
            datasets.append({
                "label": "Social",
                "data": [social_map.get(d) for d in labels],
                "borderColor": "#E65100",
                "backgroundColor": "rgba(230,81,0,0.1)",
                "fill": True,
                "lineTension": 0.3,
                "pointRadius": 4,
            })

        if datasets:
            short_topic = topic if len(topic) <= 30 else topic[:27] + "..."
            config = {
                "type": "line",
                "data": {"labels": formatted_labels, "datasets": datasets},
                "options": {
                    "title": {"display": True,
                              "text": f"{short_topic} — Sentiment Trend",
                              "fontSize": 14},
                    "legend": {"position": "bottom"},
                    "scales": {
                        "yAxes": [{"scaleLabel": {"display": True,
                                                  "labelString": "Empathy Score"}}],
                    },
                },
            }
            charts["topic_sentiment"] = _quickchart_url(config)

    # 2. Topic emotion distribution (doughnut) — only if 2+ emotions
    emo = data.get("topic_emotions", pd.DataFrame())
    if not emo.empty and len(emo) >= 2:
        emotion_labels = [str(e) for e in emo["emotion_top_1"]]
        counts = [int(c) for c in emo["cnt"]]
        palette = ["#1976D2", "#E65100", "#7B1FA2", "#00897B", "#2E7D32",
                   "#C62828", "#F57F17", "#1565C0", "#AD1457", "#4E342E"]
        bg_colors = [palette[i % len(palette)] for i in range(len(emotion_labels))]

        config = {
            "type": "doughnut",
            "data": {
                "labels": emotion_labels,
                "datasets": [{"data": counts, "backgroundColor": bg_colors}],
            },
            "options": {
                "title": {"display": True, "text": "Emotion Distribution",
                          "fontSize": 16},
                "legend": {"position": "right"},
            },
        }
        charts["topic_emotions"] = _quickchart_url(config, width=540, height=300)

    # 3. Market performance (horizontal bar) — always
    mkt = data.get("markets", pd.DataFrame())
    if not mkt.empty:
        symbols = []
        changes = []
        colors = []
        for _, row in mkt.iterrows():
            pct_str = str(row.get("change_percent", "0%")).replace("%", "")
            try:
                pct = float(pct_str)
            except (ValueError, TypeError):
                pct = 0.0
            symbols.append(str(row["symbol"]))
            changes.append(round(pct, 2))
            colors.append("#2E7D32" if pct >= 0 else "#DC143C")

        config = {
            "type": "horizontalBar",
            "data": {
                "labels": symbols,
                "datasets": [{"data": changes, "backgroundColor": colors}],
            },
            "options": {
                "title": {"display": True, "text": "Market Performance (%)",
                          "fontSize": 16},
                "legend": {"display": False},
                "scales": {
                    "xAxes": [{"ticks": {"beginAtZero": True}}],
                },
            },
        }
        charts["market_performance"] = _quickchart_url(config)

    # 4. Commodity changes (horizontal bar) — always
    comm = data.get("commodities", pd.DataFrame())
    if not comm.empty and "metric_value_7d_ago" in comm.columns:
        comm_with_delta = comm.dropna(subset=["metric_value_7d_ago"])
        if not comm_with_delta.empty:
            c_labels = []
            c_changes = []
            c_colors = []
            for _, row in comm_with_delta.iterrows():
                prev = float(row["metric_value_7d_ago"])
                if prev != 0:
                    pct = ((float(row["metric_value"]) - prev) / prev) * 100
                    c_labels.append(str(row["scope_name"]))
                    c_changes.append(round(pct, 2))
                    c_colors.append("#2E7D32" if pct >= 0 else "#DC143C")

            if c_labels:
                config = {
                    "type": "horizontalBar",
                    "data": {
                        "labels": c_labels,
                        "datasets": [{"data": c_changes,
                                      "backgroundColor": c_colors}],
                    },
                    "options": {
                        "title": {"display": True,
                                  "text": "Commodity 7d Change (%)",
                                  "fontSize": 16},
                        "legend": {"display": False},
                        "scales": {
                            "xAxes": [{"ticks": {"beginAtZero": True}}],
                        },
                    },
                }
                charts["commodity_changes"] = _quickchart_url(config)

    return charts


# ---------------------------------------------------------------------------
# 5. Chart Insertion
# ---------------------------------------------------------------------------

def insert_special_edition_charts(html, chart_urls):
    """Insert chart images into special edition HTML.

    Maps charts to section names used by the special edition prompt.
    Falls back to inserting before the <hr> footer if sections aren't found.
    """
    if not chart_urls:
        return html

    # Chart key → target section, processed in reverse for position stability.
    # For charts sharing a section, bottom-first so reversed inserts top one last.
    chart_placements = [
        ("commodity_changes", "MARKET BACKDROP"),
        ("market_performance", "MARKET BACKDROP"),
        ("topic_emotions", "MOOD CHECK"),
        ("topic_sentiment", "MOOD CHECK"),
    ]

    img_style = "max-width: 100%; height: auto; border-radius: 8px; margin: 15px 0;"

    for chart_key, section_name in reversed(chart_placements):
        url = chart_urls.get(chart_key)
        if not url:
            continue

        # Find the section badge span
        pattern = re.escape(f">{section_name}</span>")
        match = re.search(pattern, html, re.IGNORECASE)

        img_tag = (
            f'<div style="text-align: center; margin: 15px 0;">'
            f'<img src="{url}" '
            f'alt="{chart_key.replace("_", " ").title()}" '
            f'style="{img_style}" />'
            f'</div>'
        )

        if match:
            # Find the next section div after this one
            rest_start = match.end()
            next_section = re.search(
                r'<div style="margin: 25px 0 10px 0;">',
                html[rest_start:],
            )
            if next_section:
                insert_pos = rest_start + next_section.start()
            else:
                hr_match = re.search(r"<hr ", html[rest_start:])
                if hr_match:
                    insert_pos = rest_start + hr_match.start()
                else:
                    insert_pos = len(html)
        else:
            # Section not found — insert before footer <hr>
            hr_match = re.search(r"<hr ", html)
            if hr_match:
                insert_pos = hr_match.start()
            else:
                insert_pos = len(html)

        html = html[:insert_pos] + img_tag + html[insert_pos:]

    return html


# ---------------------------------------------------------------------------
# 6. Newsletter Generation
# ---------------------------------------------------------------------------

SPECIAL_EDITION_SYSTEM_PROMPT = """You are the editor of The Mood Report — a data intelligence newsletter that measures sentiment before the markets price it in.

This is a SPECIAL EDITION focused on: {topic}

Your voice: Authoritative but accessible. Data-first. You don't predict — you measure. You let the numbers speak and point out what they're saying. Think Bloomberg Terminal meets morning coffee.

RULES:
1. Every claim must be grounded in the data provided — either the user-provided context or the DB data. No training data. No made-up statistics.
2. Use the user-provided context as primary source material when available. Build the narrative around it.
3. Connect topic-specific sentiment to the economic backdrop when meaningful.
4. Keep it under 1,200 words. Dense, not padded.
5. Empathy scores: 0.04 = cold/hostile, 0.10 = detached/neutral, 0.30 = warm, 0.30+ = highly empathetic.
6. If topic-specific DB data is sparse, lean heavily on user-provided context. Be transparent about data availability.

OUTPUT FORMAT — use this structure with markdown. You may adapt section headers to fit the topic:

# THE MOOD REPORT: SPECIAL EDITION
*{topic} — [Full date]*

## THE BOTTOM LINE
[One paragraph. What the mood data says about {topic} right now.]

## THE LANDSCAPE
[Overview of {topic} — what's happening, grounded in data and context provided. 2-3 paragraphs.]

## MOOD CHECK
[If topic-specific sentiment data exists: a table or summary of empathy/intensity trends.
If not: skip this section entirely. Do NOT fabricate data.]

## MARKET BACKDROP
[1-2 paragraphs connecting economic/market data to {topic}. How does the broader economic mood affect this space?]

## WHAT TO WATCH
[2-3 things to monitor. Not predictions — things the data says are worth watching. Ground each in a specific data point or trend.]

## THE MOVE
[2-3 concrete, specific actions that a professional in this space could take THIS WEEK based on the data. Not generic advice — tie each move directly to a signal or finding from the data above. Think: "The data says X, so the smart play is Y." Be bold but grounded.]

---
*The Mood Report: Special Edition is powered by Moodlight Intelligence. Data is measured, not predicted.*
"""

SPECIAL_EDITION_X_PROMPT = """Condense this special edition newsletter into a 3-4 tweet thread (280 chars each).
Tweet 1: "THE MOOD REPORT: SPECIAL EDITION | {topic}" + the single most striking data point or insight.
Tweet 2: One key finding or observation.
Tweet 3: Forward look or market connection.
Tweet 4: "Full issue → [link]"
No hashtags. No emojis. Data speaks for itself.

Output each tweet on its own line, separated by a blank line. Number them 1/, 2/, etc."""


def generate_special_edition_newsletter(context, topic):
    """Generate the special edition newsletter body via Claude Opus."""
    system = SPECIAL_EDITION_SYSTEM_PROMPT.format(topic=topic)
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        system=system,
        messages=[{
            "role": "user",
            "content": (
                f"Generate a special edition of The Mood Report focused on: {topic}\n\n"
                f"Use this data and context:\n\n{context}"
            ),
        }],
    )
    return response.content[0].text


def generate_special_edition_x_thread(context, newsletter_md, topic):
    """Generate a condensed X/Twitter thread from the special edition."""
    system = SPECIAL_EDITION_X_PROMPT.format(topic=topic)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=system,
        messages=[{
            "role": "user",
            "content": (
                f"Here is today's special edition newsletter:\n\n{newsletter_md}\n\n"
                f"And the raw data context:\n\n{context}\n\n"
                f"Generate the X thread."
            ),
        }],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# 7. Publishing
# ---------------------------------------------------------------------------

def save_special_edition_x_thread(thread_text, topic):
    """Save X thread to file."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    safe_topic = re.sub(r'[^a-zA-Z0-9]+', '_', topic.lower()).strip('_')
    filename = f"mood_report_special_{safe_topic}_{date_str}.txt"
    with open(filename, "w") as f:
        f.write(thread_text)
    print(f"  X thread saved to: {filename}")
    return filename


def email_special_edition(newsletter_md, x_thread, chart_urls, topic):
    """Email the special edition for review."""
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    recipient = os.getenv("EMAIL_RECIPIENT", "")

    if not all([sender, password, recipient]):
        print("  Email credentials not configured. Skipping email.")
        return False

    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # Build HTML from newsletter markdown
    newsletter_html = markdown_to_newsletter_html(newsletter_md)
    if chart_urls:
        newsletter_html = insert_special_edition_charts(newsletter_html, chart_urls)

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
        <div style="background: #1a1a2e; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
          <h1 style="margin: 0; font-size: 24px;">The Mood Report: Special Edition</h1>
          <p style="margin: 5px 0 0 0; color: #aaa;">{topic} — Draft for Review — {date_str}</p>
        </div>

        <div style="border: 1px solid #eee; padding: 20px; border-radius: 0 0 8px 8px;">
          {newsletter_html}
        </div>

        <div style="margin-top: 30px; padding: 20px; background: #f0f4f8; border-radius: 8px;">
          <h3 style="margin-top: 0; color: #333;">X Thread (copy-paste to post):</h3>
          <pre style="white-space: pre-wrap; font-family: monospace; font-size: 13px; color: #444;">{x_thread}</pre>
        </div>

        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">
          This is a draft. Review and publish on Beehiiv when ready.<br>
          Moodlight Intelligence Platform
        </p>
      </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Mood Report] Special Edition: {topic} — {date_str}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"  Report emailed to {recipient}")
        return True
    except Exception as e:
        print(f"  Email failed: {e}")
        return False


# ---------------------------------------------------------------------------
# 8. Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a Mood Report Special Edition on any topic."
    )
    parser.add_argument("--topic", required=True,
                        help="Theme/topic for this edition")
    parser.add_argument("--context-file",
                        help="Path to text file with editorial context/notes")
    parser.add_argument("--context",
                        help="Inline context string")
    parser.add_argument("--lookback-days", type=int, default=7,
                        help="Days of DB data to include (default: 7)")
    parser.add_argument("--skip-email", action="store_true",
                        help="Skip sending email")
    parser.add_argument("--skip-beehiiv", action="store_true",
                        help="Skip Beehiiv draft creation")
    args = parser.parse_args()

    print("=" * 60)
    print(f"THE MOOD REPORT: SPECIAL EDITION — {args.topic}")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # 1. Load user context
    user_context = ""
    if args.context_file:
        with open(args.context_file) as f:
            user_context = f.read()
        print(f"\n[1/7] Loaded context from: {args.context_file} ({len(user_context)} chars)")
    elif args.context:
        user_context = args.context
        print(f"\n[1/7] Inline context: {len(user_context)} chars")
    else:
        print("\n[1/7] No user context provided. Using DB data only.")

    # 2. Connect to DB
    engine = _get_engine()

    # 3. Load data
    print("[2/7] Loading data...")
    data = load_special_edition_data(engine, args.topic, args.lookback_days)

    # Check we have something to work with
    has_db_data = any(
        not df.empty for df in data.values() if isinstance(df, pd.DataFrame)
    )
    if not has_db_data and not user_context:
        print("No data and no context provided. Cannot generate report.")
        return

    # 4. Build context
    print("[3/7] Building context...")
    context = build_special_edition_context(args.topic, data, user_context)
    print(f"  Context length: {len(context)} chars")

    # 5. Build charts
    print("[4/7] Building chart URLs...")
    chart_urls = build_special_edition_charts(data, args.topic)
    print(f"  Charts generated: {list(chart_urls.keys()) if chart_urls else 'none'}")

    # 6. Generate newsletter
    print("[5/7] Generating newsletter via Claude Opus...")
    newsletter_md = generate_special_edition_newsletter(context, args.topic)
    print(f"  Newsletter length: {len(newsletter_md)} chars")

    # 7. Generate X thread
    print("[6/7] Generating X thread...")
    x_thread = generate_special_edition_x_thread(context, newsletter_md, args.topic)
    print(f"  Thread length: {len(x_thread)} chars")

    # 8. Publish
    print("[7/7] Publishing...")

    # Beehiiv
    if not args.skip_beehiiv:
        beehiiv_api_key = os.getenv("BEEHIIV_API_KEY")
        if beehiiv_api_key:
            try:
                date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
                html = markdown_to_newsletter_html(newsletter_md)
                if chart_urls:
                    html = insert_special_edition_charts(html, chart_urls)
                publish_to_beehiiv(
                    html=html,
                    title=f"The Mood Report: Special Edition — {args.topic}",
                    subtitle=f"Special coverage: {args.topic}",
                )
            except Exception as e:
                print(f"  Beehiiv publish failed: {e}")
        else:
            print("  Beehiiv not configured. Skipping.")
    else:
        print("  Skipping Beehiiv (--skip-beehiiv).")

    # Save X thread
    save_special_edition_x_thread(x_thread, args.topic)

    # Email
    if not args.skip_email:
        email_special_edition(newsletter_md, x_thread, chart_urls, args.topic)
    else:
        print("  Skipping email (--skip-email).")

    # Print to stdout
    print("\n" + "=" * 60)
    print("GENERATED NEWSLETTER:")
    print("=" * 60)
    print(newsletter_md)
    print("\n" + "=" * 60)
    print("X THREAD:")
    print("=" * 60)
    print(x_thread)

    print("\nDone.")


if __name__ == "__main__":
    main()
