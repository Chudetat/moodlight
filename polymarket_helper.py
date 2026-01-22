"""
Polymarket API Integration
Fetches prediction market data for cultural intelligence dashboard
"""

import requests
import json
from typing import List, Dict, Optional
from datetime import datetime, timezone

GAMMA_API_BASE = "https://gamma-api.polymarket.com"

# Categories relevant to cultural intelligence
RELEVANT_TAGS = [
    "politics", "elections", "economy", "technology", "entertainment",
    "sports", "crypto", "ai", "business", "media"
]

def fetch_polymarket_markets(
    limit: int = 20,
    active: bool = True,
    min_volume: float = 10000
) -> List[Dict]:
    """
    Fetch active prediction markets from Polymarket.

    Returns list of markets with: question, odds, volume, category
    """
    try:
        url = f"{GAMMA_API_BASE}/markets"
        params = {
            "limit": limit,
            "active": str(active).lower(),
            "closed": "false",
            "order": "volume",
            "ascending": "false"
        }

        headers = {
            "User-Agent": "Moodlight Intelligence Platform",
            "Accept": "application/json"
        }

        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()

        markets_raw = response.json()

        markets = []
        for m in markets_raw:
            # Parse outcome prices (odds)
            try:
                outcome_prices = json.loads(m.get("outcomePrices", "[]"))
                if len(outcome_prices) >= 2:
                    yes_odds = float(outcome_prices[0]) * 100
                    no_odds = float(outcome_prices[1]) * 100
                else:
                    yes_odds = 50
                    no_odds = 50
            except (json.JSONDecodeError, IndexError, ValueError):
                yes_odds = 50
                no_odds = 50

            volume = float(m.get("volume", 0) or 0)

            # Filter by minimum volume
            if volume < min_volume:
                continue

            market = {
                "id": m.get("id"),
                "question": m.get("question", "Unknown"),
                "description": m.get("description", ""),
                "yes_odds": round(yes_odds, 1),
                "no_odds": round(no_odds, 1),
                "volume": volume,
                "liquidity": float(m.get("liquidity", 0) or 0),
                "category": m.get("groupItemTitle") or m.get("category") or "General",
                "end_date": m.get("endDate"),
                "image": m.get("image"),
                "slug": m.get("slug"),
                "outcomes": m.get("outcomes", ["Yes", "No"])
            }
            markets.append(market)

        return markets

    except requests.exceptions.RequestException as e:
        print(f"Polymarket API error: {e}")
        return []
    except Exception as e:
        print(f"Polymarket parsing error: {e}")
        return []


def fetch_polymarket_events(limit: int = 10) -> List[Dict]:
    """
    Fetch prediction market events (grouped markets).
    """
    try:
        url = f"{GAMMA_API_BASE}/events"
        params = {
            "limit": limit,
            "active": "true",
            "closed": "false",
            "order": "volume",
            "ascending": "false"
        }

        headers = {
            "User-Agent": "Moodlight Intelligence Platform",
            "Accept": "application/json"
        }

        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()

        return response.json()

    except Exception as e:
        print(f"Polymarket events error: {e}")
        return []


def calculate_sentiment_divergence(
    market_odds: float,
    social_sentiment: float
) -> Dict:
    """
    Calculate divergence between prediction market odds and social sentiment.

    market_odds: 0-100 (probability of YES outcome)
    social_sentiment: 0-100 (empathy/positivity score from Moodlight)

    Returns divergence info with interpretation.
    """
    # Normalize both to 0-100 scale
    market_signal = market_odds  # Already 0-100
    social_signal = social_sentiment  # Already 0-100

    divergence = abs(market_signal - social_signal)

    if divergence > 30:
        status = "High Divergence"
        interpretation = "Markets and social sentiment strongly disagree - potential opportunity or risk"
        color = "🔴"
    elif divergence > 15:
        status = "Moderate Divergence"
        interpretation = "Notable gap between market expectations and social mood"
        color = "🟡"
    else:
        status = "Aligned"
        interpretation = "Markets and social sentiment are in agreement"
        color = "🟢"

    return {
        "divergence": round(divergence, 1),
        "status": status,
        "interpretation": interpretation,
        "color": color,
        "market_signal": market_signal,
        "social_signal": social_signal
    }


def filter_markets_by_topic(
    markets: List[Dict],
    topics: List[str]
) -> List[Dict]:
    """
    Filter markets that match Moodlight topics for comparison.
    """
    topic_keywords = {
        "Technology & AI": ["ai", "artificial intelligence", "tech", "openai", "google", "microsoft", "apple"],
        "Economics": ["economy", "gdp", "recession", "inflation", "fed", "interest rate"],
        "Politics": ["election", "trump", "biden", "congress", "senate", "president", "vote"],
        "Entertainment": ["movie", "oscars", "grammy", "netflix", "disney", "streaming"],
        "Sports": ["nfl", "nba", "super bowl", "world cup", "championship"],
        "Energy & Climate": ["oil", "energy", "climate", "renewable", "solar"],
        "Healthcare": ["fda", "drug", "vaccine", "healthcare", "medical"],
    }

    filtered = []
    for market in markets:
        question_lower = market["question"].lower()
        category_lower = market.get("category", "").lower()

        for topic, keywords in topic_keywords.items():
            if any(kw in question_lower or kw in category_lower for kw in keywords):
                market["matched_topic"] = topic
                filtered.append(market)
                break

    return filtered


def get_top_markets_summary(limit: int = 10) -> str:
    """
    Get a text summary of top prediction markets for AI briefings.
    """
    markets = fetch_polymarket_markets(limit=limit)

    if not markets:
        return "No prediction market data available."

    lines = ["TOP PREDICTION MARKETS:"]
    for m in markets[:limit]:
        lines.append(f"- {m['question']}: {m['yes_odds']}% YES (${m['volume']:,.0f} volume)")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test the API
    print("Testing Polymarket API...")
    markets = fetch_polymarket_markets(limit=5)

    if markets:
        print(f"\nFetched {len(markets)} markets:\n")
        for m in markets:
            print(f"📊 {m['question']}")
            print(f"   Yes: {m['yes_odds']}% | No: {m['no_odds']}%")
            print(f"   Volume: ${m['volume']:,.0f}")
            print()
    else:
        print("No markets fetched - API may be unavailable")
