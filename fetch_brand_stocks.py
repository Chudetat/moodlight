#!/usr/bin/env python
"""
fetch_brand_stocks.py
Fetches 60-minute intraday stock data for watchlist brand tickers
from AlphaVantage and stores bars in the brand_stocks table.
Also stores daily summary metrics to metric_snapshots.

Tickers: NVDA (NVIDIA), AMZN (Amazon), DIS (Disney), LMT (Lockheed Martin).
FIFA has no public ticker — skipped.

Skips on weekends and outside US market hours (9:30 AM - 4:00 PM ET).
"""

import os
import sys
import time
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

BRAND_TICKER_MAP = {
    "NVIDIA": "NVDA",
    "Amazon": "AMZN",
    "Disney": "DIS",
    "Lockheed Martin": "LMT",
}

RATE_LIMIT_SLEEP = 15


def _get_engine():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return None
    from sqlalchemy import create_engine
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    if "sslmode" not in db_url:
        sep = "&" if "?" in db_url else "?"
        db_url = db_url + sep + "sslmode=require"
    return create_engine(db_url, pool_pre_ping=True, pool_size=1, max_overflow=0)


def is_market_hours():
    """Check if US markets are open (weekday, 9:30 AM - 4:00 PM ET)."""
    et = ZoneInfo("America/New_York")
    now_et = datetime.now(et)
    # Weekend check
    if now_et.weekday() >= 5:
        return False
    # Market hours check (with 30-min buffer on each side for data availability)
    market_open = now_et.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=30, second=0, microsecond=0)
    return market_open <= now_et <= market_close


def ensure_brand_stocks_table(engine):
    """Create brand_stocks table if it doesn't exist."""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS brand_stocks (
                    id SERIAL PRIMARY KEY,
                    brand_name VARCHAR(200) NOT NULL,
                    ticker VARCHAR(10) NOT NULL,
                    bar_datetime TIMESTAMPTZ NOT NULL,
                    open_price FLOAT,
                    high_price FLOAT,
                    low_price FLOAT,
                    close_price FLOAT,
                    volume BIGINT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(ticker, bar_datetime)
                )
            """))
            conn.commit()
    except Exception as e:
        print(f"  Table creation failed: {e}")


def fetch_intraday(ticker):
    """Fetch 60-min intraday bars from AlphaVantage. Returns list of bar dicts or None."""
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": ticker,
        "interval": "60min",
        "outputsize": "compact",
        "apikey": ALPHAVANTAGE_API_KEY,
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            print(f"    HTTP {response.status_code} for {ticker}")
            return None

        data = response.json()

        if "Note" in data or "Information" in data:
            msg = data.get("Note") or data.get("Information")
            print(f"    API message for {ticker}: {msg}")
            return None

        time_series = data.get("Time Series (60min)", {})
        if not time_series:
            print(f"    No intraday data for {ticker}")
            return None

        bars = []
        for dt_str, values in time_series.items():
            try:
                bars.append({
                    "bar_datetime": dt_str,
                    "open_price": float(values["1. open"]),
                    "high_price": float(values["2. high"]),
                    "low_price": float(values["3. low"]),
                    "close_price": float(values["4. close"]),
                    "volume": int(values["5. volume"]),
                })
            except (KeyError, ValueError):
                continue

        return bars if bars else None

    except requests.RequestException as e:
        print(f"    Network error for {ticker}: {e}")
        return None


def store_bars(engine, brand_name, ticker, bars):
    """Store intraday bars to brand_stocks table with ON CONFLICT skip."""
    from sqlalchemy import text
    stored = 0
    try:
        with engine.connect() as conn:
            for bar in bars:
                try:
                    conn.execute(
                        text("""
                            INSERT INTO brand_stocks
                                (brand_name, ticker, bar_datetime, open_price, high_price,
                                 low_price, close_price, volume)
                            VALUES (:brand, :ticker, :dt, :open, :high, :low, :close, :vol)
                            ON CONFLICT (ticker, bar_datetime) DO NOTHING
                        """),
                        {
                            "brand": brand_name, "ticker": ticker,
                            "dt": bar["bar_datetime"],
                            "open": bar["open_price"], "high": bar["high_price"],
                            "low": bar["low_price"], "close": bar["close_price"],
                            "vol": bar["volume"],
                        },
                    )
                    stored += 1
                except Exception:
                    continue
            conn.commit()
    except Exception as e:
        print(f"    DB error storing bars for {ticker}: {e}")
    return stored


def store_daily_summary(engine, brand_name, bars):
    """Store daily summary metrics (price, change, volatility) in metric_snapshots."""
    from sqlalchemy import text
    if not bars:
        return

    # Sort bars by datetime (most recent last)
    sorted_bars = sorted(bars, key=lambda b: b["bar_datetime"])
    latest_close = sorted_bars[-1]["close_price"]
    first_open = sorted_bars[0]["open_price"]

    # Daily change percent
    change_pct = ((latest_close - first_open) / first_open) * 100 if first_open > 0 else 0

    # Intraday volatility: (max high - min low) / first open * 100
    max_high = max(b["high_price"] for b in sorted_bars)
    min_low = min(b["low_price"] for b in sorted_bars)
    volatility = ((max_high - min_low) / first_open) * 100 if first_open > 0 else 0

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    metrics = [
        ("stock_price", latest_close),
        ("stock_change_pct", change_pct),
        ("stock_intraday_volatility", volatility),
    ]

    try:
        with engine.connect() as conn:
            for metric_name, value in metrics:
                conn.execute(
                    text("""
                        INSERT INTO metric_snapshots
                            (snapshot_date, scope, scope_name, metric_name, metric_value, sample_size)
                        VALUES (:date, 'brand', :brand, :metric, :value, :bars)
                        ON CONFLICT (snapshot_date, scope, scope_name, metric_name)
                        DO UPDATE SET metric_value = :value, sample_size = :bars
                    """),
                    {
                        "date": today, "brand": brand_name,
                        "metric": metric_name, "value": value,
                        "bars": len(sorted_bars),
                    },
                )
            conn.commit()
    except Exception as e:
        print(f"    Failed to store daily summary for {brand_name}: {e}")


def main():
    if not ALPHAVANTAGE_API_KEY:
        print("ALPHAVANTAGE_API_KEY not set — skipping brand stocks")
        sys.exit(0)

    engine = _get_engine()
    if not engine:
        print("DATABASE_URL not set — skipping brand stocks")
        sys.exit(0)

    if not is_market_hours():
        print("Outside US market hours — skipping brand stock fetch")
        sys.exit(0)

    ensure_brand_stocks_table(engine)

    print("Fetching intraday brand stock data...")
    fetched = 0

    for i, (brand_name, ticker) in enumerate(BRAND_TICKER_MAP.items()):
        if i > 0:
            time.sleep(RATE_LIMIT_SLEEP)

        print(f"  Fetching {brand_name} ({ticker})...")
        bars = fetch_intraday(ticker)
        if bars:
            stored = store_bars(engine, brand_name, ticker, bars)
            store_daily_summary(engine, brand_name, bars)
            print(f"    {stored} bars stored, latest close: ${bars[0]['close_price']:.2f}")
            fetched += 1
        else:
            print(f"    No data for {brand_name}")

    print(f"\nBrand stocks: {fetched}/{len(BRAND_TICKER_MAP)} tickers fetched")


if __name__ == "__main__":
    main()
