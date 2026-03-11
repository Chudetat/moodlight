#!/usr/bin/env python
"""
generate_trending_report.py
Generates "The Mood Report: TRENDING" — a weekly brand intelligence newsletter.

Scans the full dataset for the 3-5 most trending brands of the week using
Claude Haiku for brand discovery from headlines, then computes VLDS + momentum
scores to rank them. Published to same Beehiiv newsletter as the Daily edition.

Runs weekly on Fridays via Railway cron (worker-trending).
"""

import json
import os
import re
import smtplib
import sys
from collections import Counter
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
from mood_report_publisher import markdown_to_newsletter_html
from vlds_helper import calculate_brand_vlds

# Brand → ticker mapping (reuse from signal_log_tracker)
BRAND_TICKERS = {
    "nvidia": "NVDA",
    "amazon": "AMZN",
    "disney": "DIS",
    "lockheed martin": "LMT",
}


# ---------------------------------------------------------------------------
# 1. Brand Discovery
# ---------------------------------------------------------------------------

def _filter_by_brand(df, brand_name):
    """Filter a dataframe to rows mentioning a brand in title or text.

    Same pattern as alert_detector._filter_by_brand.
    Uses regex=False to avoid warnings on brand names with special chars.
    """
    if df.empty:
        return pd.DataFrame()
    brand_lower = brand_name.lower()
    mask = pd.Series(False, index=df.index)
    for col in ["title", "text", "source"]:
        if col in df.columns:
            mask = mask | df[col].str.contains(brand_lower, case=False, na=False, regex=False)
    return df[mask]


def _extract_brands_via_haiku(headlines):
    """Use Claude Haiku to extract brand/company names from headlines."""
    headlines_text = "\n".join(f"- {h}" for h in headlines[:150])
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": (
                    "Extract all brand and company names mentioned in these headlines. "
                    "Include corporations, tech companies, consumer brands, sports teams, "
                    "financial institutions, and any other named organizations.\n\n"
                    "Return ONLY a JSON array of unique brand/company names. "
                    "No explanation, no duplicates. Normalize names to their common form "
                    "(e.g., 'Microsoft Corp' → 'Microsoft').\n\n"
                    f"Headlines:\n{headlines_text}"
                ),
            }],
        )
        text = response.content[0].text.strip()
        # Extract JSON array from response (handle markdown code blocks)
        if "```" in text:
            match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text, re.DOTALL)
            if match:
                text = match.group(1)
        brands = json.loads(text)
        if isinstance(brands, list):
            return [str(b).strip() for b in brands if isinstance(b, str) and len(b.strip()) > 1]
    except Exception as e:
        print(f"  Haiku brand extraction failed: {e}")
    return []


def _load_watchlist_brands(engine):
    """Load known brands from brand_watchlist and brand_competitors."""
    from sqlalchemy import text as sql_text
    brands = set()

    try:
        wl = pd.read_sql(
            sql_text("SELECT DISTINCT brand_name FROM brand_watchlist"),
            engine,
        )
        brands.update(wl["brand_name"].tolist())
    except Exception as e:
        print(f"  Could not load brand_watchlist: {e}")

    try:
        comp = pd.read_sql(
            sql_text("SELECT DISTINCT competitor_name FROM brand_competitors"),
            engine,
        )
        brands.update(comp["competitor_name"].tolist())
    except Exception as e:
        print(f"  Could not load brand_competitors: {e}")

    return brands


def _deduplicate_brands(brands):
    """Case-insensitive dedup, keeping the most common casing."""
    casing_counter = Counter()
    for b in brands:
        casing_counter[b] += 1

    # Group by lowercase
    groups = {}
    for b, count in casing_counter.items():
        key = b.lower().strip()
        if key not in groups or count > groups[key][1]:
            groups[key] = (b, count)

    return [v[0] for v in groups.values()]


def discover_trending_brands(engine, lookback_days=7):
    """Stage 1: Discover brands from headlines + watchlist.

    Returns (all_brands, df_news, df_social) where all_brands is a deduplicated
    list of brand names found across Haiku extraction and watchlist.
    """
    from sqlalchemy import text as sql_text

    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d %H:%M:%S")

    # Load news and social data
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
        print(f"    {len(df_news)} articles loaded")
    except Exception as e:
        print(f"    Failed to load news_scored: {e}")
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
        print(f"    {len(df_social)} posts loaded")
    except Exception as e:
        print(f"    Failed to load social_scored: {e}")
        df_social = pd.DataFrame()

    if df_news.empty and df_social.empty:
        return [], pd.DataFrame(), pd.DataFrame()

    # Get top 150 headlines by intensity (deduped)
    all_texts = []
    if not df_news.empty:
        all_texts.extend(df_news.head(120)["text"].dropna().tolist())
    if not df_social.empty:
        all_texts.extend(df_social.head(50)["text"].dropna().tolist())

    # Deduplicate headlines
    seen = set()
    unique_headlines = []
    for t in all_texts:
        t_clean = str(t).strip()
        t_lower = t_clean.lower()
        if t_lower not in seen and len(t_clean) > 20:
            seen.add(t_lower)
            unique_headlines.append(t_clean)
    unique_headlines = unique_headlines[:150]

    print(f"  Extracting brands from {len(unique_headlines)} headlines via Haiku...")
    haiku_brands = _extract_brands_via_haiku(unique_headlines)
    print(f"    Haiku found {len(haiku_brands)} brands")

    # Load watchlist brands as seed
    watchlist_brands = _load_watchlist_brands(engine)
    print(f"    Watchlist has {len(watchlist_brands)} brands")

    # Union and deduplicate
    all_brands_raw = list(haiku_brands) + list(watchlist_brands)
    all_brands = _deduplicate_brands(all_brands_raw)
    print(f"    Total unique brands after dedup: {len(all_brands)}")

    return all_brands, df_news, df_social


# ---------------------------------------------------------------------------
# 2. Trending Score Calculation
# ---------------------------------------------------------------------------

def calculate_trending_scores(brands, df_news, df_social, lookback_days=7):
    """Stage 2: Score and rank brands by trending potential.

    For each brand:
      - Count mentions and check day spread
      - Compute VLDS via calculate_brand_vlds()
      - Compute mention momentum (last 3 days / full 7 day avg)
      - Trending score = 0.40 * velocity + 0.35 * momentum + 0.25 * density

    Returns list of dicts sorted by trending_score desc, top 5.
    """
    now = datetime.now(timezone.utc)
    results = []
    min_mentions = 15
    min_days = 3

    for brand in brands:
        # Filter data for this brand
        news_brand = _filter_by_brand(df_news, brand)
        social_brand = _filter_by_brand(df_social, brand)
        brand_df = pd.concat([news_brand, social_brand], ignore_index=True)

        if brand_df.empty:
            continue

        mention_count = len(brand_df)

        # Check day spread
        if "created_at" in brand_df.columns:
            brand_df_copy = brand_df.copy()
            brand_df_copy["date"] = brand_df_copy["created_at"].dt.date
            active_days = brand_df_copy["date"].nunique()
        else:
            active_days = 1

        if mention_count < min_mentions or active_days < min_days:
            continue

        # Compute VLDS
        vlds = calculate_brand_vlds(brand_df)
        if vlds is None:
            continue

        velocity = vlds.get("velocity", 0.5)
        density = vlds.get("density", 0.3)

        # Compute momentum: last 3 days avg vs full 7 day avg
        if "created_at" in brand_df.columns:
            cutoff_3d = now - timedelta(days=3)
            recent_count = len(brand_df[brand_df["created_at"] >= cutoff_3d])
            full_avg = mention_count / lookback_days
            recent_avg = recent_count / 3.0
            if full_avg > 0:
                momentum_raw = recent_avg / full_avg
                # Cap at 3x to avoid runaway scores
                momentum = min(momentum_raw / 3.0, 1.0)
            else:
                momentum = 0.5
        else:
            momentum = 0.5

        trending_score = 0.40 * velocity + 0.35 * momentum + 0.25 * density

        results.append({
            "brand": brand,
            "mention_count": mention_count,
            "active_days": active_days,
            "velocity": velocity,
            "density": density,
            "momentum": round(momentum, 3),
            "trending_score": round(trending_score, 3),
            "vlds": vlds,
            "brand_df": brand_df,
        })

    # Sort by trending score descending
    results.sort(key=lambda x: x["trending_score"], reverse=True)

    # Edge case: if fewer than 3 qualifying brands, relax thresholds
    if len(results) < 3:
        print(f"  Only {len(results)} brands with >=15 mentions. Relaxing to 10...")
        for brand in brands:
            if any(r["brand"].lower() == brand.lower() for r in results):
                continue
            news_brand = _filter_by_brand(df_news, brand)
            social_brand = _filter_by_brand(df_social, brand)
            brand_df = pd.concat([news_brand, social_brand], ignore_index=True)
            if brand_df.empty or len(brand_df) < 10:
                continue
            if "created_at" in brand_df.columns:
                brand_df_copy = brand_df.copy()
                brand_df_copy["date"] = brand_df_copy["created_at"].dt.date
                active_days = brand_df_copy["date"].nunique()
            else:
                active_days = 1
            if active_days < 2:
                continue
            vlds = calculate_brand_vlds(brand_df)
            if vlds is None:
                continue
            velocity = vlds.get("velocity", 0.5)
            density = vlds.get("density", 0.3)
            if "created_at" in brand_df.columns:
                cutoff_3d = now - timedelta(days=3)
                recent_count = len(brand_df[brand_df["created_at"] >= cutoff_3d])
                full_avg = len(brand_df) / lookback_days
                recent_avg = recent_count / 3.0
                momentum = min((recent_avg / full_avg) / 3.0, 1.0) if full_avg > 0 else 0.5
            else:
                momentum = 0.5
            trending_score = 0.40 * velocity + 0.35 * momentum + 0.25 * density
            results.append({
                "brand": brand,
                "mention_count": len(brand_df),
                "active_days": active_days,
                "velocity": velocity,
                "density": density,
                "momentum": round(momentum, 3),
                "trending_score": round(trending_score, 3),
                "vlds": vlds,
                "brand_df": brand_df,
            })
        results.sort(key=lambda x: x["trending_score"], reverse=True)

    if len(results) < 3:
        print(f"  Only {len(results)} brands with >=10 mentions. Relaxing to 5...")
        for brand in brands:
            if any(r["brand"].lower() == brand.lower() for r in results):
                continue
            news_brand = _filter_by_brand(df_news, brand)
            social_brand = _filter_by_brand(df_social, brand)
            brand_df = pd.concat([news_brand, social_brand], ignore_index=True)
            if brand_df.empty or len(brand_df) < 5:
                continue
            vlds = calculate_brand_vlds(brand_df)
            if vlds is None:
                continue
            velocity = vlds.get("velocity", 0.5)
            density = vlds.get("density", 0.3)
            momentum = 0.5
            trending_score = 0.40 * velocity + 0.35 * momentum + 0.25 * density
            results.append({
                "brand": brand,
                "mention_count": len(brand_df),
                "active_days": 1,
                "velocity": velocity,
                "density": density,
                "momentum": round(momentum, 3),
                "trending_score": round(trending_score, 3),
                "vlds": vlds,
                "brand_df": brand_df,
            })
        results.sort(key=lambda x: x["trending_score"], reverse=True)

    return results[:5]


# ---------------------------------------------------------------------------
# 3. Load Brand Context
# ---------------------------------------------------------------------------

def load_brand_context(engine, top_brands, lookback_days=7):
    """Stage 3: Load detailed context for each top brand.

    Enriches each brand entry with:
      - Top 5 headlines (by intensity)
      - Emotion distribution
      - Recent alerts
      - Stock data (if ticker exists)
      - Empathy trend (daily avg over 7d)
    """
    from sqlalchemy import text as sql_text

    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d %H:%M:%S")

    for entry in top_brands:
        brand = entry["brand"]
        brand_df = entry["brand_df"]

        # Top 5 headlines by intensity
        if "intensity" in brand_df.columns:
            top_headlines = brand_df.nlargest(5, "intensity")
            entry["top_headlines"] = top_headlines
        else:
            entry["top_headlines"] = pd.DataFrame()

        # Emotion distribution
        if "emotion_top_1" in brand_df.columns:
            emotions = brand_df["emotion_top_1"].value_counts().head(8)
            entry["emotions"] = emotions
        else:
            entry["emotions"] = pd.Series(dtype="int64")

        # Empathy trend (daily avg)
        if "created_at" in brand_df.columns and "empathy_score" in brand_df.columns:
            brand_copy = brand_df.copy()
            brand_copy["date"] = brand_copy["created_at"].dt.date
            daily_empathy = brand_copy.groupby("date")["empathy_score"].mean()
            entry["empathy_trend"] = daily_empathy
        else:
            entry["empathy_trend"] = pd.Series(dtype="float64")

        # Recent alerts
        try:
            alerts = pd.read_sql(
                sql_text("""
                    SELECT alert_type, severity, title, summary, timestamp
                    FROM alerts
                    WHERE (brand ILIKE :brand OR title ILIKE :brand_pct)
                      AND timestamp >= :cutoff
                    ORDER BY timestamp DESC
                    LIMIT 5
                """),
                engine,
                params={
                    "brand": brand,
                    "brand_pct": f"%{brand}%",
                    "cutoff": cutoff,
                },
            )
            entry["alerts"] = alerts
        except Exception as e:
            print(f"    Could not load alerts for {brand}: {e}")
            entry["alerts"] = pd.DataFrame()

        # Stock data (if ticker exists)
        ticker = BRAND_TICKERS.get(brand.lower())
        if ticker:
            try:
                stock = pd.read_sql(
                    sql_text("""
                        SELECT scope_name, metric_name, metric_value, snapshot_date
                        FROM metric_snapshots
                        WHERE scope = 'brand_stock'
                          AND scope_name = :ticker
                          AND snapshot_date >= :cutoff
                        ORDER BY snapshot_date DESC
                        LIMIT 10
                    """),
                    engine,
                    params={"ticker": ticker, "cutoff": cutoff},
                )
                entry["stock_data"] = stock
                entry["ticker"] = ticker
            except Exception as e:
                print(f"    Could not load stock for {brand} ({ticker}): {e}")
                entry["stock_data"] = pd.DataFrame()
                entry["ticker"] = ticker
        else:
            entry["stock_data"] = pd.DataFrame()
            entry["ticker"] = None

    return top_brands


# ---------------------------------------------------------------------------
# 4. Market Backdrop
# ---------------------------------------------------------------------------

def load_market_backdrop(engine):
    """Stage 4: Load market backdrop data (same as daily report)."""
    from sqlalchemy import text as sql_text

    now = datetime.now(timezone.utc)
    cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    data = {}

    # Markets (SPY, QQQ, DIA)
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

    return data


# ---------------------------------------------------------------------------
# 5. Context String
# ---------------------------------------------------------------------------

def build_trending_context(top_brands, market_data, lookback_days=7):
    """Stage 5: Format all brand data + market backdrop into structured text."""
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=lookback_days)).strftime("%B %d")
    week_end = now.strftime("%B %d, %Y")
    sections = []

    sections.append(f"THE MOOD REPORT: TRENDING — Week of {week_start} – {week_end}")
    sections.append(f"Generated: {now.strftime('%B %d, %Y at %H:%M UTC')}")
    sections.append("=" * 50)

    # Leaderboard summary
    lines = ["TRENDING BRANDS LEADERBOARD:"]
    lines.append(f"{'Rank':<6}{'Brand':<25}{'Mentions':<10}{'Days':<6}{'Velocity':<10}{'Momentum':<10}{'Score':<8}")
    lines.append("-" * 75)
    for i, entry in enumerate(top_brands, 1):
        lines.append(
            f"{i:<6}{entry['brand']:<25}{entry['mention_count']:<10}"
            f"{entry['active_days']:<6}{entry['velocity']:<10.2f}"
            f"{entry['momentum']:<10.3f}{entry['trending_score']:<8.3f}"
        )
    sections.append("\n".join(lines))

    # Per-brand detail
    for i, entry in enumerate(top_brands, 1):
        brand = entry["brand"]
        vlds = entry["vlds"]
        sections.append("=" * 50)
        sections.append(f"BRAND #{i}: {brand.upper()}")
        sections.append("-" * 30)

        # VLDS scores
        vlds_lines = [f"VLDS SCORES — {brand}:"]
        vlds_lines.append(f"  Velocity: {vlds.get('velocity', 'N/A')} ({vlds.get('velocity_label', '')})")
        vlds_lines.append(f"  Longevity: {vlds.get('longevity', 'N/A')} ({vlds.get('longevity_label', '')})")
        vlds_lines.append(f"  Density: {vlds.get('density', 'N/A')} ({vlds.get('density_label', '')})")
        vlds_lines.append(f"  Scarcity: {vlds.get('scarcity', 'N/A')} ({vlds.get('scarcity_label', '')})")
        vlds_lines.append(f"  Mentions: {entry['mention_count']} across {entry['active_days']} days")
        vlds_lines.append(f"  Momentum: {entry['momentum']:.3f}")
        if vlds.get("empathy_score") is not None:
            vlds_lines.append(f"  Avg Empathy: {vlds['empathy_score']:.4f} ({vlds.get('empathy_label', '')})")
        sections.append("\n".join(vlds_lines))

        # Top headlines
        hdl = entry.get("top_headlines", pd.DataFrame())
        if not hdl.empty:
            h_lines = [f"TOP HEADLINES — {brand}:"]
            for _, row in hdl.iterrows():
                ts = (pd.Timestamp(row["created_at"]).strftime("%m/%d")
                      if pd.notna(row.get("created_at")) else "?")
                h_lines.append(
                    f"  [{ts}] (intensity: {row.get('intensity', 'N/A')}, "
                    f"empathy: {row.get('empathy_score', 0):.4f}) "
                    f"{str(row['text'])[:250]}"
                )
            sections.append("\n".join(h_lines))

        # Emotions
        emotions = entry.get("emotions", pd.Series(dtype="int64"))
        if not emotions.empty:
            e_lines = [f"EMOTION DISTRIBUTION — {brand}:"]
            total = emotions.sum()
            for emotion, count in emotions.items():
                pct = (count / total) * 100
                e_lines.append(f"  {emotion}: {count} ({pct:.0f}%)")
            sections.append("\n".join(e_lines))

        # Empathy trend
        emp_trend = entry.get("empathy_trend", pd.Series(dtype="float64"))
        if not emp_trend.empty:
            t_lines = [f"EMPATHY TREND — {brand} (daily avg):"]
            for date, score in emp_trend.items():
                t_lines.append(f"  {date}: {score:.4f}")
            sections.append("\n".join(t_lines))

        # Alerts
        alerts = entry.get("alerts", pd.DataFrame())
        if not alerts.empty:
            a_lines = [f"RECENT ALERTS — {brand}:"]
            for _, row in alerts.iterrows():
                sev = (row.get("severity") or "info").upper()
                a_lines.append(f"  [{sev}] {row['title']}")
                if row.get("summary"):
                    a_lines.append(f"    {str(row['summary'])[:200]}")
            sections.append("\n".join(a_lines))

        # Stock data
        stock = entry.get("stock_data", pd.DataFrame())
        ticker = entry.get("ticker")
        if ticker and not stock.empty:
            s_lines = [f"STOCK DATA — {brand} ({ticker}):"]
            for _, row in stock.iterrows():
                s_lines.append(
                    f"  {row['snapshot_date']}: {row['metric_name']} = {row['metric_value']}"
                )
            sections.append("\n".join(s_lines))

    # Market backdrop
    sections.append("=" * 50)
    sections.append("MARKET BACKDROP")

    mkt = market_data.get("markets", pd.DataFrame())
    if not mkt.empty:
        lines = ["MARKET DATA:"]
        for _, row in mkt.iterrows():
            chg = row.get("change", 0) or 0
            pct = row.get("change_percent", "0%")
            lines.append(f"  {row['symbol']}: ${row['price']:.2f} ({chg:+.2f}, {pct})")
        sections.append("\n".join(lines))

    comm = market_data.get("commodities", pd.DataFrame())
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

    econ = market_data.get("economic_indicators", pd.DataFrame())
    if not econ.empty:
        lines = ["ECONOMIC INDICATORS:"]
        for _, row in econ.iterrows():
            lines.append(
                f"  {row['metric_name']}: {row['metric_value']:.2f} "
                f"(as of {row['snapshot_date']})"
            )
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# 6. Charts
# ---------------------------------------------------------------------------

def build_trending_charts(top_brands, market_data):
    """Stage 6: Build QuickChart.io URLs for trending edition visuals."""
    charts = {}

    # 1. Trending Leaderboard (horizontal bar: brand → trending score)
    if top_brands:
        labels = [e["brand"] for e in reversed(top_brands)]
        scores = [e["trending_score"] for e in reversed(top_brands)]
        palette = ["#1976D2", "#E65100", "#7B1FA2", "#00897B", "#2E7D32"]
        colors = [palette[i % len(palette)] for i in range(len(labels))]

        config = {
            "type": "horizontalBar",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": "Trending Score",
                    "data": scores,
                    "backgroundColor": colors,
                }],
            },
            "options": {
                "title": {"display": True, "text": "Trending Brands — Score",
                          "fontSize": 16},
                "legend": {"display": False},
                "scales": {
                    "xAxes": [{"ticks": {"beginAtZero": True, "max": 1.0}}],
                },
            },
        }
        charts["trending_leaderboard"] = _quickchart_url(config)

    # 2. VLDS Comparison (grouped bar: V/L/D/S for top brands)
    if top_brands:
        brand_labels = [e["brand"] for e in top_brands]
        v_data = [e["vlds"].get("velocity", 0) for e in top_brands]
        l_data = [e["vlds"].get("longevity", 0) for e in top_brands]
        d_data = [e["vlds"].get("density", 0) for e in top_brands]
        s_data = [e["vlds"].get("scarcity", 0) for e in top_brands]

        config = {
            "type": "bar",
            "data": {
                "labels": brand_labels,
                "datasets": [
                    {"label": "Velocity", "data": v_data, "backgroundColor": "#1976D2"},
                    {"label": "Longevity", "data": l_data, "backgroundColor": "#E65100"},
                    {"label": "Density", "data": d_data, "backgroundColor": "#7B1FA2"},
                    {"label": "Scarcity", "data": s_data, "backgroundColor": "#00897B"},
                ],
            },
            "options": {
                "title": {"display": True, "text": "VLDS Comparison",
                          "fontSize": 16},
                "legend": {"position": "bottom"},
                "scales": {
                    "yAxes": [{"ticks": {"beginAtZero": True, "max": 1.0}}],
                },
            },
        }
        charts["vlds_comparison"] = _quickchart_url(config, width=600, height=320)

    # 3. Market Performance (horizontal bar: SPY/QQQ/DIA)
    mkt = market_data.get("markets", pd.DataFrame())
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

    return charts


# ---------------------------------------------------------------------------
# 7. Newsletter Generation
# ---------------------------------------------------------------------------

TRENDING_SYSTEM_PROMPT = """You are the editor of The Mood Report — a data intelligence newsletter that measures sentiment before the markets price it in.

This is the TRENDING edition — a weekly deep dive into the brands and companies dominating the cultural conversation.

Your voice: Authoritative but accessible. Data-first. You don't predict — you measure. You let the numbers speak and point out what they're saying. Think Bloomberg Terminal meets morning coffee.

RULES:
1. Every claim must be grounded in the data provided. No training data. No made-up statistics.
2. Use the VLDS framework data for each brand. Explain what velocity, longevity, density, and scarcity mean in context.
3. Connect brand trends to the market backdrop when meaningful.
4. Keep it under 1,500 words. Dense, not padded.
5. Empathy scores: 0.04 = cold/hostile, 0.10 = detached/neutral, 0.30 = warm, 0.30+ = highly empathetic.
6. The leaderboard table MUST use exact numbers from the data.
7. Each brand section should tell a story — not just list data points. Why is this brand trending? What does it mean?

OUTPUT FORMAT — use this exact structure with markdown:

# THE MOOD REPORT: TRENDING
*Week of [date range]*

## [PROVOCATIVE HEADLINE]
Write a sharp, attention-grabbing headline (8-12 words) that captures the week's brand landscape. Think: "Five Companies That Owned the Conversation This Week" but edgier.

## THIS WEEK'S RISERS
| Rank | Brand | Mentions | Velocity | Trending Score |
|------|-------|----------|----------|----------------|
[Table with exact data for all ranked brands]

## #1: [BRAND NAME]
### The Numbers
[VLDS data, mention count, empathy, momentum — formatted clearly]
### The Conversation
[Top headlines, emotion breakdown, what people are saying — paint the picture]
### The Strategic Play
[Actionable implications — who benefits, who's at risk, what to do about it]

[Repeat ## #2, ## #3, etc. for remaining brands]

## THE PATTERN
[Cross-brand analysis: what connects these trending brands? What does it say about the cultural/market moment? 2-3 paragraphs. This is the editorial meat — find the thread that ties them together.]

## WHAT TO WATCH NEXT WEEK
[2-3 forward-looking items grounded in data. Not predictions — signals worth monitoring.]

## WHAT TO DO ABOUT IT
[2-3 concrete, actionable items. Be specific — tie each to a data point. End with one sentence that makes the reader feel like they have an edge.]

---
*The Mood Report: Trending is powered by Moodlight Intelligence. Data is measured, not predicted.*
"""

TRENDING_X_PROMPT = """Condense this trending brand newsletter into a 3-4 tweet thread (280 chars each).
Tweet 1: "THE MOOD REPORT: TRENDING | Week of [dates]" + the #1 trending brand and its score.
Tweet 2: The most surprising brand on the list or the most interesting pattern.
Tweet 3: One strategic takeaway or forward look.
Tweet 4: "Full issue → [link]"
No hashtags. No emojis. Data speaks for itself.

Output each tweet on its own line, separated by a blank line. Number them 1/, 2/, etc."""


def generate_trending_newsletter(context):
    """Generate the trending edition newsletter via Claude Opus."""
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        system=TRENDING_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                "Generate this week's Trending edition of The Mood Report "
                "using this data:\n\n" + context
            ),
        }],
    )
    return response.content[0].text


def generate_trending_x_thread(context, newsletter_md):
    """Generate a condensed X/Twitter thread from the trending edition."""
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=800,
        system=TRENDING_X_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Here is this week's trending newsletter:\n\n{newsletter_md}\n\n"
                f"And the raw data context:\n\n{context}\n\n"
                f"Generate the X thread."
            ),
        }],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# 8. Publishing
# ---------------------------------------------------------------------------

def insert_trending_charts(html, chart_urls):
    """Insert chart images into trending edition HTML."""
    if not chart_urls:
        return html

    # Chart key → target section
    chart_placements = [
        ("market_performance", "WHAT TO WATCH NEXT WEEK"),
        ("vlds_comparison", "THIS WEEK'S RISERS"),
        ("trending_leaderboard", "THIS WEEK'S RISERS"),
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


def save_trending_x_thread(thread_text):
    """Save X thread to file."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"mood_report_trending_{date_str}.txt"
    with open(filename, "w") as f:
        f.write(thread_text)
    print(f"  X thread saved to: {filename}")
    return filename


def email_trending_report(newsletter_md, x_thread, chart_urls):
    """Email the trending edition for review."""
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
        newsletter_html = insert_trending_charts(newsletter_html, chart_urls)

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
        <div style="background: #1a1a2e; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
          <h1 style="margin: 0; font-size: 24px;">The Mood Report: Trending</h1>
          <p style="margin: 5px 0 0 0; color: #aaa;">Weekly Brand Intelligence — Draft for Review — {date_str}</p>
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
    msg["Subject"] = f"[Mood Report] Trending Brands — {date_str}"
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
# Main
# ---------------------------------------------------------------------------

def main():
    lookback_days = 7

    print("=" * 60)
    print("THE MOOD REPORT: TRENDING — Weekly Brand Intelligence")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # 1. Connect to DB
    engine = _get_engine()

    # 2. Discover brands
    print("\n[1/8] Discovering brands...")
    all_brands, df_news, df_social = discover_trending_brands(engine, lookback_days)
    if not all_brands:
        print("No brands discovered. Cannot generate report.")
        return

    # 3. Calculate trending scores
    print(f"\n[2/8] Calculating trending scores for {len(all_brands)} brands...")
    top_brands = calculate_trending_scores(all_brands, df_news, df_social, lookback_days)
    if not top_brands:
        print("No brands met minimum thresholds. Cannot generate report.")
        return
    print(f"  Top {len(top_brands)} trending brands:")
    for i, entry in enumerate(top_brands, 1):
        print(f"    #{i}: {entry['brand']} — score={entry['trending_score']:.3f}, "
              f"mentions={entry['mention_count']}, momentum={entry['momentum']:.3f}")

    # 4. Load brand context
    print("\n[3/8] Loading brand context...")
    top_brands = load_brand_context(engine, top_brands, lookback_days)

    # 5. Load market backdrop
    print("\n[4/8] Loading market backdrop...")
    market_data = load_market_backdrop(engine)

    # 6. Build context string
    print("\n[5/8] Building context string...")
    context = build_trending_context(top_brands, market_data, lookback_days)
    print(f"  Context length: {len(context)} chars")

    # 7. Build charts
    print("\n[6/8] Building chart URLs...")
    chart_urls = build_trending_charts(top_brands, market_data)
    print(f"  Charts generated: {list(chart_urls.keys()) if chart_urls else 'none'}")

    # 8. Generate newsletter
    print("\n[7/8] Generating newsletter via Claude Opus...")
    newsletter_md = generate_trending_newsletter(context)
    print(f"  Newsletter length: {len(newsletter_md)} chars")

    # 9. Generate X thread
    print("  Generating X thread...")
    x_thread = generate_trending_x_thread(context, newsletter_md)
    print(f"  Thread length: {len(x_thread)} chars")

    # 10. Publish
    print("\n[8/8] Publishing...")

    # Beehiiv (if configured)
    beehiiv_api_key = os.getenv("BEEHIIV_API_KEY")
    if beehiiv_api_key:
        try:
            from mood_report_publisher import publish_to_beehiiv
            date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
            html = markdown_to_newsletter_html(newsletter_md)
            if chart_urls:
                html = insert_trending_charts(html, chart_urls)
            publish_to_beehiiv(
                html=html,
                title=f"The Mood Report: Trending — {date_str}",
                subtitle="Weekly brand intelligence — who's owning the conversation",
            )
        except Exception as e:
            print(f"  Beehiiv publish failed: {e}")
    else:
        print("  Beehiiv not configured. Skipping.")

    # Save X thread
    save_trending_x_thread(x_thread)

    # Email
    email_trending_report(newsletter_md, x_thread, chart_urls)

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
