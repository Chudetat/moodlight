#!/usr/bin/env python3
"""Cron job to fetch and score news RSS feeds, save to Postgres."""
import subprocess
import sys
import pandas as pd
from db_helper import init_tables, save_news_to_db

print("=== CRON: Starting news RSS fetch ===", flush=True)

# Initialize database tables
init_tables()

# Fetch news
result = subprocess.run(
    [sys.executable, "fetch_news_rss.py"],
    capture_output=True, text=True
)
print(result.stdout, flush=True)
if result.stderr:
    print(f"STDERR: {result.stderr}", flush=True)

if result.returncode == 0:
    print("=== CRON: News fetched, now scoring ===", flush=True)
    score = subprocess.run(
        [sys.executable, "score_empathy.py", "news.csv", "news_scored.csv"],
        capture_output=True, text=True
    )
    print(score.stdout, flush=True)
    if score.stderr:
        print(f"STDERR: {score.stderr}", flush=True)
    
    # Save to database
    try:
        df = pd.read_csv("news_scored.csv")
        save_news_to_db(df)
        print(f"=== CRON: Saved {len(df)} news entries to database ===", flush=True)
    except Exception as e:
        print(f"=== CRON: Failed to save to database: {e} ===", flush=True)
else:
    print(f"=== CRON: News fetch failed (code {result.returncode}) ===", flush=True)
