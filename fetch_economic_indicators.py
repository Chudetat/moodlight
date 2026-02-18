#!/usr/bin/env python
"""
fetch_economic_indicators.py
Fetches 6 key economic indicators from AlphaVantage and stores them
in the metric_snapshots table (scope='economic').

Indicators:
  - Treasury Yield (10-year)
  - CPI (year-over-year)
  - Unemployment Rate
  - Federal Funds Rate
  - Inflation Rate
  - Nonfarm Payroll

Designed to run hourly in the pipeline but internally skips
indicators already captured for the current date.
"""

import os
import sys
import time
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

# Each indicator: (function, params, metric_name, description)
INDICATORS = [
    ("TREASURY_YIELD", {"interval": "daily", "maturity": "10year"}, "treasury_yield_10y", "10-Year Treasury Yield"),
    ("CPI", {"interval": "monthly"}, "cpi_yoy", "CPI Year-over-Year"),
    ("UNEMPLOYMENT", {}, "unemployment_rate", "Unemployment Rate"),
    ("FEDERAL_FUNDS_RATE", {"interval": "daily"}, "federal_funds_rate", "Federal Funds Rate"),
    ("INFLATION", {}, "inflation_rate", "Inflation Rate"),
    ("NONFARM_PAYROLL", {}, "nonfarm_payroll", "Nonfarm Payroll (thousands)"),
]

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


def _cleanup_null_scope_rows(engine):
    """One-time cleanup: delete economic rows with NULL scope_name.
    NULL scope_name breaks PostgreSQL ON CONFLICT (NULL != NULL),
    causing duplicate rows on every pipeline run.
    """
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("DELETE FROM metric_snapshots WHERE scope = 'economic' AND scope_name IS NULL")
            )
            conn.commit()
            if result.rowcount > 0:
                print(f"  Cleaned up {result.rowcount} legacy NULL scope_name rows")
    except Exception as e:
        print(f"  Cleanup note: {e}")


def already_captured_today(engine, metric_name):
    """Check if this metric already has a snapshot for today."""
    from sqlalchemy import text
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT 1 FROM metric_snapshots
                    WHERE scope = 'economic' AND metric_name = :metric
                      AND scope_name = '' AND snapshot_date = :today
                    LIMIT 1
                """),
                {"metric": metric_name, "today": today},
            )
            return result.fetchone() is not None
    except Exception:
        return False


def fetch_indicator(function_name, extra_params):
    """Fetch a single indicator from AlphaVantage.

    Returns (date, value, records) where records is the full data array,
    or None on failure.
    """
    url = "https://www.alphavantage.co/query"
    params = {"function": function_name, "apikey": ALPHAVANTAGE_API_KEY}
    params.update(extra_params)

    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            print(f"    HTTP {response.status_code} for {function_name}")
            return None

        data = response.json()

        # Check for rate limit / error messages
        if "Note" in data or "Information" in data:
            msg = data.get("Note") or data.get("Information")
            print(f"    API message for {function_name}: {msg}")
            return None

        # AlphaVantage returns {"name": "...", "data": [{"date": "...", "value": "..."}]}
        records = data.get("data", [])
        if not records:
            print(f"    No data records for {function_name}")
            return None

        # Take the most recent non-empty value
        for record in records:
            val_str = record.get("value", "").strip()
            if val_str and val_str != ".":
                try:
                    return (record["date"], float(val_str), records)
                except (ValueError, KeyError):
                    continue

        print(f"    No valid numeric values for {function_name}")
        return None

    except requests.RequestException as e:
        print(f"    Network error for {function_name}: {e}")
        return None


def _parse_records(records):
    """Parse records into list of (date_str, float_value) tuples."""
    parsed = []
    for r in records:
        val_str = r.get("value", "").strip()
        if val_str and val_str != ".":
            try:
                parsed.append((r["date"], float(val_str)))
            except (ValueError, KeyError):
                continue
    return parsed


def _compute_cpi_yoy(records):
    """Compute CPI year-over-year % change from monthly index values."""
    parsed = _parse_records(records)
    return _compute_cpi_yoy_at(parsed, 0)


def _compute_cpi_yoy_at(parsed, month_offset):
    """Compute CPI YoY % for the month at the given offset (0=latest, 1=previous)."""
    if len(parsed) <= month_offset:
        return None
    ref_date, ref_val = parsed[month_offset]
    ref_year = int(ref_date[:4])
    ref_month = int(ref_date[5:7])
    target_date_prefix = f"{ref_year - 1}-{ref_month:02d}"
    for date_str, val in parsed:
        if date_str.startswith(target_date_prefix) and val > 0:
            yoy_pct = (ref_val - val) / val * 100
            return (ref_date, round(yoy_pct, 2))
    return None


def _compute_nonfarm_change(records):
    """Compute month-over-month nonfarm payroll change (thousands)."""
    parsed = _parse_records(records)
    if len(parsed) < 2:
        return None
    latest_date, latest_val = parsed[0]
    _, prev_val = parsed[1]
    change = latest_val - prev_val
    return (latest_date, round(change, 0))


def store_indicator(engine, metric_name, date_str, value):
    """Store indicator value in metric_snapshots with ON CONFLICT update."""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO metric_snapshots
                        (snapshot_date, scope, scope_name, metric_name, metric_value, sample_size)
                    VALUES (:date, 'economic', '', :metric, :value, 1)
                    ON CONFLICT (snapshot_date, scope, scope_name, metric_name)
                    DO UPDATE SET metric_value = :value
                """),
                {"date": date_str, "metric": metric_name, "value": value},
            )
            conn.commit()
            return True
    except Exception as e:
        print(f"    DB error storing {metric_name}: {e}")
        return False


def main():
    if not ALPHAVANTAGE_API_KEY:
        print("ALPHAVANTAGE_API_KEY not set — skipping economic indicators")
        sys.exit(0)

    engine = _get_engine()
    if not engine:
        print("DATABASE_URL not set — skipping economic indicators")
        sys.exit(0)

    # One-time cleanup of NULL scope_name rows (caused duplicate inserts)
    _cleanup_null_scope_rows(engine)

    print("Fetching economic indicators...")
    fetched = 0
    skipped = 0

    for i, (function_name, extra_params, metric_name, description) in enumerate(INDICATORS):
        # Skip if already captured today
        if already_captured_today(engine, metric_name):
            print(f"  {description}: already captured today — skipping")
            skipped += 1
            continue

        # Rate limit between API calls (skip delay on first call)
        if i > 0 and fetched > 0:
            time.sleep(RATE_LIMIT_SLEEP)

        print(f"  Fetching {description}...")
        result = fetch_indicator(function_name, extra_params)
        if result:
            date_str, value, records = result

            # Compute derived value for CPI (YoY % from raw index)
            if metric_name == "cpi_yoy":
                derived = _compute_cpi_yoy(records)
                if derived:
                    date_str, value = derived
                    print(f"    CPI YoY computed: {value}% (from index, date: {date_str})")
                else:
                    print(f"    Could not compute CPI YoY — storing raw index")
            # Nonfarm: store raw total (non-seasonally-adjusted, MoM change is misleading)

            if store_indicator(engine, metric_name, date_str, value):
                print(f"    {metric_name} = {value} (date: {date_str})")
                fetched += 1

                # Also store previous value for dashboard delta arrows
                parsed = _parse_records(records)
                if metric_name == "cpi_yoy" and len(parsed) >= 14:
                    prev_yoy = _compute_cpi_yoy_at(parsed, 1)
                    if prev_yoy:
                        store_indicator(engine, metric_name, prev_yoy[0], prev_yoy[1])
                elif metric_name == "nonfarm_payroll":
                    pass  # No delta for nonfarm (non-seasonally-adjusted data)
                elif len(parsed) >= 2:
                    store_indicator(engine, metric_name, parsed[1][0], parsed[1][1])
            else:
                print(f"    Failed to store {metric_name}")
        else:
            print(f"    No data for {description}")

    print(f"\nEconomic indicators: {fetched} fetched, {skipped} skipped (already captured)")


if __name__ == "__main__":
    main()
