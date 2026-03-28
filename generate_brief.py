#!/usr/bin/env python
"""
generate_brief.py
Generates an executive intelligence brief using Claude AI
"""

import os
import pandas as pd
from datetime import datetime, timezone, timedelta
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
        "WHAT JUST HAPPENED": "#DC143C",
        "WHAT THE MONEY SAYS": "#1976D2",
        "THE THREAD": "#7B1FA2",
        # Legacy section names (backwards compat)
        "WHAT NOBODY'S WATCHING": "#DC143C",
        "WHAT CHANGED IN 12 HOURS": "#FFB300",
        "THE EMOTIONAL UNDERCURRENT": "#7B1FA2",
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

    # Blockquote items: "> text" → styled blockquote blocks
    # Match lines starting with > and all continuation lines until next > or blank line
    def _format_blockquote(m):
        content = m.group(1).strip()
        # Clean up any internal newlines
        content = re.sub(r'\n(?!>)', ' ', content).strip()
        return (
            '<div style="margin: 12px 0; padding: 10px 15px; border-left: 3px solid #DC143C; '
            f'background: #fafafa; font-size: 15px; line-height: 1.6;">{content}</div>'
        )
    text = re.sub(
        r'^>\s*(.+?)(?=\n\s*\n|\n\s*>|\Z)',
        _format_blockquote,
        text,
        flags=re.MULTILINE | re.DOTALL,
    )

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
                msg['Subject'] = f'[Moodlight] \U0001f6a8 What Just Happened — {datetime.now(timezone.utc).strftime("%B %d, %Y")}'
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
    for _, row in critical_fresh.head(20).iterrows():
        date_str = row['created_at'].strftime('%Y-%m-%d %H:%M') if pd.notna(row.get('created_at')) else 'unknown'
        critical_lines.append(f"  [{date_str}] [{row.get('country', '?')}] (intensity: {row.get('intensity', '?')}) {row.get('text', '')[:300]}")
    critical_block = "\n".join(critical_lines) if critical_lines else "  No critical articles in last 48 hours."

    # Also grab notable lower-intensity stories (intensity 2-3) that may contain
    # important contradictions, corporate hypocrisy, or tech developments.
    # These often get scored low on intensity but are high on editorial value.
    notable_fresh = fresh_df[
        (fresh_df['intensity'].between(2, 3))
    ].sort_values('created_at', ascending=False) if 'created_at' in fresh_df.columns else pd.DataFrame()
    notable_lines = []
    if not notable_fresh.empty:
        # Deduplicate by taking first 300 chars as key
        seen = set()
        for _, row in notable_fresh.head(100).iterrows():
            snippet = row.get('text', '')[:80].lower()
            if snippet in seen:
                continue
            seen.add(snippet)
            date_str = row['created_at'].strftime('%Y-%m-%d %H:%M') if pd.notna(row.get('created_at')) else 'unknown'
            notable_lines.append(f"  [{date_str}] [{row.get('topic', '?')}] {row.get('text', '')[:300]}")
            if len(notable_lines) >= 15:
                break

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

    notable_block = "\n".join(notable_lines) if notable_lines else "  None."

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

NOTABLE STORIES (lower intensity but potentially high editorial value):
{notable_block}

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
                # Staleness guard — skip if data is older than 5 days
                latest_date = pd.to_datetime(stock_df["snapshot_date"]).max()
                if latest_date < (datetime.now(timezone.utc) - timedelta(days=5)):
                    print("  Brand stock data is stale (>5 days old) — skipping")
                    stock_df = pd.DataFrame()
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
        econ_df = load_economic_data(days=730)
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
        comm_df = load_commodity_data(days=14)
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

def _load_recent_story_history():
    """Load stories featured in recent briefs (last 3 days) for dedup."""
    try:
        engine = _get_db_engine()
        if not engine:
            return []
        from sqlalchemy import text as sql_text
        with engine.connect() as conn:
            rows = conn.execute(sql_text(
                "SELECT story_key, item_text FROM brief_story_history "
                "WHERE brief_date >= NOW() - INTERVAL '3 days' "
                "ORDER BY brief_date DESC"
            )).fetchall()
        return [{"key": r[0], "text": r[1] or r[0]} for r in rows]
    except Exception as e:
        print(f"  Could not load story history (non-fatal): {e}")
        return []


def _log_brief_stories(brief_text):
    """Extract and log story keys from a generated brief for future dedup."""
    try:
        engine = _get_db_engine()
        if not engine:
            return
        import re
        from sqlalchemy import text as sql_text
        # Extract blockquote items (each starts with >)
        items = re.findall(r'>\s*(.+?)(?=\n\n|\n>|$)', brief_text, re.DOTALL)
        story_keys = []
        for item in items:
            item = item.strip()
            if len(item) < 20:
                continue
            # Extract a short key: first sentence, up to 120 chars
            first_sentence = re.split(r'\.\.|\.\s', item)[0][:120].strip()
            if first_sentence:
                story_keys.append((first_sentence, item[:300]))

        if story_keys:
            with engine.connect() as conn:
                for key, text in story_keys:
                    conn.execute(sql_text(
                        "INSERT INTO brief_story_history (story_key, item_text) VALUES (:key, :text)"
                    ), {"key": key, "text": text})
                conn.commit()
            print(f"  Logged {len(story_keys)} story keys to history")
    except Exception as e:
        print(f"  Could not log story history (non-fatal): {e}")


def _select_stories_with_haiku(news_df, social_df=None):
    """Use Haiku to pre-select the most interesting, diverse stories from the raw data.
    Returns a curated list of stories that would make someone stop scrolling."""

    now = datetime.now(timezone.utc)
    # Use 14h window to avoid repeating stories from previous brief (runs 2x daily, 12h apart)
    cutoff = now - pd.Timedelta(hours=14)
    fresh_df = news_df[news_df['created_at'] >= cutoff] if 'created_at' in news_df.columns else news_df

    # If slim pickings in 14h, expand to 24h
    if len(fresh_df) < 50:
        cutoff = now - pd.Timedelta(hours=24)
        fresh_df = news_df[news_df['created_at'] >= cutoff] if 'created_at' in news_df.columns else news_df

    if fresh_df.empty:
        return ""

    # Sample up to 10 articles per topic to ensure diversity
    topic_samples = []
    seen_snippets = set()
    for topic, group in fresh_df.groupby('topic'):
        # Sort by intensity desc, then recency
        sorted_group = group.sort_values(['intensity', 'created_at'], ascending=[False, False])
        count = 0
        for _, row in sorted_group.iterrows():
            snippet = row.get('text', '')[:60].lower()
            if snippet in seen_snippets or not row.get('text', '').strip():
                continue
            seen_snippets.add(snippet)
            topic_samples.append({
                'topic': topic,
                'text': row.get('text', '')[:250],
                'intensity': row.get('intensity', 0),
            })
            count += 1
            if count >= 10:
                break

    if not topic_samples:
        return ""

    # Pre-filter: remove articles that match previously featured stories
    recent_stories = _load_recent_story_history()
    if recent_stories:
        # Build keyword patterns from history (extract key nouns/names)
        import re as _re
        history_patterns = set()
        for s in recent_stories:
            key = s['key'].lower()
            # Extract distinctive 2-3 word phrases (company + action)
            for pattern in _re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', s['key']):
                if len(pattern) > 4:
                    history_patterns.add(pattern.lower())
            # Also add full key as a matching string
            history_patterns.add(key[:80])

        def _is_repeat(article_text):
            """Check if article matches a previously featured story."""
            text_lower = article_text.lower()
            match_count = sum(1 for p in history_patterns if p in text_lower)
            # If 2+ distinct history patterns match, it's likely a repeat
            return match_count >= 2

        before = len(topic_samples)
        topic_samples = [s for s in topic_samples if not _is_repeat(s['text'])]
        filtered = before - len(topic_samples)
        if filtered > 0:
            print(f"  Pre-filtered {filtered} repeat articles from candidate pool")

    if not topic_samples:
        return ""

    # Add high-engagement social posts
    social_items = []
    if social_df is not None and not social_df.empty:
        fresh_social = social_df[social_df['created_at'] >= cutoff] if 'created_at' in social_df.columns else social_df
        if not fresh_social.empty and 'engagement' in fresh_social.columns:
            top_social = fresh_social.nlargest(20, 'engagement')
            for _, row in top_social.iterrows():
                txt = row.get('text', '')[:250]
                if txt.strip():
                    social_items.append(f"[SOCIAL] [{row.get('topic', '?')}] {txt}")

    # Format for Haiku
    story_lines = []
    for i, s in enumerate(topic_samples):
        story_lines.append(f"{i+1}. [{s['topic']}] {s['text']}")

    social_block = ""
    if social_items:
        social_block = "\n\nSOCIAL MEDIA (high engagement):\n" + "\n".join(social_items[:15])

    # Load recently featured stories for dedup
    recent_stories = _load_recent_story_history()
    dedup_block = ""
    if recent_stories:
        dedup_lines = [f"- {s['key']}" for s in recent_stories[:30]]
        dedup_block = f"""

STORIES ALREADY FEATURED IN RECENT BRIEFS (DO NOT SELECT THESE AGAIN):
{chr(10).join(dedup_lines)}

RULE: If a story from the list above appears in the candidates below, SKIP IT — even if new
articles were published about it. The ONLY exception: if the new article reveals a genuinely
new development (e.g., a company that was "in talks" last brief has now "signed the deal,"
or a conflict that was "escalating" has now produced casualties). Rehashed coverage, opinion
pieces, and follow-up analysis about the SAME event do NOT count as evolution. When in doubt,
skip it and pick something fresh.
"""

    haiku_prompt = f"""You are a story selector for a daily intelligence dispatch. Your job: pick the 15 stories
that would make someone STOP SCROLLING. Not the biggest stories — the most INTERESTING ones.
{dedup_block}
What makes a story interesting:
- A powerful person or company contradicting themselves
- A billion-dollar deal dying or being born
- A cybersecurity breach that could affect millions
- A CEO saying something that exposes what their company actually does
- An absurd juxtaposition (country builds bunkers while talking peace)
- A hidden motive (someone pushing for war because it helps their portfolio)
- Something that affects the reader personally (AI taking jobs, prices rising, security threat)

What is NOT interesting:
- "War continues" without a specific ironic angle
- Market moved X% (unless someone specific benefits or loses)
- Generic policy announcements without contradiction
- Celebrity news without a systemic angle
- Stories that were ALREADY covered in a previous brief (see list above) unless they have
  a genuinely new development — not just new articles about the same event
- PARTISAN stories: anything where the main point is "politician did something bad" or
  "politician said something hypocritical." Political stories are ONLY interesting when
  the contradiction is SYSTEMIC — a government agency contradicting itself, a policy
  producing the opposite of its stated goal, money flowing opposite to stated values.
  "Senator X is a hypocrite" = skip. "The government declared victory while deploying
  more troops" = systemic, keep. If the story reads like opposition research for either
  party, SKIP IT.

CRITICAL: You MUST select stories from at least 6 different topic areas. Do NOT let one topic
dominate. If there are 5 great war stories, pick the 2 best and move on.

From this list, return ONLY the numbers of the 15 most interesting stories, one per line.
Then add a line "---" and list 3-5 stories from the social media section (by topic keyword) if any are stop-scrolling worthy.

NEWS STORIES:
{chr(10).join(story_lines)}
{social_block}
"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": haiku_prompt}]
        )
        selection_text = response.content[0].text.strip()
        print(f"  Haiku story selector returned: {selection_text[:200]}")

        # Parse selected story numbers
        import re
        selected_indices = []
        for line in selection_text.split("\n"):
            line = line.strip()
            if line == "---":
                break
            nums = re.findall(r'\b(\d+)\b', line)
            for n in nums:
                idx = int(n) - 1
                if 0 <= idx < len(topic_samples):
                    selected_indices.append(idx)

        # Build curated context
        curated_lines = []
        for idx in selected_indices:
            s = topic_samples[idx]
            curated_lines.append(f"  [{s['topic']}] {s['text']}")

        curated_block = "\n".join(curated_lines) if curated_lines else "  No stories selected."
        print(f"  Selected {len(curated_lines)} stories across {len(set(topic_samples[i]['topic'] for i in selected_indices))} topics")
        return curated_block

    except Exception as e:
        print(f"  Haiku story selection failed: {e}")
        return ""


def generate_brief(context, curated_stories=""):
    """Generate executive brief using Claude AI — editorial edge, contradictions, irony."""

    # If we have curated stories from Haiku, make them prominent
    curated_section = ""
    if curated_stories:
        curated_section = f"""

CURATED STORIES (pre-selected as the most interesting, diverse stories of the day — USE THESE FIRST):
==========================================
{curated_stories}

The stories above were specifically selected for being stop-scrolling worthy across diverse topics.
You MUST use most of them. The full signal data below provides additional context (markets, prediction
markets, economic data, etc.) to add irony and contradiction to these stories.
"""

    prompt = f"""Based on the curated stories and signal data below, write today's intelligence brief.
{curated_section}

FULL SIGNAL DATA (for context, market data, prediction markets, and additional stories):
{context}

YOUR JOB: Be the most sarcastic, well-informed person in the room. Find the contradictions. Twist the knife. Connect the dots nobody else connects. Make the reader feel like an idiot for almost scrolling past this.

Here is an example of the EXACT voice and format. Study it carefully — notice the SARCASM:

> Disney pulled out of its $1 billion deal with OpenAI.. the company that spent 100 years suing over Mickey Mouse decided AI video wasn't worth the risk..

> MBS personally called Trump pushing him to continue strikes on Iran.. the man running a $930 billion oil fund wants war because war means higher oil prices.. shocking absolutely nobody.

> Karpathy exposed a supply chain attack on a Python package with 97 million downloads.. a single pip install could steal every password and crypto wallet on your machine.. sleep well.

> Satya Nadella said the biggest obstacle to AI is convincing people to change how they work.. translation: "we built the replacement, now we need you to train it before we let you go"..

> Pinterest's CEO asked governments to ban social media for kids under 16.. the man running a $3.6 billion social media company built on teenage girls saving outfit ideas..

> An insider trade appeared on a publicly traded pharma stock 72 hours before a surprise FDA approval.. the SEC's enforcement division is currently running at half staff.. which is just beautiful timing really.

Notice what makes this work:
- Each item is 1-2 sentences MAX. A punch, not a paragraph.
- The SARCASM does the work. "shocking absolutely nobody." "sleep well." "which is just beautiful timing really." These land because they're SHORT.
- "translation:" = saying the quiet part out loud. Use it.
- The irony is in the SAME sentence as the fact. Not a separate explanation.
- DIVERSE topics: AI, geopolitics, cybersecurity, corporate hypocrisy, social media — all different.
- No topic gets more than 2 items. Period.
- Specific names, specific dollar amounts, specific numbers.
- If it sounds like a Reuters wire, you failed. If it sounds like your sharpest friend texting you at 2am, you nailed it.

CRITICAL RULES:
1. Your ONLY sources of truth are the data provided. Do NOT inject facts from training data.
1b. NEVER repeat a story from a previous brief. If the curated stories contain something that
   was already covered in an earlier dispatch, SKIP IT and write about something else from the
   data. The ONLY exception: a genuinely new development (deal signed, casualties reported,
   verdict delivered). New articles about the same event do NOT count.
2. NO TOPIC gets more than 2 items. War, oil, geopolitics, Middle East — these are ALL the same
   topic. Maximum 2 items on that entire cluster, then MOVE ON.
3. You MUST cover at least 6 DIFFERENT worlds: tech/AI, geopolitics, corporate/business, economy,
   social/culture, and at least one wildcard. If the data has a major tech story (company deal,
   product launch/death, cybersecurity breach), it MUST be included.
4. Each item is 1-2 sentences. NOT 3. Drop the fact, twist the knife, move on. No explaining.
5. Never explain the irony. State the fact and the contradiction in the SAME sentence. The reader
   gets it. If they don't, that's fine. Do NOT add a third sentence that interprets.
6. Name the person. Name the dollar amount. Name the company. Vague = weak.
7. Scan ALL signal sources including NOTABLE STORIES. Major corporate deals, product deaths,
   CEO hypocrisy, cybersecurity events — these are GOLD. Don't skip them because they scored
   low on intensity. A billion-dollar deal dying is a bigger story than most wars.
8. NONPARTISAN IS NON-NEGOTIABLE.
   - Never name a political party (Republican, Democrat, GOP, DNC).
   - Never name a politician as the subject of an item unless the irony is purely structural.
   - Never write an item where the takeaway is "this politician/party did something bad."
   - Political stories are ONLY worth including when the SYSTEM contradicts itself — an agency
     doing the opposite of its mandate, a policy producing opposite results, money flowing
     opposite to stated goals. Frame these as institutional failures, not political attacks.
   - Test: if removing the politician's name makes the item weaker, it's a partisan item. Cut it.
     If removing the name and it still works, it's a systemic item. Keep it.

FORMAT:

WHAT JUST HAPPENED
8-12 items. Each one starts with ">" on its own line. Each is 2-3 sentences max.
Every item: fact + irony in the same breath. Diverse topics. Rapid fire.

THE THREAD
2-3 sentences. The pattern connecting today's items. End with a line that sticks.

Close with: "all of this.. one [day of week].. and you almost scrolled past it."

STRICT FORMATTING RULES:
- Section headers: ALL CAPS, no markdown hashes, no colons
- Use ".." (double periods) for dramatic pauses — NEVER use "—" or "..."
- Each item starts with ">" on its own line
- No jargon. No scores. No analysis paragraphs.
- No [NEW] or [ONGOING] tags. No confidence tags. Just sharp writing.
- Use real names, real numbers, real dollar amounts.
- Target 400-600 words total. Short and punchy beats long and thorough.
- Do NOT start with a date line or title. Jump straight into WHAT JUST HAPPENED.

DATA:
{context}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3000,
        system="""You write like the most savage, well-read person on the internet who happens to have access to every data feed on earth. Your tone is dry, sarcastic, and laced with dark humor. You don't report news — you expose the absurdity of it. Every sentence should make the reader exhale sharply through their nose.

You are nonpartisan. You don't care about politics. You care about hypocrisy, contradiction, and the gap between what people say and what they do. You find it genuinely funny when a trillion-dollar company trips over its own shoelaces.

FORMAT: Rapid-fire items. Each one: 1-2 sentences. Fact + sarcasm in the same breath. The irony should HIT, not be explained. Then move to the next topic. Never linger. Never explain. Never write a paragraph when a sentence will do. If you catch yourself writing a third sentence, delete it.

DIVERSITY IS EVERYTHING. Cover tech, geopolitics, business, AI, economy, social issues, culture — as many different worlds as the data supports. No single topic gets more than 2 items. The power comes from the RANGE, showing the reader how much happened while they weren't paying attention.

VOICE CALIBRATION:
- "translation:" is your secret weapon. Use it to say the quiet part out loud.
- ".." is your dramatic pause. Use it to let the absurdity land.
- Be the friend who texts you at 2am with "bro.. you seeing this?" energy.
- If a sentence could appear in a Reuters wire, rewrite it. You are the opposite of Reuters.
- Sarcasm > analysis. "The company building safe AI couldn't secure a server" > "This raises questions about Anthropic's security practices."

RULES:
- Your ONLY sources of truth are the data provided. If it's not in the data, it doesn't exist.
- Every item: fact + twist. Make it sting. "X happened.. the same company that Y.." — done. Move on.
- If you can't find genuine irony in a story, skip it. Forced irony is worse than silence.
- NONPARTISAN. Never write items that read like opposition research. Expose systems, not individuals.
- Never use "—" dashes. Use ".." for all dramatic pauses.
- Never show raw scores or jargon. Translate everything into plain language.""",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text

def main():
    # Temporary skip flag — set SKIP_BRIEF=true in Railway env to pause sends
    if os.getenv("SKIP_BRIEF", "").lower() == "true":
        print("SKIP_BRIEF is set — skipping this run.")
        return

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

    # Step 1: Haiku selects the most interesting, diverse stories
    print("Step 1: Haiku selecting most interesting stories...")
    curated_stories = _select_stories_with_haiku(news_df, social_df)

    # Step 2: Build full context (markets, prediction markets, economics, etc.)
    context = prepare_intelligence_context(news_df, social_df)

    # Step 3: Opus writes the brief using curated stories + full context
    print("Step 2: Opus writing the brief...")
    brief = generate_brief(context, curated_stories)

    print(brief)
    print()
    print("=" * 60)

    # Log featured stories for dedup in future briefs
    _log_brief_stories(brief)

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
