#!/usr/bin/env python
"""Save scored CSV data to PostgreSQL"""
import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def save_news_to_db(csv_path: str = "news_scored.csv"):
    """Save news_scored.csv to PostgreSQL news_scored table"""
    
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
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")

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
        print(f"📥 Inserting {len(df_clean)} rows...")
        df_clean.to_sql("news_scored", engine, if_exists="replace", index=False, chunksize=50)
        print("✅ News data saved to PostgreSQL")
    except Exception as e:
        print(f"❌ Error inserting data: {e}")
        raise

if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "news_scored.csv"
    save_news_to_db(csv_path)
