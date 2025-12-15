#!/usr/bin/env python3
"""Cron job to fetch and score news RSS feeds."""
import subprocess
import sys
import os

print("=== CRON: Starting news RSS fetch ===", flush=True)

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
    print(f"=== CRON: Scoring complete (code {score.returncode}) ===", flush=True)
else:
    print(f"=== CRON: News fetch failed (code {result.returncode}) ===", flush=True)
