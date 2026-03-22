#!/usr/bin/env python
"""
generate_brief.py
Generates an executive intelligence brief using Claude AI
"""

import os
import pandas as pd
from datetime import datetime, timezone
from anthropic import Anthropic
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_cancelled_subscriber_emails():
    """Get emails of users who cancelled their subscription.
    Only these emails will be excluded from the daily brief.
    Active tiers (monthly, annually) always pass through regardless of Stripe status."""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return None  # No database — send to full EMAIL_RECIPIENT list
    try:
        from sqlalchemy import create_engine, text
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT email FROM users
                WHERE tier NOT IN ('monthly', 'annually', 'professional', 'enterprise')
                  AND username != 'admin'
            """))
            emails = {row[0].lower() for row in result.fetchall()}
            print(f"Cancelled/inactive subscribers (will be excluded): {emails}")
            return emails
    except Exception as e:
        print(f"Could not query subscriber status: {e}")
        return None  # Send to full EMAIL_RECIPIENT list

def _build_brief_html(brief_text):
    """Convert brief plain text to styled HTML matching alert email format."""
    import re

    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

    # Parse sections from the brief text
    sections_html = []
    current_section = None
    current_lines = []

    for line in brief_text.split("\n"):
        # Detect section headers (ALL CAPS lines, optionally with colons or markdown #)
        stripped = line.strip()
        # Strip leading markdown hashes: "## KEY THREATS" → "KEY THREATS"
        header_text = re.sub(r'^#{1,4}\s*', '', stripped).strip()
        if (header_text and re.match(r'^[A-Z][A-Z &\-/]+:?\s*$', header_text)
                and len(header_text) > 3 and header_text not in ("DATA:", "FORMAT:")):
            # Save previous section
            if current_section:
                sections_html.append(_format_brief_section(current_section, current_lines))
            current_section = header_text.rstrip(":")
            current_lines = []
        elif header_text.startswith("DAILY INTELLIGENCE BRIEF") or re.match(r'^\d+\s+\w+\s+\d{4}', header_text):
            # Skip the title line and date subtitle — we render our own header
            continue
        elif stripped.startswith("===") or stripped.startswith("---"):
            continue
        else:
            current_lines.append(line)

    # Save last section
    if current_section:
        sections_html.append(_format_brief_section(current_section, current_lines))
    elif current_lines:
        # No sections detected — render as single block
        content = "\n".join(current_lines).strip()
        content_html = _markdown_to_html(content)
        sections_html.append(
            f'<div style="margin: 15px 0;">'
            f'<p style="font-size: 15px; color: #333; line-height: 1.6;">{content_html}</p>'
            f'</div>'
        )

    body = "\n".join(sections_html)

    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
        <div style="border-left: 4px solid #1976D2; padding-left: 15px; margin-bottom: 20px;">
          <span style="background: #1976D2; color: white; padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: bold;">
            INTELLIGENCE BRIEF
          </span>
          <h2 style="margin: 10px 0 5px 0; color: #333;">Daily Intelligence Brief</h2>
          <p style="color: #666; margin: 0;">{date_str}</p>
        </div>

        {body}

        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">
          Moodlight Intelligence Platform — Executive Brief<br>
          <a href="https://moodlight.app" style="color: #1976D2;">View Dashboard</a>
        </p>
      </body>
    </html>
    """


def _format_brief_section(title, lines):
    """Format a single section of the brief as styled HTML."""
    content = "\n".join(lines).strip()
    if not content:
        return ""

    # Section color coding
    section_colors = {
        "KEY THREATS": "#DC143C",
        "WATCH LIST": "#FFB300",
        "EMERGING PATTERNS": "#1976D2",
        "FORWARD LOOK": "#7B1FA2",
        "RECOMMENDED ACTIONS": "#2E7D32",
        "WHAT NOBODY'S WATCHING": "#DC143C",
        "WHAT CHANGED IN 12 HOURS": "#FFB300",
        "THE EMOTIONAL UNDERCURRENT": "#7B1FA2",
        "WHAT THE MONEY SAYS": "#1976D2",
        "KNOWN SITUATIONS": "#546E7A",
        "ONE PREDICTION": "#2E7D32",
    }
    color = section_colors.get(title, "#1976D2")

    content_html = _markdown_to_html(content)

    return (
        f'<div style="margin: 20px 0;">'
        f'<div style="margin-bottom: 10px;">'
        f'<span style="background: {color}; color: white; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: bold; letter-spacing: 0.5px;">{title}</span>'
        f'</div>'
        f'<div style="background: #fafafa; padding: 12px 15px; border-radius: 8px; border-left: 3px solid {color};">'
        f'<div style="font-size: 15px; color: #333; line-height: 1.6;">{content_html}</div>'
        f'</div>'
        f'</div>'
    )


def _markdown_to_html(text):
    """Convert basic markdown patterns to HTML for email rendering."""
    import re

    # Bold: **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    # Numbered list items: "1. text" → styled list
    text = re.sub(
        r'^(\d+)\.\s+(.+)$',
        r'<div style="margin: 6px 0; padding-left: 8px;">'
        r'<span style="color: #999; font-size: 13px;">\1.</span> \2</div>',
        text,
        flags=re.MULTILINE,
    )

    # Bullet items: "- text" → styled bullets
    text = re.sub(
        r'^[-•]\s+(.+)$',
        r'<div style="margin: 4px 0; padding-left: 12px;">'
        r'<span style="color: #999;">&#8226;</span> \1</div>',
        text,
        flags=re.MULTILINE,
    )

    # Tags: [NEW], [ONGOING], [HIGH CONFIDENCE], etc.
    def _style_tag(m):
        tag = m.group(1)
        if tag in ("NEW",):
            return f'<span style="background: #E8F5E9; color: #2E7D32; padding: 1px 6px; border-radius: 3px; font-size: 11px; font-weight: bold;">{tag}</span>'
        elif tag in ("ONGOING",):
            return f'<span style="background: #FFF3E0; color: #E65100; padding: 1px 6px; border-radius: 3px; font-size: 11px; font-weight: bold;">{tag}</span>'
        elif "CONFIDENCE" in tag:
            return f'<span style="background: #E3F2FD; color: #1565C0; padding: 1px 6px; border-radius: 3px; font-size: 11px;">{tag}</span>'
        elif tag in ("IMMEDIATE", "SHORT-TERM", "MONITOR"):
            return f'<span style="background: #F3E5F5; color: #7B1FA2; padding: 1px 6px; border-radius: 3px; font-size: 11px; font-weight: bold;">{tag}</span>'
        return f'<span style="background: #ECEFF1; color: #546E7A; padding: 1px 6px; border-radius: 3px; font-size: 11px;">{tag}</span>'

    text = re.sub(r'\[([A-Z][A-Z \-]+?)\]', _style_tag, text)

    # Inline labels: What:, So What:, Data points:, Projection:
    def _style_inline_label(m):
        label = m.group(1)
        return (
            f'<span style="background: #ECEFF1; color: #37474F; padding: 1px 6px; border-radius: 3px; '
            f'font-size: 11px; font-weight: bold;">{label}</span>'
        )
    text = re.sub(r'\b(What|So What|Data points?|Projection):', _style_inline_label, text)

    # Arrows
    text = text.replace("↑", '<span style="color: #DC143C;">&#8593;</span>')
    text = text.replace("↓", '<span style="color: #2E7D32;">&#8595;</span>')

    # Preserve paragraph breaks
    text = re.sub(r'\n\s*\n', '</p><p style="margin: 8px 0;">', text)
    text = text.replace("\n", "<br>")

    return text


def _get_subscriber_emails_for_brief():
    """Get all subscriber emails from the users table for brief delivery."""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return []
    try:
        from sqlalchemy import create_engine, text
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT u.email FROM users u
                LEFT JOIN user_preferences p ON u.username = p.username
                WHERE u.email IS NOT NULL AND u.email != ''
                  AND COALESCE(p.digest_daily, TRUE) = TRUE
            """))
            return [row[0] for row in result.fetchall()]
    except Exception as e:
        print(f"Could not query subscriber emails: {e}")
        return []


def send_email_brief(brief_text):
    """Send intelligence brief via email to each recipient individually.
    Cancelled subscribers are filtered out; everyone else passes through."""
    sender = os.getenv("EMAIL_ADDRESS")
    recipients_str = os.getenv("EMAIL_RECIPIENT", "")
    password = os.getenv("EMAIL_PASSWORD")

    if not all([sender, password]):
        print("Email credentials not configured. Skipping email.")
        return False

    # Build recipient list: DB subscribers + env var, deduplicated
    env_recipients = [r.strip() for r in recipients_str.split(",") if r.strip()]
    db_subscribers = _get_subscriber_emails_for_brief()
    all_emails = set(e.lower() for e in env_recipients)
    all_emails.update(e.lower() for e in db_subscribers if e)

    if not all_emails:
        print("No recipients found (DB or env var). Skipping email.")
        return False

    # Remove cancelled subscribers
    cancelled_emails = get_cancelled_subscriber_emails()
    if cancelled_emails:
        all_emails -= cancelled_emails

    recipients = list(all_emails)
    if not recipients:
        print("All recipients are cancelled. Skipping email.")
        return False

    print(f"Sending brief to {len(recipients)} active recipient(s)")

    # Convert brief text to styled HTML matching alert email format
    html = _build_brief_html(brief_text)

    success_count = 0
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)

            for recipient in recipients:
                # Create fresh message for each recipient
                msg = MIMEMultipart('alternative')
                msg['Subject'] = f'[Moodlight Brief] \U0001f4ca Daily Intelligence Brief — {datetime.now(timezone.utc).strftime("%B %d, %Y")}'
                msg['From'] = sender
                msg['To'] = recipient  # Only this recipient visible
                msg.attach(MIMEText(html, 'html'))

                try:
                    server.send_message(msg)
                    print(f"✅ Email sent to {recipient}")
                    success_count += 1
                except Exception as e:
                    print(f"❌ Email failed for {recipient}: {e}")

        return success_count > 0
    except Exception as e:
        print(f"❌ Email connection failed: {e}")
        return False

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def load_recent_data():
    """Load last 24 hours of intelligence data"""
    # Try PostgreSQL first
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        try:
            from sqlalchemy import create_engine
            db_url = db_url.replace("postgres://", "postgresql://", 1)
            engine = create_engine(db_url)
            from sqlalchemy import text as sql_text
            cutoff = datetime.now(timezone.utc) - pd.Timedelta(days=7)
            cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
            df = pd.read_sql(sql_text("SELECT * FROM news_scored WHERE created_at >= :cutoff"), engine, params={"cutoff": cutoff_str})
            if not df.empty:
                print(f"✅ Loaded {len(df)} rows from PostgreSQL")
                df['created_at'] = pd.to_datetime(df['created_at'], utc=True, errors='coerce')
                return df
        except Exception as e:
            print(f"DB error: {e}")
    # Fallback to CSV
    df = pd.read_csv("news_scored.csv")
    df['created_at'] = pd.to_datetime(df['created_at'], utc=True, errors='coerce')

    # Last 7 days
    cutoff = datetime.now(timezone.utc) - pd.Timedelta(days=7)
    recent = df[df['created_at'] >= cutoff]

    return recent


def load_social_data():
    """Load social media data for sentiment analysis"""
    cutoff = datetime.now(timezone.utc) - pd.Timedelta(days=7)
    # Try PostgreSQL first
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        try:
            from sqlalchemy import create_engine
            db_url = db_url.replace("postgres://", "postgresql://", 1)
            engine = create_engine(db_url)
            from sqlalchemy import text as sql_text
            cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
            df = pd.read_sql(sql_text("SELECT * FROM social_scored WHERE created_at >= :cutoff"), engine, params={"cutoff": cutoff_str})
            if not df.empty:
                df['created_at'] = pd.to_datetime(df['created_at'], utc=True, errors='coerce')
                print(f"✅ Loaded {len(df)} social posts from PostgreSQL")
                return df
        except Exception as e:
            print(f"Social DB error: {e}")
    # Fallback to CSV
    if os.path.exists("social_scored.csv"):
        try:
            df = pd.read_csv("social_scored.csv")
            df['created_at'] = pd.to_datetime(df['created_at'], utc=True, errors='coerce')
            recent = df[df['created_at'] >= cutoff]
            if not recent.empty:
                print(f"✅ Loaded {len(recent)} social posts from CSV")
                return recent
        except Exception as e:
            print(f"Social CSV error: {e}")
    print("⚠️ No social data available")
    return pd.DataFrame()

def _get_db_engine():
    """Get a shared DB engine."""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        return None
    from sqlalchemy import create_engine, text as sql_text
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url)


def prepare_intelligence_context(news_df, social_df=None):
    """Prepare comprehensive context from ALL data sources for AI briefing."""

    now = datetime.now(timezone.utc)
    cutoff_48h = now - pd.Timedelta(hours=48)
    engine = _get_db_engine()

    # ── 1. NEWS HEADLINES (fresh vs background) ──
    fresh_df = news_df[news_df['created_at'] >= cutoff_48h] if 'created_at' in news_df.columns else news_df
    fresh_count = len(fresh_df)

    critical_fresh = fresh_df[fresh_df['intensity'] >= 4].sort_values('created_at', ascending=False) if 'created_at' in fresh_df.columns else fresh_df[fresh_df['intensity'] >= 4]
    critical_lines = []
    for _, row in critical_fresh.head(15).iterrows():
        date_str = row['created_at'].strftime('%Y-%m-%d %H:%M') if pd.notna(row.get('created_at')) else 'unknown'
        critical_lines.append(f"  [{date_str}] [{row.get('country', '?')}] (intensity: {row.get('intensity', '?')}) {row.get('text', '')[:300]}")
    critical_block = "\n".join(critical_lines) if critical_lines else "  No critical articles in last 48 hours."

    older_df = news_df[news_df['created_at'] < cutoff_48h] if 'created_at' in news_df.columns else pd.DataFrame()
    ongoing_lines = []
    if not older_df.empty:
        older_critical = older_df[older_df['intensity'] >= 4].sort_values('created_at', ascending=False)
        for _, row in older_critical.head(5).iterrows():
            date_str = row['created_at'].strftime('%Y-%m-%d') if pd.notna(row.get('created_at')) else 'unknown'
            ongoing_lines.append(f"  [{date_str}] [{row.get('country', '?')}] {row.get('text', '')[:200]}")
    ongoing_block = "\n".join(ongoing_lines) if ongoing_lines else "  None."

    topic_counts = news_df['topic'].value_counts().head(5)
    topic_intensity = news_df.groupby('topic')['intensity'].mean().sort_values(ascending=False).head(5)
    country_counts = fresh_df['country'].value_counts().head(5) if not fresh_df.empty else news_df['country'].value_counts().head(5)

    context = f"""
SIGNAL SOURCE 1: NEWS HEADLINES
==========================================
Fresh articles (last 48 hours): {fresh_count}
Background articles (48h-7d): {len(news_df) - fresh_count}

TOP TOPICS BY VOLUME: {topic_counts.to_string()}
HIGHEST INTENSITY: {topic_intensity.round(2).to_string()}
GEOGRAPHIC SPREAD: {country_counts.to_string()}

FRESH CRITICAL ARTICLES (48h, newest first):
{critical_block}

OLDER ONGOING (context only):
{ongoing_block}
"""

    # ── 2. SOCIAL PULSE (X/Twitter + NewsAPI social) ──
    if social_df is not None and not social_df.empty:
        social_topics = social_df['topic'].value_counts().head(5)
        emotion_dist = social_df['emotion_top_1'].value_counts().head(8)
        empathy_dist = social_df['empathy_label'].value_counts()
        topic_empathy = social_df.groupby('topic')['empathy_score'].mean().sort_values(ascending=False).head(5)

        if 'engagement' in social_df.columns:
            top_engagement = social_df.nlargest(5, 'engagement')[['text', 'engagement', 'emotion_top_1', 'source']]
        else:
            top_engagement = social_df.head(5)[['text', 'emotion_top_1', 'source']]

        context += f"""
SIGNAL SOURCE 2: SOCIAL MEDIA (X/Twitter + NewsAPI)
==========================================
Total posts analyzed: {len(social_df)}

TRENDING SOCIAL TOPICS: {social_topics.to_string()}
DOMINANT EMOTIONS: {emotion_dist.to_string()}
EMPATHY TEMPERATURE: {empathy_dist.to_string()}
CULTURAL HEAT BY TOPIC: {topic_empathy.round(4).to_string()}

HIGH-ENGAGEMENT CONTENT:
{top_engagement.to_string()}
"""

    # ── 3. MARKET INDICES & SENTIMENT ──
    if engine:
        try:
            from sqlalchemy import text as sql_text
            mkt_df = pd.read_sql(sql_text("""
                SELECT symbol, name, price, change, change_percent, volume, market_sentiment, timestamp
                FROM markets
                WHERE timestamp::timestamptz >= NOW() - INTERVAL '24 hours'
                ORDER BY timestamp DESC
            """), engine)
            if not mkt_df.empty:
                latest = mkt_df.drop_duplicates(subset=['symbol'], keep='first')
                mkt_lines = []
                for _, row in latest.iterrows():
                    try:
                        chg = float(row.get('change_percent', 0) or 0)
                        price = float(row.get('price', 0) or 0)
                    except (ValueError, TypeError):
                        chg, price = 0, 0
                    direction = "UP" if chg > 0 else "DOWN" if chg < 0 else "FLAT"
                    mkt_lines.append(f"  {row['name']} ({row['symbol']}): ${price:,.2f} {direction} {abs(chg):.2f}%")
                try:
                    avg_sentiment = latest['market_sentiment'].astype(float).mean()
                except (ValueError, TypeError):
                    avg_sentiment = 0.5
                mood = "BULLISH" if avg_sentiment > 0.55 else "BEARISH" if avg_sentiment < 0.45 else "NEUTRAL"
                context += f"""
SIGNAL SOURCE 3: GLOBAL MARKETS
==========================================
Overall market mood: {mood} (sentiment: {avg_sentiment:.2f}/1.0)
{chr(10).join(mkt_lines)}
"""
                print(f"  Added {len(latest)} market indices to context")
        except Exception as e:
            print(f"  Could not load market data: {e}")

    # ── 4. BRAND STOCK SIGNALS ──
    if engine:
        try:
            from sqlalchemy import text as sql_text
            stock_df = pd.read_sql(sql_text("""
                SELECT scope_name AS brand, metric_name, metric_value, snapshot_date
                FROM metric_snapshots
                WHERE scope = 'brand' AND snapshot_date >= CURRENT_DATE - INTERVAL '3 days'
                ORDER BY snapshot_date DESC
            """), engine)
            if not stock_df.empty:
                stock_lines = []
                for brand in stock_df['brand'].unique():
                    brand_data = stock_df[stock_df['brand'] == brand]
                    latest_price = brand_data[brand_data['metric_name'] == 'stock_price']
                    latest_change = brand_data[brand_data['metric_name'] == 'stock_change_pct']
                    latest_vol = brand_data[brand_data['metric_name'] == 'stock_intraday_volatility']
                    price = latest_price.iloc[0]['metric_value'] if not latest_price.empty else None
                    change = latest_change.iloc[0]['metric_value'] if not latest_change.empty else None
                    volatility = latest_vol.iloc[0]['metric_value'] if not latest_vol.empty else None
                    parts = [f"{brand}:"]
                    if price is not None:
                        parts.append(f"${price:.2f}")
                    if change is not None:
                        direction = "up" if change > 0 else "down"
                        parts.append(f"({direction} {abs(change):.2f}%)")
                    if volatility is not None and volatility > 1.5:
                        parts.append(f"[HIGH VOLATILITY: {volatility:.2f}%]")
                    stock_lines.append("  " + " ".join(parts))
                context += f"""
SIGNAL SOURCE 4: BRAND STOCKS (Watchlist)
==========================================
{chr(10).join(stock_lines)}
"""
                print(f"  Added {len(stock_df['brand'].unique())} brand stock signals to context")
        except Exception as e:
            print(f"  Could not load brand stocks: {e}")

    # ── 5. ECONOMIC INDICATORS ──
    try:
        from db_helper import load_economic_data
        econ_df = load_economic_data(days=7)
        if not econ_df.empty:
            latest = econ_df.sort_values("snapshot_date").groupby("metric_name").last().reset_index()
            econ_lines = []
            for _, row in latest.iterrows():
                econ_lines.append(f"  {row['metric_name']}: {row['metric_value']:.2f}")
            context += f"""
SIGNAL SOURCE 5: ECONOMIC INDICATORS
==========================================
{chr(10).join(econ_lines)}
"""
    except Exception:
        pass

    # ── 6. COMMODITY PRICES ──
    try:
        from db_helper import load_commodity_data
        comm_df = load_commodity_data(days=7)
        if not comm_df.empty:
            price_df = comm_df[comm_df["metric_name"] == "price"]
            change_df = comm_df[comm_df["metric_name"] == "daily_change_pct"]
            if not price_df.empty:
                latest_price = price_df.sort_values("snapshot_date").groupby("scope_name").last().reset_index()
                latest_change = change_df.sort_values("snapshot_date").groupby("scope_name").last().reset_index() if not change_df.empty else pd.DataFrame()
                comm_lines = []
                for _, row in latest_price.iterrows():
                    line = f"  {row['scope_name']}: ${row['metric_value']:.2f}"
                    if not latest_change.empty:
                        chg_row = latest_change[latest_change['scope_name'] == row['scope_name']]
                        if not chg_row.empty:
                            chg = chg_row.iloc[0]['metric_value']
                            line += f" ({'up' if chg > 0 else 'down'} {abs(chg):.2f}%)"
                    comm_lines.append(line)
                context += f"""
SIGNAL SOURCE 6: COMMODITY PRICES
==========================================
{chr(10).join(comm_lines)}
"""
    except Exception:
        pass

    # ── 7. PREDICTION MARKETS (Polymarket) ──
    try:
        from polymarket_helper import fetch_polymarket_markets, filter_markets_by_topic
        markets = fetch_polymarket_markets(limit=15, min_volume=50000)
        if markets:
            poly_lines = []
            for m in markets[:10]:
                poly_lines.append(f"  \"{m['question']}\" — {m['yes_odds']:.0f}% YES (${m['volume']:,.0f} wagered)")
            context += f"""
SIGNAL SOURCE 7: PREDICTION MARKETS (Polymarket — real money bets)
==========================================
These represent where people are putting REAL MONEY on outcomes. Divergence between prediction
market odds and social sentiment/news tone is a powerful signal.

{chr(10).join(poly_lines)}
"""
            print(f"  Added {len(markets)} Polymarket signals to context")
    except Exception as e:
        print(f"  Could not load Polymarket data: {e}")

    # ── 8. PREDICTIVE SIGNALS (Moodlight's own detectors) ──
    if engine:
        try:
            from sqlalchemy import text as sql_text
            cutoff_pred = (now - pd.Timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
            pred_df = pd.read_sql(
                sql_text("""
                    SELECT alert_type, severity, title, summary, brand, topic, timestamp
                    FROM alerts
                    WHERE alert_type LIKE 'predictive_%%'
                      AND timestamp >= :cutoff
                    ORDER BY timestamp DESC
                    LIMIT 20
                """),
                engine,
                params={"cutoff": cutoff_pred},
            )
            if not pred_df.empty:
                pred_lines = []
                for _, row in pred_df.iterrows():
                    scope = f" [{row['brand']}]" if row.get("brand") else f" [{row['topic']}]" if row.get("topic") else ""
                    sev = row.get("severity", "info").upper()
                    pred_lines.append(f"  [{sev}]{scope} {row['title']}: {row['summary']}")
                context += f"""
SIGNAL SOURCE 8: MOODLIGHT PREDICTIVE SIGNALS (last 48h)
==========================================
Statistical trends detected by Moodlight's 7-day regression + momentum engine.
{chr(10).join(pred_lines)}
"""
                print(f"  Added {len(pred_df)} predictive signals to context")
        except Exception as e:
            print(f"  Could not load predictive signals: {e}")

    # ── 9. TOPIC INTELLIGENCE (VLDS deltas, staleness, white space) ──
    if engine:
        try:
            from topic_intelligence import compute_topic_intelligence, format_intelligence_context
            topics = compute_topic_intelligence(engine, output_type="brief")
            if topics:
                context += f"""

SIGNAL SOURCE 9: TOPIC INTELLIGENCE (VLDS deltas + staleness analysis)
==========================================
{format_intelligence_context(topics)}
"""
                print(f"  Added topic intelligence for {len(topics)} topics")
        except Exception as e:
            print(f"  Could not load topic intelligence: {e}")

    # ── 10. SIGNAL TRACK RECORD ──
    if engine:
        try:
            sig_df = pd.read_sql(sql_text("""
                SELECT alert_type,
                       COUNT(*) AS total_signals,
                       COUNT(spy_change_1d) AS has_1d,
                       AVG(spy_change_1d) AS avg_spy_1d,
                       SUM(CASE WHEN spy_change_1d > 0 THEN 1 ELSE 0 END)::float
                           / NULLIF(COUNT(spy_change_1d), 0) AS up_rate_1d
                FROM signal_log
                GROUP BY alert_type
                ORDER BY total_signals DESC
            """), engine)
            if not sig_df.empty:
                sig_lines = []
                for _, row in sig_df.iterrows():
                    up_rate = f"{row['up_rate_1d']*100:.0f}%" if pd.notna(row.get("up_rate_1d")) else "N/A"
                    avg_1d = f"{row['avg_spy_1d']:+.2f}%" if pd.notna(row.get("avg_spy_1d")) else "N/A"
                    sig_lines.append(
                        f"  {row['alert_type']}: {int(row['total_signals'])} signals, "
                        f"SPY up rate: {up_rate}, avg 1d move: {avg_1d}"
                    )
                context += f"""

SIGNAL SOURCE 10: MOODLIGHT SIGNAL TRACK RECORD
==========================================
How our predictive signals have performed historically:
{chr(10).join(sig_lines)}
"""
                print(f"  Added signal track record ({len(sig_df)} alert types)")
        except Exception as e:
            print(f"  Could not load signal track record: {e}")

    return context

def generate_brief(context):
    """Generate executive brief using Claude AI — insight-driven, not headline-driven."""

    prompt = f"""Based on the following data from 9 signal sources, write today's intelligence brief.

You have access to: news headlines, social media sentiment, global market indices, brand stock data,
economic indicators, commodity prices, Polymarket prediction markets, Moodlight's predictive signals,
and topic intelligence (VLDS scores with 24h deltas showing what changed).

CRITICAL RULES:
1. EVERY SECTION must contain at least one insight that REQUIRES multiple signal sources to produce.
   If a human could write it from reading headlines alone, it doesn't belong. Cross-reference signals.
2. DO NOT lead with the biggest headline. Lead with the thing nobody else sees.
3. Topics marked as STALE in the Topic Intelligence section must NOT lead any section unless there's
   a measurable delta (velocity change, empathy shift, prediction market move) proving something new happened.
4. When prediction markets disagree with social sentiment or news tone, that divergence IS the story.
5. When empathy shifts (up or down) on a topic, explain what that means for real people's behavior.
6. Commodity and market data must be connected to HUMAN impact — not just reported as numbers.

FORMAT:

WHAT NOBODY'S WATCHING
The most important section. 2-3 items from: high-scarcity topics, prediction market signals that
contradict the news narrative, signals hiding in the data that will become headlines in 5-10 days.
For each:
- What's happening (one sentence, plain language)
- Why you should care (connect to the reader's daily life, money, career, or decisions)
- What to do about it (one specific, actionable recommendation)

WHAT CHANGED IN 12 HOURS
2-3 items where the DATA actually shifted — not "this story is still happening" but "this metric
moved." Use VLDS deltas, empathy shifts, market moves, commodity price changes. For each:
- What moved and by how much (in plain language, not scores)
- What that movement means (interpret it — don't just report it)

THE EMOTIONAL UNDERCURRENT
One paragraph. What are people FEELING right now, beneath the headlines? Use social emotion data,
empathy scores, and engagement patterns. Translate this into: what kind of messaging, content, or
action will resonate right now? What won't?

WHAT THE MONEY SAYS
One paragraph combining market indices, brand stocks, commodity prices, AND prediction market odds.
Where is real money flowing? What are bettors saying vs. what headlines are saying?
If there's a divergence between market bets and public sentiment — that's the lead.

KNOWN SITUATIONS
ONLY include ongoing stories if there's a measurable new data point (not just another headline).
2-3 bullet points max. Each bullet: what's new (not what's ongoing), one sentence.

ONE PREDICTION
One specific, time-bound, falsifiable prediction grounded in converging signals from at least
3 different data sources. State what you expect, by when, and which signals support it.

STRICT FORMATTING RULES:
- Section headers: ALL CAPS, no colons
- Write like a smart, articulate friend — not an analyst, not a news anchor
- No jargon. No scores. No "VLDS" or "empathy 0.04" in the output. Translate everything into
  what it means for the reader
- Tags: [NEW] or [ONGOING] for Known Situations only. Confidence tags: [HIGH CONFIDENCE],
  [MODERATE CONFIDENCE], [LIMITED CONFIDENCE]
- Target 700-900 words. Every sentence must earn its place.

DATA:
{context}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3000,
        system="""You write intelligence briefs that sound like a brilliant friend explaining the world over coffee. You're direct, opinionated, and insightful — never dry, never jargon-heavy, never "analyst voice."

Your superpower: you see connections between signals that nobody else has access to. You have social sentiment data, prediction market odds, market indices, commodity prices, brand stock movements, economic indicators, AND cultural velocity/density/scarcity scores. Most analysts have one or two of these. You have all nine. USE THEM TOGETHER.

ABSOLUTE RULES:
- Your ONLY sources of truth are the data provided. Do NOT inject facts from training data.
- Never report a number without explaining what it means for real people.
- Never describe a trend without saying what to do about it.
- When data sources contradict each other (e.g., prediction markets say one thing, social sentiment says another), that contradiction IS the insight. Lead with it.
- If a topic has been in every brief for a week, DO NOT INCLUDE IT unless you can point to a specific data change. "Still happening" is not insight.

EMPATHY SCORE INTERPRETATION:
Raw empathy scores cluster 0.03-0.15 (GoEmotions model). 0.04 = neutral, 0.10 = warm, 0.30+ = highly empathetic.
A score of 0.06 is NORMAL. Do not describe it as "near-zero." Instead, describe what the emotional TONE tells you about how people are processing a story — are they numb? Engaged? Hostile? Compassionate?
Never show raw scores to the reader. Translate into human feelings.""",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text

def main():
    print("=" * 60)
    print("GENERATING EXECUTIVE INTELLIGENCE BRIEF")
    print("=" * 60)
    print()

    news_df = load_recent_data()
    social_df = load_social_data()

    if len(news_df) == 0 and len(social_df) == 0:
        print("No recent data available for briefing.")
        return

    print(f"Analyzing {len(news_df)} news articles + {len(social_df)} social posts...")
    print()

    context = prepare_intelligence_context(news_df, social_df)
    brief = generate_brief(context)

    print(brief)
    print()
    print("=" * 60)

    # Log which topics appeared for staleness tracking
    try:
        engine = _get_db_engine()
        if engine:
            from topic_intelligence import log_output_topics
            # Extract topic mentions from the brief text (simple heuristic)
            import re
            known_topics = ["economics", "technology & ai", "sports", "entertainment",
                            "media & journalism", "labor & work", "government",
                            "healthcare & wellbeing", "war", "energy", "climate"]
            mentioned = [t for t in known_topics if t.lower() in brief.lower()]
            if mentioned:
                log_output_topics(engine, "brief", mentioned)
                print(f"  Logged {len(mentioned)} topics to output history")
    except Exception as e:
        print(f"  Could not log output topics (non-fatal): {e}")

    # Save to file
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"intel_brief_{timestamp}.txt"

    with open(filename, 'w') as f:
        f.write(brief)

    print(f"Brief saved to: {filename}")

    # Send email
    send_email_brief(brief)

if __name__ == "__main__":
    main()
