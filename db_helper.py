import os
from datetime import datetime, timedelta, timezone
import pandas as pd
from sqlalchemy import create_engine, text as sql_text

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Data retention period (matches X API recent search window)
DATA_RETENTION_DAYS = 7

# Valid table names for query safety
ALLOWED_TABLES = {
    "news_scored", "social_scored", "markets", "alerts",
    "metric_snapshots", "competitive_snapshots",
    "brand_watchlist", "topic_watchlist", "users",
}

_engine_instance = None

def get_engine():
    global _engine_instance
    if _engine_instance is not None:
        return _engine_instance
    if not DATABASE_URL:
        return None
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    _engine_instance = create_engine(url, pool_pre_ping=True, pool_recycle=300)
    return _engine_instance

def save_df_to_db(df, table_name):
    engine = get_engine()
    if not engine or df.empty:
        return False
    try:
        df.to_sql(table_name, engine, if_exists="replace", index=False, chunksize=50)
        return True
    except Exception as e:
        print(f"DB error: {e}")
        return False

def load_df_from_db(table_name):
    """Load data from database, filtered to last 7 days only.

    Returns (DataFrame, status_message) tuple.
    status_message is None on success, or a string describing the failure.
    """
    if table_name not in ALLOWED_TABLES:
        return pd.DataFrame(), f"Invalid table name: {table_name}"
    engine = get_engine()
    if not engine:
        return pd.DataFrame(), "DATABASE_URL not set"
    try:
        # Filter to last 7 days to match data retention policy
        cutoff = datetime.now(timezone.utc) - timedelta(days=DATA_RETENTION_DAYS)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
        query = sql_text(f"SELECT * FROM {table_name} WHERE created_at >= :cutoff")
        df = pd.read_sql(query, engine, params={"cutoff": cutoff_str})
        return df, None
    except Exception as e:
        # Fall back to loading all data if query fails (e.g., column doesn't exist)
        try:
            df = pd.read_sql(f"SELECT * FROM {table_name}", engine)
            return df, None
        except Exception as e2:
            return pd.DataFrame(), f"DB query failed: {e2}"
