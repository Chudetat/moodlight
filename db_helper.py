import os
from datetime import datetime, timedelta, timezone
import pandas as pd
from sqlalchemy import create_engine

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Data retention period (matches X API recent search window)
DATA_RETENTION_DAYS = 7

def get_engine():
    if not DATABASE_URL:
        return None
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    return create_engine(url)

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
    """Load data from database, filtered to last 7 days only."""
    engine = get_engine()
    if not engine:
        return pd.DataFrame()
    try:
        # Filter to last 7 days to match data retention policy
        cutoff = datetime.now(timezone.utc) - timedelta(days=DATA_RETENTION_DAYS)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
        query = f"SELECT * FROM {table_name} WHERE created_at >= '{cutoff_str}'"
        return pd.read_sql(query, engine)
    except Exception as e:
        # Fall back to loading all data if query fails (e.g., column doesn't exist)
        try:
            return pd.read_sql(f"SELECT * FROM {table_name}", engine)
        except:
            return pd.DataFrame()
