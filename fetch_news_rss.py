#!/usr/bin/env python
"""
fetch_news_rss.py
Fetches news + Reddit via RSS -> news.csv
With fallback dates so 48h filter works.
"""

import csv
import hashlib
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import feedparser
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
import pandas as pd
import sys

# -------------------------------
# HTTP Session with retry + timeout
# -------------------------------
session = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)

# -------------------------------
# RSS feeds (including Reddit)
# -------------------------------
FEEDS: List[tuple[str, str]] = [
    ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("BBC Politics", "http://feeds.bbci.co.uk/news/politics/rss.xml"),
    ("BBC Business", "http://feeds.bbci.co.uk/news/business/rss.xml"),
    ("BBC Technology", "http://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("BBC Entertainment", "http://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"),

    ("CNN Top", "http://rss.cnn.com/rss/edition.rss"),
    ("CNN World", "http://rss.cnn.com/rss/edition_world.rss"),
    ("CNN Business", "http://rss.cnn.com/rss/edition_business.rss"),
    ("CNN Tech", "http://rss.cnn.com/rss/edition_technology.rss"),

    ("Guardian World", "https://www.theguardian.com/world/rss"),
    ("Guardian Politics", "https://www.theguardian.com/politics/rss"),

    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),

    ("Japan Times", "https://www.japantimes.co.jp/feed/"),
    ("Korea Herald", "http://www.koreaherald.com/rss/020000000000.xml"),

    ("FT World", "https://www.ft.com/world/rss"),
    ("FT Markets", "https://www.ft.com/markets/rss"),

    ("ESPN", "https://www.espn.com/espn/rss/news"),

    ("TechCrunch", "http://feeds.feedburner.com/TechCrunch/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),

    # REDDIT
    ("Reddit World News", "https://www.reddit.com/r/worldnews/.rss"),
    ("Reddit Uplifting News", "https://www.reddit.com/r/UpliftingNews/.rss"),
    ("Reddit News", "https://www.reddit.com/r/news/.rss"),
]

OUTPUT_CSV = "news.csv"
MAX_ITEMS_PER_FEED = 30

# -------------------------------
# Google News Dynamic Feeds (for brand coverage)
# -------------------------------
GOOGLE_NEWS_QUERIES = [
    # Automotive
    "Porsche",
    "Hyundai", 
    "Toyota",
    "Ford",
    "Tesla",
    "BMW",
    "Mercedes-Benz",
    
    # Tech
    "Apple",
    "Samsung",
    "Google",
    "Microsoft",
    
    # Apparel/Retail
    "Nike",
    "Adidas",
    "Amazon",
    "Walmart",
    "Target",
    "Starbucks",
    
    # Entertainment
    "Disney",
    "Netflix",
    "Spotify",
]

def get_google_news_feeds() -> List[tuple[str, str]]:
    """Generate Google News RSS feeds for brand queries"""
    feeds = []
    for query in GOOGLE_NEWS_QUERIES:
        url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
        feeds.append((f"Google News: {query}", url))
    return feeds

# -------------------------------
# Topic classification
# -------------------------------
TOPIC_KEYWORDS = {
    "politics": ["election", "president", "congress", "senate", "vote", "democrat", "republican", "political"],
    "government": ["government", "minister", "prime minister", "white house", "regulation", "policy", "administration"],
    "economics": ["economy", "inflation", "recession", "gdp", "markets", "stocks", "finance", "economic", "federal reserve"],
    "education": ["school", "teacher", "student", "university", "college", "campus", "education"],
    "culture & identity": ["culture", "identity", "values", "tradition", "community", "heritage"],
    "branding & advertising": ["branding", "brand", "marketing", "advertising", "commercial", "campaign"],
    "creative & design": ["design", "designer", "creative", "art direction", "illustration", "graphic"],
    "technology & ai": ["technology", "tech", "software", "hardware", "ai", "artificial intelligence", "startup", "app", "digital"],
    "climate & environment": ["climate", "environment", "warming", "emissions", "pollution", "flood", "weather", "storm", "wildfire"],
    "healthcare & wellbeing": ["healthcare", "hospital", "doctor", "mental health", "vaccine", "covid", "medical", "pandemic"],
    "immigration": ["immigration", "migrant", "refugee", "asylum", "border", "visa", "deportation"],
    "crime & safety": ["crime", "police", "shooting", "violence", "homicide", "murder", "robbery", "arrest"],
    "war & foreign policy": ["war", "conflict", "military", "israel", "gaza", "ukraine", "russia", "attack", "troops", "nuclear"],
    "media & journalism": ["media", "journalism", "reporter", "press", "headline", "newspaper"],
    "race & ethnicity": ["race", "racism", "ethnicity", "minority", "black", "asian", "discrimination"],
    "gender & sexuality": ["gender", "feminist", "lgbtq", "queer", "trans", "women", "abortion"],
    "business & corporate": ["business", "company", "ceo", "merger", "earnings", "profit", "revenue", "corporate"],
    "labor & work": ["labor", "union", "strike", "worker", "job", "wage", "employment", "unemployment"],
    "housing": ["housing", "rent", "landlord", "mortgage", "eviction", "real estate", "property"],
    "religion & values": ["religion", "church", "faith", "spiritual", "bible", "religious", "muslim", "christian"],
    "sports": ["sports", "game", "match", "team", "player", "athlete", "championship", "football", "basketball"],
    "entertainment": ["movie", "film", "tv", "music", "concert", "celebrity", "actor", "entertainment"],
}

def classify_topic(text: str) -> str:
    """Classify topic with priority ordering (more specific first)"""
    t = text.lower()

    # Priority order - check specific topics first
    priority_topics = [
        "war & foreign policy",
        "climate & environment", 
        "technology & ai",
        "healthcare & wellbeing",
        "crime & safety",
        "immigration",
    ]

    for topic in priority_topics:
        if any(kw in t for kw in TOPIC_KEYWORDS[topic]):
            return topic

    # Then check remaining topics
    for topic, kws in TOPIC_KEYWORDS.items():
        if topic not in priority_topics:
            if any(kw in t for kw in kws):
                return topic

    return "other"

# -------------------------------
# Text cleaning
# -------------------------------
def clean_text(text: Any) -> str:
    """Clean and normalize text"""
    if not text:
        return ""
    text = str(text)

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Remove URLs
    text = re.sub(r"http\S+|www\.\S+", "", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Remove common RSS artifacts
    text = re.sub(r"\[CDATA\[|\]\]", "", text)

    return text[:5000]

# -------------------------------
# Date parsing with better fallback
# -------------------------------
def parse_pubdate(date_str: str) -> str | None:
    """Parse publication date with multiple fallback methods"""
    if not date_str:
        return None

    # Try feedparser's built-in parser first
    try:
        parsed = feedparser._parse_date(date_str)
        if parsed:
            dt = datetime(*parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
    except:
        pass

    # Try common date formats
    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %z",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except:
            continue

    return None

# -------------------------------
# Deduplicate by content similarity
# -------------------------------
def deduplicate_entries(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate entries based on text similarity"""
    seen_hashes = set()
    unique_rows = []

    for row in rows:
        # Create hash from first 200 chars of text
        text_hash = hashlib.md5(row["text"][:200].lower().encode()).hexdigest()
        
        if text_hash not in seen_hashes:
            seen_hashes.add(text_hash)
            unique_rows.append(row)

    removed = len(rows) - len(unique_rows)
    if removed > 0:
        print(f"   Removed {removed} duplicate entries")

    return unique_rows

# -------------------------------
# Fetch one feed
# -------------------------------
def fetch_feed(source: str, url: str) -> List[Dict[str, Any]]:
    """Fetch and parse a single RSS feed"""
    print(f"Fetching {source} -> {url}")

    try:
        response = session.get(
            url, 
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; WorldMoodBot/1.0)",
                "Accept": "application/rss+xml, application/xml, text/xml"
            }
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        print(f"   Timeout (skipping)")
        return []
    except requests.exceptions.RequestException as e:
        print(f"   Failed: {str(e)[:100]}")
        return []

    try:
        feed = feedparser.parse(response.content)
    except Exception as e:
        print(f"   Parse error: {e}")
        return []

    if feed.bozo and not feed.entries:
        print(f"   Parse warning: {feed.bozo_exception}")
        return []

    entries = feed.entries[:MAX_ITEMS_PER_FEED]
    rows = []
    now = datetime.now(timezone.utc)

    for entry in entries:
        try:
            # Get title and summary
            title = clean_text(entry.get("title", ""))
            
            # Try multiple fields for content
            summary = clean_text(
                entry.get("summary")
                or entry.get("description")
                or (entry.get("content", [{}])[0].get("value") if entry.get("content") else "")
                or ""
            )
            
            # Combine title and summary
            text = f"{title}. {summary}".strip() if summary else title
            
            # Skip if too short or empty
            if not text or len(text) < 20:
                continue

            # Get link
            link = entry.get("link", "")
            if isinstance(link, dict):
                link = link.get("href", "")

            # Generate ID
            eid = entry.get("id") or link or hashlib.md5(text.encode()).hexdigest()

            # Parse date with fallback
            pubdate = entry.get("published") or entry.get("updated") or ""
            created_at = parse_pubdate(pubdate)
            
            # Fallback: use current time if parsing failed
            if not created_at:
                created_at = now.isoformat()
            else:
                # Validate date isn't in the future or too old
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                if dt > now:
                    created_at = now.isoformat()
                elif dt < now - timedelta(days=30):
                    # If older than 30 days, use current time
                    created_at = now.isoformat()

            # Classify topic
            topic = classify_topic(text)

            rows.append({
                "id": eid,
                "text": text,
                "created_at": created_at,
                "link": link,
                "source": source.lower().replace(" ", "_"),
                "topic": topic,
                "engagement": 0,
            })
        
        except Exception as e:
            print(f"   Skipped entry: {str(e)[:50]}")
            continue

    print(f"   Got {len(rows)} items")
    return rows

# -------------------------------
# Load existing data to preserve history
# -------------------------------
def load_existing_data() -> pd.DataFrame:
    """Load existing news.csv to preserve older entries"""
    try:
        df = pd.read_csv(OUTPUT_CSV)
        print(f"Loaded {len(df)} existing entries from {OUTPUT_CSV}")

        # Keep entries from last 7 days only
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            df = df[df["created_at"] >= cutoff]
            print(f"Kept {len(df)} entries from last 7 days")
        
        return df
    except (FileNotFoundError, pd.errors.EmptyDataError):
        print("No existing data found (will create new file)")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading existing data: {e}")
        return pd.DataFrame()

# -------------------------------
# Main
# -------------------------------
def main():
    print("=" * 60)
    print("FETCHING NEWS & REDDIT RSS FEEDS")
    print("=" * 60)

    # Load existing data
    existing_df = load_existing_data()

    # Fetch new data
    all_rows = []
    successful_feeds = 0
    failed_feeds = 0

    # Combine static feeds with dynamic Google News feeds
    all_feeds = FEEDS + get_google_news_feeds()

    for source, url in all_feeds:

        rows = fetch_feed(source, url)
        if rows:
            all_rows.extend(rows)
            successful_feeds += 1
        else:
            failed_feeds += 1

    if not all_rows:
        print("\nNo new items fetched")
        if existing_df.empty:
            print("No existing data either - writing empty CSV")
            columns = ["id", "text", "created_at", "link", "source", "topic", "engagement"]
            df = pd.DataFrame(columns=columns)
            df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_MINIMAL)
            print(f"Saved empty file to {OUTPUT_CSV}")
            sys.exit(1)
        else:
            print(f"Keeping {len(existing_df)} existing entries")
            existing_df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_MINIMAL)
            print(f"Saved to {OUTPUT_CSV}")
            sys.exit(0)

    print(f"\nSummary:")
    print(f"   Feeds attempted: {len(all_feeds)}")
    print(f"   Successful: {successful_feeds}")
    print(f"   Failed: {failed_feeds}")
    print(f"   New items fetched: {len(all_rows)}")

    # Deduplicate new entries
    all_rows = deduplicate_entries(all_rows)

    # Create DataFrame from new entries
    columns = ["id", "text", "created_at", "link", "source", "topic", "engagement"]
    new_df = pd.DataFrame(all_rows, columns=columns)

    # Combine with existing data
    if not existing_df.empty:
        # Ensure same columns
        for col in columns:
            if col not in existing_df.columns:
                existing_df[col] = ""
        
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        
        # Remove duplicates based on ID
        combined_df = combined_df.drop_duplicates(subset=["id"], keep="last")
        
        print(f"   Combined with existing: {len(combined_df)} total items")
    else:
        combined_df = new_df

    # Sort by date (newest first)
    if "created_at" in combined_df.columns:
        combined_df["created_at"] = pd.to_datetime(combined_df["created_at"], errors="coerce")
        combined_df = combined_df.sort_values("created_at", ascending=False)
        # Convert back to ISO format strings
        # Only convert if it's actually datetime type
    if pd.api.types.is_datetime64_any_dtype(combined_df["created_at"]):
        combined_df["created_at"] = combined_df["created_at"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")

    # Save to CSV
    combined_df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_MINIMAL)
    print(f"\nSaved {len(combined_df)} entries to {OUTPUT_CSV}")

    # Show topic breakdown
    if "topic" in combined_df.columns:
        print(f"\nTopic breakdown:")
        topic_counts = combined_df["topic"].value_counts().head(10)
        for topic, count in topic_counts.items():
            print(f"   {topic}: {count}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)