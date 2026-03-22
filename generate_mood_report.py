#!/usr/bin/env python
"""
generate_mood_report.py
Generates "The Mood Report" — a daily economic sentiment newsletter.

Uses real Moodlight data (sentiment scores, market data, commodity prices,
prediction signals, emotion analysis) to deliver quantified daily mood
measurement correlated with market outcomes.

Publishing channels:
  - Beehiiv (draft via API — Daniel reviews before publish)
  - X/Twitter thread (saved for manual posting initially)
  - Email backup to Daniel for review
"""

import os
import sys
import json
from urllib.parse import quote
import pandas as pd
from datetime import datetime, timezone, timedelta
from anthropic import Anthropic
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ---------------------------------------------------------------------------
# 1. Data Loading
# ---------------------------------------------------------------------------

def _get_engine():
    from sqlalchemy import create_engine
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url)


def load_mood_data(engine):
    """Load all data needed for The Mood Report."""
    from sqlalchemy import text as sql_text

    now = datetime.now(timezone.utc)
    data = {}

    # --- Economic sentiment trend (7d daily avg empathy + intensity) ---
    try:
        cutoff_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        sentiment = pd.read_sql(
            sql_text("""
                SELECT
                    created_at::date AS day,
                    AVG(empathy_score) AS avg_empathy,
                    AVG(intensity) AS avg_intensity,
                    COUNT(*) AS article_count
                FROM news_scored
                WHERE topic = 'economics'
                  AND created_at >= :cutoff
                GROUP BY created_at::date
                ORDER BY day
            """),
            engine,
            params={"cutoff": cutoff_7d},
        )
        data["sentiment_trend"] = sentiment
    except Exception as e:
        print(f"  Could not load sentiment trend: {e}")
        data["sentiment_trend"] = pd.DataFrame()

    # Also grab social sentiment for economics
    try:
        social_sentiment = pd.read_sql(
            sql_text("""
                SELECT
                    created_at::date AS day,
                    AVG(empathy_score) AS avg_empathy,
                    AVG(intensity) AS avg_intensity,
                    COUNT(*) AS post_count
                FROM social_scored
                WHERE topic = 'economics'
                  AND created_at >= :cutoff
                GROUP BY created_at::date
                ORDER BY day
            """),
            engine,
            params={"cutoff": cutoff_7d},
        )
        data["social_sentiment_trend"] = social_sentiment
    except Exception as e:
        print(f"  Could not load social sentiment: {e}")
        data["social_sentiment_trend"] = pd.DataFrame()

    # --- Market data (SPY, QQQ, DIA) ---
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
        # Latest per symbol
        data["markets"] = markets.groupby("symbol").first().reset_index()
    except Exception as e:
        print(f"  Could not load market data: {e}")
        data["markets"] = pd.DataFrame()

    # --- Commodity prices ---
    try:
        cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d")
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
        # Latest per commodity + previous data point for delta
        if not commodities.empty:
            commodities["snapshot_date"] = pd.to_datetime(
                commodities["snapshot_date"]
            ).dt.tz_localize(None)
            latest = commodities.groupby("scope_name").first().reset_index()
            # Get 2nd-most-recent entry per commodity for change calc
            # (handles API data lag — commodity data can be 5-10 days behind)
            prev_rows = []
            for name, grp in commodities.groupby("scope_name"):
                unique_dates = grp.drop_duplicates(subset=["snapshot_date"])
                if len(unique_dates) >= 2:
                    prev_rows.append(unique_dates.iloc[1])
            if prev_rows:
                prev = pd.DataFrame(prev_rows)
                latest = latest.merge(
                    prev[["scope_name", "metric_value"]],
                    on="scope_name", how="left", suffixes=("", "_prev"),
                )
            data["commodities"] = latest
        else:
            data["commodities"] = pd.DataFrame()
    except Exception as e:
        print(f"  Could not load commodities: {e}")
        data["commodities"] = pd.DataFrame()

    # --- Economic indicators ---
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

    # --- Recent alerts (economics-related) ---
    try:
        cutoff_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        alerts = pd.read_sql(
            sql_text("""
                SELECT alert_type, severity, title, summary, brand, topic, timestamp
                FROM alerts
                WHERE (topic = 'economics'
                       OR alert_type IN ('economic_stress', 'economic_threshold_crossing',
                                         'commodity_spike', 'brand_stock_divergence',
                                         'market_mood_divergence'))
                  AND timestamp >= :cutoff
                ORDER BY timestamp DESC
                LIMIT 20
            """),
            engine,
            params={"cutoff": cutoff_7d},
        )
        data["alerts"] = alerts
    except Exception as e:
        print(f"  Could not load alerts: {e}")
        data["alerts"] = pd.DataFrame()

    # --- Signal log track record ---
    try:
        signal_log = pd.read_sql(
            sql_text("""
                SELECT alert_type,
                       COUNT(*) AS total_signals,
                       COUNT(spy_change_1d) AS has_1d,
                       AVG(spy_change_1d) AS avg_spy_1d,
                       SUM(CASE WHEN spy_change_1d > 0 THEN 1 ELSE 0 END)::float
                           / NULLIF(COUNT(spy_change_1d), 0) AS up_rate_1d,
                       COUNT(spy_change_3d) AS has_3d,
                       AVG(spy_change_3d) AS avg_spy_3d,
                       COUNT(spy_change_5d) AS has_5d,
                       AVG(spy_change_5d) AS avg_spy_5d
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

    # --- Dominant emotions (last 3d) ---
    try:
        cutoff_3d = (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        emotions = pd.read_sql(
            sql_text("""
                SELECT emotion_top_1, COUNT(*) AS cnt
                FROM news_scored
                WHERE topic = 'economics'
                  AND created_at >= :cutoff
                  AND emotion_top_1 IS NOT NULL
                GROUP BY emotion_top_1
                ORDER BY cnt DESC
                LIMIT 10
            """),
            engine,
            params={"cutoff": cutoff_3d},
        )
        data["emotions"] = emotions
    except Exception as e:
        print(f"  Could not load emotions: {e}")
        data["emotions"] = pd.DataFrame()

    # --- Top headlines (highest intensity, last 3d) — economics ---
    try:
        cutoff_3d = (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        headlines = pd.read_sql(
            sql_text("""
                SELECT text, intensity, empathy_score, emotion_top_1, country, created_at
                FROM news_scored
                WHERE topic = 'economics'
                  AND created_at >= :cutoff
                ORDER BY intensity DESC
                LIMIT 10
            """),
            engine,
            params={"cutoff": cutoff_3d},
        )
        data["headlines"] = headlines
    except Exception as e:
        print(f"  Could not load headlines: {e}")
        data["headlines"] = pd.DataFrame()

    # --- All-topics headlines (24h) — for cross-domain observations ---
    try:
        cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        all_headlines = pd.read_sql(
            sql_text("""
                SELECT text, topic, intensity, empathy_score, emotion_top_1,
                       source, created_at
                FROM news_scored
                WHERE created_at >= :cutoff
                ORDER BY intensity DESC
                LIMIT 20
            """),
            engine,
            params={"cutoff": cutoff_24h},
        )
        data["all_headlines"] = all_headlines
    except Exception as e:
        print(f"  Could not load all-topics headlines: {e}")
        data["all_headlines"] = pd.DataFrame()

    # --- All-topics social posts (24h) ---
    try:
        cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        all_social = pd.read_sql(
            sql_text("""
                SELECT text, topic, intensity, empathy_score, emotion_top_1,
                       source, created_at
                FROM social_scored
                WHERE created_at >= :cutoff
                ORDER BY intensity DESC
                LIMIT 15
            """),
            engine,
            params={"cutoff": cutoff_24h},
        )
        data["all_social"] = all_social
    except Exception as e:
        print(f"  Could not load all-topics social: {e}")
        data["all_social"] = pd.DataFrame()

    # --- Prediction markets (Polymarket) ---
    try:
        from polymarket_helper import fetch_polymarket_markets
        poly_markets = fetch_polymarket_markets(limit=10, min_volume=50000)
        data["polymarket"] = poly_markets or []
    except Exception as e:
        print(f"  Could not load Polymarket data: {e}")
        data["polymarket"] = []

    return data


# ---------------------------------------------------------------------------
# 2. Context Building
# ---------------------------------------------------------------------------

def build_newsletter_context(data):
    """Format all data into a structured text block for Claude."""
    now = datetime.now(timezone.utc)
    sections = []

    sections.append(f"THE MOOD REPORT — DATA CONTEXT")
    sections.append(f"Generated: {now.strftime('%B %d, %Y at %H:%M UTC')}")
    sections.append("=" * 50)

    # Sentiment trend
    st = data.get("sentiment_trend", pd.DataFrame())
    if not st.empty:
        lines = ["ECONOMIC SENTIMENT TREND (7 days, news):"]
        for _, row in st.iterrows():
            lines.append(
                f"  {row['day']}: empathy={row['avg_empathy']:.4f}, "
                f"intensity={row['avg_intensity']:.2f}, articles={row['article_count']}"
            )
        sections.append("\n".join(lines))

    sst = data.get("social_sentiment_trend", pd.DataFrame())
    if not sst.empty:
        lines = ["ECONOMIC SENTIMENT TREND (7 days, social):"]
        for _, row in sst.iterrows():
            lines.append(
                f"  {row['day']}: empathy={row['avg_empathy']:.4f}, "
                f"intensity={row['avg_intensity']:.2f}, posts={row['post_count']}"
            )
        sections.append("\n".join(lines))

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
            prev_col = "metric_value_prev" if "metric_value_prev" in row else "metric_value_7d_ago"
            if prev_col in row and pd.notna(row.get(prev_col)):
                delta = row["metric_value"] - row[prev_col]
                pct = (delta / row[prev_col]) * 100
                delta_str = f" (prev: {delta:+.2f}, {pct:+.1f}%)"
            lines.append(f"  {row['scope_name']}: ${row['metric_value']:.2f}{delta_str}")
        sections.append("\n".join(lines))

    # Economic indicators
    econ = data.get("economic_indicators", pd.DataFrame())
    if not econ.empty:
        lines = ["ECONOMIC INDICATORS:"]
        for _, row in econ.iterrows():
            lines.append(f"  {row['metric_name']}: {row['metric_value']:.2f} (as of {row['snapshot_date']})")
        sections.append("\n".join(lines))

    # Alerts
    alerts = data.get("alerts", pd.DataFrame())
    if not alerts.empty:
        lines = ["RECENT INTELLIGENCE ALERTS (7d):"]
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

    # Signal track record
    sig = data.get("signal_track_record", pd.DataFrame())
    if not sig.empty:
        lines = ["SIGNAL TRACK RECORD (all-time):"]
        for _, row in sig.iterrows():
            up_rate = f"{row['up_rate_1d']*100:.0f}%" if pd.notna(row.get("up_rate_1d")) else "N/A"
            avg_1d = f"{row['avg_spy_1d']:+.2f}%" if pd.notna(row.get("avg_spy_1d")) else "N/A"
            lines.append(
                f"  {row['alert_type']}: {int(row['total_signals'])} signals, "
                f"1d outcomes: {int(row['has_1d'])} filled, "
                f"SPY up rate: {up_rate}, avg 1d move: {avg_1d}"
            )
        sections.append("\n".join(lines))

    # Emotions
    emo = data.get("emotions", pd.DataFrame())
    if not emo.empty:
        lines = ["DOMINANT EMOTIONS IN ECONOMIC COVERAGE (3d):"]
        total = emo["cnt"].sum()
        for _, row in emo.iterrows():
            pct = (row["cnt"] / total) * 100
            lines.append(f"  {row['emotion_top_1']}: {row['cnt']} ({pct:.0f}%)")
        sections.append("\n".join(lines))

    # Economic headlines
    hdl = data.get("headlines", pd.DataFrame())
    if not hdl.empty:
        lines = ["TOP ECONOMIC HEADLINES BY INTENSITY (3d):"]
        for _, row in hdl.iterrows():
            ts = pd.Timestamp(row["created_at"]).strftime("%m/%d") if pd.notna(row.get("created_at")) else "?"
            lines.append(
                f"  [{ts}] (intensity: {row['intensity']}, empathy: {row['empathy_score']:.4f}) "
                f"{str(row['text'])[:250]}"
            )
        sections.append("\n".join(lines))

    # All-topics headlines (cross-domain material)
    all_hdl = data.get("all_headlines", pd.DataFrame())
    if not all_hdl.empty:
        lines = ["TOP HEADLINES ACROSS ALL TOPICS (24h):"]
        for _, row in all_hdl.iterrows():
            topic = row.get("topic", "N/A")
            emotion = row.get("emotion_top_1", "N/A")
            intensity = row.get("intensity", 0)
            text = str(row.get("text", ""))[:200]
            lines.append(f"  [{topic}] {text} | emotion: {emotion} | intensity: {intensity:.1f}")
        sections.append("\n".join(lines))

    # All-topics social posts
    all_social = data.get("all_social", pd.DataFrame())
    if not all_social.empty:
        lines = ["TOP SOCIAL POSTS ACROSS ALL TOPICS (24h):"]
        for _, row in all_social.iterrows():
            topic = row.get("topic", "N/A")
            emotion = row.get("emotion_top_1", "N/A")
            intensity = row.get("intensity", 0)
            text = str(row.get("text", ""))[:200]
            lines.append(f"  [{topic}] {text} | emotion: {emotion} | intensity: {intensity:.1f}")
        sections.append("\n".join(lines))

    # Prediction markets (Polymarket)
    poly_markets = data.get("polymarket", [])
    if poly_markets:
        lines = ["PREDICTION MARKETS (Polymarket — real money bets):"]
        for m in poly_markets[:8]:
            lines.append(f"  \"{m['question']}\" — {m['yes_odds']:.0f}% YES (${m['volume']:,.0f} wagered)")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# 2b. Chart URL Building (QuickChart.io)
# ---------------------------------------------------------------------------

def _quickchart_url(config, width=540, height=280):
    """Build a QuickChart.io URL from a Chart.js v2 config."""
    config_json = json.dumps(config, separators=(",", ":"))
    encoded = quote(config_json, safe="")
    return f"https://quickchart.io/chart?c={encoded}&w={width}&h={height}&bkg=white"


def _build_top_movers_chart(data):
    """Build the Top Movers snapshot — the 6 biggest % changes across all data.

    Always included as the anchor visual. Shows normalized % change so
    sentiment shifts, market moves, and commodity spikes are comparable.
    """
    movers = []  # (label, pct_change)

    # Sentiment: news empathy % change (latest day vs previous day)
    news_st = data.get("sentiment_trend", pd.DataFrame())
    if not news_st.empty and len(news_st) >= 2:
        latest = float(news_st.iloc[-1]["avg_empathy"])
        prev = float(news_st.iloc[-2]["avg_empathy"])
        if prev != 0:
            movers.append(("News Empathy", ((latest - prev) / prev) * 100))

    # Sentiment: news intensity % change
    if not news_st.empty and len(news_st) >= 2:
        latest = float(news_st.iloc[-1]["avg_intensity"])
        prev = float(news_st.iloc[-2]["avg_intensity"])
        if prev != 0:
            movers.append(("News Intensity", ((latest - prev) / prev) * 100))

    # Sentiment: social empathy % change
    social_st = data.get("social_sentiment_trend", pd.DataFrame())
    if not social_st.empty and len(social_st) >= 2:
        latest = float(social_st.iloc[-1]["avg_empathy"])
        prev = float(social_st.iloc[-2]["avg_empathy"])
        if prev != 0:
            movers.append(("Social Empathy", ((latest - prev) / prev) * 100))

    # Social intensity
    if not social_st.empty and len(social_st) >= 2:
        latest = float(social_st.iloc[-1]["avg_intensity"])
        prev = float(social_st.iloc[-2]["avg_intensity"])
        if prev != 0:
            movers.append(("Social Intensity", ((latest - prev) / prev) * 100))

    # Markets: SPY, QQQ, DIA
    mkt = data.get("markets", pd.DataFrame())
    if not mkt.empty:
        for _, row in mkt.iterrows():
            pct_str = str(row.get("change_percent", "0%")).replace("%", "")
            try:
                pct = float(pct_str)
            except (ValueError, TypeError):
                pct = 0.0
            movers.append((str(row["symbol"]), pct))

    # Commodities
    comm = data.get("commodities", pd.DataFrame())
    if not comm.empty and "metric_value_prev" in comm.columns:
        for _, row in comm.dropna(subset=["metric_value_prev"]).iterrows():
            prev_val = float(row["metric_value_prev"])
            if prev_val != 0:
                delta_pct = ((float(row["metric_value"]) - prev_val) / prev_val) * 100
                movers.append((str(row["scope_name"]).title(), delta_pct))

    if len(movers) < 3:
        return None

    # Sort by absolute magnitude, take top 6
    movers.sort(key=lambda x: abs(x[1]), reverse=True)
    top = movers[:6]

    # Build horizontal bar chart
    labels = [m[0] for m in top]
    values = [round(m[1], 1) for m in top]
    colors = ["#2E7D32" if v >= 0 else "#DC143C" for v in values]

    config = {
        "type": "horizontalBar",
        "data": {
            "labels": labels,
            "datasets": [{
                "data": values,
                "backgroundColor": colors,
            }],
        },
        "options": {
            "title": {"display": True, "text": "Top Movers (% Change, 24h)",
                      "fontSize": 16, "fontColor": "#333"},
            "legend": {"display": False},
            "scales": {
                "xAxes": [{"ticks": {"beginAtZero": True, "callback": "PERCENT_CB"},
                           "scaleLabel": {"display": True, "labelString": "% Change"}}],
            },
        },
    }

    # QuickChart doesn't support JS callbacks, so add % via plugin annotation
    # Instead, embed the % in the labels
    config["options"]["plugins"] = {
        "datalabels": {
            "display": True,
            "anchor": "end",
            "align": "end",
            "formatter": "PERCENT_FMT",
            "color": "#333",
            "font": {"weight": "bold"},
        }
    }

    # Clean up — QuickChart can't run JS, so remove callback placeholders
    config["options"]["scales"]["xAxes"][0]["ticks"].pop("callback", None)
    config["options"].pop("plugins", None)

    config_json = json.dumps(config, separators=(",", ":"))
    encoded = quote(config_json, safe="")
    return f"https://quickchart.io/chart?c={encoded}&w=540&h=280&bkg=white"


def build_chart_urls(data):
    """Build QuickChart.io image URLs for newsletter visuals.

    Always includes the Top Movers snapshot, plus the 2 most relevant
    charts from a scored pool of options.
    """
    palette = ["#1976D2", "#E65100", "#7B1FA2", "#00897B", "#2E7D32",
               "#C62828", "#F57F17", "#1565C0", "#AD1457", "#4E342E"]

    # Pool: (key, score, config_or_None)
    pool = []

    # --- 1. Empathy Trend (line) — score by variance ---
    news_st = data.get("sentiment_trend", pd.DataFrame())
    social_st = data.get("social_sentiment_trend", pd.DataFrame())
    if not news_st.empty or not social_st.empty:
        all_days = set()
        if not news_st.empty:
            all_days.update(str(d) for d in news_st["day"])
        if not social_st.empty:
            all_days.update(str(d) for d in social_st["day"])
        labels = sorted(all_days)
        formatted_labels = []
        for d in labels:
            try:
                formatted_labels.append(pd.Timestamp(d).strftime("%b %d"))
            except Exception:
                formatted_labels.append(d)

        datasets = []
        all_values = []
        if not news_st.empty:
            news_map = {str(r["day"]): round(float(r["avg_empathy"]), 4)
                        for _, r in news_st.iterrows()}
            vals = [news_map.get(d) for d in labels]
            all_values.extend(v for v in vals if v is not None)
            datasets.append({
                "label": "News",
                "data": vals,
                "borderColor": "#1976D2",
                "backgroundColor": "rgba(25,118,210,0.1)",
                "fill": True, "lineTension": 0.3, "pointRadius": 4,
            })
        if not social_st.empty:
            social_map = {str(r["day"]): round(float(r["avg_empathy"]), 4)
                          for _, r in social_st.iterrows()}
            vals = [social_map.get(d) for d in labels]
            all_values.extend(v for v in vals if v is not None)
            datasets.append({
                "label": "Social",
                "data": vals,
                "borderColor": "#E65100",
                "backgroundColor": "rgba(230,81,0,0.1)",
                "fill": True, "lineTension": 0.3, "pointRadius": 4,
            })

        if datasets:
            # Score: higher variance = more interesting trend
            variance = max(all_values) - min(all_values) if len(all_values) >= 2 else 0
            score = min(variance * 100, 10)  # normalize to ~0-10
            config = {
                "type": "line",
                "data": {"labels": formatted_labels, "datasets": datasets},
                "options": {
                    "title": {"display": True, "text": "7-Day Empathy Trend", "fontSize": 16},
                    "legend": {"position": "bottom"},
                    "scales": {"yAxes": [{"scaleLabel": {"display": True,
                                                         "labelString": "Empathy Score"}}]},
                },
            }
            pool.append(("empathy_trend", score, config, "WHAT'S INTERESTING"))

    # --- 2. Market Performance (horizontal bar) — score by magnitude ---
    mkt = data.get("markets", pd.DataFrame())
    if not mkt.empty:
        symbols, changes, colors = [], [], []
        for _, row in mkt.iterrows():
            pct_str = str(row.get("change_percent", "0%")).replace("%", "")
            try:
                pct = float(pct_str)
            except (ValueError, TypeError):
                pct = 0.0
            symbols.append(str(row["symbol"]))
            changes.append(round(pct, 2))
            colors.append("#2E7D32" if pct >= 0 else "#DC143C")

        max_move = max(abs(c) for c in changes) if changes else 0
        score = min(max_move * 3, 10)  # 1% move = score 3, 3%+ = 10
        config = {
            "type": "horizontalBar",
            "data": {"labels": symbols, "datasets": [{"data": changes, "backgroundColor": colors}]},
            "options": {
                "title": {"display": True, "text": "Market Performance (%)", "fontSize": 16},
                "legend": {"display": False},
                "scales": {"xAxes": [{"ticks": {"beginAtZero": True}}]},
            },
        }
        pool.append(("market_performance", score, config, "MARKETS & MOOD"))

    # --- 3. Emotion Distribution (doughnut) — score by skewness ---
    emo = data.get("emotions", pd.DataFrame())
    if not emo.empty and len(emo) >= 2:
        emotion_labels = [str(e) for e in emo["emotion_top_1"]]
        counts = [int(c) for c in emo["cnt"]]
        bg_colors = [palette[i % len(palette)] for i in range(len(emotion_labels))]

        # Score: if top emotion dominates >60%, it's interesting (skewed)
        total = sum(counts)
        top_pct = counts[0] / total if total else 0
        score = top_pct * 8  # 75% dominance = score 6, 50% = score 4

        config = {
            "type": "doughnut",
            "data": {"labels": emotion_labels, "datasets": [{"data": counts, "backgroundColor": bg_colors}]},
            "options": {
                "title": {"display": True, "text": "Emotion Distribution (3d)", "fontSize": 16},
                "legend": {"position": "right"},
            },
        }
        pool.append(("emotion_distribution", score, config, "ALSO WORTH NOTICING"))

    # --- 4. Topic Intensity (bar) — what topics are hottest today ---
    all_hdl = data.get("all_headlines", pd.DataFrame())
    if not all_hdl.empty and "topic" in all_hdl.columns and "intensity" in all_hdl.columns:
        topic_avg = all_hdl.groupby("topic")["intensity"].mean().sort_values(ascending=False).head(8)
        if len(topic_avg) >= 3:
            t_labels = [str(t).title() for t in topic_avg.index]
            t_values = [round(float(v), 1) for v in topic_avg.values]
            t_colors = [palette[i % len(palette)] for i in range(len(t_labels))]

            # Score: higher if spread between top and bottom topic is large
            spread = t_values[0] - t_values[-1] if len(t_values) >= 2 else 0
            score = min(spread * 2, 10)

            config = {
                "type": "horizontalBar",
                "data": {"labels": t_labels, "datasets": [{"data": t_values, "backgroundColor": t_colors}]},
                "options": {
                    "title": {"display": True, "text": "Topic Intensity (24h)", "fontSize": 16},
                    "legend": {"display": False},
                    "scales": {"xAxes": [{"ticks": {"beginAtZero": True}}]},
                },
            }
            pool.append(("topic_intensity", score, config, "WHAT'S INTERESTING"))

    # --- 5. Commodity Moves (bar) — score by magnitude of changes ---
    comm = data.get("commodities", pd.DataFrame())
    if not comm.empty and "metric_value_prev" in comm.columns:
        comm_with_delta = comm.dropna(subset=["metric_value_prev"])
        if not comm_with_delta.empty:
            c_labels, c_values, c_colors = [], [], []
            for _, row in comm_with_delta.iterrows():
                delta_pct = ((row["metric_value"] - row["metric_value_prev"])
                             / row["metric_value_prev"]) * 100
                c_labels.append(str(row["scope_name"]))
                c_values.append(round(delta_pct, 1))
                c_colors.append("#2E7D32" if delta_pct >= 0 else "#DC143C")

            max_commodity_move = max(abs(v) for v in c_values) if c_values else 0
            score = min(max_commodity_move * 2, 10)  # 2% move = score 4, 5%+ = 10

            if len(c_labels) >= 2:
                config = {
                    "type": "horizontalBar",
                    "data": {"labels": c_labels, "datasets": [{"data": c_values, "backgroundColor": c_colors}]},
                    "options": {
                        "title": {"display": True, "text": "Commodity Price Changes (%)", "fontSize": 16},
                        "legend": {"display": False},
                        "scales": {"xAxes": [{"ticks": {"beginAtZero": True}}]},
                    },
                }
                pool.append(("commodity_moves", score, config, "MARKETS & MOOD"))

    # --- 6. News vs Social Empathy (grouped bar) — score by divergence ---
    if not news_st.empty and not social_st.empty:
        news_map = {str(r["day"]): round(float(r["avg_empathy"]), 4) for _, r in news_st.iterrows()}
        social_map = {str(r["day"]): round(float(r["avg_empathy"]), 4) for _, r in social_st.iterrows()}
        common_days = sorted(set(news_map.keys()) & set(social_map.keys()))
        if len(common_days) >= 3:
            divergences = [abs(news_map[d] - social_map[d]) for d in common_days]
            avg_div = sum(divergences) / len(divergences)
            score = min(avg_div * 200, 10)  # 0.05 avg divergence = score 10

            formatted = []
            for d in common_days:
                try:
                    formatted.append(pd.Timestamp(d).strftime("%b %d"))
                except Exception:
                    formatted.append(d)

            config = {
                "type": "bar",
                "data": {
                    "labels": formatted,
                    "datasets": [
                        {"label": "News", "data": [news_map[d] for d in common_days],
                         "backgroundColor": "#1976D2"},
                        {"label": "Social", "data": [social_map[d] for d in common_days],
                         "backgroundColor": "#E65100"},
                    ],
                },
                "options": {
                    "title": {"display": True, "text": "News vs Social Empathy (7d)", "fontSize": 16},
                    "legend": {"position": "bottom"},
                    "scales": {"yAxes": [{"scaleLabel": {"display": True,
                                                         "labelString": "Empathy Score"}}]},
                },
            }
            pool.append(("news_vs_social", score, config, "WHAT'S INTERESTING"))

    # --- Always include Top Movers ---
    charts = {}
    chart_placements = {}

    top_movers_url = _build_top_movers_chart(data)
    if top_movers_url:
        charts["top_movers"] = top_movers_url
        chart_placements["top_movers"] = "BOTTOM LINE"

    # --- Select top 2 from pool (top movers is the anchor) ---
    pool.sort(key=lambda x: x[1], reverse=True)
    for key, _score, config, section in pool[:2]:
        charts[key] = _quickchart_url(config, width=540, height=300 if key == "emotion_distribution" else 280)
        chart_placements[key] = section

    # Stash placements for insert_chart_images
    charts["_placements"] = chart_placements
    return charts


# ---------------------------------------------------------------------------
# 3. Newsletter Generation (Claude)
# ---------------------------------------------------------------------------

NEWSLETTER_SYSTEM_PROMPT = """You are the writer behind The Mood Report — a daily newsletter that tells you what the world is feeling and why it matters.

You have access to sentiment data, market data, economic indicators, headlines across every topic, and social posts. Your job is to find the most interesting observations in today's data and write about them in a way that makes people feel smarter.

Your reader might be a portfolio manager or a curious parent. Write for both. No jargon unless you explain it. Sharp observations, not data dumps.

VOICE: Warm, sharp, curious. Like a smart friend who reads everything and texts you the interesting parts. Conversational, not performative. Funny when it's natural, never forced. Never breathless, never preachy. If it sounds like a Bloomberg terminal or a LinkedIn post, start over.

RULES:

1. EVERY CLAIM MUST BE GROUNDED IN THE DATA PROVIDED. No training data. No made-up statistics. Wear the data lightly — one well-placed number is worth more than five.

2. OBSERVATIONS OVER METRICS. Don't just report that empathy went up 0.02. Tell the reader what's interesting — the contradiction, the second-order effect, the thing hiding in plain sight. The numbers support the story, they aren't the story.

3. GO CROSS-DOMAIN. You have headlines from every topic — economics, entertainment, tech, labor, sports. The best observations sit at the intersection of two unrelated trends. A market move + a cultural shift. An economic indicator + how people are talking online. Find those collisions.

4. EMPATHY FIRST, ECONOMICS SECOND. This is the rule that defines Moodlight. Do NOT lead with markets, oil prices, or Fed decisions — every other newsletter does that and your reader already saw it. Lead with the most emotionally resonant human observation in the data — how people are actually feeling, behaving, withdrawing, or surprising each other — and THEN connect it to the economic and global forces driving it. "Two-thirds of Americans stopped going to weddings because they can't afford it" is a Moodlight lead. "SPY dropped 1.4%" is not. Start with empathy, then show the machinery. That's what makes someone screenshot your newsletter instead of skimming it.

5. NO REPETITIVE STRUCTURE. Every issue should feel different because every day IS different. Some days the lead is a market divergence. Some days it's a social media pattern. Some days it's a single buried headline that reveals something bigger. Follow the data, not a template.

6. THE MARKET SNAPSHOT SHOULD BE BRIEF. Include SPY/QQQ/DIA and any notable commodity moves, but keep it to a few lines. Don't build the whole newsletter around market numbers — they're context, not the main event.

7. EMPATHY SCORE REFERENCE: 0.04 = cold/hostile, 0.10 = detached/neutral, 0.30 = warm, 0.30+ = highly empathetic.

8. KEEP IT UNDER 800 WORDS. Every sentence should earn its spot. If you can cut a sentence without losing meaning, cut it.

9. EVEN WHEN THE NEWS IS HEAVY, FIND THE HUMAN ANGLE. You're not ignoring hard things — you're finding the part of the story about how people respond, adapt, and surprise each other.

OUTPUT FORMAT — use this exact structure with markdown:

# THE MOOD REPORT
*[Full date]*

## [Sharp, specific headline that earns curiosity — not clickbait, not corporate]

## BOTTOM LINE
[One paragraph. The single most important thing in today's data, in plain English. What should the reader walk away knowing?]

## WHAT'S INTERESTING
[This is the heart of the newsletter. 3-4 paragraphs. Lead with the most emotionally resonant human observation — how people are feeling, behaving, or being affected in ways that aren't obvious. Then connect it to the economic and global forces driving it. The reader should feel something before they learn something. Reference specific headlines, data points, and social posts. Cross-domain connections are your superpower.]

## ALSO WORTH NOTICING
[2-3 brief observations (2-3 sentences each) from different parts of the data. Different topics, different angles. These should each deliver a small "huh" moment.]

## MARKETS & MOOD
[Brief market snapshot — SPY, QQQ, DIA with prices and changes. Any notable commodity or economic indicator moves. Then 1-2 sentences connecting market action to sentiment. Do markets and mood agree or diverge today?]

## WHAT TO WATCH
[2-3 specific things the data says are worth monitoring. Not predictions — observations that suggest something is building. Ground each in a data point.]

---
*The Mood Report — daily from Moodlight Intelligence.*
"""

X_THREAD_SYSTEM_PROMPT = """Condense this newsletter into a 3-4 tweet thread (280 chars each).
Tweet 1: "THE MOOD REPORT | [Mon DD]" + the single most important data point.
Tweet 2: One striking finding or signal.
Tweet 3: Track record stat or forward look.
Tweet 4: "Full issue → [link]"
No hashtags. No emojis. Data speaks for itself.

Output each tweet on its own line, separated by a blank line. Number them 1/, 2/, etc."""


def generate_newsletter(context):
    """Generate the newsletter body via Claude Opus."""
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3000,
        system=NEWSLETTER_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Generate today's issue of The Mood Report using this data:\n\n{context}",
        }],
    )
    return response.content[0].text


def generate_x_thread(context, newsletter_md):
    """Generate a condensed X/Twitter thread from the newsletter."""
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=800,
        system=X_THREAD_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Here is today's newsletter:\n\n{newsletter_md}\n\n"
                f"And the raw data context:\n\n{context}\n\n"
                f"Generate the X thread."
            ),
        }],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# 4. Publishing
# ---------------------------------------------------------------------------

def save_x_thread(thread_text):
    """Save X thread to file for manual posting."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"mood_report_x_thread_{date_str}.txt"
    with open(filename, "w") as f:
        f.write(thread_text)
    print(f"  X thread saved to: {filename}")
    return filename


def email_report(newsletter_md, x_thread, chart_urls=None):
    """Email the generated report to Daniel for review."""
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    recipient = os.getenv("EMAIL_RECIPIENT", "")

    if not all([sender, password, recipient]):
        print("  Email credentials not configured. Skipping email.")
        return False

    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # Build HTML from newsletter markdown
    from mood_report_publisher import markdown_to_newsletter_html, insert_chart_images
    newsletter_html = markdown_to_newsletter_html(newsletter_md)
    if chart_urls:
        newsletter_html = insert_chart_images(newsletter_html, chart_urls)

    # Build email body with newsletter + X thread preview
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
        <div style="background: #1a1a2e; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
          <h1 style="margin: 0; font-size: 24px;">The Mood Report</h1>
          <p style="margin: 5px 0 0 0; color: #aaa;">Draft for Review — {date_str}</p>
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
    msg["Subject"] = f"[Mood Report] Draft for Review — {date_str}"
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
# 5. Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("THE MOOD REPORT — Daily Newsletter Generator")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # 1. Connect to DB
    engine = _get_engine()

    # 2. Load all data
    print("\n[1/6] Loading mood data...")
    data = load_mood_data(engine)

    # Quick sanity check
    has_data = any(
        not df.empty for df in data.values() if isinstance(df, pd.DataFrame)
    )
    if not has_data:
        print("No data available. Cannot generate report.")
        return

    # 3. Build context + chart URLs
    print("[2/6] Building newsletter context...")
    context = build_newsletter_context(data)
    print(f"  Context length: {len(context)} chars")

    print("  Building chart URLs...")
    chart_urls = build_chart_urls(data)
    print(f"  Charts generated: {list(chart_urls.keys()) if chart_urls else 'none'}")

    # 4. Generate newsletter
    print("[3/6] Generating newsletter via Claude Opus...")
    newsletter_md = generate_newsletter(context)
    print(f"  Newsletter length: {len(newsletter_md)} chars")

    # 5. Generate X thread
    print("[4/6] Generating X thread...")
    x_thread = generate_x_thread(context, newsletter_md)
    print(f"  Thread length: {len(x_thread)} chars")

    # 6. Publish to Beehiiv (if configured)
    print("[5/6] Publishing...")
    beehiiv_api_key = os.getenv("BEEHIIV_API_KEY")
    if beehiiv_api_key:
        try:
            from mood_report_publisher import (
                publish_to_beehiiv, markdown_to_newsletter_html, insert_chart_images,
            )
            date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
            html = markdown_to_newsletter_html(newsletter_md)
            if chart_urls:
                html = insert_chart_images(html, chart_urls)
            publish_to_beehiiv(
                html=html,
                title=f"The Mood Report — {date_str}",
                subtitle="Daily economic sentiment intelligence",
            )
        except Exception as e:
            print(f"  Beehiiv publish failed: {e}")
    else:
        print("  Beehiiv not configured (no BEEHIIV_API_KEY). Skipping.")

    # Save X thread for manual posting
    save_x_thread(x_thread)

    # 7. Email report to Daniel
    print("[6/6] Emailing report...")
    email_report(newsletter_md, x_thread, chart_urls=chart_urls)

    # Print the newsletter to stdout
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
