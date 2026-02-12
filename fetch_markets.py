#!/usr/bin/env python
import time
"""
fetch_markets.py
Fetches major global market indices and calculates market sentiment.
Creates markets.csv with daily market data and sentiment scores.
"""

import os
import sys
import csv
import requests
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

# Config
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
OUTPUT_CSV = "markets.csv"

# Major indices to track
INDICES = {
    "SPY": "S&P 500",
    "DIA": "Dow Jones",
    "QQQ": "NASDAQ",
    "EWU": "FTSE 100",
    "EWJ": "Nikkei 225",
    "EWG": "DAX",
    "FXI": "China Markets"
}

def fetch_index_data(symbol: str) -> Dict:
    """Fetch latest data for a market index"""
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": ALPHAVANTAGE_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            print(f"   Error fetching {symbol}: Status {response.status_code}")
            return None
            
        data = response.json()
        
        if "Global Quote" not in data or not data["Global Quote"]:
            print(f"   No data returned for {symbol}")
            return None
            
        quote = data["Global Quote"]
        
        # Extract relevant data
        return {
            "symbol": symbol,
            "price": float(quote.get("05. price", 0)),
            "change": float(quote.get("09. change", 0)),
            "change_percent": quote.get("10. change percent", "0%").replace("%", ""),
            "volume": quote.get("06. volume", "0"),
            "latest_trading_day": quote.get("07. latest trading day", ""),
        }
        
    except requests.RequestException as e:
        print(f"   Network error fetching {symbol}: {e}")
        return None
    except (KeyError, ValueError) as e:
        print(f"   Data parsing error for {symbol}: {e}")
        return None

def calculate_market_sentiment(markets_data: List[Dict]) -> float:
    """
    Calculate overall market sentiment score (0-1 scale)
    Based on percentage changes across all indices
    
    Logic:
    - Average the % changes
    - Normalize to 0-1 scale where:
      - Strong rally (+3% avg) = 0.9
      - Flat (0%) = 0.5
      - Strong selloff (-3% avg) = 0.1
    """
    if not markets_data:
        return 0.5  # Neutral if no data
    
    # Calculate average percent change
    total_change = 0
    count = 0
    
    for market in markets_data:
        try:
            change_pct = float(market["change_percent"])
            total_change += change_pct
            count += 1
        except (ValueError, KeyError):
            continue
    
    if count == 0:
        return 0.5
    
    avg_change = total_change / count
    
    # Normalize to 0-1 scale
    # Map -5% to 0.0, 0% to 0.5, +5% to 1.0
    # Formula: sentiment = (avg_change + 5) / 10
    # Clamp between 0 and 1
    sentiment = (avg_change + 5) / 10
    sentiment = max(0.0, min(1.0, sentiment))
    
    return sentiment

def main():
    print("=" * 60)
    print("FETCHING GLOBAL MARKET DATA")
    print("=" * 60)
    
    if not ALPHAVANTAGE_API_KEY:
        print("ERROR: ALPHAVANTAGE_API_KEY not set")
        sys.exit(1)
    
    markets_data = []
    
    print(f"Fetching {len(INDICES)} major indices...")
    
    for symbol, name in INDICES.items():
        print(f"   Fetching {name} ({symbol})...")
        data = fetch_index_data(symbol)
        time.sleep(15)
        
        if data:
            data["name"] = name
            markets_data.append(data)
            print(f"      ✓ {name}: {data['change_percent']}%")
        else:
            print(f"      ✗ Failed to fetch {name}")
    
    if not markets_data:
        print("\nNo market data retrieved")
        sys.exit(1)
    
    # Calculate overall sentiment
    sentiment = calculate_market_sentiment(markets_data)
    
    print(f"\n{'='*60}")
    print(f"MARKET SENTIMENT: {sentiment:.3f} (0=Bearish, 0.5=Neutral, 1=Bullish)")
    print(f"{'='*60}")
    
    # Prepare rows for CSV
    timestamp = datetime.now(timezone.utc).isoformat()
    
    rows = []
    for market in markets_data:
        rows.append({
            "timestamp": timestamp,
            "symbol": market["symbol"],
            "name": market["name"],
            "price": market["price"],
            "change": market["change"],
            "change_percent": market["change_percent"],
            "volume": market["volume"],
            "latest_trading_day": market["latest_trading_day"],
            "market_sentiment": sentiment
        })
    
    # Write to CSV
    fieldnames = [
        "timestamp", "symbol", "name", "price", "change", 
        "change_percent", "volume", "latest_trading_day", "market_sentiment"
    ]
    
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\nSaved {len(rows)} market records to {OUTPUT_CSV}")
    print(f"Overall market sentiment: {sentiment:.3f}")

    # Save to PostgreSQL for historical tracking
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            db_url = db_url.replace("postgres://", "postgresql://", 1)
            if "sslmode" not in db_url:
                separator = "&" if "?" in db_url else "?"
                db_url = db_url + separator + "sslmode=require"
            engine = create_engine(db_url, pool_pre_ping=True)

            trading_day = rows[0]["latest_trading_day"]

            # Delete existing rows for this trading day to avoid dupes on re-runs
            with engine.connect() as conn:
                conn.execute(
                    text("DELETE FROM markets WHERE latest_trading_day = :day"),
                    {"day": trading_day},
                )
                conn.commit()

            df = pd.DataFrame(rows)
            df.to_sql("markets", engine, if_exists="append", index=False)
            print(f"Saved {len(rows)} rows to PostgreSQL (markets table, trading day {trading_day})")
        except Exception as e:
            # Table may not exist yet on first run — use append which auto-creates
            try:
                df = pd.DataFrame(rows)
                df.to_sql("markets", engine, if_exists="append", index=False)
                print(f"Created markets table and saved {len(rows)} rows to PostgreSQL")
            except Exception as e2:
                print(f"Warning: Could not save to database: {e2}")
    else:
        print("DATABASE_URL not set — skipping database save")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
