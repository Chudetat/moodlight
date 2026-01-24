"""
Application constants - ported from app.py.
Colors, categories, and configuration values.
"""

# Empathy level labels (0-100 scale)
EMPATHY_LEVELS = [
    "Cold / Hostile",
    "Detached / Neutral",
    "Warm / Supportive",
    "Highly Empathetic",
]

# Topic categories for classification
TOPIC_CATEGORIES = [
    "politics",
    "government",
    "economics",
    "education",
    "culture & identity",
    "branding & advertising",
    "creative & design",
    "technology & ai",
    "climate & environment",
    "healthcare & wellbeing",
    "immigration",
    "crime & safety",
    "war & foreign policy",
    "media & journalism",
    "business & corporate",
    "labor & work",
    "housing",
    "religion & values",
    "sports",
    "entertainment",
    "other",
]

# GoEmotions emotion colors (for charts)
EMOTION_COLORS = {
    "admiration": "#FFD700",
    "amusement": "#FF8C00",
    "anger": "#DC143C",
    "annoyance": "#CD5C5C",
    "approval": "#32CD32",
    "caring": "#FF69B4",
    "confusion": "#9370DB",
    "curiosity": "#00CED1",
    "desire": "#FF1493",
    "disappointment": "#708090",
    "disapproval": "#B22222",
    "disgust": "#556B2F",
    "embarrassment": "#DDA0DD",
    "excitement": "#FF4500",
    "fear": "#8B008B",
    "gratitude": "#20B2AA",
    "grief": "#2F4F4F",
    "joy": "#FFD700",
    "love": "#FF69B4",
    "nervousness": "#DA70D6",
    "neutral": "#808080",
    "optimism": "#98FB98",
    "pride": "#4169E1",
    "realization": "#00BFFF",
    "relief": "#87CEEB",
    "remorse": "#696969",
    "sadness": "#4682B4",
    "surprise": "#FF8C00",
}

# Emotion emojis for display
EMOTION_EMOJIS = {
    "admiration": "star-struck",
    "amusement": "grinning-face",
    "anger": "angry-face",
    "annoyance": "unamused-face",
    "approval": "thumbs-up",
    "caring": "hugging-face",
    "confusion": "confused-face",
    "curiosity": "thinking-face",
    "desire": "smiling-face-with-heart-eyes",
    "disappointment": "disappointed-face",
    "disapproval": "thumbs-down",
    "disgust": "nauseated-face",
    "embarrassment": "flushed-face",
    "excitement": "party-popper",
    "fear": "fearful-face",
    "gratitude": "folded-hands",
    "grief": "crying-face",
    "joy": "smiling-face",
    "love": "red-heart",
    "nervousness": "anxious-face-with-sweat",
    "neutral": "neutral-face",
    "optimism": "glowing-star",
    "pride": "lion",
    "realization": "light-bulb",
    "relief": "relieved-face",
    "remorse": "pensive-face",
    "sadness": "crying-face",
    "surprise": "face-with-open-mouth",
}

# Spam keywords to filter from trending headlines
SPAM_KEYWORDS = [
    "crypto", "bitcoin", "btc", "eth", "ethereum", "nft", "airdrop", "presale",
    "whitelist", "pump", "moon", "hodl", "doge", "shib", "memecoin", "web3", "defi",
    "trading signals", "forex", "binary options", "giveaway", "dm for", "link in bio"
]

# Source display names
SOURCE_NAMES = {
    "x": "X (Twitter)",
    "news": "NewsAPI",
    "newsapi": "NewsAPI",
}

# Timeouts and limits
FETCH_TIMEOUT = 300  # 5 minutes
CACHE_TTL_DATA = 10  # 10 seconds for data loads
CACHE_TTL_MARKETS = 3600  # 1 hour for market data
CACHE_TTL_STOCKS = 86400  # 24 hours for stock quotes

# View mode configurations
VIEW_MODES = {
    "breaking": {
        "label": "Breaking (48h)",
        "days": 2,
        "description": "Real-time focus on recent developments"
    },
    "strategic": {
        "label": "Strategic (30d)",
        "days": 30,
        "description": "Broader context for pattern recognition"
    }
}


def empathy_label_from_score(score: float | None) -> str | None:
    """
    Convert empathy score (0-1) to human-readable label.

    Args:
        score: Empathy score between 0 and 1

    Returns:
        Human-readable empathy level label
    """
    if score is None:
        return None
    try:
        score = float(score)
        if score != score:  # NaN check
            return None
    except (TypeError, ValueError):
        return None

    score = max(0.0, min(1.0, score))

    if score < 0.04:
        return EMPATHY_LEVELS[0]
    if score < 0.10:
        return EMPATHY_LEVELS[1]
    if score < 0.30:
        return EMPATHY_LEVELS[2]
    return EMPATHY_LEVELS[3]


def empathy_index_from_label(label: str | None) -> int | None:
    """Get numeric index for empathy label."""
    if label not in EMPATHY_LEVELS:
        return None
    return EMPATHY_LEVELS.index(label)


def clean_source_name(source: str) -> str:
    """Convert source codes to readable names."""
    if source in SOURCE_NAMES:
        return SOURCE_NAMES[source]
    if "reddit" in source.lower():
        parts = source.replace("reddit_", "").replace("_", " ")
        return f"Reddit: {parts.title()}"
    return source.replace("_", " ").title()


def is_spam_headline(text: str) -> bool:
    """Check if a headline contains spam keywords."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in SPAM_KEYWORDS)
