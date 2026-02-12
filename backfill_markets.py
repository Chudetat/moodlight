#!/usr/bin/env python
"""
One-time backfill: fetch 7 days of daily market data from AlphaVantage
TIME_SERIES_DAILY and insert into the PostgreSQL markets table.
"""

import os
import sys
import time
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

INDICES = {
    "SPY": "S&P 500",
    "DIA": "Dow Jones",
    "QQQ": "NASDAQ",
    "EWU": "FTSE 100",
    "EWJ": "Nikkei 225",
    "EWG": "DAX",
    "FXI": "China Markets",
}

BACKFILL_DAYS = 7


def fetch_daily_series(symbol: str):
    """Fetch recent daily OHLCV data for a symbol."""
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "compact",
        "apikey": ALPHAVANTAGE_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code != 200:
        print(f"  Error fetching {symbol}: HTTP {resp.status_code}")
        return None
    data = resp.json()
    ts = data.get("Time Series (Daily)")
    if not ts:
        print(f"  No daily data for {symbol}: {list(data.keys())}")
        return None
    return ts


def main():
    if not ALPHAVANTAGE_API_KEY:
        print("ERROR: ALPHAVANTAGE_API_KEY not set")
        sys.exit(1)
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=BACKFILL_DAYS)).strftime("%Y-%m-%d")
    print(f"Backfilling market data from {cutoff} onward\n")

    # Collect rows keyed by trading day
    day_rows = {}  # date_str -> list of market dicts

    for symbol, name in INDICES.items():
        print(f"Fetching daily series for {name} ({symbol})...")
        ts = fetch_daily_series(symbol)
        time.sleep(15)  # rate limit
        if not ts:
            continue

        for date_str, bar in sorted(ts.items()):
            if date_str < cutoff:
                continue
            prev_close = float(bar["1. open"])  # approximate prev close with open
            close = float(bar["4. close"])
            change = close - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0

            day_rows.setdefault(date_str, []).append({
                "symbol": symbol,
                "name": name,
                "price": close,
                "change": round(change, 4),
                "change_percent": round(change_pct, 4),
                "volume": bar["5. volume"],
                "latest_trading_day": date_str,
            })
            print(f"  {date_str} {name}: {change_pct:+.2f}%")

    if not day_rows:
        print("No data collected")
        sys.exit(1)

    # Calculate sentiment per day and build final rows
    all_rows = []
    for date_str in sorted(day_rows):
        markets = day_rows[date_str]
        changes = [float(m["change_percent"]) for m in markets]
        avg_change = sum(changes) / len(changes)
        sentiment = max(0.0, min(1.0, (avg_change + 5) / 10))

        timestamp = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).isoformat()
        for m in markets:
            all_rows.append({
                "timestamp": timestamp,
                "symbol": m["symbol"],
                "name": m["name"],
                "price": m["price"],
                "change": m["change"],
                "change_percent": m["change_percent"],
                "volume": m["volume"],
                "latest_trading_day": m["latest_trading_day"],
                "market_sentiment": sentiment,
            })
        print(f"\n{date_str}: sentiment={sentiment:.3f} ({len(markets)} indices)")

    # Write to DB
    db_url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    if "sslmode" not in db_url:
        sep = "&" if "?" in db_url else "?"
        db_url = db_url + sep + "sslmode=require"
    engine = create_engine(db_url, pool_pre_ping=True)

    df = pd.DataFrame(all_rows)
    trading_days = df["latest_trading_day"].unique().tolist()

    # Remove existing rows for these days to avoid dupes
    with engine.connect() as conn:
        for day in trading_days:
            conn.execute(text("DELETE FROM markets WHERE latest_trading_day = :day"), {"day": day})
        conn.commit()
    print(f"\nCleared existing rows for {len(trading_days)} trading days")

    df.to_sql("markets", engine, if_exists="append", index=False)
    print(f"Inserted {len(df)} rows across {len(trading_days)} trading days")
    print("Backfill complete!")


if __name__ == "__main__":
    main()
