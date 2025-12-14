#!/usr/bin/env python
"""
fetch_posts.py
Fetches recent X (Twitter) posts + NewsAPI articles, blends them,
filters spam, deduplicates, classifies topics, and writes social.csv.

NOW PRESERVES HISTORICAL DATA (last 7 days) for trend analysis.

Supports:

- Custom query via `--query "your search terms"`
- Exit code 2 when X quota is hit (for app.py to detect)
- Clear source: "x" or "news"
"""

import os
import sys
import csv
import hashlib
import argparse
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone

import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# -------------------------------
# Config
# -------------------------------
BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

TOTAL_MAX_TWEETS = 500
TOTAL_MAX_NEWS = 400
OUTPUT_CSV = "social.csv"
SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"
NEWSAPI_URL = "https://newsapi.org/v2/everything"

# -------------------------------
# Default queries (with viral filter)
# -------------------------------
X_DEFAULT_QUERY = "(politics OR war OR economy OR technology OR sports) lang:en -is:retweet "

NEWS_DEFAULT_QUERY = (
    "war OR military OR nuclear OR terrorism OR China OR Russia OR Iran OR Israel OR Ukraine OR NATO OR "
    "politics OR election OR congress OR sanctions OR "
    "economy OR inflation OR Federal Reserve OR GDP OR "
    "merger OR IPO OR hedge fund OR billionaire OR "
    "AI OR quantum OR semiconductor OR Tesla OR EV OR "
    "supply chain OR infrastructure OR 5G OR "
    "energy OR oil OR lithium OR solar OR "
    "real estate OR mortgage OR housing OR "
    "pandemic OR FDA OR climate OR Davos"
)

# -------------------------------
# CLI
# -------------------------------
parser = argparse.ArgumentParser(description="Fetch X + News for World Mood")
parser.add_argument(
    "--query",
    type=str,
    default="",
    help="Custom search query (e.g. 'student loans'). Leave empty for default broad query."
)
args = parser.parse_args()

custom_query = args.query.strip()
x_query = f"({custom_query}) lang:en -is:retweet " if custom_query else X_DEFAULT_QUERY 
news_query = custom_query or NEWS_DEFAULT_QUERY

# -------------------------------
# Headers
# -------------------------------
def auth_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {BEARER_TOKEN}"}

# -------------------------------
# Load existing data to preserve history
# -------------------------------
def load_existing_data() -> pd.DataFrame:
    """Load existing social.csv to preserve older entries"""
    try:
        df = pd.read_csv(OUTPUT_CSV)
        print(f"Loaded {len(df)} existing entries from {OUTPUT_CSV}")

        # Keep entries from last 7 days only
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)

            df = df[df["created_at"] >= cutoff]
            print(f"Kept {len(df)} entries from last 7 days")
        
        return df
    except FileNotFoundError:
        print("No existing data found (will create new file)")
        return pd.DataFrame()
    except pd.errors.EmptyDataError:
        print("Existing file is empty")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading existing data: {str(e)[:100]}")
        return pd.DataFrame()

# -------------------------------
# X Fetch (with quota detection)
# -------------------------------
def search_tweets_paged(query: str, total_max: int) -> Tuple[List[Dict], bool]:
    all_tweets: List[Dict] = []
    next_token: str | None = None
    hit_cap = False

    print(f"Fetching X posts (max {total_max})...")

    while len(all_tweets) < total_max:
        params = {
            "query": query,
            "max_results": min(100, total_max - len(all_tweets)),
            "tweet.fields": "created_at,public_metrics,author_id,conversation_id,in_reply_to_user_id",
        }
        if next_token:
            params["next_token"] = next_token

        try:
            resp = requests.get(SEARCH_URL, headers=auth_headers(), params=params, timeout=15)
        except requests.RequestException as e:
            print(f"   Network error: {e}")
            break

        if resp.status_code == 429:
            print("   X API 429: Usage cap exceeded")
            hit_cap = True
            break
        if resp.status_code != 200:
            print(f"   X API error {resp.status_code}: {resp.text[:200]}")
            break

        data = resp.json()
        tweets = data.get("data", [])
        meta = data.get("meta", {})

        print(f"   Page: {len(tweets)} tweets")
        all_tweets.extend(tweets)

        next_token = meta.get("next_token")
        if not next_token:
            break

    print(f"   Total fetched: {len(all_tweets)} tweets")
    return all_tweets, hit_cap

# -------------------------------
# Topic classification
# -------------------------------
TOPIC_KEYWORDS = {
    "politics": ["election", "president", "congress", "senate", "parliament", "vote", "democrat", "republican", "tory", "labour", "policy", "political"],
    "government": ["government", "minister", "prime minister", "white house", "administration", "regulation"],
    "economics": ["economy", "inflation", "recession", "gdp", "markets", "stocks", "bonds", "interest rate", "fed", "finance", "economic"],
    "education": ["school", "teacher", "student", "university", "college", "campus", "curriculum", "education"],
    "culture & identity": ["culture", "identity", "values", "tradition", "community", "heritage"],
    "branding & advertising": ["branding", "brand", "marketing", "advertising", "ad campaign", "commercial"],
    "creative & design": ["design", "designer", "creative", "art direction", "illustration", "graphic design", "animation"],
    "technology & ai": ["technology", "tech", "software", "hardware", "startup", "ai", "artificial intelligence", "chatbot", "machine learning", "app"],
    "climate & environment": ["climate", "environment", "global warming", "emissions", "carbon", "pollution", "wildfire", "flood", "drought", "hurricane", "weather"],
    "healthcare & wellbeing": ["healthcare", "hospital", "doctor", "nurse", "mental health", "therapy", "wellbeing", "vaccine", "covid", "medical"],
    "immigration": ["immigration", "migrant", "refugee", "asylum", "border", "visa", "deportation"],
    "crime & safety": ["crime", "criminal", "police", "law enforcement", "homicide", "shooting", "safety", "violence", "murder", "arrest"],
    "war & foreign policy": ["war", "conflict", "military", "army", "airstrike", "troops", "israel", "gaza", "ukraine", "russia", "nato", "ceasefire", "foreign policy", "attack"],
    "media & journalism": ["media", "journalism", "journalist", "reporter", "news outlet", "press", "headline", "fake news"],
    "race & ethnicity": ["race", "racism", "racial", "ethnicity", "minority", "black", "white", "asian", "latino", "indigenous", "discrimination"],
    "gender & sexuality": ["gender", "sexism", "feminist", "patriarchy", "lgbtq", "queer", "trans", "non-binary", "sexuality", "women", "abortion"],
    "business & corporate": ["business", "company", "corporate", "ceo", "cfo", "board", "merger", "acquisition", "earnings", "profit", "revenue"],
    "labor & work": ["labor", "union", "strike", "worker", "workplace", "job", "employment", "wage", "salary", "unemployment"],
    "housing": ["housing", "rent", "renter", "landlord", "mortgage", "real estate", "tenant", "eviction", "homeless", "property"],
    "religion & values": ["religion", "religious", "church", "mosque", "synagogue", "faith", "spiritual", "morality", "ethics", "bible"],
    "sports": ["sports", "game", "match", "tournament", "league", "team", "player", "athlete", "coach", "championship"],
    "entertainment": ["movie", "film", "cinema", "tv", "series", "episode", "music", "album", "song", "concert", "festival", "celebrity", "actor", "hollywood"],
    "energy & resources": ["energy", "oil", "gas", "natural gas", "opec", "petroleum", "fuel", "power grid", "blackout", "electricity", "energy crisis", "renewable energy", "solar", "wind power", "nuclear power", "coal", "fracking"],
    "infrastructure & supply chain": ["supply chain", "logistics", "shipping", "port", "cargo", "container", "semiconductor", "chip shortage", "rare earth", "infrastructure", "bridge collapse", "road", "railway", "transport", "freight", "bottleneck"],    
    "cybersecurity & tech threats": ["cyberattack", "cyber attack", "ransomware", "hack", "hacker", "data breach", "cybersecurity", "malware", "phishing", "ddos", "zero day", "vulnerability", "exploit", "disinformation", "misinformation", "deepfake"],
    "social unrest & protests": ["protest", "riot", "unrest", "demonstration", "rally", "march", "civil disobedience", "uprising", "revolt", "strike", "labor strike", "walkout", "picket", "activism", "mass protest"],
    "food security & agriculture": ["food shortage", "famine", "hunger", "starvation", "crop failure", "harvest", "drought", "agriculture", "farming", "food crisis", "grain", "wheat", "corn", "livestock", "food supply", "water scarcity"],
    "financial system stress": ["bank failure", "banking crisis", "liquidity", "debt default", "bankruptcy", "foreclosure", "currency collapse", "hyperinflation", "financial crisis", "stock market crash", "recession", "depression", "bailout", "contagion"],
    "nuclear & wmd threats": ["nuclear", "nuclear weapon", "nuke", "atomic", "warhead", "missile test", "icbm", "ballistic missile", "enrichment", "uranium", "plutonium", "wmd", "chemical weapon", "biological weapon", "bioweapon", "nerve agent", "dirty bomb", "proliferation", "non-proliferation"],
    "terrorism & extremism": ["terrorism", "terrorist", "terror attack", "bombing", "suicide bomber", "isis", "isil", "al qaeda", "al-qaeda", "hezbollah", "taliban", "extremist", "extremism", "jihad", "jihadist", "radicalization", "militant", "insurgent", "hostage", "kidnapping"],    
    "humanitarian crises & migration": ["humanitarian crisis", "refugee", "displaced", "displacement", "migration", "migrant crisis", "asylum seeker", "genocide", "ethnic cleansing", "war crime", "atrocity", "mass grave", "humanitarian aid", "refugee camp", "internally displaced", "humanitarian disaster"],
    "disinformation & propaganda": ["disinformation", "misinformation", "fake news", "propaganda", "troll farm", "bot network", "election interference", "foreign interference", "information warfare", "psyop", "psychological operation", "influence campaign", "state media", "deepfake", "manipulated media"],
}

def classify_topic(text: str) -> str:
    """Classify topic with priority ordering"""
    t = text.lower()

    # Priority topics (check more specific ones first)
    priority_topics = [
        "war & foreign policy",
        "nuclear & wmd threats",
        "terrorism & extremism",
        "climate & environment",
        "technology & ai",
        "healthcare & wellbeing",
        "crime & safety",
        "immigration",
        "cybersecurity & tech threats",
        "energy & resources",
        "financial system stress",
        "food security & agriculture",
        "social unrest & protests",
        "infrastructure & supply chain",
        "humanitarian crises & migration",
        "disinformation & propaganda",
    ]

    for topic in priority_topics:
        if any(kw in t for kw in TOPIC_KEYWORDS[topic]):
            return topic

    for topic, kws in TOPIC_KEYWORDS.items():
        if topic not in priority_topics:
            if any(kw in t for kw in kws):
                return topic

    return "other"

# -------------------------------
# Country extraction
# -------------------------------
COUNTRIES = [
    "afghanistan", "albania", "algeria", "argentina", "armenia", "australia", "austria", 
    "azerbaijan", "bahrain", "bangladesh", "belarus", "belgium", "bolivia", "bosnia", 
    "brazil", "bulgaria", "cambodia", "cameroon", "canada", "chile", "china", "colombia", 
    "congo", "costa rica", "croatia", "cuba", "cyprus", "czech", "denmark", "ecuador", 
    "egypt", "estonia", "ethiopia", "finland", "france", "georgia", "germany", "ghana", 
    "greece", "guatemala", "haiti", "honduras", "hong kong", "hungary", "iceland", "india", 
    "indonesia", "iran", "iraq", "ireland", "israel", "italy", "jamaica", "japan", "jordan", 
    "kazakhstan", "kenya", "korea", "kuwait", "latvia", "lebanon", "libya", "lithuania", 
    "malaysia", "mexico", "moldova", "morocco", "myanmar", "nepal", "netherlands", "new zealand", 
    "nicaragua", "niger", "nigeria", "norway", "oman", "pakistan", "palestine", "panama", 
    "paraguay", "peru", "philippines", "poland", "portugal", "qatar", "romania", "russia", 
    "rwanda", "saudi", "senegal", "serbia", "singapore", "slovakia", "slovenia", "somalia", 
    "south africa", "spain", "sri lanka", "sudan", "sweden", "switzerland", "syria", "taiwan", 
    "tanzania", "thailand", "tunisia", "turkey", "uganda", "ukraine", "united arab emirates", 
    "united kingdom", "uruguay", "uzbekistan", "venezuela", "vietnam", "yemen", "zimbabwe",
    "britain", "uk"
]

def extract_country(text: str) -> str:
    """Extract country name from text with USA standardization"""
    import re
    t = text.lower()
    
    # Standardize USA variants with word boundaries
    if re.search(r'\b(u\.s\.|usa|america|united states)\b', t):
        return "United States"
    
    for country in COUNTRIES:
        if country in t:
            return country.title()
    return "Unknown"

# -------------------------------
# Intensity/Threat scoring
# -------------------------------
THREAT_KEYWORDS = {
    "severe": ["war", "attack", "killed", "dead", "death", "massacre", "genocide", "nuclear", "bomb", "terror", "crisis", "collapse", "disaster"],
    "high": ["violence", "conflict", "strike", "protest", "riot", "threat", "danger", "emergency", "critical", "severe"],
    "moderate": ["concern", "risk", "issue", "problem", "tension", "dispute", "unrest", "warning"],
}

def calculate_intensity(text: str) -> int:
    """Calculate threat intensity 1-5 based on keywords"""
    t = text.lower()
    
    severe_count = sum(1 for kw in THREAT_KEYWORDS["severe"] if kw in t)
    high_count = sum(1 for kw in THREAT_KEYWORDS["high"] if kw in t)
    moderate_count = sum(1 for kw in THREAT_KEYWORDS["moderate"] if kw in t)
    
    # Scoring logic
    if severe_count >= 2:
        return 5  # Critical
    elif severe_count >= 1 or high_count >= 2:
        return 4  # High
    elif high_count >= 1 or moderate_count >= 2:
        return 3  # Moderate
    elif moderate_count >= 1:
        return 2  # Low
    else:
        return 1  # Minimal

# -------------------------------
# Spam filter
# -------------------------------
SPAM_KEYWORDS = [
    # Crypto/Investment spam
    "crypto", "bitcoin", "btc", "eth", "ethereum", "nft", "airdrop", "presale", "whitelist",
    "pump", "moon", "lambo", "hodl", "doge", "shib", "memecoin", "web3", "defi",
    "investment savior", "investment recommendation", "funds to steadily", "investment guru",
    "trading signals", "day trading", "daytrading", "forex", "binary options", 
    "stock picks", "trade alert", "buy signal", "sell signal",
    "$PTN", "$GOOGL", "$SNAP", "$NBIS", "$GLTO", "$SMCI",  # Stock tickers with $
    "make money fast", "passive income", "get rich", "financial freedom",
    "guaranteed returns", "investment opportunity",
    # Promotional spam  
    "promo code", "discount code", "use code", "limited time", "sign up now", "shop now",
    "% off", "giveaway", "enter to win", "#ad", "sponsored",
    # Engagement bait
    "follow for follow", "dm for", "link in bio", "check profile", "clickbait",
    "you won't believe", "trading bot",
    # Emojis commonly used in spam (multiple money/financial emojis)
    "💰💰", "🚀🚀", "📈📈", "💸💸", "🤑🤑",
    # Sports (block all)
    "game", "match", "tournament", "playoff", "championship", "league", "season",
    "score", "win", "loss", "defeat", "victory", "team", "player", "athlete", "coach",
    "nfl", "nba", "mlb", "nhl", "fifa", "uefa", "premier league", "super bowl",
    "usmnt", "world cup", "goals scored",
    # Entertainment/Celebrity
    "movie", "film", "cinema", "box office", "premiere", "trailer", "actor", "actress",
    "celebrity", "star", "hollywood", "tv show", "series", "episode", "streaming",
    "album", "concert", "tour", "grammy", "oscar", "emmy",
    # Gaming
    "video game", "gaming", "gamer", "playstation", "xbox", "nintendo", "esports",
]

def is_spam(text: str) -> bool:
    """Check if text appears to be spam or promotional"""
    t = text.lower()
    
    # Immediate ban list - these are ALWAYS spam
    instant_ban = [
        "investment savior", "investment guru", "my investment", 
        "his recommendations", "her recommendations",
        "thank you for sharing", "funds to steadily",
        "check my profile", "link in bio", "dm for"
    ]
    
    if any(phrase in t for phrase in instant_ban):
        return True
    
    # Multiple stock tickers = spam
    stock_tickers = ["$" + ticker for ticker in ["ptn", "googl", "snap", "nbis", "glto", "smci", "tsla", "aapl"]]
    ticker_count = sum(1 for ticker in stock_tickers if ticker in t)
    if ticker_count >= 2:
        return True
    
    # Count spam indicators
    spam_count = sum(1 for kw in SPAM_KEYWORDS if kw in t)
    
    # Multiple spam keywords = definitely spam
    if spam_count >= 2:
        return True
    
    # Single strong indicator
    if spam_count >= 1:
        # But allow if it's legitimate news
        if any(word in t for word in ["breaking", "report", "according", "announced"]):
            return False
        return True
    
    return False

# -------------------------------
# NewsAPI fetch
# -------------------------------
def fetch_news(query: str, max_articles: int) -> List[Dict]:
    """Fetch articles from NewsAPI"""
    if not NEWSAPI_KEY:
        print("NEWSAPI_KEY not set, skipping news")
        return []

    print(f"Fetching NewsAPI articles (max {max_articles})...")

    articles: List[Dict] = []
    page = 1
    page_size = 100

    while len(articles) < max_articles and page <= 20:
        params = {
            "q": query,
            "language": "en",
            "pageSize": page_size,
            "page": page,
            "sortBy": "publishedAt",
            "from": (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d"),
        }
        headers = {"X-Api-Key": NEWSAPI_KEY}

        try:
            resp = requests.get(NEWSAPI_URL, params=params, headers=headers, timeout=15)
            if resp.status_code != 200:
                print(f"   NewsAPI error {resp.status_code}: {resp.text}")
                break
            data = resp.json()
            batch = data.get("articles", [])
            if not batch:
                break
            articles.extend(batch)
            print(f"   Page {page}: {len(batch)} articles")

            page += 1
        except Exception as e:
            print(f"   News fetch exception: {e}")
            break

    print(f"   Total fetched: {len(articles)} articles")
    return articles[:max_articles]

# -------------------------------
# Deduplication
# -------------------------------
def deduplicate_rows(rows: List[Dict]) -> List[Dict]:
    """Remove duplicate entries by ID"""
    seen = set()
    unique = []
    duplicates = 0

    for row in rows:
        key = row["id"]
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(row)

    if duplicates > 0:
        print(f"   Removed {duplicates} duplicates")

    return unique

# -------------------------------
# Main
# -------------------------------
def main():
    print("=" * 60)
    print("FETCHING X & NEWSAPI DATA")
    print("=" * 60)
    print(f"X query: {x_query[:100]}...")
    print(f"News query: {news_query[:100]}...")
    print()

    # Load existing data first
    existing_df = load_existing_data()

    # --- Fetch News (always runs) ---
    news_articles = fetch_news(news_query, TOTAL_MAX_NEWS)

    # --- Fetch X (might hit quota) ---
    tweets, hit_cap = search_tweets_paged(x_query, TOTAL_MAX_TWEETS)

    # --- Process X ---
    print("\nProcessing X posts...")
    x_rows: List[Dict] = []
    x_spam_filtered = 0

    for tw in tweets:
        text = tw.get("text", "")
        if not text:
            continue
            
        if is_spam(text):
            x_spam_filtered += 1
            continue

        metrics = tw.get("public_metrics", {})
        engagement = sum(metrics.get(k, 0) for k in ["like_count", "reply_count", "retweet_count", "quote_count"])

        x_rows.append({
            "id": tw["id"],
            "text": text,
            "created_at": tw.get("created_at"),
            "author_id": tw.get("author_id"),
            "like_count": metrics.get("like_count", 0),
            "reply_count": metrics.get("reply_count", 0),
            "repost_count": metrics.get("retweet_count", 0),
            "quote_count": metrics.get("quote_count", 0),
            "engagement": engagement,
            "topic": classify_topic(text),
            "country": extract_country(text),
            "intensity": calculate_intensity(text),
            "source": "x",
        })

    if hit_cap:
        print(f"   X quota hit - kept {len(x_rows)} X posts from partial fetch")
    else:
        print(f"   Kept {len(x_rows)} X posts (filtered {x_spam_filtered} spam)")

    # --- Process News ---
    print("\nProcessing NewsAPI articles...")
    news_rows: List[Dict] = []
    news_spam_filtered = 0
    news_too_short = 0

    for art in news_articles:
        title = art.get("title", "") or ""
        desc = art.get("description", "") or ""
        text = f"{title}. {desc}".strip()
        
        if not text or len(text) < 30:
            news_too_short += 1
            continue
            
        if is_spam(text):
            news_spam_filtered += 1
            continue

        url = art.get("url", "")
        news_id = url or hashlib.md5(text.encode()).hexdigest()

        news_rows.append({
            "id": news_id,
            "text": text,
            "created_at": art.get("publishedAt"),
            "author_id": art.get("source", {}).get("name", "news"),
            "like_count": 0,
            "reply_count": 0,
            "repost_count": 0,
            "quote_count": 0,
            "engagement": 0,
            "topic": classify_topic(text),
            "country": extract_country(text),
            "intensity": calculate_intensity(text),
            "source": art.get("source", {}).get("name", "newsapi").lower().replace(" ", "_"),
        })

    print(f"   Kept {len(news_rows)} news articles (filtered {news_spam_filtered} spam, {news_too_short} too short)")

    # --- Combine new data ---
    new_rows = x_rows + news_rows
    new_rows = deduplicate_rows(new_rows)

    # Remove "other" category - no actionable signal
    before_filter = len(new_rows)
    new_rows = [row for row in new_rows if row.get("topic") != "other"]
    filtered_count = before_filter - len(new_rows)
    if filtered_count > 0:
        print(f"   Filtered out {filtered_count} 'other' category articles")

    if not new_rows:
        print("\nNo new data after filtering")
        if not existing_df.empty:
            print(f"Keeping {len(existing_df)} existing entries")
            # Convert timestamps back to strings
            if "created_at" in existing_df.columns:
                existing_df["created_at"] = existing_df["created_at"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")
            existing_df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_NONNUMERIC)
            print(f"Saved to {OUTPUT_CSV}")
        else:
            print("No existing data either - creating empty file")
        sys.exit(0)

    # --- Combine with existing data ---
    columns = [
        "id", "text", "created_at", "author_id",
        "like_count", "reply_count", "repost_count", "quote_count",
        "engagement", "topic", "country", "intensity", "source"
    ]

    new_df = pd.DataFrame(new_rows, columns=columns)

    print(f"\nNew data summary:")
    print(f"   X posts: {len(x_rows)}")
    print(f"   News articles: {len(news_rows)}")
    print(f"   Total new: {len(new_df)}")

    if not existing_df.empty:
        # Ensure same columns
        for col in columns:
            if col not in existing_df.columns:
                existing_df[col] = ""
        
        # Convert timestamps back to strings for existing data
        if "created_at" in existing_df.columns and existing_df["created_at"].dtype != 'object':
            existing_df["created_at"] = existing_df["created_at"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        
        # Remove duplicates (keep newest)
        combined_df = combined_df.drop_duplicates(subset=["id"], keep="last")
        
        print(f"   Combined with existing: {len(combined_df)} total entries")
    else:
        combined_df = new_df

    # Sort by engagement (most engaging first) for better visibility
    if "engagement" in combined_df.columns:
        combined_df = combined_df.sort_values("engagement", ascending=False)

    # Show topic distribution
    print(f"\nTopic distribution:")
    topic_counts = combined_df["topic"].value_counts().head(10)
    for topic, count in topic_counts.items():
        print(f"   {topic}: {count}")

    # Show source breakdown
    source_counts = combined_df["source"].value_counts()
    print(f"\nSource breakdown:")
    for source, count in source_counts.items():
        print(f"   {source}: {count}")

    # Save
    combined_df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_NONNUMERIC)
    print(f"\nSaved {len(combined_df)} rows to {OUTPUT_CSV}")

# Exit with code 2 if X quota was hit (signals to workflow)
    if hit_cap:
        print("\nNote: X API quota was exceeded, but RSS + News data was still fetched")
        sys.exit(2)

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
