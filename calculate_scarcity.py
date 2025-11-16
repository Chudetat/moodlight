#!/usr/bin/env python
"""
calculate_scarcity.py
Identifies topic gaps and opportunities:
- What's NOT being discussed enough?
- Competitive white space
- Underserved topics with potential
"""

import pandas as pd
from collections import Counter

# Expected important topics in 2025
EXPECTED_TOPICS = {
    'AI regulation & ethics': ['ai regulation', 'ai ethics', 'ai safety', 'ai governance'],
    'Climate action': ['climate action', 'renewable energy', 'carbon emissions', 'sustainability'],
    'Mental health': ['mental health', 'therapy', 'wellbeing', 'anxiety', 'depression'],
    'Remote work': ['remote work', 'hybrid work', 'work from home', 'digital nomad'],
    'Inflation & cost of living': ['inflation', 'cost of living', 'prices', 'affordability'],
    'Cybersecurity': ['cybersecurity', 'data breach', 'privacy', 'hacking'],
    'Healthcare access': ['healthcare access', 'medical costs', 'insurance', 'hospital'],
    'Education reform': ['education reform', 'student debt', 'online learning', 'teachers'],
    'Housing affordability': ['housing crisis', 'rent', 'mortgage', 'homelessness'],
    'Social media regulation': ['social media regulation', 'content moderation', 'platform accountability'],
    'Crypto regulation': ['crypto regulation', 'bitcoin regulation', 'defi'],
    'Space exploration': ['space exploration', 'mars', 'spacex', 'nasa'],
    'EV adoption': ['electric vehicles', 'ev', 'tesla', 'charging infrastructure'],
    'Aging population': ['aging', 'elderly care', 'retirement', 'social security'],
    'Food security': ['food security', 'supply chain', 'agriculture', 'farming']
}

def check_topic_coverage(df_all):
    """Check which expected topics are underrepresented"""
    
    # Combine all text
    all_text = ' '.join(df_all['text'].astype(str).str.lower())
    
    coverage = []
    
    for topic_name, keywords in EXPECTED_TOPICS.items():
        # Count mentions
        mentions = sum(all_text.count(kw) for kw in keywords)
        
        # Calculate scarcity (inverse of coverage)
        # More mentions = less scarce
        if mentions == 0:
            scarcity = 1.0
            coverage_level = 'Zero coverage'
        elif mentions < 5:
            scarcity = 0.9
            coverage_level = 'Minimal coverage'
        elif mentions < 20:
            scarcity = 0.7
            coverage_level = 'Low coverage'
        elif mentions < 50:
            scarcity = 0.5
            coverage_level = 'Moderate coverage'
        elif mentions < 100:
            scarcity = 0.3
            coverage_level = 'Good coverage'
        else:
            scarcity = 0.1
            coverage_level = 'High coverage'
        
        coverage.append({
            'topic': topic_name,
            'scarcity_score': scarcity,
            'mention_count': mentions,
            'coverage_level': coverage_level,
            'opportunity': 'HIGH' if scarcity > 0.7 else ('MEDIUM' if scarcity > 0.4 else 'LOW')
        })
    
    return pd.DataFrame(coverage).sort_values('scarcity_score', ascending=False)

def find_topic_gaps():
    """Find gaps between what exists and what's expected"""
    
    # Load data
    df_social = pd.read_csv('social_scored.csv')
    df_news = pd.read_csv('news_scored.csv')
    df_all = pd.concat([df_social, df_news], ignore_index=True)
    
    print("Analyzing topic coverage...\n")
    
    # Check existing topic distribution
    existing_topics = df_all['topic'].value_counts()
    print("Current Topic Distribution:")
    print("=" * 80)
    print(existing_topics.head(10).to_string())
    
    # Check expected topic coverage
    print("\n\nExpected Topic Scarcity Analysis:")
    print("=" * 80)
    coverage_df = check_topic_coverage(df_all)
    print(coverage_df.to_string(index=False))
    
    # Save results
    coverage_df.to_csv('topic_scarcity.csv', index=False)
    print(f"\n✓ Saved to topic_scarcity.csv")
    
    # Strategic recommendations
    print("\n\n�� STRATEGIC OPPORTUNITIES:")
    print("=" * 80)
    high_opp = coverage_df[coverage_df['opportunity'] == 'HIGH']
    
    if len(high_opp) > 0:
        print("\nHIGH OPPORTUNITY TOPICS (First-mover advantage):")
        for _, row in high_opp.iterrows():
            print(f"  • {row['topic']} (Scarcity: {row['scarcity_score']:.2f})")
            print(f"    → Only {row['mention_count']} mentions. Room to own this space.\n")
    
    medium_opp = coverage_df[coverage_df['opportunity'] == 'MEDIUM']
    if len(medium_opp) > 0:
        print("\nMEDIUM OPPORTUNITY TOPICS (Differentiation possible):")
        for _, row in medium_opp.head(3).iterrows():
            print(f"  • {row['topic']} (Scarcity: {row['scarcity_score']:.2f})")
    
    return coverage_df

if __name__ == "__main__":
    find_topic_gaps()

