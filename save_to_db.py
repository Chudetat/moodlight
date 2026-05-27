#!/usr/bin/env python
"""Save scored CSV data to PostgreSQL with retry logic"""
import os
import sys
import time
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 5
ALLOWED_TABLES = {"news_scored", "social_scored"}


def create_db_engine(db_url: str):
    """Create SQLAlchemy engine with connection pool settings for reliability"""
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    # Add sslmode=require if no sslmode is set (Railway typically requires SSL)
    if "sslmode" not in db_url:
        separator = "&" if "?" in db_url else "?"
        db_url = db_url + separator + "sslmode=require"
    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=1,
        max_overflow=0,
        connect_args={
            "connect_timeout": 30,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
    )


def save_to_db(csv_path: str, table_name: str):
    """Save scored CSV to PostgreSQL table"""

    if table_name not in ALLOWED_TABLES:
        print(f"❌ Invalid table name: {table_name}. Allowed: {ALLOWED_TABLES}")
        return

    if not os.path.exists(csv_path):
        print(f"❌ {csv_path} not found")
        return

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL not set")
        return

    engine = create_db_engine(db_url)

    # Pipeline run tracking
    run_id = None
    try:
        from alert_pipeline import start_pipeline_run, complete_pipeline_run
        run_id = start_pipeline_run(engine, f"save_to_db_{table_name}")
    except Exception as e:
        print(f"WARNING: start_pipeline_run tracking failed: {e}")

    df = pd.read_csv(csv_path)

    print(f"📊 Loaded {len(df)} rows from {csv_path}")

    # Convert created_at to datetime with UTC
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], format="mixed", utc=True, errors="coerce")

    # Only keep columns that exist in table
    valid_cols = ["id", "text", "created_at", "link", "source", "topic", "audience",
                  "engagement", "country", "intensity", "empathy_score",
                  "empathy_label", "emotion_top_1", "emotion_top_2", "emotion_top_3"]
    df_clean = df[[c for c in valid_cols if c in df.columns]].copy()

    # Remove duplicate IDs
    orig_len = len(df_clean)
    df_clean = df_clean.drop_duplicates(subset=["id"], keep="last")
    if len(df_clean) < orig_len:
        print(f"⚠️ Removed {orig_len - len(df_clean)} duplicate IDs")

    # Retry loop for database insertion
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Pre-flight: verify we can connect before attempting bulk insert
            print(f"🔌 Testing connection (attempt {attempt}/{MAX_RETRIES})...")
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"✅ Connection OK")

            # Upsert: delete existing rows with matching IDs, then append new data.
            # This preserves historical data from previous runs while updating
            # any posts that appear in the new batch.
            print(f"📥 Upserting {len(df_clean)} rows into {table_name}...")

            # Ensure table exists (create if first run)
            with engine.connect() as setup_conn:
                table_exists = setup_conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"),
                    {"t": table_name},
                ).scalar()

            if not table_exists:
                # First run — create the table
                df_clean.to_sql(table_name, engine, if_exists="replace", index=False, chunksize=25)
                print(f"✅ Created new table: {table_name}")
            else:
                # Ensure newer columns exist on pre-existing tables (idempotent).
                # Gated on the column being present in this batch, so it only
                # touches tables that actually carry the field (e.g. news_data).
                if "audience" in df_clean.columns:
                    with engine.connect() as mig_conn:
                        mig_conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS audience TEXT"))
                        mig_conn.commit()
                # Delete rows with matching IDs, then append
                if "id" in df_clean.columns and len(df_clean) > 0:
                    new_ids = df_clean["id"].dropna().tolist()
                    if new_ids:
                        # Batch delete in chunks to avoid query size limits
                        chunk_size = 500
                        with engine.connect() as del_conn:
                            for i in range(0, len(new_ids), chunk_size):
                                chunk = new_ids[i:i + chunk_size]
                                placeholders = ",".join([f":id_{j}" for j in range(len(chunk))])
                                params = {f"id_{j}": str(v) for j, v in enumerate(chunk)}
                                del_conn.execute(
                                    text(f"DELETE FROM {table_name} WHERE id IN ({placeholders})"),
                                    params,
                                )
                            del_conn.commit()
                        print(f"🔄 Removed {len(new_ids)} existing rows for upsert")

                # Append new data
                df_clean.to_sql(table_name, engine, if_exists="append", index=False, chunksize=25)
                print(f"✅ Appended {len(df_clean)} rows to {table_name}")

            try:
                complete_pipeline_run(engine, run_id, "success", len(df_clean))
            except Exception as e:
                print(f"WARNING: complete_pipeline_run success tracking failed: {e}")

            # Add performance indexes
            try:
                with engine.connect() as idx_conn:
                    idx_conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_created_at ON {table_name} (created_at)"))
                    idx_conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_topic ON {table_name} (topic)"))
                    idx_conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_source ON {table_name} (source)"))
                    idx_conn.commit()
                print(f"📇 Indexes created on {table_name}")
            except Exception as idx_err:
                print(f"⚠️ Index creation failed (non-fatal): {idx_err}")

            return
        except Exception as e:
            print(f"❌ Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                wait = INITIAL_RETRY_DELAY * (2 ** (attempt - 1))  # exponential: 5, 10, 20, 40
                print(f"⏳ Retrying in {wait}s...")
                time.sleep(wait)
                # Recreate engine to get a fresh connection
                engine.dispose()
                engine = create_db_engine(db_url)
            else:
                print(f"❌ All {MAX_RETRIES} attempts failed. Database may be unreachable.")
                try:
                    complete_pipeline_run(engine, run_id, "failed", 0, str(e)[:500])
                except Exception as e2:
                    print(f"WARNING: complete_pipeline_run failure tracking failed: {e2}")
                raise


if __name__ == "__main__":
    # Default: save news_scored.csv to news_scored table
    # Can also be called with: python save_to_db.py social_scored.csv social_scored
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "news_scored.csv"
    table_name = sys.argv[2] if len(sys.argv) > 2 else csv_path.replace(".csv", "")
    save_to_db(csv_path, table_name)
