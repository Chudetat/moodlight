#!/usr/bin/env python
"""Save scored CSV data to PostgreSQL"""
import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()


def save_to_db(csv_path: str, table_name: str):
    """Save scored CSV to PostgreSQL table"""

    if not os.path.exists(csv_path):
        print(f"❌ {csv_path} not found")
        return

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL not set")
        return

    db_url = db_url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(db_url)
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

    try:
        # Use if_exists="replace" to let pandas handle table creation
        # This avoids PRIMARY KEY constraint issues entirely
        print(f"📥 Inserting {len(df_clean)} rows into {table_name}...")
        df_clean.to_sql(table_name, engine, if_exists="replace", index=False, chunksize=50)
        print(f"✅ Data saved to PostgreSQL table: {table_name}")
    except Exception as e:
        print(f"❌ Error inserting data: {e}")
        raise


if __name__ == "__main__":
    # Default: save news_scored.csv to news_scored table
    # Can also be called with: python save_to_db.py social_scored.csv social_scored
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "news_scored.csv"
    table_name = sys.argv[2] if len(sys.argv) > 2 else csv_path.replace(".csv", "")
    save_to_db(csv_path, table_name)
