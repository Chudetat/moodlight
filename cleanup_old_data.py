#!/usr/bin/env python
"""
cleanup_old_data.py
Prunes stale rows from large tables to prevent unbounded DB growth.

Retention policy:
  - news_scored, social_scored: 30 days
  - metric_snapshots: 90 days
  - pipeline_runs: 30 days

Safe: only deletes rows older than the retention window.
Run daily from fetch_news.yml pipeline.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()


def cleanup(engine):
    from sqlalchemy import text

    policies = [
        ("news_scored", "created_at", 30),
        ("social_scored", "created_at", 30),
        ("metric_snapshots", "snapshot_date", 90),
        ("pipeline_runs", "started_at", 30),
    ]

    total_deleted = 0
    for table, column, days in policies:
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(f"DELETE FROM {table} WHERE {column} < NOW() - INTERVAL ':days days'".replace(":days", str(int(days))))
                )
                deleted = result.rowcount
                conn.commit()
                if deleted > 0:
                    print(f"  Pruned {deleted} rows from {table} (older than {days} days)")
                    total_deleted += deleted
                else:
                    print(f"  {table}: nothing to prune")
        except Exception as e:
            # Table may not exist yet — skip gracefully
            print(f"  {table}: skipped ({e})")

    return total_deleted


if __name__ == "__main__":
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("DATABASE_URL not set — skipping cleanup")
        sys.exit(0)

    from sqlalchemy import create_engine
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    if "sslmode" not in db_url:
        sep = "&" if "?" in db_url else "?"
        db_url = db_url + sep + "sslmode=require"
    engine = create_engine(db_url, pool_pre_ping=True, pool_size=1, max_overflow=0)

    print("Running data retention cleanup...\n")
    total = cleanup(engine)
    print(f"\nDone. {total} total rows pruned.")
