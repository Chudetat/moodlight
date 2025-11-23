import os
import subprocess
from datetime import datetime, timedelta

def fetch_data_if_needed():
    """Fetch data if social.csv is missing or older than 12 hours"""
    if not os.path.exists('social.csv'):
        print("No data found, fetching...")
        subprocess.run(['python', 'fetch_posts.py'])
        subprocess.run(['python', 'fetch_news_rss.py'])
        subprocess.run(['python', 'score_empathy.py', 'social.csv', 'social_scored.csv'])
        subprocess.run(['python', 'score_empathy.py', 'news.csv', 'news_scored.csv'])
        subprocess.run(['python', '-c', "import pandas as pd; pd.concat([pd.read_csv('social_scored.csv'), pd.read_csv('news_scored.csv')]).drop_duplicates().to_csv('social.csv', index=False)"])
        return
    
    # Check if data is older than 12 hours
    mtime = os.path.getmtime('social.csv')
    age_hours = (datetime.now().timestamp() - mtime) / 3600
    
    if age_hours > 12:
        print(f"Data is {age_hours:.1f} hours old, refreshing...")
        subprocess.run(['python', 'fetch_posts.py'])
        subprocess.run(['python', 'fetch_news_rss.py'])
        subprocess.run(['python', 'score_empathy.py', 'social.csv', 'social_scored.csv'])
        subprocess.run(['python', 'score_empathy.py', 'news.csv', 'news_scored.csv'])
        subprocess.run(['python', '-c', "import pandas as pd; pd.concat([pd.read_csv('social_scored.csv'), pd.read_csv('news_scored.csv')]).drop_duplicates().to_csv('social.csv', index=False)"])

if __name__ == "__main__":
    fetch_data_if_needed()
