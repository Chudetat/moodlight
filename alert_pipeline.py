#!/usr/bin/env python
"""
Moodlight Alert Pipeline — Orchestrator.
Detects anomalies, investigates with AI, stores to DB, sends email alerts.
Runs as a step in fetch_news.yml and fetch_social.yml workflows.
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_engine():
    """Create a SQLAlchemy engine."""
    if not DATABASE_URL:
        return None
    try:
        from sqlalchemy import create_engine
        db_url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        if "sslmode" not in db_url:
            sep = "&" if "?" in db_url else "?"
            db_url = db_url + sep + "sslmode=require"
        return create_engine(db_url, pool_pre_ping=True)
    except Exception as e:
        print(f"ERROR: Could not create DB engine: {e}")
        return None


def ensure_tables(engine):
    """Create alerts and brand_watchlist tables if they don't exist."""
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS alerts (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ DEFAULT NOW(),
                alert_type VARCHAR(50),
                severity VARCHAR(20),
                title TEXT,
                summary TEXT,
                investigation TEXT,
                data TEXT,
                emailed BOOLEAN DEFAULT FALSE,
                cooldown_key VARCHAR(100),
                username VARCHAR(100),
                brand VARCHAR(200)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS brand_watchlist (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) NOT NULL,
                brand_name VARCHAR(200) NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(username, brand_name)
            )
        """))
        conn.commit()
    print("DB tables verified")


def load_data(engine):
    """Load recent news, social, and market data from DB."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    df_news = pd.DataFrame()
    df_social = pd.DataFrame()
    df_markets = pd.DataFrame()

    try:
        df_news = pd.read_sql(
            f"SELECT * FROM news_scored WHERE created_at >= '{cutoff}'", engine
        )
        if not df_news.empty and "created_at" in df_news.columns:
            df_news["created_at"] = pd.to_datetime(
                df_news["created_at"], utc=True, errors="coerce"
            )
        print(f"  Loaded {len(df_news)} news rows")
    except Exception as e:
        print(f"  Could not load news: {e}")

    try:
        df_social = pd.read_sql(
            f"SELECT * FROM social_scored WHERE created_at >= '{cutoff}'", engine
        )
        if not df_social.empty and "created_at" in df_social.columns:
            df_social["created_at"] = pd.to_datetime(
                df_social["created_at"], utc=True, errors="coerce"
            )
        print(f"  Loaded {len(df_social)} social rows")
    except Exception as e:
        print(f"  Could not load social: {e}")

    try:
        df_markets = pd.read_sql(
            f"SELECT * FROM markets WHERE latest_trading_day >= '{cutoff}'", engine
        )
        print(f"  Loaded {len(df_markets)} market rows")
    except Exception as e:
        print(f"  Could not load markets: {e}")

    return df_news, df_social, df_markets


def load_watchlist(engine):
    """Load brand watchlist: {username: [brand1, brand2, ...]}."""
    try:
        df = pd.read_sql("SELECT username, brand_name FROM brand_watchlist", engine)
        watchlist = {}
        for _, row in df.iterrows():
            watchlist.setdefault(row["username"], []).append(row["brand_name"])
        return watchlist
    except Exception as e:
        print(f"  Could not load watchlist: {e}")
        return {}


def check_cooldown(engine, cooldown_key, hours=6):
    """Check if an alert with this cooldown_key was created within the last N hours."""
    try:
        from sqlalchemy import text
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM alerts WHERE cooldown_key = :key AND timestamp > :cutoff"),
                {"key": cooldown_key, "cutoff": cutoff},
            )
            return result.scalar() > 0
    except Exception:
        return False


def build_cooldown_key(alert):
    """Build a unique cooldown key for deduplication."""
    parts = [alert.get("alert_type", "")]
    if alert.get("brand"):
        parts.append(alert["brand"])
    if alert.get("username"):
        parts.append(alert["username"])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parts.append(today)
    return ":".join(parts)


def store_alert(engine, alert):
    """Insert an alert into the alerts table."""
    from sqlalchemy import text
    investigation = alert.get("investigation")
    if isinstance(investigation, dict):
        investigation = json.dumps(investigation)

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO alerts (alert_type, severity, title, summary,
                    investigation, data, emailed, cooldown_key, username, brand)
                VALUES (:alert_type, :severity, :title, :summary,
                    :investigation, :data, :emailed, :cooldown_key, :username, :brand)
            """),
            {
                "alert_type": alert.get("alert_type"),
                "severity": alert.get("severity"),
                "title": alert.get("title"),
                "summary": alert.get("summary"),
                "investigation": investigation,
                "data": alert.get("data"),
                "emailed": alert.get("emailed", False),
                "cooldown_key": alert.get("cooldown_key"),
                "username": alert.get("username"),
                "brand": alert.get("brand"),
            },
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("MOODLIGHT ALERT PIPELINE")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # 1. Connect to DB
    engine = get_engine()
    if not engine:
        print("ERROR: DATABASE_URL not set or invalid — cannot run alert pipeline")
        sys.exit(0)  # Exit 0 so workflow doesn't fail

    ensure_tables(engine)

    # 2. Load data
    print("\nLoading data...")
    df_news, df_social, df_markets = load_data(engine)

    if df_news.empty and df_social.empty:
        print("No news or social data available — nothing to detect")
        sys.exit(0)

    # 3. Run global detectors
    print("\nRunning global detectors...")
    from alert_detector import run_global_detectors, run_brand_detectors
    global_alerts = run_global_detectors(df_news, df_social, df_markets)
    print(f"  Found {len(global_alerts)} global anomalies")

    # 4. Run brand detectors
    print("\nLoading brand watchlist...")
    watchlist = load_watchlist(engine)
    brand_alerts = []

    if watchlist:
        print(f"  {sum(len(v) for v in watchlist.values())} brands across {len(watchlist)} subscribers")
        for username, brands in watchlist.items():
            for brand_name in brands:
                print(f"  Scanning brand: {brand_name} (subscriber: {username})")
                alerts, _ = run_brand_detectors(
                    df_news, df_social, brand_name, username
                )
                brand_alerts.extend(alerts)
                print(f"    Found {len(alerts)} alerts for {brand_name}")
    else:
        print("  No brands in watchlist — skipping brand detectors")

    # 5. Process all alerts
    all_alerts = global_alerts + brand_alerts
    print(f"\nTotal anomalies detected: {len(all_alerts)}")

    if not all_alerts:
        print("No anomalies — all signals nominal")
        sys.exit(0)

    # 6. Investigate and store
    from alert_investigator import investigate_alert
    stored_alerts = []

    for alert in all_alerts:
        cooldown_key = build_cooldown_key(alert)

        # Check cooldown
        if check_cooldown(engine, cooldown_key):
            print(f"  SKIP (cooldown): {alert['title']}")
            continue

        print(f"\n  Processing: {alert['title']}")

        # Investigate
        investigation = investigate_alert(
            alert, df_news=df_news, df_social=df_social, df_markets=df_markets
        )
        if investigation:
            alert["investigation"] = investigation
            print(f"    Investigation complete")
        else:
            alert["investigation"] = None
            print(f"    No investigation (skipped or failed)")

        # Store
        alert["cooldown_key"] = cooldown_key
        store_alert(engine, alert)
        stored_alerts.append(alert)
        print(f"    Stored to DB")

    # 7. Send emails
    print(f"\nSending email alerts...")
    from alert_emailer import send_alert_emails
    sent = send_alert_emails(stored_alerts, engine=engine)

    # Mark emailed alerts
    if sent > 0:
        from sqlalchemy import text
        with engine.connect() as conn:
            for alert in stored_alerts:
                if alert.get("severity") in ("critical", "warning"):
                    conn.execute(
                        text("UPDATE alerts SET emailed = true WHERE cooldown_key = :key"),
                        {"key": alert.get("cooldown_key")},
                    )
            conn.commit()

    # 8. Summary
    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print(f"  Global alerts: {len(global_alerts)}")
    print(f"  Brand alerts:  {len(brand_alerts)}")
    print(f"  Stored:        {len(stored_alerts)} (after cooldown filter)")
    print(f"  Emails sent:   {sent}")
    print("=" * 60)


if __name__ == "__main__":
    main()
