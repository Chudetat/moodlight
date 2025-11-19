#!/usr/bin/env python
"""
analyze_trends.py
Detects trends, spikes, and shifts in intelligence data
"""

import pandas as pd
from datetime import datetime, timedelta, timezone
from collections import Counter

INPUT_CSV = "social.csv"

def load_data():
    """Load and parse social.csv"""
    df = pd.read_csv(INPUT_CSV)
    df['created_at'] = pd.to_datetime(df['created_at'], utc=True, errors='coerce')
    return df

def analyze_topic_trends(df):
    """Compare Nov 17-18 vs Nov 15-16"""
    
    # Nov 17-18 (recent)
    recent_start = pd.Timestamp('2025-11-17', tz='UTC')
    recent_end = pd.Timestamp('2025-11-19', tz='UTC')
    
    # Nov 15-16 (previous)
    prev_start = pd.Timestamp('2025-11-15', tz='UTC')
    prev_end = pd.Timestamp('2025-11-17', tz='UTC')
    
    recent_df = df[(df['created_at'] >= recent_start) & (df['created_at'] < recent_end)]
    previous_df = df[(df['created_at'] >= prev_start) & (df['created_at'] < prev_end)]
    
    recent_topics = Counter(recent_df['topic'])
    previous_topics = Counter(previous_df['topic'])
    
    trends = []
    for topic in set(list(recent_topics.keys()) + list(previous_topics.keys())):
        recent_count = recent_topics.get(topic, 0)
        previous_count = previous_topics.get(topic, 0)
        
        if previous_count == 0:
            change_pct = 100 if recent_count > 0 else 0
        else:
            change_pct = ((recent_count - previous_count) / previous_count) * 100
            
        if recent_count > 0 or previous_count > 0:
            trends.append({
                'topic': topic,
                'recent': recent_count,
                'previous': previous_count,
                'change_pct': round(change_pct, 1)
            })
    
    trends.sort(key=lambda x: abs(x['change_pct']), reverse=True)
    return trends
    
def analyze_country_hotspots(df):
    """Identify countries with highest average intensity"""
    now = datetime.now(timezone.utc)
    last_48h = now - timedelta(hours=48)
    
    recent_df = df[df['created_at'] >= last_48h]
    
    # Group by country and calculate average intensity
    country_stats = recent_df.groupby('country').agg({
        'intensity': ['mean', 'count']
    }).reset_index()
    
    country_stats.columns = ['country', 'avg_intensity', 'article_count']
    
    # Filter out low-volume countries and "Unknown"
    country_stats = country_stats[
        (country_stats['article_count'] >= 3) & 
        (country_stats['country'] != 'Unknown')
    ]
    
    country_stats = country_stats.sort_values('avg_intensity', ascending=False)
    
    return country_stats.head(10).to_dict('records')

def main():
    df = load_data()
    
    print("=" * 60)
    print("INTELLIGENCE TREND ANALYSIS")
    print("=" * 60)
    
    trends = analyze_topic_trends(df)
    
    print("\nTOP TOPIC TRENDS (Nov 17-18 vs Nov 15-16):")
    for trend in trends[:10]:
        arrow = "🔺" if trend['change_pct'] > 0 else "🔻"
        print(f"{arrow} {trend['topic']}: {trend['change_pct']:+.1f}% ({trend['previous']} → {trend['recent']})")
    
    # Geographic hotspots
    hotspots = analyze_country_hotspots(df)
    
    print("\nGEOGRAPHIC HOTSPOTS (Highest threat intensity, last 48h):")
    for spot in hotspots:
        intensity_bar = "🔴" * int(spot['avg_intensity'])
        print(f"{spot['country']}: {spot['avg_intensity']:.1f}/5 {intensity_bar} ({int(spot['article_count'])} articles)")

if __name__ == "__main__":
    main()