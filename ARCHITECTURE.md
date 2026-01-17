# Moodlight Architecture

## Core Systems

### 1. Strategic Brief Generator (`app.py`)
- **Trigger**: Manual, via dashboard button
- **Requires user input**: Product/service, target audience, markets/geography, key challenge, timeline/budget
- **Process**: Synthesizes real-time data with 19 strategic frameworks based on user context
- **Output**: Cultural Momentum Matrix (WHERE to play, WHEN to play, WHAT to say)

### 2. Daily Intelligence Brief (`generate_brief.py`)
- **Trigger**: Automated, 2x daily via GitHub Actions
- **Delivery**: Email
- **No user input** — fully automated situational awareness
- **Output**: IC-level intelligence brief
  - Key Threats
  - Emerging Patterns
  - Recommended Actions

## Data Flow

```
GitHub Actions (scheduled)
    │
    ├── fetch_news.py → NewsAPI → news_raw.csv
    ├── fetch_social.py → X API → social_raw.csv
    │
    ├── score_news.py → news_scored.csv → PostgreSQL (news_scored)
    ├── score_social.py → social_scored.csv → PostgreSQL (social_scored)
    │
    └── generate_brief.py → Email (Daily Intelligence Brief)

Dashboard (app.py)
    │
    ├── Reads from PostgreSQL (news_scored, social_scored)
    ├── Displays Cultural Pulse charts
    └── Strategic Brief Generator → Cultural Momentum Matrix
```

## Key Distinctions

| Aspect | Strategic Brief Generator | Daily Intelligence Brief |
|--------|---------------------------|--------------------------|
| Location | `app.py` | `generate_brief.py` |
| Trigger | Manual (dashboard) | Automated (2x daily) |
| User input | Required | None |
| Framework | 19 strategic frameworks | Simple summary |
| Output | Cultural Momentum Matrix | Key Threats / Emerging Patterns / Recommended Actions |
| Audience | Executives needing strategic guidance | Anyone needing situational awareness |
