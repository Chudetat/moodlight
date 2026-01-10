#!/usr/bin/env python
"""Create news_data table in PostgreSQL"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS news_data (
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
            emotion_top_3 TEXT,
            scored_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    conn.commit()
    print("✅ news_data table created")
