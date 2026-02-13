#!/usr/bin/env python
"""
Moodlight Alert Pipeline — Orchestrator.
Detects anomalies, investigates with AI, stores to DB, sends email alerts.
Includes competitive analysis and adaptive threshold tuning.
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
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS topic_watchlist (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) NOT NULL,
                topic_name VARCHAR(200) NOT NULL,
                is_category BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(username, topic_name)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                digest_daily BOOLEAN DEFAULT TRUE,
                digest_weekly BOOLEAN DEFAULT TRUE,
                alert_emails BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        # Add topic column to alerts if it doesn't exist
        try:
            conn.execute(text(
                "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS topic VARCHAR(200)"
            ))
        except Exception:
            pass  # Column already exists or DB doesn't support IF NOT EXISTS
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id SERIAL PRIMARY KEY,
                pipeline_name VARCHAR(100) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'running',
                row_count INTEGER DEFAULT 0,
                error_message TEXT,
                started_at TIMESTAMPTZ DEFAULT NOW(),
                completed_at TIMESTAMPTZ
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_events (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                event_data TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        # Performance indexes for persistent tables
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts (timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_brand ON alerts (brand)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_topic ON alerts (topic)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_username ON alerts (username)",
            "CREATE INDEX IF NOT EXISTS idx_brand_watchlist_username ON brand_watchlist (username)",
            "CREATE INDEX IF NOT EXISTS idx_topic_watchlist_username ON topic_watchlist (username)",
            "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_name ON pipeline_runs (pipeline_name)",
            "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs (started_at)",
            "CREATE INDEX IF NOT EXISTS idx_user_events_username ON user_events (username)",
            "CREATE INDEX IF NOT EXISTS idx_user_events_type ON user_events (event_type)",
            "CREATE INDEX IF NOT EXISTS idx_user_events_created ON user_events (created_at)",
        ]:
            try:
                conn.execute(text(idx_sql))
            except Exception:
                pass
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
            text("SELECT * FROM news_scored WHERE created_at >= :cutoff"),
            engine, params={"cutoff": cutoff},
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
            text("SELECT * FROM social_scored WHERE created_at >= :cutoff"),
            engine, params={"cutoff": cutoff},
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
            text("SELECT * FROM markets WHERE latest_trading_day >= :cutoff"),
            engine, params={"cutoff": cutoff},
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


def load_topic_watchlist(engine):
    """Load topic watchlist: {username: [(topic_name, is_category), ...]}."""
    try:
        df = pd.read_sql(
            "SELECT username, topic_name, is_category FROM topic_watchlist", engine
        )
        watchlist = {}
        for _, row in df.iterrows():
            watchlist.setdefault(row["username"], []).append(
                (row["topic_name"], bool(row["is_category"]))
            )
        return watchlist
    except Exception as e:
        print(f"  Could not load topic watchlist: {e}")
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
    if alert.get("topic"):
        parts.append(alert["topic"])
    if alert.get("username"):
        parts.append(alert["username"])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parts.append(today)
    return ":".join(parts)


def start_pipeline_run(engine, pipeline_name):
    """Record the start of a pipeline run. Returns the run ID."""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("INSERT INTO pipeline_runs (pipeline_name, status) VALUES (:name, 'running') RETURNING id"),
                {"name": pipeline_name},
            )
            run_id = result.scalar()
            conn.commit()
            return run_id
    except Exception:
        return None


def complete_pipeline_run(engine, run_id, status="success", row_count=0, error_message=None):
    """Record the completion of a pipeline run."""
    if run_id is None:
        return
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    UPDATE pipeline_runs
                    SET status = :status, row_count = :row_count,
                        error_message = :error_message, completed_at = NOW()
                    WHERE id = :id
                """),
                {"id": run_id, "status": status, "row_count": row_count, "error_message": error_message},
            )
            conn.commit()
    except Exception:
        pass


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
                    investigation, data, emailed, cooldown_key, username, brand, topic)
                VALUES (:alert_type, :severity, :title, :summary,
                    :investigation, :data, :emailed, :cooldown_key, :username, :brand, :topic)
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
                "topic": alert.get("topic"),
            },
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Reasoning chain routing
# ---------------------------------------------------------------------------

def _should_use_chain(alert):
    """Determine if this alert warrants multi-step reasoning.

    Use chain for complex/strategic alerts. Use single-turn for simple ones.
    """
    alert_type = alert.get("alert_type", "")
    severity = alert.get("severity", "info")

    # Always use chain for predictive alerts
    if alert_type.startswith("predictive_"):
        return True

    # Always use chain for competitive alerts
    if alert_type in ("competitor_momentum", "share_of_voice_shift", "competitive_white_space"):
        return True

    # Always use chain for new complex alert types
    if alert_type in ("brand_crisis", "regulatory_policy_spike",
                       "geopolitical_risk_escalation", "breaking_signal"):
        return True

    # Always use chain for topic VLDS alerts (strategic)
    if alert_type in ("topic_velocity_spike", "topic_saturation"):
        return True

    # Use chain for critical severity
    if severity == "critical":
        return True

    # Use chain for strategic brand alerts
    if alert_type in ("brand_white_space", "brand_narrative_fading"):
        return True

    return False


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

    run_id = start_pipeline_run(engine, "alert_pipeline")

    _pipeline_row_count = 0
    try:
        # 1b. Initialize threshold and feedback tables
        from alert_thresholds import ensure_threshold_tables, get_thresholds
        from alert_feedback import ensure_feedback_table
        from competitor_discovery import ensure_competitor_tables

        from predictive_detector import ensure_metric_snapshots_table

        ensure_threshold_tables(engine)
        ensure_feedback_table(engine)
        ensure_competitor_tables(engine)
        ensure_metric_snapshots_table(engine)
        print("Threshold, feedback, competitor, and metric snapshot tables verified")

        # 1c. Load configurable thresholds from DB
        thresholds = get_thresholds(engine)
        print(f"Loaded {len(thresholds)} alert thresholds")

        # 2. Load data
        print("\nLoading data...")
        df_news, df_social, df_markets = load_data(engine)

        if df_news.empty and df_social.empty:
            print("No news or social data available — nothing to detect")
            complete_pipeline_run(engine, run_id, "success", 0)
            sys.exit(0)

        # 2b. Capture metric snapshots for trend analysis
        print("\nCapturing metric snapshots...")
        watchlist = load_watchlist(engine)
        _early_topic_watchlist = load_topic_watchlist(engine)
        try:
            from predictive_detector import capture_metric_snapshots
            capture_metric_snapshots(engine, df_news, df_social, df_markets, watchlist,
                                     topic_watchlist=_early_topic_watchlist)
        except Exception as e:
            print(f"  Metric snapshot capture failed (non-fatal): {e}")

        # 2c. Capture geopolitical intensity for trend tracking
        try:
            geo_topics = {"war & foreign policy", "immigration", "crime & safety"}
            if not df_news.empty and "topic" in df_news.columns and "intensity" in df_news.columns:
                geo_df = df_news[df_news["topic"].isin(geo_topics)]
                if not geo_df.empty:
                    from predictive_detector import _store_single_metric
                    avg_geo = float(geo_df["intensity"].mean())
                    _store_single_metric(engine, "global", None, "avg_intensity_geopolitical", avg_geo, len(geo_df))
                    print(f"  Captured geopolitical intensity metric: {avg_geo:.2f} ({len(geo_df)} articles)")
        except Exception as e:
            print(f"  Geopolitical metric capture failed (non-fatal): {e}")

        # 3. Run global detectors (with configurable thresholds)
        print("\nRunning global detectors...")
        from alert_detector import run_global_detectors, run_brand_detectors, run_competitive_detectors
        global_alerts = run_global_detectors(df_news, df_social, df_markets, thresholds, engine=engine)
        print(f"  Found {len(global_alerts)} global anomalies")

        # 4. Run brand detectors (with configurable thresholds)
        print("\nRunning brand detectors...")
        brand_alerts = []
        competitive_alerts = []

        if watchlist:
            from competitor_discovery import ensure_competitors_cached
            from competitive_analyzer import (
                compute_competitive_snapshot,
                get_previous_snapshot,
                store_snapshot,
            )

            print(f"  {sum(len(v) for v in watchlist.values())} brands across {len(watchlist)} subscribers")
            for username, brands in watchlist.items():
                for brand_name in brands:
                    print(f"  Scanning brand: {brand_name} (subscriber: {username})")

                    # 4a. Brand-specific detectors
                    alerts, _ = run_brand_detectors(
                        df_news, df_social, brand_name, username,
                        thresholds=thresholds,
                    )
                    brand_alerts.extend(alerts)
                    print(f"    Found {len(alerts)} brand alerts for {brand_name}")

                    # 4b. Competitive analysis
                    print(f"    Running competitive analysis for {brand_name}...")
                    competitors = ensure_competitors_cached(engine, brand_name)
                    if competitors:
                        print(f"    Competitors: {[c['competitor_name'] for c in competitors]}")

                        # Compute snapshot
                        current_snapshot = compute_competitive_snapshot(
                            df_news, df_social, brand_name, competitors
                        )

                        # Load previous snapshot for comparison
                        previous_snapshot = get_previous_snapshot(engine, brand_name)

                        # Store current snapshot
                        store_snapshot(engine, brand_name, current_snapshot)

                        # Run competitive detectors
                        comp_alerts = run_competitive_detectors(
                            brand_name, username,
                            current_snapshot, previous_snapshot,
                            thresholds,
                        )
                        competitive_alerts.extend(comp_alerts)
                        print(f"    Found {len(comp_alerts)} competitive alerts for {brand_name}")
                    else:
                        print(f"    No competitors found for {brand_name} — skipping competitive analysis")
        else:
            print("  No brands in watchlist — skipping brand detectors")

        # 4b2. Run topic detectors
        print("\nRunning topic detectors...")
        topic_alerts = []
        topic_watchlist = load_topic_watchlist(engine)
        if topic_watchlist:
            from alert_detector import run_topic_detectors
            seen_topics = set()
            total_topic_count = sum(len(v) for v in topic_watchlist.values())
            print(f"  {total_topic_count} topics across {len(topic_watchlist)} subscribers")
            for username, topics in topic_watchlist.items():
                for topic_name, is_category in topics:
                    print(f"  Scanning topic: {topic_name} (category={is_category}, subscriber: {username})")
                    alerts, _ = run_topic_detectors(
                        df_news, df_social, topic_name, is_category, username, thresholds,
                    )
                    topic_alerts.extend(alerts)
                    print(f"    Found {len(alerts)} topic alerts for {topic_name}")
                    seen_topics.add(topic_name)
        else:
            print("  No topics in watchlist — skipping topic detectors")

        # 4c. Run predictive detectors
        print("\nRunning predictive detectors...")
        predictive_alerts = []
        try:
            from predictive_detector import run_predictive_detectors
            predictive_alerts = run_predictive_detectors(
                engine, df_news, df_social, df_markets, watchlist, thresholds,
                topic_watchlist=topic_watchlist,
            )
            print(f"  Found {len(predictive_alerts)} predictive signals")
        except Exception as e:
            print(f"  Predictive detection failed (non-fatal): {e}")

        # 5. Process all alerts
        all_alerts = global_alerts + brand_alerts + competitive_alerts + topic_alerts + predictive_alerts
        print(f"\nTotal anomalies detected: {len(all_alerts)}")

        if not all_alerts:
            print("No anomalies — all signals nominal")

            # Still run adaptive tuning even with no new alerts
            print("\nRunning adaptive threshold tuning...")
            try:
                from adaptive_tuner import run_adaptive_tuning
                run_adaptive_tuning(engine)
            except Exception as e:
                print(f"  Adaptive tuning failed (non-fatal): {e}")

            _pipeline_row_count = len(df_news) + len(df_social)
            complete_pipeline_run(engine, run_id, "success", _pipeline_row_count)
            sys.exit(0)

        # 5b. Alert correlation — detect related signals and generate situation reports
        print("\nRunning alert correlation...")
        situation_reports = []
        try:
            from alert_correlator import correlate_alerts, generate_situation_report
            clusters = correlate_alerts(all_alerts)
            print(f"  Found {len(clusters)} correlated alert cluster(s)")
            for i, cluster in enumerate(clusters):
                print(f"  Cluster {i+1}: {len(cluster)} alerts — "
                      f"{[a.get('alert_type', '?') for a in cluster]}")
                sit_report = generate_situation_report(
                    cluster, engine=engine, df_news=df_news, df_social=df_social,
                )
                situation_reports.append(sit_report)
                all_alerts.append(sit_report)
                print(f"    Generated situation report: {sit_report['title'][:80]}")
        except Exception as e:
            print(f"  Alert correlation failed (non-fatal): {e}")

        # 6. Investigate and store
        from alert_investigator import investigate_alert
        stored_alerts = []

        # Import reasoning chain (graceful fallback to single-turn)
        try:
            from reasoning_chain import run_reasoning_chain
            _has_chain = True
        except ImportError:
            _has_chain = False
            print("  Reasoning chain module not available — using single-turn investigation")

        for alert in all_alerts:
            cooldown_key = build_cooldown_key(alert)

            # Use longer cooldown for predictive alerts
            cooldown_hours = 24 if alert.get("alert_type", "").startswith("predictive_") else 6

            # Check cooldown
            if check_cooldown(engine, cooldown_key, hours=cooldown_hours):
                print(f"  SKIP (cooldown): {alert['title']}")
                continue

            print(f"\n  Processing: {alert['title']}")

            # Situation reports already have investigation from the correlator
            if alert.get("alert_type") == "situation_report" and alert.get("investigation"):
                print(f"    Situation report — using correlator investigation")
                alert["cooldown_key"] = cooldown_key
                store_alert(engine, alert)
                stored_alerts.append(alert)
                print(f"    Stored to DB")
                continue

            # Investigate — use reasoning chain for complex alerts, single-turn for simple
            investigation = None
            use_chain = _has_chain and _should_use_chain(alert)

            if use_chain:
                print(f"    Using multi-step reasoning chain...")
                investigation = run_reasoning_chain(
                    alert, engine=engine,
                    df_news=df_news, df_social=df_social, df_markets=df_markets
                )
                if investigation:
                    steps = investigation.get("steps", [])
                    print(f"    Reasoning chain complete ({len(steps)} steps, "
                          f"confidence: {investigation.get('overall_confidence', '?')}/100)")

            if not investigation:
                # Fallback to single-turn
                investigation = investigate_alert(
                    alert, df_news=df_news, df_social=df_social, df_markets=df_markets
                )
                if investigation:
                    print(f"    Single-turn investigation complete")
                else:
                    print(f"    No investigation (skipped or failed)")

            alert["investigation"] = investigation

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

        # 8. Adaptive threshold tuning
        print("\nRunning adaptive threshold tuning...")
        try:
            from adaptive_tuner import run_adaptive_tuning
            run_adaptive_tuning(engine)
        except Exception as e:
            print(f"  Adaptive tuning failed (non-fatal): {e}")

        # 9. Summary
        _pipeline_row_count = len(stored_alerts)
        print("\n" + "=" * 60)
        print("PIPELINE SUMMARY")
        print(f"  Global alerts:      {len(global_alerts)}")
        print(f"  Brand alerts:       {len(brand_alerts)}")
        print(f"  Competitive alerts: {len(competitive_alerts)}")
        print(f"  Topic alerts:       {len(topic_alerts)}")
        print(f"  Predictive alerts:  {len(predictive_alerts)}")
        print(f"  Situation reports:  {len(situation_reports)}")
        print(f"  Stored:             {len(stored_alerts)} (after cooldown filter)")
        print(f"  Emails sent:        {sent}")
        print("=" * 60)

        complete_pipeline_run(engine, run_id, "success", _pipeline_row_count)

    except Exception as _pipeline_err:
        print(f"\nPIPELINE ERROR: {_pipeline_err}")
        complete_pipeline_run(engine, run_id, "failed", _pipeline_row_count, str(_pipeline_err)[:500])
        raise


if __name__ == "__main__":
    main()
