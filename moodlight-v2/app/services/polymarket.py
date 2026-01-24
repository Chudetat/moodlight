"""
Polymarket API integration for prediction market data.
Port of polymarket_helper.py with async support.
"""
import httpx
import json
from typing import Optional

GAMMA_API_BASE = "https://gamma-api.polymarket.com"

# Topic keywords for filtering markets
TOPIC_KEYWORDS = {
    "technology & ai": ["ai", "artificial intelligence", "tech", "openai", "google", "microsoft", "apple", "chatgpt"],
    "economics": ["economy", "gdp", "recession", "inflation", "fed", "interest rate", "unemployment"],
    "politics": ["election", "trump", "biden", "congress", "senate", "president", "vote", "governor"],
    "entertainment": ["movie", "oscars", "grammy", "netflix", "disney", "streaming", "taylor swift"],
    "sports": ["nfl", "nba", "super bowl", "world cup", "championship", "playoffs"],
    "climate & environment": ["oil", "energy", "climate", "renewable", "solar", "ev"],
    "healthcare & wellbeing": ["fda", "drug", "vaccine", "healthcare", "medical", "covid"],
}


async def fetch_polymarket_markets(
    limit: int = 20,
    active: bool = True,
    min_volume: float = 10000
) -> list[dict]:
    """
    Fetch active prediction markets from Polymarket.

    Args:
        limit: Maximum number of markets to fetch
        active: Only fetch active markets
        min_volume: Minimum trading volume filter

    Returns:
        List of market dicts with question, odds, volume, etc.
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

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers, timeout=15)
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
                "volume_display": format_volume(volume),
                "liquidity": float(m.get("liquidity", 0) or 0),
                "category": m.get("groupItemTitle") or m.get("category") or "General",
                "end_date": m.get("endDate"),
                "image": m.get("image"),
                "slug": m.get("slug"),
                "outcomes": m.get("outcomes", ["Yes", "No"]),
                "url": f"https://polymarket.com/event/{m.get('slug')}" if m.get("slug") else None
            }

            # Match to Moodlight topics
            market["matched_topic"] = match_market_to_topic(market["question"], market["category"])

            markets.append(market)

        return markets

    except httpx.RequestError as e:
        print(f"Polymarket API error: {e}")
        return []
    except Exception as e:
        print(f"Polymarket parsing error: {e}")
        return []


def format_volume(volume: float) -> str:
    """Format volume for display."""
    if volume >= 1_000_000:
        return f"${volume / 1_000_000:.1f}M"
    elif volume >= 1_000:
        return f"${volume / 1_000:.1f}K"
    else:
        return f"${volume:.0f}"


def match_market_to_topic(question: str, category: str) -> Optional[str]:
    """Match a market question to Moodlight topics."""
    text = (question + " " + category).lower()

    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return topic

    return None


def calculate_sentiment_divergence(
    market_odds: float,
    social_sentiment: float
) -> dict:
    """
    Calculate divergence between prediction market odds and social sentiment.

    Args:
        market_odds: 0-100 (probability of YES outcome)
        social_sentiment: 0-100 (empathy/positivity score from Moodlight)

    Returns:
        Dict with divergence info and interpretation
    """
    divergence = abs(market_odds - social_sentiment)

    if divergence > 30:
        status = "High Divergence"
        interpretation = "Markets and social sentiment strongly disagree - potential opportunity or risk"
        color = "red"
    elif divergence > 15:
        status = "Moderate Divergence"
        interpretation = "Notable gap between market expectations and social mood"
        color = "yellow"
    else:
        status = "Aligned"
        interpretation = "Markets and social sentiment are in agreement"
        color = "green"

    return {
        "divergence": round(divergence, 1),
        "status": status,
        "interpretation": interpretation,
        "color": color,
        "market_signal": market_odds,
        "social_signal": social_sentiment
    }


def get_top_markets_summary(markets: list[dict], limit: int = 10) -> str:
    """
    Get a text summary of top prediction markets for AI briefings.

    Args:
        markets: List of market dicts
        limit: Number of markets to include

    Returns:
        Formatted text summary
    """
    if not markets:
        return "No prediction market data available."

    lines = ["TOP PREDICTION MARKETS:"]
    for m in markets[:limit]:
        lines.append(f"- {m['question']}: {m['yes_odds']}% YES ({m['volume_display']} volume)")

    return "\n".join(lines)


async def get_markets_by_topic(topic: str, limit: int = 10) -> list[dict]:
    """
    Get markets matching a specific topic.

    Args:
        topic: Topic to filter by
        limit: Maximum markets to return

    Returns:
        List of matching markets
    """
    markets = await fetch_polymarket_markets(limit=50)

    filtered = [m for m in markets if m.get("matched_topic") == topic.lower()]
    return filtered[:limit]
