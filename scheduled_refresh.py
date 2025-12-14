#!/usr/bin/env python3
"""
Scheduled data refresh for Moodlight
Run by Railway cron job
"""

import subprocess
import sys
from datetime import datetime

print(f"=== Scheduled Refresh Started: {datetime.now()} ===")

# Run fetch_posts.py
print("\n1. Fetching posts...")
result = subprocess.run([sys.executable, "fetch_posts.py"], capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print(f"Errors: {result.stderr}")

# Run score_empathy.py
print("\n2. Scoring empathy...")
result = subprocess.run([sys.executable, "score_empathy.py"], capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print(f"Errors: {result.stderr}")

# Run fetch_markets.py
print("\n3. Fetching market data...")
result = subprocess.run([sys.executable, "fetch_markets.py"], capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print(f"Errors: {result.stderr}")

print(f"\n=== Scheduled Refresh Complete: {datetime.now()} ===")
