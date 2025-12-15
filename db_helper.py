import os
import pandas as pd
from sqlalchemy import create_engine

DATABASE_URL = os.environ.get("DATABASE_URL", "")

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
        df.to_sql(table_name, engine, if_exists="replace", index=False)
        return True
    except Exception as e:
        print(f"DB error: {e}")
        return False

def load_df_from_db(table_name):
    engine = get_engine()
    if not engine:
        return pd.DataFrame()
    try:
        return pd.read_sql(f"SELECT * FROM {table_name}", engine)
    except:
        return pd.DataFrame()
