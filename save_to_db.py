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
    
    engine = create_engine(db_url)
    df = pd.read_csv(csv_path)
    
    print(f"📊 Loaded {len(df)} rows from {csv_path}")
    
    # Convert created_at to datetime
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    
    # Upsert to database (delete old, insert new)
    with engine.connect() as conn:
        # Clear existing data older than 7 days
        conn.execute(text("""
            DELETE FROM news_scored 
            WHERE created_at < NOW() - INTERVAL '7 days'
        """))
        
        # Get existing IDs
        result = conn.execute(text("SELECT id FROM news_scored"))
        existing_ids = set(row[0] for row in result)
        
        # Filter to new rows only
        df_new = df[~df["id"].isin(existing_ids)]
        print(f"📥 Inserting {len(df_new)} new rows")
        
        if len(df_new) > 0:
            df_new.to_sql("news_scored", conn, if_exists="append", index=False)
        
        conn.commit()
    
    print("✅ News data saved to PostgreSQL")

if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "news_scored.csv"
    save_news_to_db(csv_path)
