# Moodlight

An agentic reasoning engine for cultural and competitive intelligence. Moodlight autonomously monitors news, social media, and global markets — detecting anomalies, predicting trends, investigating signals with multi-step AI reasoning, and adapting its own sensitivity based on user feedback.

Unlike conventional AI agents that wrap an LLM in a prompt loop, Moodlight's intelligence is domain-native: a custom detection layer (VLDS scoring, 21 statistical detectors, predictive trend analysis) decides *what matters*, while Claude is called surgically for investigation, competitor discovery, and strategic framework application. The LLM is a tool, not the brain.

## Architecture

```
Data Ingestion          Detection Layer           AI Reasoning            Action Layer
─────────────          ───────────────           ────────────            ────────────
150+ RSS feeds    →    18 reactive detectors  →  Multi-step chains   →  Email alerts
X (Twitter) API   →    Predictive trend        →  (2-5 steps with    →  Dashboard
NewsAPI            →      extrapolation         →   confidence scoring →  Competitive
7 market indices   →    Compound signal         →   & early bailout)  →    War Room
                        detection               →                     →  Weekly digest
                        VLDS scoring            →                     →  Adaptive
                        Crisis & breaking       →                        threshold
                          signal detection                               tuning
                   ←──────────────── Feedback Loop ←──────────────────
                        User thumbs up/down → adaptive threshold adjustment
```

## Core Intelligence

### VLDS Scoring Framework

A proprietary metric system for measuring brand and topic dynamics:

- **Velocity** — Conversation momentum (recent activity vs baseline)
- **Longevity** — Narrative staying power (how many days a story persists)
- **Density** — Market saturation (coverage volume relative to capacity)
- **Scarcity** — White space opportunity (inverse of density)

VLDS scores are computed for every watched brand and used across detection, competitive analysis, and strategic recommendations.

### Anomaly Detection (21 Detectors)

**7 Global Detectors** — Run on all data every pipeline cycle:
| Detector | What It Catches |
|----------|----------------|
| Mood Shift | Day-over-day swing in average empathy score |
| Market-Mood Divergence | Social sentiment diverging from market sentiment |
| Intensity Cluster | Unusual concentration of high-emotion content |
| Topic Emergence | New topic absent from prior days now dominating coverage |
| Regulatory/Policy Spike | High-intensity surge in government, economics, or political topics |
| Breaking Signal | High-intensity story spreading across 3+ sources within 6 hours |
| Geopolitical Risk Escalation | Accelerating intensity in conflict and foreign policy topics |

**8 Brand-Specific Detectors** — Per watched brand:
| Detector | What It Catches |
|----------|----------------|
| White Space | High scarcity = first-mover opportunity |
| Velocity Spike | Conversation accelerating rapidly |
| Narrative Fading | Longevity dropping = closing window |
| Saturation Warning | Density too high = crowded space |
| News Mention Surge | 3x+ spike in daily news mentions |
| Social Buzz Spike | 3x+ spike in daily social mentions |
| Sentiment Shift | Brand sentiment deviating from rolling average |
| Crisis Detection | Volume surge + low empathy + negative emotions = PR crisis signal |

**3 Competitive Detectors** — Brand vs discovered competitors:
| Detector | What It Catches |
|----------|----------------|
| Competitor Momentum | Competitor velocity exceeding the brand's |
| Share of Voice Shift | Competitor SOV overtaking the brand's |
| Competitive White Space | Density gap between brand and competitors |

**3 Predictive Detectors** — Early warning before thresholds are crossed:
| Detector | What It Catches |
|----------|----------------|
| Threshold Approach | Metric trending toward a threshold at current rate |
| Momentum Tracking | Acceleration/deceleration of key metrics |
| Compound Signals | Multiple weak signals converging simultaneously |

All thresholds are configurable via database and adapt automatically based on user feedback. High-confidence predictive alerts (R² > 0.7 or compound score >= 4) are automatically promoted to warning severity and emailed to subscribers.

### Multi-Step Reasoning Chains

Complex alerts are investigated through sequential AI analysis where each step builds on the previous:

1. **Situation Assessment** — What is happening? Raw data summarization.
2. **Historical Context** — Has this happened before? Queries past alerts and metric history for precedent.
3. **Causal Analysis** — Why is this happening? Cross-references news, social, and market signals.
4. **Strategic Implications** — What should the user do? Applies relevant strategic frameworks (19 available including Porter's Five Forces, Blue Ocean, JTBD, STEPPS, SCCT).
5. **Confidence Scoring** — How confident are we? Scores 0-100 with actionable recommendation (Act Now / Monitor / Investigate Further).

Not every alert gets all 5 steps. Simple alerts (mention surge, mood shift) get 2-3 steps. Complex alerts (predictive, competitive, crisis, breaking signal, geopolitical, regulatory) get the full chain. The system bails out early if confidence drops below 20%.

### Competitive War Room

When a brand is added to the watchlist, Moodlight autonomously:
1. **Discovers competitors** using Claude (3-5 per brand, cached in DB)
2. **Computes competitive snapshots** — VLDS comparison, share of voice, competitive gaps
3. **Runs competitive detectors** — alerts when competitors outpace the brand
4. **Generates AI positioning insights** on demand

The dashboard displays share of voice charts, VLDS comparison metrics with deltas, and competitor profiles.

### Adaptive Feedback Loops

The system learns from user behavior:
- **Thumbs up/down** on every alert feeds engagement and approval rates
- **Adaptive tuner** runs every pipeline cycle: raises thresholds for noisy alerts (high thumbs-down), lowers thresholds for valued alerts (high approval + engagement)
- **Guardrails** prevent oscillation: max 10% change per cycle, clamped to 0.5x-2x of defaults
- **Audit trail** logs every threshold change with reasoning

## Data Pipeline

### Ingestion

| Source | Frequency | What |
|--------|-----------|------|
| RSS Feeds (150+) | Hourly | Global news across politics, business, tech, health, culture |
| NewsAPI | Hourly | Brand-specific queries for watched brands |
| X (Twitter) API | 3x daily | Social posts from major outlets, viral signals, brand mentions |
| AlphaVantage | Daily | 7 market indices (SPY, DIA, QQQ, EWU, EWJ, EWG, FXI) |

### Scoring

Every article and post is scored by a RoBERTa-based emotion model (SamLowe/roberta-base-go_emotions):

- **Empathy Score** (0-1) — Prosocial emotion concentration
- **Empathy Label** — Cold/Hostile, Detached/Neutral, Warm/Supportive, Highly Empathetic
- **Top 3 Emotions** — From 27 GoEmotions categories
- **Topic Classification** — 26 categories including high-risk topics (war, terrorism, cybersecurity, financial stress)
- **Intensity Score** — 1-5 severity scale

### Pipeline Flow

```
Fetch → Score → Store → Detect → Predict → Investigate → Alert → Tune
```

Each pipeline run (hourly for news, 3x daily for social):
1. Fetches and scores new content
2. Saves to PostgreSQL
3. Captures daily metric snapshots for trend analysis (including geopolitical intensity tracking)
4. Runs 18 reactive detectors with configurable thresholds (7 global + 8 brand + 3 competitive)
5. Runs predictive detectors (trend extrapolation, compound signals, auto-promotion of high-confidence predictions)
6. For each brand in watchlist: discovers competitors, computes competitive snapshot, runs competitive detectors
7. Investigates alerts via multi-step reasoning chains (or single-turn for simple alerts)
8. Stores alerts with cooldown deduplication (6h reactive, 24h predictive)
9. Emails critical/warning alerts to subscribers (rate-limited 5/day, critical-first priority)
10. Runs adaptive threshold tuning based on accumulated feedback

## Email Intelligence

Subscribers receive three types of email communications:

| Type | Frequency | Content |
|------|-----------|---------|
| **Alert Emails** | Real-time (max 5/day) | Critical and warning alerts with AI investigation, severity-coded with reasoning chain results |
| **Intelligence Brief** | 2x daily (6am/6pm PST) | AI-generated executive summary of key threats, watch list, emerging patterns, and recommended actions |
| **Weekly Strategic Digest** | Weekly (Monday 7am PST) | Deep analysis covering alert patterns, VLDS trends, competitive shifts, and forward-looking assessment |

All emails are styled with consistent HTML formatting, color-coded sections, and tagged metadata ([NEW], [ONGOING], [HIGH CONFIDENCE], etc.).

## Dashboard

Streamlit-based intelligence dashboard deployed on Railway.

**Sections:**
- **Executive Summary** — Key metrics, market sentiment, empathy temperature
- **Intelligence Alerts** — Severity-coded alert cards with expandable multi-step reasoning, thumbs up/down feedback, predictive badges
- **Competitive War Room** — Per-brand SOV charts, VLDS comparison, competitor profiles, AI insight generation
- **Detailed Analysis** — Empathy by topic, emotion distributions, geographic heatmaps
- **Brand Analysis** — Per-brand VLDS deep dive with topic and emotion breakdowns
- **Prediction Markets** — Polymarket integration for cultural signal tracking
- **Strategic Brief** — AI-generated executive intelligence brief (2x daily)

**User System:**
- Authentication with session management (single active session per user)
- Free and Professional tiers with brief credit system
- Stripe integration for subscription management
- Admin panel for user management

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Streamlit, Altair |
| Backend | Python, FastAPI (webhooks) |
| Database | PostgreSQL (Railway) |
| AI Models | Claude Sonnet 4.5 (investigation, discovery, strategy), RoBERTa (emotion scoring) |
| Deployment | Railway (web + webhook processes) |
| CI/CD | GitHub Actions (5 scheduled workflows) |
| Payments | Stripe (webhooks + subscription management) |
| Email | Gmail SMTP (alerts + briefs + weekly digest) |

## Database Schema

**Data Tables:**
- `news_scored` — Scored news articles (7-day retention)
- `social_scored` — Scored social posts (7-day retention)
- `markets` — Market indices and sentiment

**Alert System Tables:**
- `alerts` — Detected anomalies with investigation, severity, cooldown keys
- `alert_thresholds` — Configurable thresholds per alert type (21 types)
- `threshold_audit_log` — Audit trail of threshold changes
- `alert_feedback` — User engagement tracking (expand, thumbs up/down)
- `metric_snapshots` — Daily metric values for trend analysis (global + per-brand + geopolitical)

**Competitive Intelligence Tables:**
- `brand_watchlist` — User brand subscriptions
- `brand_competitors` — Discovered competitors with confidence scores
- `competitive_snapshots` — Periodic competitive landscape snapshots

**User Tables:**
- `users` — Accounts, tiers, subscription status, brief credits

## Project Structure

```
moodlight/
├── app.py                      # Main Streamlit dashboard
├── webhook_server.py           # FastAPI Stripe webhook server
│
├── # Data Collection
├── fetch_news_rss.py           # News ingestion (RSS + NewsAPI)
├── fetch_posts.py              # Social ingestion (X API + NewsAPI)
├── fetch_markets.py            # Market indices + sentiment
├── score_empathy.py            # RoBERTa emotion scoring
├── save_to_db.py               # PostgreSQL persistence
│
├── # Intelligence Engine
├── vlds_helper.py              # VLDS scoring framework
├── alert_detector.py           # 18 reactive detectors (7 global + 8 brand + 3 competitive)
├── predictive_detector.py      # Trend extrapolation + compound signals + auto-promotion
├── alert_pipeline.py           # Pipeline orchestrator
│
├── # AI Reasoning
├── alert_investigator.py       # Single-turn Claude investigation
├── reasoning_chain.py          # Multi-step reasoning chains (2-5 steps)
├── competitor_discovery.py     # Claude-powered competitor identification
├── competitive_analyzer.py     # VLDS comparison + SOV + gap analysis
├── strategic_frameworks.py     # 19 strategic frameworks library
├── generate_brief.py           # Executive intelligence brief (2x daily)
├── generate_weekly_digest.py   # Weekly strategic digest (Monday)
│
├── # Adaptive Learning
├── alert_thresholds.py         # DB-backed configurable thresholds
├── alert_feedback.py           # User engagement tracking
├── adaptive_tuner.py           # Feedback-driven threshold adjustment
├── alert_emailer.py            # Email alert delivery (critical-first priority)
│
├── # User Management
├── db_helper.py                # Database utilities
├── tier_helper.py              # Subscription tier management
├── session_manager.py          # Single-session enforcement
├── config.yaml                 # Authentication config
│
├── .github/workflows/
│   ├── fetch_news.yml          # Hourly news pipeline
│   ├── fetch_social.yml        # 3x daily social pipeline
│   ├── generate_brief.yml      # 2x daily intelligence brief
│   ├── generate_weekly_digest.yml  # Weekly strategic digest (Monday 7am PST)
│   └── backfill_markets.yml    # One-time market backfill
│
├── Procfile                    # Railway deployment (web + webhook)
├── requirements.txt            # Python dependencies
└── .streamlit/config.toml      # Dashboard theme
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string |
| `ANTHROPIC_API_KEY` | Claude API for investigation + discovery |
| `X_BEARER_TOKEN` | X (Twitter) API access |
| `NEWSAPI_KEY` | NewsAPI for news + brand queries |
| `ALPHAVANTAGE_API_KEY` | Market data API |
| `EMAIL_ADDRESS` | Gmail sender for alerts + briefs |
| `EMAIL_PASSWORD` | Gmail app password |
| `EMAIL_RECIPIENT` | Comma-separated fallback subscriber list |
| `STRIPE_SECRET_KEY` | Stripe payment processing |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook verification |

## License

Proprietary. All rights reserved.
