#!/usr/bin/env python
"""
signal_log_tracker.py
Tracks prediction signal outcomes against market data.
Two modes:
  - log_new_signals(): called from alert_pipeline after predictive alerts fire
  - fill_outcomes(): called daily via cron after market close
  - main(backfill): one-time backfill of existing alerts
"""

import os
import sys
import pandas as pd
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text as sql_text
from dotenv import load_dotenv

load_dotenv()

BRAND_TICKERS = {
    "NVIDIA": "NVDA",
    "Amazon": "AMZN",
    "Disney": "DIS",
    "Lockheed Martin": "LMT",
}

HORIZONS = [1, 3, 5]


def _get_engine():
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url)


def ensure_signal_log_table(engine):
    """Create signal_log table if it doesn't exist."""
    with engine.connect() as conn:
        conn.execute(sql_text("""
            CREATE TABLE IF NOT EXISTS signal_log (
                id SERIAL PRIMARY KEY,
                alert_id INTEGER NOT NULL UNIQUE,
                alert_type VARCHAR(50),
                severity VARCHAR(20),
                brand VARCHAR(200),
                topic VARCHAR(200),
                title TEXT,
                summary TEXT,
                signal_date DATE NOT NULL,

                spy_price_at_signal FLOAT,
                brand_ticker VARCHAR(10),
                brand_price_at_signal FLOAT,

                spy_price_1d FLOAT,
                spy_price_3d FLOAT,
                spy_price_5d FLOAT,
                spy_change_1d FLOAT,
                spy_change_3d FLOAT,
                spy_change_5d FLOAT,

                brand_price_1d FLOAT,
                brand_price_3d FLOAT,
                brand_price_5d FLOAT,
                brand_change_1d FLOAT,
                brand_change_3d FLOAT,
                brand_change_5d FLOAT,

                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.execute(sql_text(
            "CREATE INDEX IF NOT EXISTS idx_signal_log_date ON signal_log (signal_date)"
        ))
        conn.execute(sql_text(
            "CREATE INDEX IF NOT EXISTS idx_signal_log_type ON signal_log (alert_type)"
        ))
        conn.commit()
    print("  signal_log table ensured")


def _get_spy_price_on_date(engine, target_date):
    """Get SPY closing price for a given trading day."""
    df = pd.read_sql(
        sql_text("""
            SELECT price FROM markets
            WHERE symbol = 'SPY' AND latest_trading_day = :d
            ORDER BY timestamp DESC LIMIT 1
        """),
        engine,
        params={"d": str(target_date)},
    )
    return float(df.iloc[0]["price"]) if not df.empty else None


def _get_brand_price_on_date(engine, ticker, target_date):
    """Get brand stock closing price for a given trading day."""
    df = pd.read_sql(
        sql_text("""
            SELECT close_price FROM brand_stocks
            WHERE ticker = :ticker
              AND bar_datetime::date = :d
            ORDER BY bar_datetime DESC LIMIT 1
        """),
        engine,
        params={"ticker": ticker, "d": str(target_date)},
    )
    return float(df.iloc[0]["close_price"]) if not df.empty else None


def _get_trading_days(engine):
    """Get sorted list of trading days from SPY data."""
    df = pd.read_sql(
        sql_text("""
            SELECT DISTINCT latest_trading_day
            FROM markets WHERE symbol = 'SPY'
            ORDER BY latest_trading_day
        """),
        engine,
    )
    return [pd.Timestamp(d).date() for d in df["latest_trading_day"]]


def _trading_day_offset(trading_days, signal_date, offset):
    """Find the trading day N days after signal_date."""
    # Find first trading day >= signal_date
    start_idx = None
    for i, d in enumerate(trading_days):
        if d >= signal_date:
            start_idx = i
            break
    if start_idx is None:
        return None
    target_idx = start_idx + offset
    if target_idx >= len(trading_days):
        return None
    return trading_days[target_idx]


def log_new_signals(engine, stored_alerts):
    """Log newly stored predictive/divergence alerts into signal_log.

    Called from alert_pipeline.py after alerts are stored.
    stored_alerts should be a list of dicts with at least 'id' and alert fields.
    """
    ensure_signal_log_table(engine)

    # Get current SPY price for snapshot
    spy_price = None
    try:
        spy_df = pd.read_sql(
            sql_text("""
                SELECT price FROM markets
                WHERE symbol = 'SPY'
                ORDER BY timestamp DESC LIMIT 1
            """),
            engine,
        )
        if not spy_df.empty:
            spy_price = float(spy_df.iloc[0]["price"])
    except Exception:
        pass

    logged = 0
    for alert in stored_alerts:
        alert_type = alert.get("alert_type", "")
        if not alert_type.startswith("predictive_") and alert_type != "market_mood_divergence":
            continue

        alert_id = alert.get("id")
        if not alert_id:
            continue

        brand = alert.get("brand", "")
        ticker = BRAND_TICKERS.get(brand) if brand else None
        brand_price = None
        if ticker:
            try:
                brand_price = _get_brand_price_on_date(
                    engine, ticker, datetime.now(timezone.utc).date()
                )
            except Exception:
                pass

        try:
            with engine.connect() as conn:
                conn.execute(
                    sql_text("""
                        INSERT INTO signal_log
                            (alert_id, alert_type, severity, brand, topic, title, summary,
                             signal_date, spy_price_at_signal, brand_ticker, brand_price_at_signal)
                        VALUES
                            (:alert_id, :alert_type, :severity, :brand, :topic, :title, :summary,
                             :signal_date, :spy_price, :ticker, :brand_price)
                        ON CONFLICT (alert_id) DO NOTHING
                    """),
                    {
                        "alert_id": alert_id,
                        "alert_type": alert_type,
                        "severity": alert.get("severity", ""),
                        "brand": brand or "",
                        "topic": alert.get("topic", ""),
                        "title": alert.get("title", ""),
                        "summary": alert.get("summary", ""),
                        "signal_date": datetime.now(timezone.utc).date(),
                        "spy_price": spy_price,
                        "ticker": ticker,
                        "brand_price": brand_price,
                    },
                )
                conn.commit()
                logged += 1
        except Exception as e:
            print(f"  Failed to log signal {alert_id}: {e}")

    if logged:
        print(f"  Logged {logged} new signals to signal_log")


def fill_outcomes(engine):
    """Fill in market outcomes for signals that have pending horizons."""
    ensure_signal_log_table(engine)

    trading_days = _get_trading_days(engine)
    if not trading_days:
        print("  No trading days available")
        return

    # Get signals with any unfilled outcomes
    pending = pd.read_sql(
        sql_text("""
            SELECT id, signal_date, spy_price_at_signal, brand_ticker, brand_price_at_signal,
                   spy_change_1d, spy_change_3d, spy_change_5d,
                   brand_change_1d, brand_change_3d, brand_change_5d
            FROM signal_log
            WHERE spy_change_1d IS NULL OR spy_change_3d IS NULL OR spy_change_5d IS NULL
        """),
        engine,
    )

    if pending.empty:
        print("  No pending outcomes to fill")
        return

    print(f"  Processing {len(pending)} signals with pending outcomes")
    updated = 0

    for _, row in pending.iterrows():
        sig_date = pd.Timestamp(row["signal_date"]).date()
        spy_entry = row["spy_price_at_signal"]
        brand_ticker = row["brand_ticker"]
        brand_entry = row["brand_price_at_signal"]

        updates = {}

        for horizon in HORIZONS:
            spy_col = f"spy_change_{horizon}d"
            price_col = f"spy_price_{horizon}d"

            # Skip if already filled
            if pd.notna(row.get(spy_col)):
                continue

            target_day = _trading_day_offset(trading_days, sig_date, horizon)
            if target_day is None:
                continue

            spy_target = _get_spy_price_on_date(engine, target_day)
            if spy_target and spy_entry:
                pct = ((spy_target - spy_entry) / spy_entry) * 100
                updates[price_col] = spy_target
                updates[spy_col] = round(pct, 4)

            # Brand stock outcome
            if brand_ticker and brand_entry:
                brand_target = _get_brand_price_on_date(engine, brand_ticker, target_day)
                if brand_target:
                    bpct = ((brand_target - brand_entry) / brand_entry) * 100
                    updates[f"brand_price_{horizon}d"] = brand_target
                    updates[f"brand_change_{horizon}d"] = round(bpct, 4)

        if updates:
            set_clause = ", ".join(f"{k} = :{k}" for k in updates)
            updates["row_id"] = row["id"]
            with engine.connect() as conn:
                conn.execute(
                    sql_text(f"UPDATE signal_log SET {set_clause} WHERE id = :row_id"),
                    updates,
                )
                conn.commit()
            updated += 1

    print(f"  Updated outcomes for {updated} signals")


def backfill(engine):
    """One-time backfill: log all existing predictive alerts and fill outcomes."""
    ensure_signal_log_table(engine)

    trading_days = _get_trading_days(engine)

    # Load all predictive/divergence alerts
    alerts = pd.read_sql(
        sql_text("""
            SELECT id, alert_type, severity, brand, topic, title, summary, timestamp
            FROM alerts
            WHERE alert_type LIKE 'predictive_%%'
               OR alert_type = 'market_mood_divergence'
            ORDER BY timestamp
        """),
        engine,
    )
    print(f"  Found {len(alerts)} historical signals to backfill")

    logged = 0
    for _, alert in alerts.iterrows():
        sig_date = pd.Timestamp(alert["timestamp"]).date()
        brand = alert.get("brand", "") or ""
        ticker = BRAND_TICKERS.get(brand) if brand else None

        # Find SPY price on signal date
        spy_price = _get_spy_price_on_date(engine, sig_date)
        if not spy_price:
            # Try next trading day
            td = _trading_day_offset(trading_days, sig_date, 0)
            if td:
                spy_price = _get_spy_price_on_date(engine, td)

        brand_price = None
        if ticker:
            brand_price = _get_brand_price_on_date(engine, ticker, sig_date)

        try:
            with engine.connect() as conn:
                conn.execute(
                    sql_text("""
                        INSERT INTO signal_log
                            (alert_id, alert_type, severity, brand, topic, title, summary,
                             signal_date, spy_price_at_signal, brand_ticker, brand_price_at_signal)
                        VALUES
                            (:alert_id, :alert_type, :severity, :brand, :topic, :title, :summary,
                             :signal_date, :spy_price, :ticker, :brand_price)
                        ON CONFLICT (alert_id) DO NOTHING
                    """),
                    {
                        "alert_id": int(alert["id"]),
                        "alert_type": alert["alert_type"],
                        "severity": alert["severity"],
                        "brand": brand,
                        "topic": alert.get("topic", "") or "",
                        "title": alert.get("title", "") or "",
                        "summary": alert.get("summary", "") or "",
                        "signal_date": sig_date,
                        "spy_price": spy_price,
                        "ticker": ticker,
                        "brand_price": brand_price,
                    },
                )
                conn.commit()
                logged += 1
        except Exception as e:
            print(f"  Failed to backfill alert {alert['id']}: {e}")

    print(f"  Backfilled {logged} signals")

    # Now fill outcomes
    print("\n  Filling outcomes for backfilled signals...")
    fill_outcomes(engine)


def main():
    """Entry point for cron worker and CLI."""
    engine = _get_engine()

    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        print("=" * 60)
        print("SIGNAL LOG BACKFILL")
        print("=" * 60)
        backfill(engine)
    else:
        print("=" * 60)
        print("SIGNAL LOG OUTCOME TRACKER")
        print("=" * 60)
        fill_outcomes(engine)

    # Print summary
    try:
        summary = pd.read_sql(
            sql_text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(spy_change_1d) as has_1d,
                    COUNT(spy_change_3d) as has_3d,
                    COUNT(spy_change_5d) as has_5d
                FROM signal_log
            """),
            engine,
        )
        r = summary.iloc[0]
        print(f"\n  Signal log: {r['total']} total | "
              f"1d: {r['has_1d']} | 3d: {r['has_3d']} | 5d: {r['has_5d']} outcomes filled")
    except Exception:
        pass

    print("\nDone.")


if __name__ == "__main__":
    main()
