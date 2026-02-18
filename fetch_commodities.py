#!/usr/bin/env python
"""
fetch_commodities.py
Fetches 5 key commodity prices from AlphaVantage and stores them
in the metric_snapshots table (scope='commodity').

Commodities:
  - WTI (Crude Oil)
  - BRENT (Brent Crude)
  - NATURAL_GAS (Henry Hub)
  - COPPER
  - ALUMINUM

Stores both the price and daily_change_pct for each commodity.
Designed to run hourly but internally skips if already captured today.
"""

import os
import sys
import time
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

# Each commodity: (function, scope_name, description)
COMMODITIES = [
    ("WTI", "WTI", "Crude Oil (WTI)"),
    ("BRENT", "BRENT", "Brent Crude"),
    ("NATURAL_GAS", "NATURAL_GAS", "Natural Gas"),
    ("COPPER", "COPPER", "Copper"),
    ("ALUMINUM", "ALUMINUM", "Aluminum"),
]

# Which brands are affected by which commodities
COMMODITY_BRAND_RELEVANCE = {
    "WTI": ["Lockheed Martin"],
    "BRENT": ["Lockheed Martin"],
    "COPPER": ["NVIDIA"],
    "ALUMINUM": ["NVIDIA", "Amazon"],
}

RATE_LIMIT_SLEEP = 15  # seconds between API calls


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


def already_captured_today(engine, scope_name):
    """Check if this commodity already has a price snapshot for today."""
    from sqlalchemy import text
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT 1 FROM metric_snapshots
                    WHERE scope = 'commodity' AND scope_name = :name
                      AND metric_name = 'price' AND snapshot_date = :today
                    LIMIT 1
                """),
                {"name": scope_name, "today": today},
            )
            return result.fetchone() is not None
    except Exception:
        return False


def get_previous_price(engine, scope_name):
    """Get the most recent price before today for daily change calculation."""
    from sqlalchemy import text
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT metric_value FROM metric_snapshots
                    WHERE scope = 'commodity' AND scope_name = :name
                      AND metric_name = 'price' AND snapshot_date < :today
                    ORDER BY snapshot_date DESC LIMIT 1
                """),
                {"name": scope_name, "today": today},
            )
            row = result.fetchone()
            return row[0] if row else None
    except Exception:
        return None


def fetch_commodity(function_name):
    """Fetch a commodity price from AlphaVantage.

    Returns (date, value, prev_value) or None.
    prev_value is the previous data point for computing daily change.
    """
    url = "https://www.alphavantage.co/query"
    params = {
        "function": function_name,
        "interval": "daily",
        "apikey": ALPHAVANTAGE_API_KEY,
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            print(f"    HTTP {response.status_code} for {function_name}")
            return None

        data = response.json()

        if "Note" in data or "Information" in data:
            msg = data.get("Note") or data.get("Information")
            print(f"    API message for {function_name}: {msg}")
            return None

        records = data.get("data", [])
        if not records:
            print(f"    No data records for {function_name}")
            return None

        # Parse the two most recent valid values
        parsed = []
        for record in records:
            val_str = record.get("value", "").strip()
            if val_str and val_str != ".":
                try:
                    parsed.append((record["date"], float(val_str)))
                    if len(parsed) == 2:
                        break
                except (ValueError, KeyError):
                    continue

        if not parsed:
            print(f"    No valid numeric values for {function_name}")
            return None

        latest_date, latest_val = parsed[0]
        prev_val = parsed[1][1] if len(parsed) >= 2 else None
        return (latest_date, latest_val, prev_val)

    except requests.RequestException as e:
        print(f"    Network error for {function_name}: {e}")
        return None


def store_commodity(engine, scope_name, date_str, price, daily_change_pct=None):
    """Store commodity price and change in metric_snapshots."""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            # Store price
            conn.execute(
                text("""
                    INSERT INTO metric_snapshots
                        (snapshot_date, scope, scope_name, metric_name, metric_value, sample_size)
                    VALUES (:date, 'commodity', :name, 'price', :value, 1)
                    ON CONFLICT (snapshot_date, scope, scope_name, metric_name)
                    DO UPDATE SET metric_value = :value
                """),
                {"date": date_str, "name": scope_name, "value": price},
            )
            # Store daily change percent if available
            if daily_change_pct is not None:
                conn.execute(
                    text("""
                        INSERT INTO metric_snapshots
                            (snapshot_date, scope, scope_name, metric_name, metric_value, sample_size)
                        VALUES (:date, 'commodity', :name, 'daily_change_pct', :value, 1)
                        ON CONFLICT (snapshot_date, scope, scope_name, metric_name)
                        DO UPDATE SET metric_value = :value
                    """),
                    {"date": date_str, "name": scope_name, "value": daily_change_pct},
                )
            conn.commit()
            return True
    except Exception as e:
        print(f"    DB error storing {scope_name}: {e}")
        return False


def main():
    if not ALPHAVANTAGE_API_KEY:
        print("ALPHAVANTAGE_API_KEY not set — skipping commodities")
        sys.exit(0)

    engine = _get_engine()
    if not engine:
        print("DATABASE_URL not set — skipping commodities")
        sys.exit(0)

    print("Fetching commodity prices...")
    fetched = 0
    skipped = 0

    for i, (function_name, scope_name, description) in enumerate(COMMODITIES):
        if already_captured_today(engine, scope_name):
            print(f"  {description}: already captured today — skipping")
            skipped += 1
            continue

        if i > 0 and fetched > 0:
            time.sleep(RATE_LIMIT_SLEEP)

        print(f"  Fetching {description}...")
        result = fetch_commodity(function_name)
        if result:
            date_str, price, prev_val = result

            # Compute daily change from API response (previous data point)
            daily_change_pct = None
            if prev_val and prev_val > 0:
                daily_change_pct = ((price - prev_val) / prev_val) * 100

            if store_commodity(engine, scope_name, date_str, price, daily_change_pct):
                change_str = f", change: {daily_change_pct:+.2f}%" if daily_change_pct is not None else ""
                print(f"    {scope_name} = ${price:.2f}{change_str} (date: {date_str})")
                fetched += 1
            else:
                print(f"    Failed to store {scope_name}")
        else:
            print(f"    No data for {description}")

    print(f"\nCommodities: {fetched} fetched, {skipped} skipped (already captured)")


if __name__ == "__main__":
    main()
