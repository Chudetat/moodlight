#!/usr/bin/env python
"""
calculate_density.py
Calculates concentration/depth of topic discussions:
- Geographic density (where is this discussed?)
- Platform density (which platforms care?)
- Conversation depth (surface vs. deep discussions)
"""

import pandas as pd
from collections import Counter

# Geographic mapping based on source
GEO_MAPPING = {
    'bbc': 'UK/Europe',
    'cnn': 'North America',
    'guardian': 'UK/Europe',
    'al_jazeera': 'Middle East',
    'japan_times': 'Asia',
    'korea_herald': 'Asia',
    'times_of_india': 'Asia',
    'indian_express': 'Asia',
    'fox_news': 'North America',
    'abc_news': 'North America',
    'cbs_news': 'North America',
    'nbc': 'North America',
    'x': 'Global',
    'reddit': 'Global (English-speaking)'
}

def get_geographic_density(topic_df):
    """Which regions are discussing this topic?"""
    regions = []
    
    for source in topic_df['source']:
        source_lower = str(source).lower()
        for key, region in GEO_MAPPING.items():
            if key in source_lower:
                regions.append(region)
                break
        else:
            regions.append('Other')
    
    if not regions:
        return {'diversity': 0, 'primary_region': 'Unknown', 'regions': {}}
    
    region_counts = Counter(regions)
    total = len(regions)
    
    # Calculate diversity (0-1, higher = more geographically diverse)
    diversity = len(region_counts) / len(GEO_MAPPING)
    
    # Primary region
    primary = region_counts.most_common(1)[0][0]
    
    # Distribution
    distribution = {r: count/total for r, count in region_counts.items()}
    
    return {
        'diversity': diversity,
        'primary_region': primary,
        'regions': distribution
    }

def get_platform_density(topic_df):
    """Which platforms are discussing this topic?"""
    platform_map = {
        'x': 'Social Media (X)',
        'reddit': 'Social Media (Reddit)',
        'news': 'News Media',
        'newsapi': 'News Media'
    }
    
    platforms = []
    for source in topic_df['source']:
        source_lower = str(source).lower()
        if 'reddit' in source_lower:
            platforms.append('Social Media (Reddit)')
        elif source_lower == 'x':
            platforms.append('Social Media (X)')
        else:
            platforms.append('News Media')
    
    platform_counts = Counter(platforms)
    total = len(platforms)
    
    diversity = len(platform_counts) / 3  # Max 3 platform types
    primary = platform_counts.most_common(1)[0][0]
    distribution = {p: count/total for p, count in platform_counts.items()}
    
    return {
        'diversity': diversity,
        'primary_platform': primary,
        'platforms': distribution
    }

def get_conversation_depth(topic_df):
    """How deep are the discussions? (replies vs surface engagement)"""
    if 'reply_count' not in topic_df.columns or 'like_count' not in topic_df.columns:
        return {'depth_score': 0.5, 'depth_category': 'Medium'}
    
    total_replies = topic_df['reply_count'].sum()
    total_likes = topic_df['like_count'].sum()
    
    if total_likes == 0:
        depth_score = 0.5
    else:
        # High reply ratio = deep discussion
        depth_ratio = total_replies / total_likes
        depth_score = min(depth_ratio / 0.3, 1.0)  # 0.3 = very deep discussion
    
    if depth_score < 0.3:
        depth_category = 'Surface (shares only)'
    elif depth_score < 0.6:
        depth_category = 'Medium (some discussion)'
    else:
        depth_category = 'Deep (active debate)'
    
    return {
        'depth_score': depth_score,
        'depth_category': depth_category,
        'reply_like_ratio': total_replies / max(total_likes, 1)
    }

def analyze_topic_density(topic_name, topic_df):
    """Complete density analysis for a topic"""
    geo = get_geographic_density(topic_df)
    platform = get_platform_density(topic_df)
    depth = get_conversation_depth(topic_df)
    
    # Overall density score (0-1)
    # High density = concentrated in specific geo/platform with deep discussion
    # Low density = scattered, surface-level
    
    density_score = (
        (1 - geo['diversity']) * 0.3 +      # More concentrated = higher density
        (1 - platform['diversity']) * 0.2 +  # Platform focus = higher density
        depth['depth_score'] * 0.5           # Deep discussion = higher density
    )
    
    return {
        'topic': topic_name,
        'density_score': density_score,
        'geographic': geo,
        'platform': platform,
        'conversation': depth,
        'post_count': len(topic_df)
    }

def analyze_all_densities():
    """Analyze density for all topics"""
    # Load data
    df_social = pd.read_csv('social_scored.csv')
    df_news = pd.read_csv('news_scored.csv')
    df_all = pd.concat([df_social, df_news], ignore_index=True)
    
    results = []
    
    for topic in df_all['topic'].unique():
        if pd.isna(topic):
            continue
        
        topic_df = df_all[df_all['topic'] == topic]
        analysis = analyze_topic_density(topic, topic_df)
        
        results.append({
            'topic': topic,
            'density_score': analysis['density_score'],
            'primary_region': analysis['geographic']['primary_region'],
            'geo_diversity': analysis['geographic']['diversity'],
            'primary_platform': analysis['platform']['primary_platform'],
            'conversation_depth': analysis['conversation']['depth_category'],
            'depth_score': analysis['conversation']['depth_score'],
            'post_count': analysis['post_count']
        })
    
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('density_score', ascending=False)
    
    return results_df

if __name__ == "__main__":
    print("Calculating topic density...\n")
    results = analyze_all_densities()
    
    print("Topics by Density (High = Concentrated & Deep):")
    print("=" * 100)
    print(results.to_string(index=False))
    
    # Save
    results.to_csv('topic_density.csv', index=False)
    print(f"\n✓ Saved to topic_density.csv")

