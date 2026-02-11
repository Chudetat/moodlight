#!/usr/bin/env python
"""Save scored CSV data to PostgreSQL with retry logic"""
import os
import sys
import time
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5


def create_db_engine(db_url: str):
    """Create SQLAlchemy engine with connection pool settings for reliability"""
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"connect_timeout": 10},
    )


def save_to_db(csv_path: str, table_name: str):
    """Save scored CSV to PostgreSQL table"""

    if not os.path.exists(csv_path):
        print(f"❌ {csv_path} not found")
        return

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL not set")
        return

    engine = create_db_engine(db_url)
    df = pd.read_csv(csv_path)

    print(f"📊 Loaded {len(df)} rows from {csv_path}")

    # Convert created_at to datetime with UTC
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], format="mixed", utc=True, errors="coerce")

    # Only keep columns that exist in table
    valid_cols = ["id", "text", "created_at", "link", "source", "topic",
                  "engagement", "country", "intensity", "empathy_score",
                  "empathy_label", "emotion_top_1", "emotion_top_2", "emotion_top_3"]
    df_clean = df[[c for c in valid_cols if c in df.columns]].copy()

    # Remove duplicate IDs
    orig_len = len(df_clean)
    df_clean = df_clean.drop_duplicates(subset=["id"], keep="first")
    if len(df_clean) < orig_len:
        print(f"⚠️ Removed {orig_len - len(df_clean)} duplicate IDs")

    # Retry loop for database insertion
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"📥 Inserting {len(df_clean)} rows into {table_name} (attempt {attempt}/{MAX_RETRIES})...")
            df_clean.to_sql(table_name, engine, if_exists="replace", index=False, chunksize=50)
            print(f"✅ Data saved to PostgreSQL table: {table_name}")
            return
        except Exception as e:
            print(f"❌ Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY_SECONDS * attempt
                print(f"⏳ Retrying in {wait}s...")
                time.sleep(wait)
                # Recreate engine to get a fresh connection
                engine.dispose()
                engine = create_db_engine(db_url)
            else:
                print(f"❌ All {MAX_RETRIES} attempts failed. Database may be unreachable.")
                raise


if __name__ == "__main__":
    # Default: save news_scored.csv to news_scored table
    # Can also be called with: python save_to_db.py social_scored.csv social_scored
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "news_scored.csv"
    table_name = sys.argv[2] if len(sys.argv) > 2 else csv_path.replace(".csv", "")
    save_to_db(csv_path, table_name)
