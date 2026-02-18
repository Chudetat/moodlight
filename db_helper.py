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
    "brand_stocks",
}

_engine_instance = None

def get_engine():
    global _engine_instance
    if _engine_instance is not None:
        return _engine_instance
    if not DATABASE_URL:
        return None
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    if "sslmode" not in url:
        sep = "&" if "?" in url else "?"
        url = url + sep + "sslmode=require"
    _engine_instance = create_engine(
        url, pool_pre_ping=True, pool_recycle=300,
        pool_size=3, max_overflow=2, pool_timeout=30,
    )
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

def load_metric_trends(scope: str, scope_name: str = None, metric_name: str = None, days: int = 30):
    """Load historical metric trends from metric_snapshots.

    Parameters:
        scope: 'global', 'brand', or 'topic'
        scope_name: brand/topic name (None for global)
        metric_name: specific metric or None for all
        days: lookback window (7, 30, 60, 90)

    Returns DataFrame with snapshot_date, metric_name, metric_value, sample_size.
    """
    engine = get_engine()
    if not engine:
        return pd.DataFrame()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        conditions = ["scope = :scope", "snapshot_date >= :cutoff"]
        params = {"scope": scope, "cutoff": cutoff}
        if scope_name:
            conditions.append("scope_name = :scope_name")
            params["scope_name"] = scope_name
        if metric_name:
            conditions.append("metric_name = :metric_name")
            params["metric_name"] = metric_name
        where = " AND ".join(conditions)
        query = sql_text(f"""
            SELECT snapshot_date, scope_name, metric_name, metric_value, sample_size
            FROM metric_snapshots
            WHERE {where}
            ORDER BY snapshot_date ASC
            LIMIT 1000
        """)
        return pd.read_sql(query, engine, params=params)
    except Exception:
        return pd.DataFrame()


def load_economic_data(days=30):
    """Load economic indicator data from metric_snapshots."""
    return load_metric_trends(scope="economic", days=days)


def load_commodity_data(days=7):
    """Load commodity price data from metric_snapshots."""
    return load_metric_trends(scope="commodity", days=days)


def load_brand_stock_data(ticker, days=2):
    """Load intraday brand stock bars from brand_stocks table."""
    engine = get_engine()
    if not engine:
        return pd.DataFrame()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        query = sql_text("""
            SELECT bar_datetime, open_price, high_price, low_price, close_price, volume
            FROM brand_stocks
            WHERE ticker = :ticker AND bar_datetime >= :cutoff
            ORDER BY bar_datetime ASC
        """)
        return pd.read_sql(query, engine, params={"ticker": ticker, "cutoff": cutoff})
    except Exception:
        return pd.DataFrame()


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
            df = pd.read_sql(f"SELECT * FROM {table_name} LIMIT 5000", engine)
            return df, None
        except Exception as e2:
            return pd.DataFrame(), f"DB query failed: {e2}"
