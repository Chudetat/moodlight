#!/usr/bin/env python
"""
generate_brief.py
Generates an executive intelligence brief using AI
"""

import os
import pandas as pd
from datetime import datetime, timezone
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def load_recent_data():
    """Load last 24 hours of intelligence data"""
    df = pd.read_csv("social.csv")
    df['created_at'] = pd.to_datetime(df['created_at'], utc=True, errors='coerce')
    
    # Last 24 hours
    cutoff = datetime.now(timezone.utc) - pd.Timedelta(days=7)
    recent = df[df['created_at'] >= cutoff]
    
    return recent

def prepare_intelligence_context(df):
    """Prepare context for AI briefing"""
    
    # Top topics by volume
    topic_counts = df['topic'].value_counts().head(5)
    
    # High intensity articles (4-5 severity)
    critical = df[df['intensity'] >= 4]
    
    # Geographic distribution
    country_counts = df['country'].value_counts().head(5)
    
    # Average intensity by topic
    topic_intensity = df.groupby('topic')['intensity'].mean().sort_values(ascending=False).head(5)
    
    context = f"""
INTELLIGENCE DATA SUMMARY (Last 24 Hours)
==========================================

TOP TOPICS BY VOLUME:
{topic_counts.to_string()}

HIGHEST INTENSITY TOPICS:
{topic_intensity.round(2).to_string()}

CRITICAL SEVERITY ARTICLES ({len(critical)} total):
{critical[['text', 'country', 'intensity']].head(10).to_string()}

GEOGRAPHIC DISTRIBUTION:
{country_counts.to_string()}

Total Articles Analyzed: {len(df)}
"""
    
    return context

def generate_brief(context):
    """Generate executive brief using AI"""
    
    prompt = f"""You are a senior intelligence analyst preparing a daily executive brief for national security leadership.

Based on the following intelligence data, create a concise executive summary that:

1. Highlights the TOP 3 CRITICAL THREATS or developments
2. Identifies emerging patterns or trends
3. Provides ACTIONABLE INSIGHTS for decision-makers
4. Uses clear, direct language (no jargon)
5. Keeps it under 300 words

Format as:
EXECUTIVE INTELLIGENCE BRIEF - [DATE]

KEY THREATS:
1. [Most critical]
2. [Second priority]
3. [Third priority]

EMERGING PATTERNS:
[2-3 sentences on trends]

RECOMMENDED ACTIONS:
[Bullet points]

DATA:
{context}
"""
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a senior intelligence analyst with 20 years of experience in national security and geopolitical risk assessment."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=500
    )
    
    return response.choices[0].message.content

def main():
    print("=" * 60)
    print("GENERATING EXECUTIVE INTELLIGENCE BRIEF")
    print("=" * 60)
    print()
    
    df = load_recent_data()
    
    if len(df) == 0:
        print("No recent data available for briefing.")
        return
    
    print(f"Analyzing {len(df)} intelligence reports...")
    print()
    
    context = prepare_intelligence_context(df)
    brief = generate_brief(context)
    
    print(brief)
    print()
    print("=" * 60)
    
    # Save to file
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"intel_brief_{timestamp}.txt"
    
    with open(filename, 'w') as f:
        f.write(brief)
    
    print(f"Brief saved to: {filename}")

if __name__ == "__main__":
    main()