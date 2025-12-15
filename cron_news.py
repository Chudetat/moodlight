import subprocess
import sys
import pandas as pd
from db_helper import save_df_to_db

print("=== CRON START ===", flush=True)

result = subprocess.run([sys.executable, "fetch_news_rss.py"], capture_output=True, text=True)

if result.returncode == 0:
    print("News fetched, scoring...", flush=True)
    subprocess.run([sys.executable, "score_empathy.py", "news.csv", "news_scored.csv"], capture_output=True, text=True)
    
    try:
        df = pd.read_csv("news_scored.csv")
        save_df_to_db(df, "news_scored")
        print(f"Saved {len(df)} to database", flush=True)
    except Exception as e:
        print(f"DB save failed: {e}", flush=True)
else:
    print(f"Fetch failed: {result.returncode}", flush=True)

print("=== CRON END ===", flush=True)
