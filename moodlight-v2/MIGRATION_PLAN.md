# Moodlight FastAPI Migration Plan

## Overview
Migrating from Streamlit monolith (2,860 lines) to FastAPI + HTMX architecture.

---

## Day 1: Foundation (6-8 hours)
### Project Setup
- [x] Create moodlight-v2 directory structure
- [x] Initialize requirements.txt with dependencies
- [x] Create config.py with environment settings
- [x] Set up database.py with async SQLAlchemy

### Database Models
- [x] User model (matches existing schema)
- [x] Session model (replaces file-based session_manager.py)
- [x] NewsItem model (for news_scored/social_scored tables)

### Authentication System
- [x] JWT token service (replaces streamlit_authenticator)
- [x] Single-session enforcement (database-backed, replaces JSON file)
- [x] Auth router: /login, /logout, /me endpoints
- [x] Login page template with HTMX

### Deliverables
- Working login/logout flow
- JWT-based session management
- Database connection verified

---

## Day 2: Dashboard Core (6-8 hours)
### Data Loading Service
- [ ] Port load_data() function
- [ ] Database-first with CSV fallback
- [ ] Filter by date range (Breaking 48h / Strategic 30d)

### Dashboard Router & Template
- [ ] Main dashboard route
- [ ] World mood gauge (empathy score 0-100)
- [ ] View mode toggle (Breaking/Strategic)
- [ ] Basic layout with sidebar navigation

### Constants Migration
- [ ] EMOTION_COLORS, EMOTION_EMOJIS
- [ ] TOPIC_CATEGORIES, EMPATHY_LEVELS
- [ ] SPAM_KEYWORDS for filtering

### Deliverables
- Dashboard loads and displays world mood
- View mode switching works
- User tier displayed in sidebar

---

## Day 3: Data Visualization (6-8 hours)
### Chart.js Integration
- [ ] Replace Altair with Chart.js
- [ ] Emotion distribution pie/doughnut chart
- [ ] Topic distribution horizontal bar chart
- [ ] Mood history line chart (7-day trend)

### HTMX Partial Updates
- [ ] Chart refresh without full page reload
- [ ] Date range filter updates charts
- [ ] Loading states for async data

### Headlines Component
- [ ] Trending headlines list
- [ ] Spam filtering (SPAM_KEYWORDS)
- [ ] Source badges (X, NewsAPI, Reddit)

### Deliverables
- All 3 main charts rendering
- Headlines list with filtering
- HTMX partial updates working

---

## Day 4: Features Migration (6-8 hours)
### Polymarket Integration
- [ ] Port polymarket_helper.py
- [ ] Market sentiment display
- [ ] Sentiment divergence calculation

### Stock Data Service
- [ ] Yahoo Finance ticker lookup
- [ ] AlphaVantage quote fetching
- [ ] Stock display component

### Geographic Analysis
- [ ] Country-level sentiment map (or table)
- [ ] Top countries by volume

### Deliverables
- Polymarket section functional
- Stock quotes displaying
- Geographic breakdown working

---

## Day 5: Strategic Briefs (8-10 hours)
### Brief Generator Service
- [ ] Port strategic_frameworks.py (19 frameworks)
- [ ] Claude API integration
- [ ] Cultural Momentum Matrix generation

### Brief Router & UI
- [ ] Brief generation form
- [ ] Framework selection (multi-select)
- [ ] Progress indicator during generation
- [ ] Brief display with formatting

### Tier Enforcement
- [ ] Port tier_helper.py logic
- [ ] Brief quota checking
- [ ] Upgrade prompts

### Email Delivery
- [ ] Gmail SMTP integration
- [ ] Brief email formatting
- [ ] Send confirmation

### Deliverables
- Full brief generation working
- Tier limits enforced
- Email delivery functional

---

## Day 6: Brand Analysis & Polish (6-8 hours)
### Brand Analysis Feature
- [ ] Brand filter input
- [ ] VLDS calculations (Velocity, Longevity, Density, Scarcity)
- [ ] Port calculate_*.py helpers
- [ ] Brand-specific charts

### Data Refresh
- [ ] Manual refresh button
- [ ] Background job for fetch + score
- [ ] Progress tracking

### UI Polish
- [ ] Dark theme styling (match Streamlit theme)
- [ ] Mobile responsiveness
- [ ] Error handling & toasts
- [ ] Loading skeletons

### Deliverables
- Brand analysis fully functional
- Refresh working
- Polished UI

---

## Day 7: Deployment & Cutover (4-6 hours)
### Railway Setup
- [ ] Create moodlight-v2 Railway project
- [ ] Configure environment variables
- [ ] PostgreSQL connection
- [ ] Health check endpoint

### Stripe Webhook
- [ ] Port webhook_server.py logic
- [ ] Update webhook URL in Stripe
- [ ] Test subscription flow

### Testing & Validation
- [ ] End-to-end testing all features
- [ ] Performance comparison
- [ ] Data integrity checks

### Cutover
- [ ] Update DNS/domain
- [ ] Monitor for errors
- [ ] Keep Streamlit as fallback

---

## Technical Stack

| Component | Old (Streamlit) | New (FastAPI) |
|-----------|-----------------|---------------|
| Framework | Streamlit | FastAPI + HTMX |
| Templates | Streamlit components | Jinja2 + HTMX |
| Auth | streamlit_authenticator | JWT + httponly cookies |
| Sessions | JSON file | PostgreSQL table |
| Charts | Altair | Chart.js |
| Styling | Streamlit theme | Tailwind CSS |
| Database | SQLAlchemy sync | SQLAlchemy async |

---

## Environment Variables Required
```
DATABASE_URL=postgresql://...
SECRET_KEY=your-jwt-secret-key
X_BEARER_TOKEN=twitter-api-token
NEWSAPI_KEY=newsapi-key
ANTHROPIC_API_KEY=claude-api-key
STRIPE_SECRET_KEY=stripe-key
STRIPE_WEBHOOK_SECRET=webhook-secret
EMAIL_ADDRESS=sender@gmail.com
EMAIL_PASSWORD=app-password
ALPHAVANTAGE_API_KEY=alphavantage-key
```

---

## File Mapping

| Old File | New Location |
|----------|--------------|
| app.py (auth) | app/routers/auth.py, app/services/auth.py |
| app.py (dashboard) | app/routers/dashboard.py |
| app.py (briefs) | app/routers/briefs.py, app/services/brief_generator.py |
| session_manager.py | app/services/auth.py (db-backed) |
| tier_helper.py | app/services/tier.py |
| db_helper.py | app/database.py |
| polymarket_helper.py | app/services/polymarket.py |
| strategic_frameworks.py | app/services/brief_generator.py |
| calculate_*.py | app/services/vlds.py |
| fetch_posts.py | jobs/fetch_social.py |
| fetch_news_rss.py | jobs/fetch_news.py |
| score_empathy.py | app/services/empathy_scorer.py |
