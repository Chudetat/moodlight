#!/usr/bin/env python
"""
calculate_longevity.py
Calculates longevity scores for topics based on:
- Source diversity
- Conversation depth
- Topic breadth
- Time persistence (improves as data accumulates)
"""

import pandas as pd
from datetime import datetime, timedelta, timezone
from collections import defaultdict

def calculate_source_diversity(topic_df):
    """How many different sources discuss this topic?"""
    unique_sources = topic_df['source'].nunique()
    total_possible = 20  # Approximate max sources (X + NewsAPI + RSS feeds)
    return min(unique_sources / total_possible, 1.0)

def calculate_conversation_depth(topic_df):
    """Ratio of replies to likes - deeper discussion = higher longevity"""
    if 'reply_count' in topic_df.columns and 'like_count' in topic_df.columns:
        total_replies = topic_df['reply_count'].sum()
        total_likes = topic_df['like_count'].sum()
        
        if total_likes > 0:
            depth_ratio = total_replies / total_likes
            # Normalize: typically 0.05-0.3 range for good discussions
            return min(depth_ratio / 0.3, 1.0)
    return 0.5  # Default if no data

def calculate_time_persistence(topic_df):
    """How many days does this topic appear? (improves over time)"""
    if 'created_at' not in topic_df.columns:
        return 0.5
    
    topic_df['date'] = pd.to_datetime(topic_df['created_at']).dt.date
    unique_days = topic_df['date'].nunique()
    
    # Normalize: 1 day = 0.3, 7+ days = 1.0
    if unique_days == 1:
        return 0.3
    elif unique_days >= 7:
        return 1.0
    else:
        return 0.3 + (unique_days - 1) * 0.7 / 6

def calculate_topic_breadth(topic_name):
    """Does this topic connect to fundamental themes?"""
    # Broad, lasting topics
    lasting_topics = {
        'war & foreign policy': 0.9,
        'economics': 0.85,
        'climate & environment': 0.85,
        'politics': 0.8,
        'healthcare & wellbeing': 0.8,
        'technology & ai': 0.75,
        'education': 0.7,
        'crime & safety': 0.6,
        'sports': 0.4,  # Event-driven, less lasting
        'entertainment': 0.3,  # Trend-driven
        'other': 0.5
    }
    return lasting_topics.get(topic_name, 0.5)

def calculate_longevity_score(topic_name, topic_df):
    """
    Calculate overall longevity score (0-1)
    
    Weights:
    - Source diversity: 30%
    - Conversation depth: 20%
    - Time persistence: 30%
    - Topic breadth: 20%
    """
    source_div = calculate_source_diversity(topic_df)
    conv_depth = calculate_conversation_depth(topic_df)
    time_persist = calculate_time_persistence(topic_df)
    topic_broad = calculate_topic_breadth(topic_name)
    
    longevity = (
        source_div * 0.30 +
        conv_depth * 0.20 +
        time_persist * 0.30 +
        topic_broad * 0.20
    )
    
    return longevity

def analyze_all_topics():
    """Analyze longevity for all topics"""
    # Load data
    df_social = pd.read_csv('social_scored.csv')
    df_news = pd.read_csv('news_scored.csv')
    df_all = pd.concat([df_social, df_news], ignore_index=True)
    
    # Parse dates
    df_all['created_at'] = pd.to_datetime(df_all['created_at'], errors='coerce', utc=True)
    
    # Calculate longevity for each topic
    results = []
    
    for topic in df_all['topic'].unique():
        if pd.isna(topic):
            continue
            
        topic_df = df_all[df_all['topic'] == topic]
        
        longevity = calculate_longevity_score(topic, topic_df)
        
        # Calculate velocity (engagement per hour)
        if 'engagement' in topic_df.columns:
            avg_engagement = topic_df['engagement'].mean()
            now = datetime.now(timezone.utc)
            topic_df['age_hours'] = (now - topic_df['created_at']).dt.total_seconds() / 3600
            topic_df['age_hours'] = topic_df['age_hours'].replace(0, 0.1)
            avg_velocity = (topic_df['engagement'] / topic_df['age_hours']).mean()
        else:
            avg_engagement = 0
            avg_velocity = 0
        
        results.append({
            'topic': topic,
            'longevity_score': longevity,
            'velocity_score': avg_velocity,
            'post_count': len(topic_df),
            'source_count': topic_df['source'].nunique(),
            'avg_engagement': avg_engagement
        })
    
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('longevity_score', ascending=False)
    
    return results_df

if __name__ == "__main__":
    print("Calculating longevity scores for all topics...\n")
    results = analyze_all_topics()
    
    print("Top 10 Topics by Longevity:")
    print("=" * 80)
    print(results.head(10).to_string(index=False))
    
    print("\n\nBottom 5 Topics by Longevity:")
    print("=" * 80)
    print(results.tail(5).to_string(index=False))
    
    # Save results
    results.to_csv('topic_longevity.csv', index=False)
    print(f"\n✓ Saved results to topic_longevity.csv")

