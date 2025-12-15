"""Database helper for shared Postgres storage."""
import os
import pandas as pd
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "")

def get_engine():
    if not DATABASE_URL:
        return None
    # Railway uses postgres:// but sqlalchemy needs postgresql://
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    return create_engine(url)

def init_tables():
    """Create tables if they don't exist."""
    engine = get_engine()
    if not engine:
        return
    
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS news (
                id TEXT PRIMARY KEY,
                text TEXT,
                created_at TIMESTAMP,
                link TEXT,
                source TEXT,
                topic TEXT,
                engagement INTEGER,
                country TEXT,
                intensity REAL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS social (
                id TEXT PRIMARY KEY,
                text TEXT,
                created_at TIMESTAMP,
                link TEXT,
                source TEXT,
                topic TEXT,
                engagement INTEGER,
                country TEXT,
                intensity REAL,
                empathy_score REAL,
                empathy_label TEXT
            )
        """))
        conn.commit()

def save_news_to_db(df: pd.DataFrame):
    """Save news dataframe to database."""
    engine = get_engine()
    if not engine or df.empty:
        return
    
    # Upsert - replace existing entries
    df.to_sql("news", engine, if_exists="replace", index=False)

def load_news_from_db() -> pd.DataFrame:
    """Load news from database."""
    engine = get_engine()
    if not engine:
        return pd.DataFrame()
    
    try:
        return pd.read_sql("SELECT * FROM news", engine)
    except:
        return pd.DataFrame()

def save_social_to_db(df: pd.DataFrame):
    """Save social dataframe to database."""
    engine = get_engine()
    if not engine or df.empty:
        return
    
    df.to_sql("social", engine, if_exists="replace", index=False)

def load_social_from_db() -> pd.DataFrame:
    """Load social from database."""
    engine = get_engine()
    if not engine:
        return pd.DataFrame()
    
    try:
        return pd.read_sql("SELECT * FROM social", engine)
    except:
        return pd.DataFrame()
