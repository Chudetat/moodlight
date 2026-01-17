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
    
    with engine.connect() as conn:
        # Drop and recreate table to ensure correct schema
        conn.execute(text("DROP TABLE IF EXISTS news_scored"))
        conn.execute(text("""
            CREATE TABLE news_scored (
                id TEXT PRIMARY KEY,
                text TEXT,
                created_at TIMESTAMP WITH TIME ZONE,
                link TEXT,
                source TEXT,
                topic TEXT,
                engagement FLOAT DEFAULT 0,
                country TEXT,
                intensity FLOAT,
                empathy_score FLOAT,
                empathy_label TEXT,
                emotion_top_1 TEXT,
                emotion_top_2 TEXT,
                emotion_top_3 TEXT
            )
        """))
        conn.commit()
        
        # Only keep columns that exist in table
        valid_cols = ["id", "text", "created_at", "link", "source", "topic", 
                      "engagement", "country", "intensity", "empathy_score", 
                      "empathy_label", "emotion_top_1", "emotion_top_2", "emotion_top_3"]
        df_clean = df[[c for c in valid_cols if c in df.columns]].copy()
        
        print(f"📥 Inserting {len(df_clean)} rows")
        df_clean.to_sql("news_scored", conn, if_exists="append", index=False, chunksize=50)
        conn.commit()
    
    print("✅ News data saved to PostgreSQL")

if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "news_scored.csv"
    save_news_to_db(csv_path)
