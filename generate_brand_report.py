#!/usr/bin/env python
"""
generate_brand_report.py
Generates a polished one-page brand intelligence report for sales outreach.

Use case: Find companies hiring for "Brand Intelligence" roles on LinkedIn,
generate a Moodlight report on their brand, and send it as proof of value.

Usage:
    python generate_brand_report.py --brand "Nike"
    python generate_brand_report.py --brand "Nike" --ticker NKE
    python generate_brand_report.py --brand "Nike" --ticker NKE --days 14
    python generate_brand_report.py --brand "Nike" --skip-email
    python generate_brand_report.py --brand "Nike" --email vp@company.com
"""

import argparse
import json
import os
import re
import smtplib
import tempfile
from datetime import datetime, timezone, timedelta
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from urllib.parse import quote

import pandas as pd
import requests
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Reuse from existing modules
from generate_mood_report import _get_engine, _quickchart_url
from mood_report_publisher import markdown_to_newsletter_html
from vlds_helper import calculate_brand_vlds
from competitor_discovery import ensure_competitors_cached
from competitive_analyzer import compute_competitive_snapshot, generate_competitive_insight


# ---------------------------------------------------------------------------
# 1. Data Loading
# ---------------------------------------------------------------------------

def _fetch_live_quote(ticker):
    """Fetch a live stock quote from AlphaVantage GLOBAL_QUOTE.

    Returns a dict with price, change, change_percent, latest_trading_day
    or None on failure.
    """
    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not api_key:
        print("    ALPHAVANTAGE_API_KEY not set — skipping live quote")
        return None
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": ticker,
                "apikey": api_key,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"    AlphaVantage HTTP {resp.status_code}")
            return None
        data = resp.json()
        gq = data.get("Global Quote", {})
        if not gq or not gq.get("05. price"):
            msg = data.get("Note") or data.get("Information") or "No quote data"
            print(f"    AlphaVantage: {msg}")
            return None
        quote = {
            "ticker": ticker,
            "price": float(gq["05. price"]),
            "change": float(gq["09. change"]),
            "change_percent": gq["10. change percent"],
            "latest_trading_day": gq["07. latest trading day"],
            "previous_close": float(gq["08. previous close"]),
        }
        print(f"    {ticker}: ${quote['price']:.2f} ({quote['change']:+.2f}, {quote['change_percent']})")
        return quote
    except Exception as e:
        print(f"    Live quote failed: {e}")
        return None


def _filter_by_brand(df, brand_name):
    """Filter a dataframe to rows mentioning a brand in title or text."""
    if df.empty:
        return pd.DataFrame()
    brand_lower = brand_name.lower()
    mask = pd.Series(False, index=df.index)
    for col in ["title", "text", "source"]:
        if col in df.columns:
            mask = mask | df[col].str.contains(
                brand_lower, case=False, na=False, regex=False
            )
    return df[mask]


def load_brand_data(engine, brand_name, ticker=None, lookback_days=7):
    """Load all data needed for a brand intelligence report."""
    from sqlalchemy import text as sql_text

    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d %H:%M:%S")
    data = {"brand": brand_name, "ticker": ticker, "lookback_days": lookback_days}

    # --- Load news + social, filter by brand ---
    print("  Loading news_scored...")
    try:
        df_news = pd.read_sql(
            sql_text("""
                SELECT text, intensity, empathy_score, emotion_top_1, source,
                       topic, country, created_at
                FROM news_scored
                WHERE created_at >= :cutoff
                ORDER BY intensity DESC
            """),
            engine,
            params={"cutoff": cutoff},
        )
        df_news["created_at"] = pd.to_datetime(df_news["created_at"], utc=True)
    except Exception as e:
        print(f"    Failed: {e}")
        df_news = pd.DataFrame()

    print("  Loading social_scored...")
    try:
        df_social = pd.read_sql(
            sql_text("""
                SELECT text, intensity, empathy_score, emotion_top_1, source,
                       topic, created_at
                FROM social_scored
                WHERE created_at >= :cutoff
                ORDER BY intensity DESC
            """),
            engine,
            params={"cutoff": cutoff},
        )
        df_social["created_at"] = pd.to_datetime(df_social["created_at"], utc=True)
    except Exception as e:
        print(f"    Failed: {e}")
        df_social = pd.DataFrame()

    # Preserve unfiltered DataFrames for competitive analysis
    data["df_news_all"] = df_news
    data["df_social_all"] = df_social

    # Filter by brand
    news_brand = _filter_by_brand(df_news, brand_name)
    social_brand = _filter_by_brand(df_social, brand_name)
    brand_df = pd.concat([news_brand, social_brand], ignore_index=True)

    data["brand_df"] = brand_df
    data["news_count"] = len(news_brand)
    data["social_count"] = len(social_brand)
    data["total_mentions"] = len(brand_df)
    print(f"    {brand_name}: {len(news_brand)} news + {len(social_brand)} social = {len(brand_df)} total")

    if brand_df.empty:
        print(f"  WARNING: No mentions found for '{brand_name}' in last {lookback_days} days.")
        data["vlds"] = None
        data["top_headlines"] = pd.DataFrame()
        data["emotions"] = pd.Series(dtype="int64")
        data["empathy_trend"] = pd.Series(dtype="float64")
        data["daily_mentions"] = pd.Series(dtype="int64")
        data["alerts"] = pd.DataFrame()
        data["stock_data"] = pd.DataFrame()
        data["markets"] = pd.DataFrame()
        data["competitors"] = []
        data["competitive_snapshot"] = None
        data["competitive_insight"] = None
        return data

    # --- VLDS ---
    print("  Computing VLDS...")
    vlds = calculate_brand_vlds(brand_df)
    data["vlds"] = vlds
    if vlds:
        print(f"    V={vlds.get('velocity', 'N/A')} L={vlds.get('longevity', 'N/A')} "
              f"D={vlds.get('density', 'N/A')} S={vlds.get('scarcity', 'N/A')}")

    # --- Top 10 headlines by intensity ---
    if "intensity" in brand_df.columns:
        data["top_headlines"] = brand_df.nlargest(10, "intensity")
    else:
        data["top_headlines"] = pd.DataFrame()

    # --- Emotion distribution (top 5) ---
    if "emotion_top_1" in brand_df.columns:
        data["emotions"] = brand_df["emotion_top_1"].value_counts().head(5)
    else:
        data["emotions"] = pd.Series(dtype="int64")

    # --- Daily empathy trend ---
    if "created_at" in brand_df.columns and "empathy_score" in brand_df.columns:
        brand_copy = brand_df.copy()
        brand_copy["date"] = brand_copy["created_at"].dt.date
        data["empathy_trend"] = brand_copy.groupby("date")["empathy_score"].mean()
    else:
        data["empathy_trend"] = pd.Series(dtype="float64")

    # --- Daily mention volume ---
    if "created_at" in brand_df.columns:
        brand_copy = brand_df.copy()
        brand_copy["date"] = brand_copy["created_at"].dt.date
        data["daily_mentions"] = brand_copy.groupby("date").size()
    else:
        data["daily_mentions"] = pd.Series(dtype="int64")

    # --- Recent alerts ---
    try:
        alerts = pd.read_sql(
            sql_text("""
                SELECT alert_type, severity, title, summary, timestamp
                FROM alerts
                WHERE (brand ILIKE :brand OR title ILIKE :brand_pct)
                  AND timestamp >= :cutoff
                ORDER BY timestamp DESC
                LIMIT 10
            """),
            engine,
            params={
                "brand": brand_name,
                "brand_pct": f"%{brand_name}%",
                "cutoff": cutoff,
            },
        )
        data["alerts"] = alerts
        print(f"    {len(alerts)} alerts found")
    except Exception as e:
        print(f"    Alerts query failed: {e}")
        data["alerts"] = pd.DataFrame()

    # --- Stock data (if ticker provided) ---
    if ticker:
        # Try DB first (watchlisted brands have historical data)
        stock = pd.DataFrame()
        try:
            stock = pd.read_sql(
                sql_text("""
                    SELECT scope_name, metric_name, metric_value, snapshot_date
                    FROM metric_snapshots
                    WHERE scope = 'brand_stock'
                      AND scope_name = :ticker
                      AND snapshot_date >= :cutoff
                    ORDER BY snapshot_date DESC
                    LIMIT 20
                """),
                engine,
                params={"ticker": ticker, "cutoff": cutoff},
            )
        except Exception:
            pass

        if not stock.empty:
            data["stock_data"] = stock
            print(f"    {len(stock)} stock data points for {ticker} (from DB)")
        else:
            # Fetch live from AlphaVantage GLOBAL_QUOTE
            print(f"    No DB stock data for {ticker} — fetching live from AlphaVantage...")
            data["stock_data"] = pd.DataFrame()
            data["stock_live"] = _fetch_live_quote(ticker)
    else:
        data["stock_data"] = pd.DataFrame()

    # --- Market backdrop (SPY, QQQ, DIA) ---
    try:
        markets = pd.read_sql(
            sql_text("""
                SELECT symbol, price, change, change_percent, latest_trading_day
                FROM markets
                WHERE symbol IN ('SPY', 'QQQ', 'DIA')
                ORDER BY timestamp DESC
            """),
            engine,
        )
        data["markets"] = markets.groupby("symbol").first().reset_index()
    except Exception as e:
        print(f"    Markets query failed: {e}")
        data["markets"] = pd.DataFrame()

    # --- Competitive analysis ---
    print("  Loading competitive data...")
    try:
        competitors = ensure_competitors_cached(engine, brand_name)
        data["competitors"] = competitors
        if competitors:
            print(f"    {len(competitors)} competitors: {[c['competitor_name'] for c in competitors]}")
            snapshot = compute_competitive_snapshot(
                df_news, df_social, brand_name, competitors
            )
            data["competitive_snapshot"] = snapshot
            print(f"    SOV: {snapshot.get('share_of_voice', {})}")

            insight = generate_competitive_insight(engine, snapshot, brand_name)
            data["competitive_insight"] = insight
            if insight:
                print(f"    Competitive insight: {insight[:80]}...")
        else:
            print("    No competitors found — skipping competitive analysis")
            data["competitive_snapshot"] = None
            data["competitive_insight"] = None
    except Exception as e:
        print(f"    Competitive analysis failed: {e}")
        data["competitors"] = []
        data["competitive_snapshot"] = None
        data["competitive_insight"] = None

    return data


# ---------------------------------------------------------------------------
# 2. Context String
# ---------------------------------------------------------------------------

def build_report_context(brand, data):
    """Format all data into a structured text block for Claude."""
    now = datetime.now(timezone.utc)
    lookback = data["lookback_days"]
    start_date = (now - timedelta(days=lookback)).strftime("%B %d")
    end_date = now.strftime("%B %d, %Y")
    sections = []

    sections.append(f"BRAND INTELLIGENCE REPORT — {brand.upper()}")
    sections.append(f"Period: {start_date} – {end_date} ({lookback} days)")
    sections.append(f"Generated: {now.strftime('%B %d, %Y at %H:%M UTC')}")
    sections.append("=" * 50)

    # Mention stats
    sections.append(
        f"COVERAGE VOLUME:\n"
        f"  Total mentions: {data['total_mentions']}\n"
        f"  News articles: {data['news_count']}\n"
        f"  Social posts: {data['social_count']}"
    )

    # VLDS scores
    vlds = data.get("vlds")
    if vlds:
        lines = ["VLDS CULTURAL POSITION SCORES:"]
        lines.append(f"  Velocity: {vlds.get('velocity', 'N/A')} — {vlds.get('velocity_label', '')} ({vlds.get('velocity_insight', '')})")
        lines.append(f"  Longevity: {vlds.get('longevity', 'N/A')} — {vlds.get('longevity_label', '')} ({vlds.get('longevity_insight', '')})")
        lines.append(f"  Density: {vlds.get('density', 'N/A')} — {vlds.get('density_label', '')} ({vlds.get('density_insight', '')})")
        lines.append(f"  Scarcity: {vlds.get('scarcity', 'N/A')} — {vlds.get('scarcity_label', '')} ")
        if vlds.get("empathy_score") is not None:
            lines.append(f"  Avg Empathy: {vlds['empathy_score']:.4f} ({vlds.get('empathy_label', '')})")
        if vlds.get("source_count"):
            lines.append(f"  Source diversity: {vlds.get('source_diversity', 'N/A')} ({vlds['source_count']} unique sources)")
        sections.append("\n".join(lines))

    # Daily mention volume
    daily = data.get("daily_mentions", pd.Series(dtype="int64"))
    if not daily.empty:
        lines = ["DAILY MENTION VOLUME:"]
        for date, count in daily.items():
            lines.append(f"  {date}: {count}")
        sections.append("\n".join(lines))

    # Empathy trend
    emp = data.get("empathy_trend", pd.Series(dtype="float64"))
    if not emp.empty:
        lines = ["DAILY EMPATHY TREND:"]
        for date, score in emp.items():
            lines.append(f"  {date}: {score:.4f}")
        sections.append("\n".join(lines))

    # Emotions
    emotions = data.get("emotions", pd.Series(dtype="int64"))
    if not emotions.empty:
        lines = ["EMOTION DISTRIBUTION:"]
        total = emotions.sum()
        for emotion, count in emotions.items():
            pct = (count / total) * 100
            lines.append(f"  {emotion}: {count} ({pct:.0f}%)")
        sections.append("\n".join(lines))

    # Top headlines
    hdl = data.get("top_headlines", pd.DataFrame())
    if not hdl.empty:
        lines = ["TOP HEADLINES BY INTENSITY:"]
        for _, row in hdl.head(10).iterrows():
            ts = (pd.Timestamp(row["created_at"]).strftime("%m/%d")
                  if pd.notna(row.get("created_at")) else "?")
            lines.append(
                f"  [{ts}] (intensity: {row.get('intensity', 'N/A'):.2f}, "
                f"empathy: {row.get('empathy_score', 0):.4f}) "
                f"{str(row['text'])[:250]}"
            )
        sections.append("\n".join(lines))

    # Alerts
    alerts = data.get("alerts", pd.DataFrame())
    if not alerts.empty:
        lines = ["RECENT INTELLIGENCE ALERTS:"]
        for _, row in alerts.iterrows():
            sev = (row.get("severity") or "info").upper()
            lines.append(f"  [{sev}] {row['title']}")
            if row.get("summary"):
                lines.append(f"    {str(row['summary'])[:200]}")
        sections.append("\n".join(lines))

    # Stock data (DB historical or live quote)
    stock = data.get("stock_data", pd.DataFrame())
    ticker = data.get("ticker")
    stock_live = data.get("stock_live")
    if ticker and not stock.empty:
        lines = [f"STOCK DATA — {ticker}:"]
        for _, row in stock.iterrows():
            lines.append(f"  {row['snapshot_date']}: {row['metric_name']} = {row['metric_value']}")
        sections.append("\n".join(lines))
    elif ticker and stock_live:
        q = stock_live
        lines = [f"STOCK DATA — {ticker} (live quote):"]
        lines.append(f"  Price: ${q['price']:.2f}")
        lines.append(f"  Change: {q['change']:+.2f} ({q['change_percent']})")
        lines.append(f"  Previous close: ${q['previous_close']:.2f}")
        lines.append(f"  Latest trading day: {q['latest_trading_day']}")
        sections.append("\n".join(lines))

    # Market backdrop
    mkt = data.get("markets", pd.DataFrame())
    if not mkt.empty:
        lines = ["MARKET BACKDROP:"]
        for _, row in mkt.iterrows():
            chg = row.get("change", 0) or 0
            pct = row.get("change_percent", "0%")
            lines.append(f"  {row['symbol']}: ${row['price']:.2f} ({chg:+.2f}, {pct})")
        sections.append("\n".join(lines))

    # Competitive positioning
    snapshot = data.get("competitive_snapshot")
    if snapshot:
        competitors = data.get("competitors", [])
        sov = snapshot.get("share_of_voice", {})
        gaps = snapshot.get("competitive_gaps", {})

        lines = ["COMPETITIVE POSITIONING:"]

        # Competitor names
        comp_names = [c["competitor_name"] for c in competitors]
        lines.append(f"  Competitors analyzed: {', '.join(comp_names)}")

        # Share of voice table
        lines.append("  Share of Voice:")
        for name, pct in sov.items():
            marker = " (target)" if name == brand else ""
            lines.append(f"    {name}: {pct}%{marker}")

        # VLDS comparison
        lines.append("  VLDS Comparison:")
        for name, bdata in snapshot.items():
            if name in ("share_of_voice", "competitive_gaps"):
                continue
            v = bdata.get("vlds") or {}
            if v:
                lines.append(
                    f"    {name}: V={v.get('velocity', 'N/A')} "
                    f"L={v.get('longevity', 'N/A')} "
                    f"D={v.get('density', 'N/A')} "
                    f"S={v.get('scarcity', 'N/A')} "
                    f"({bdata.get('mention_count', 0)} mentions)"
                )
            else:
                lines.append(f"    {name}: insufficient data ({bdata.get('mention_count', 0)} mentions)")

        # Competitive gaps
        if gaps:
            lines.append("  Competitive Gaps (brand minus competitor avg):")
            for metric in ["velocity", "longevity", "density", "scarcity"]:
                gap_val = gaps.get(f"{metric}_gap")
                if gap_val is not None:
                    direction = "leads by" if gap_val > 0 else "trails by"
                    lines.append(f"    {metric.title()}: {direction} {abs(gap_val):.3f}")

        # AI insight
        insight = data.get("competitive_insight")
        if insight:
            lines.append(f"  AI Competitive Insight: {insight}")

        sections.append("\n".join(lines))

    # Market correlation (only if ticker provided)
    ticker = data.get("ticker")
    if ticker:
        lines = ["MARKET CORRELATION:"]

        # Stock performance
        stock = data.get("stock_data", pd.DataFrame())
        stock_live = data.get("stock_live")
        stock_direction = None
        if not stock.empty:
            price_rows = stock[stock["metric_name"] == "close"] if "metric_name" in stock.columns else stock
            if len(price_rows) >= 2:
                latest = float(price_rows.iloc[0]["metric_value"])
                earliest = float(price_rows.iloc[-1]["metric_value"])
                stock_direction = "UP" if latest > earliest else "DOWN"
                lines.append(f"  Stock trend ({ticker}): {stock_direction} (${earliest:.2f} -> ${latest:.2f})")
        elif stock_live:
            stock_direction = "UP" if stock_live["change"] > 0 else "DOWN"
            lines.append(f"  Stock ({ticker}): ${stock_live['price']:.2f} ({stock_live['change']:+.2f}, {stock_live['change_percent']})")

        # Market backdrop summary
        mkt = data.get("markets", pd.DataFrame())
        if not mkt.empty:
            lines.append("  Market backdrop:")
            for _, row in mkt.iterrows():
                chg = row.get("change", 0) or 0
                pct = row.get("change_percent", "0%")
                lines.append(f"    {row['symbol']}: ${row['price']:.2f} ({chg:+.2f}, {pct})")

        # Sentiment-market alignment
        emp = data.get("empathy_trend", pd.Series(dtype="float64"))
        if not emp.empty and len(emp) >= 2 and stock_direction:
            emp_direction = "UP" if emp.iloc[-1] > emp.iloc[0] else "DOWN"
            alignment = "CONVERGING" if emp_direction == stock_direction else "DIVERGING"
            lines.append(f"  Sentiment trend: {emp_direction} (empathy {emp.iloc[0]:.4f} -> {emp.iloc[-1]:.4f})")
            lines.append(f"  Sentiment-Market Alignment: {alignment}")
            if alignment == "DIVERGING":
                lines.append(f"    Sentiment is {emp_direction} while stock is {stock_direction} — potential signal for correction or emerging narrative shift.")
            else:
                lines.append(f"    Sentiment and market are aligned ({emp_direction}) — narrative is reinforcing market movement.")

        if len(lines) > 1:
            sections.append("\n".join(lines))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# 3. Charts (QuickChart.io)
# ---------------------------------------------------------------------------

def build_report_charts(brand, data):
    """Build QuickChart.io URLs for the brand report."""
    charts = {}

    # 1. VLDS Gauge — horizontal bar showing V/L/D/S scores
    vlds = data.get("vlds")
    if vlds:
        metrics = ["Scarcity", "Density", "Longevity", "Velocity"]
        scores = [
            round(vlds.get("scarcity", 0) * 100, 1),
            round(vlds.get("density", 0) * 100, 1),
            round(vlds.get("longevity", 0) * 100, 1),
            round(vlds.get("velocity", 0) * 100, 1),
        ]
        colors = ["#00897B", "#7B1FA2", "#E65100", "#1976D2"]

        config = {
            "type": "horizontalBar",
            "data": {
                "labels": metrics,
                "datasets": [{
                    "data": scores,
                    "backgroundColor": colors,
                }],
            },
            "options": {
                "title": {"display": True, "text": f"{brand} — VLDS Cultural Position",
                          "fontSize": 16},
                "legend": {"display": False},
                "scales": {
                    "xAxes": [{"ticks": {"beginAtZero": True, "max": 100},
                               "scaleLabel": {"display": True, "labelString": "Score (%)"}}],
                },
            },
        }
        charts["vlds_gauge"] = _quickchart_url(config)

    # 2. Mention Trend — line chart of daily mention count
    daily = data.get("daily_mentions", pd.Series(dtype="int64"))
    if not daily.empty and len(daily) >= 2:
        labels = [pd.Timestamp(str(d)).strftime("%b %d") for d in daily.index]
        values = [int(v) for v in daily.values]

        config = {
            "type": "line",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": "Mentions",
                    "data": values,
                    "borderColor": "#1976D2",
                    "backgroundColor": "rgba(25,118,210,0.1)",
                    "fill": True,
                    "lineTension": 0.3,
                    "pointRadius": 4,
                }],
            },
            "options": {
                "title": {"display": True, "text": f"{brand} — Daily Mention Volume",
                          "fontSize": 16},
                "legend": {"display": False},
                "scales": {
                    "yAxes": [{"ticks": {"beginAtZero": True},
                               "scaleLabel": {"display": True, "labelString": "Mentions"}}],
                },
            },
        }
        charts["mention_trend"] = _quickchart_url(config)

    # 3. Emotion Distribution — doughnut chart
    emotions = data.get("emotions", pd.Series(dtype="int64"))
    if not emotions.empty and len(emotions) >= 2:
        emotion_labels = [str(e) for e in emotions.index]
        counts = [int(c) for c in emotions.values]
        palette = ["#1976D2", "#E65100", "#7B1FA2", "#00897B", "#2E7D32"]
        bg_colors = [palette[i % len(palette)] for i in range(len(emotion_labels))]

        config = {
            "type": "doughnut",
            "data": {
                "labels": emotion_labels,
                "datasets": [{"data": counts, "backgroundColor": bg_colors}],
            },
            "options": {
                "title": {"display": True, "text": f"{brand} — Emotion Distribution",
                          "fontSize": 16},
                "legend": {"position": "right"},
            },
        }
        charts["emotion_distribution"] = _quickchart_url(config, width=540, height=300)

    # 4. Empathy Trend — line chart of daily avg empathy
    emp = data.get("empathy_trend", pd.Series(dtype="float64"))
    if not emp.empty and len(emp) >= 2:
        labels = [pd.Timestamp(str(d)).strftime("%b %d") for d in emp.index]
        values = [round(float(v), 4) for v in emp.values]

        config = {
            "type": "line",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": "Empathy",
                    "data": values,
                    "borderColor": "#E65100",
                    "backgroundColor": "rgba(230,81,0,0.1)",
                    "fill": True,
                    "lineTension": 0.3,
                    "pointRadius": 4,
                }],
            },
            "options": {
                "title": {"display": True, "text": f"{brand} — Empathy Trend",
                          "fontSize": 16},
                "legend": {"display": False},
                "scales": {
                    "yAxes": [{"scaleLabel": {"display": True, "labelString": "Empathy Score"}}],
                },
            },
        }
        charts["empathy_trend"] = _quickchart_url(config)

    # 5. SOV Doughnut — share of voice per brand (only if competitive data exists)
    snapshot = data.get("competitive_snapshot")
    if snapshot:
        sov = snapshot.get("share_of_voice", {})
        if sov and len(sov) >= 2:
            sov_labels = list(sov.keys())
            sov_values = list(sov.values())
            palette = ["#1976D2", "#E65100", "#7B1FA2", "#00897B", "#2E7D32", "#F57C00"]
            bg_colors = [palette[i % len(palette)] for i in range(len(sov_labels))]

            config = {
                "type": "doughnut",
                "data": {
                    "labels": sov_labels,
                    "datasets": [{"data": sov_values, "backgroundColor": bg_colors}],
                },
                "options": {
                    "title": {"display": True, "text": f"{brand} — Share of Voice",
                              "fontSize": 16},
                    "legend": {"position": "right"},
                },
            }
            charts["sov_doughnut"] = _quickchart_url(config, width=540, height=300)

        # 6. VLDS Comparison Bar — grouped bar for brand + competitors
        vlds_brands = []
        for name, bdata in snapshot.items():
            if name in ("share_of_voice", "competitive_gaps"):
                continue
            if isinstance(bdata, dict) and bdata.get("vlds"):
                vlds_brands.append((name, bdata["vlds"]))

        if len(vlds_brands) >= 2:
            labels = [b[0] for b in vlds_brands]
            v_scores = [round(b[1].get("velocity", 0) * 100, 1) for b in vlds_brands]
            l_scores = [round(b[1].get("longevity", 0) * 100, 1) for b in vlds_brands]
            d_scores = [round(b[1].get("density", 0) * 100, 1) for b in vlds_brands]
            s_scores = [round(b[1].get("scarcity", 0) * 100, 1) for b in vlds_brands]

            config = {
                "type": "bar",
                "data": {
                    "labels": labels,
                    "datasets": [
                        {"label": "Velocity", "data": v_scores, "backgroundColor": "#1976D2"},
                        {"label": "Longevity", "data": l_scores, "backgroundColor": "#E65100"},
                        {"label": "Density", "data": d_scores, "backgroundColor": "#7B1FA2"},
                        {"label": "Scarcity", "data": s_scores, "backgroundColor": "#00897B"},
                    ],
                },
                "options": {
                    "title": {"display": True, "text": f"{brand} vs Competitors — VLDS Comparison",
                              "fontSize": 16},
                    "scales": {
                        "yAxes": [{"ticks": {"beginAtZero": True, "max": 100},
                                   "scaleLabel": {"display": True, "labelString": "Score (%)"}}],
                    },
                },
            }
            charts["vlds_comparison"] = _quickchart_url(config, width=600, height=350)

    return charts


# ---------------------------------------------------------------------------
# 4. Report Generation (Claude Opus)
# ---------------------------------------------------------------------------

REPORT_SYSTEM_PROMPT = """You are a brand intelligence analyst at Moodlight Intelligence.
Generate a concise, professional brand intelligence report for sales outreach.
This report will be sent to a VP of Marketing or similar executive at the brand's company.
It should demonstrate the depth of insight Moodlight provides.

RULES:
1. Every claim must be grounded in the data provided. No training data.
2. Be concise — this is a 1-2 page brief. Dense and high-signal.
3. The VLDS table must use exact scores from the data.
4. Empathy scores: 0.04 = cold/hostile, 0.10 = detached/neutral, 0.30 = warm, 0.30+ = highly empathetic.
5. Frame insights as actionable strategic intelligence, not academic analysis.
6. The tone should make the reader think "I need this data every week."
7. Only include sections for which data is provided. If no competitive or market data exists, omit those sections entirely.

OUTPUT FORMAT — use this exact structure with markdown:

# [BRAND] — Cultural Intelligence Brief
*[Date range] | Powered by Moodlight Intelligence*

## EXECUTIVE SUMMARY
[3-4 sentences: what's happening with this brand right now, the key signal, and why it matters. Lead with the most surprising or actionable finding.]

## CULTURAL POSITION
| Metric | Score | Reading |
|--------|-------|---------|
| Velocity | X% | [one-word label] |
| Longevity | X% | [one-word label] |
| Density | X% | [one-word label] |
| Scarcity | X% | [one-word label] |

[2-3 sentences interpreting what the VLDS scores mean for this brand's strategic position]

## CONVERSATION ANALYSIS
- **[Mention count]** mentions across **[N]** days ([news count] news, [social count] social)
- **Dominant emotions:** [top 3 with %]
- **Empathy score:** [value] ([label])
- **Key insight:** [one sentence connecting the data to brand perception]

## KEY HEADLINES
[Top 5 headlines with dates — format as bullet list]

## COMPETITIVE POSITIONING
[Only if competitive data is provided]
- **Share of voice:** [brand]% vs [competitor breakdown]
- **VLDS comparison:** Where the brand leads and trails vs competitors
- **Competitive gaps:** [highlight the largest gap, positive or negative]
- **Strategic read:** [2-3 sentences on competitive positioning — what the SOV and VLDS gaps mean strategically]

## MARKET CORRELATION
[Only if stock/market data is provided]
- **Stock performance:** [ticker] at $[price] ([change])
- **Market backdrop:** [SPY/QQQ/DIA summary]
- **Sentiment-market alignment:** [CONVERGING or DIVERGING] — [1-2 sentences explaining what this means: if diverging, is sentiment leading or lagging? If converging, is the narrative reinforcing or exhausted?]

## STRATEGIC IMPLICATIONS
[3 bullet points: specific, actionable insights that demonstrate the value of continuous monitoring. Each should answer "so what?" for a brand strategist. Integrate competitive and market insights if available.]

---
*This report was generated by Moodlight Intelligence — real-time cultural and competitive monitoring powered by AI, tracking 80,000+ articles and social posts weekly.*
*A full-time brand intelligence analyst costs $85,000-$120,000/year. Moodlight delivers deeper, faster insights at a fraction of the cost.*
*Interested? Contact daniel@moodlightintel.com*
"""


def generate_report(context, brand):
    """Generate the brand intelligence report via Claude Opus."""
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3000,
        system=REPORT_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Generate a brand intelligence report for {brand} "
                f"using this data:\n\n{context}"
            ),
        }],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# 5. PDF Generation
# ---------------------------------------------------------------------------

def _download_chart_image(url):
    """Download a QuickChart image to a temp file. Returns path or None."""
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.write(resp.content)
            tmp.close()
            return tmp.name
    except Exception as e:
        print(f"    Chart download failed: {e}")
    return None


def _sanitize_for_pdf(text):
    """Replace unicode characters that fpdf2 Helvetica (latin-1) can't render."""
    replacements = {
        "\u2014": "--",   # em dash
        "\u2013": "-",    # en dash
        "\u2018": "'",    # left single quote
        "\u2019": "'",    # right single quote
        "\u201c": '"',    # left double quote
        "\u201d": '"',    # right double quote
        "\u2026": "...",  # ellipsis
        "\u2022": "-",    # bullet
        "\u2192": "->",   # right arrow
        "\u2190": "<-",   # left arrow
        "\u2191": "^",    # up arrow
        "\u2193": "v",    # down arrow
        "\u00b7": "-",    # middle dot
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    # Fallback: strip any remaining non-latin-1 characters
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_pdf(report_md, charts, brand, lookback_days):
    """Generate a branded PDF from the report markdown + charts."""
    from pdf_export import MoodlightPDF, _render_markdown_to_pdf

    pdf = MoodlightPDF(title=f"Cultural Intelligence Brief: {brand}")
    pdf.alias_nb_pages()
    pdf.add_page()

    # Sanitize unicode for Helvetica (latin-1 only)
    safe_md = _sanitize_for_pdf(report_md)

    # Render markdown content
    _render_markdown_to_pdf(pdf, safe_md)

    # Add charts on a new page
    chart_images = []
    if charts:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(107, 70, 193)
        pdf.cell(0, 10, "Visual Intelligence", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        chart_order = ["vlds_gauge", "mention_trend", "emotion_distribution", "empathy_trend", "sov_doughnut", "vlds_comparison"]
        for key in chart_order:
            url = charts.get(key)
            if not url:
                continue
            img_path = _download_chart_image(url)
            if img_path:
                chart_images.append(img_path)
                try:
                    # Check if we need a page break (leave room for image)
                    if pdf.get_y() > 200:
                        pdf.add_page()
                    pdf.image(img_path, x=15, w=180)
                    pdf.ln(8)
                except Exception as e:
                    print(f"    Failed to embed chart {key}: {e}")

    # Output PDF
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    safe_brand = re.sub(r'[^\w\-]', '_', brand)
    filename = f"brand_report_{safe_brand}_{date_str}.pdf"
    pdf.output(filename)

    # Cleanup temp chart images
    for path in chart_images:
        try:
            os.unlink(path)
        except OSError:
            pass

    return filename


# ---------------------------------------------------------------------------
# 6. Email
# ---------------------------------------------------------------------------

def _insert_report_charts(html, chart_urls):
    """Insert chart images into report HTML after relevant sections."""
    if not chart_urls:
        return html

    chart_placements = [
        ("vlds_gauge", "CULTURAL POSITION"),
        ("emotion_distribution", "CONVERSATION ANALYSIS"),
        ("mention_trend", "EXECUTIVE SUMMARY"),
        ("empathy_trend", "CONVERSATION ANALYSIS"),
        ("sov_doughnut", "COMPETITIVE POSITIONING"),
        ("vlds_comparison", "COMPETITIVE POSITIONING"),
    ]

    img_style = "max-width: 100%; height: auto; border-radius: 8px; margin: 15px 0;"

    for chart_key, section_name in reversed(chart_placements):
        url = chart_urls.get(chart_key)
        if not url:
            continue

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
            hr_match = re.search(r"<hr ", html)
            if hr_match:
                insert_pos = hr_match.start()
            else:
                insert_pos = len(html)

        html = html[:insert_pos] + img_tag + html[insert_pos:]

    return html


def email_report(pdf_path, report_md, chart_urls, brand, recipient=None):
    """Email the report with HTML body + PDF attachment."""
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    if not recipient:
        recipient = os.getenv("EMAIL_RECIPIENT", "")

    if not all([sender, password, recipient]):
        print("  Email credentials not configured. Skipping email.")
        return False

    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # Build HTML from report markdown
    report_html = markdown_to_newsletter_html(report_md)
    if chart_urls:
        report_html = _insert_report_charts(report_html, chart_urls)

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
        <div style="background: #1a1a2e; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
          <h1 style="margin: 0; font-size: 24px;">Moodlight Intelligence</h1>
          <p style="margin: 5px 0 0 0; color: #aaa;">Cultural Intelligence Brief — {brand} — {date_str}</p>
        </div>

        <div style="border: 1px solid #eee; padding: 20px; border-radius: 0 0 8px 8px;">
          {report_html}
        </div>

        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">
          PDF version attached. Forward to the prospect or use as a leave-behind.<br>
          Moodlight Intelligence Platform
        </p>
      </body>
    </html>
    """

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"{brand} Cultural Intelligence Brief — Moodlight"
    msg["From"] = sender
    msg["To"] = recipient

    # HTML body
    html_part = MIMEMultipart("alternative")
    html_part.attach(MIMEText(html_body, "html"))
    msg.attach(html_part)

    # PDF attachment
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            pdf_part = MIMEBase("application", "pdf")
            pdf_part.set_payload(f.read())
            encoders.encode_base64(pdf_part)
            pdf_part.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(pdf_path)}",
            )
            msg.attach(pdf_part)

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
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a brand intelligence report for sales outreach."
    )
    parser.add_argument("--brand", required=True, help="Brand name to analyze")
    parser.add_argument("--ticker", default=None, help="Stock ticker (e.g. NKE)")
    parser.add_argument("--days", type=int, default=7, help="Lookback period in days (default: 7)")
    parser.add_argument("--skip-email", action="store_true", help="Skip emailing the report")
    parser.add_argument("--email", default=None, help="Custom email recipient")
    args = parser.parse_args()

    brand = args.brand
    ticker = args.ticker
    lookback_days = args.days

    print("=" * 60)
    print(f"BRAND INTELLIGENCE REPORT — {brand.upper()}")
    print(f"Ticker: {ticker or 'N/A'}  |  Lookback: {lookback_days}d")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # 1. Connect
    engine = _get_engine()

    # 2. Load data
    print("\n[1/5] Loading brand data...")
    data = load_brand_data(engine, brand, ticker, lookback_days)

    if data["total_mentions"] == 0:
        print(f"\nNo data found for '{brand}'. Try a different brand name or longer lookback.")
        return

    # Log competitive analysis status
    competitors = data.get("competitors", [])
    snapshot = data.get("competitive_snapshot")
    if competitors:
        print(f"  Competitive: {len(competitors)} competitors, snapshot={'yes' if snapshot else 'no'}, insight={'yes' if data.get('competitive_insight') else 'no'}")
    else:
        print("  Competitive: no competitors found")

    # 3. Build context + charts
    print("\n[2/5] Building context...")
    context = build_report_context(brand, data)
    print(f"  Context: {len(context)} chars")

    print("  Building charts...")
    charts = build_report_charts(brand, data)
    print(f"  Charts: {list(charts.keys()) if charts else 'none'}")

    # 4. Generate report
    print("\n[3/5] Generating report via Claude Opus...")
    report_md = generate_report(context, brand)
    print(f"  Report: {len(report_md)} chars")

    # 5. Generate PDF
    print("\n[4/5] Generating PDF...")
    pdf_path = generate_pdf(report_md, charts, brand, lookback_days)
    print(f"  PDF saved: {pdf_path}")

    # 6. Email
    if not args.skip_email:
        print("\n[5/5] Emailing report...")
        email_report(pdf_path, report_md, charts, brand, recipient=args.email)
    else:
        print("\n[5/5] Email skipped (--skip-email)")

    # Print report to stdout
    print("\n" + "=" * 60)
    print("GENERATED REPORT:")
    print("=" * 60)
    print(report_md)

    print(f"\nDone. PDF: {pdf_path}")


if __name__ == "__main__":
    main()
