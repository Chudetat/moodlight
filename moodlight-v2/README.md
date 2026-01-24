# Moodlight v2

FastAPI + HTMX rewrite of the Moodlight cultural intelligence platform.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your credentials

# Initialize database
python -m scripts.init_db

# Add a test user
python -m scripts.add_user admin admin@example.com yourpassword pro

# Run development server
uvicorn app.main:app --reload --port 8000
```

## Project Structure

```
moodlight-v2/
├── app/
│   ├── main.py           # FastAPI application entry point
│   ├── config.py         # Environment configuration
│   ├── database.py       # SQLAlchemy async setup
│   ├── models.py         # Database models
│   │
│   ├── routers/          # API route handlers
│   │   └── auth.py       # Authentication routes
│   │
│   ├── services/         # Business logic
│   │   ├── auth.py       # JWT + session management
│   │   └── tier.py       # Subscription tier logic
│   │
│   ├── templates/        # Jinja2 HTML templates
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   └── auth/
│   │
│   └── utils/            # Utilities
│       └── constants.py  # App constants
│
├── static/               # Static assets
│   ├── css/
│   └── js/
│
├── scripts/              # CLI scripts
│   ├── init_db.py
│   └── add_user.py
│
├── requirements.txt
├── Procfile              # Railway deployment
└── .env.example
```

## Tech Stack

- **Backend**: FastAPI
- **Frontend**: HTMX + Jinja2 + Tailwind CSS
- **Database**: PostgreSQL + SQLAlchemy (async)
- **Auth**: JWT + httponly cookies
- **Charts**: Chart.js

## Migration from Streamlit

This is a complete rewrite of the original Streamlit application.

Key differences:
- Session management moved from file-based to database-backed
- Authentication uses JWT instead of streamlit_authenticator
- Charts use Chart.js instead of Altair
- Single-session enforcement via database

## Development

```bash
# Run with auto-reload
uvicorn app.main:app --reload --port 8000

# Run tests
pytest

# Format code
black app/ scripts/
```

## Deployment

Configured for Railway deployment via Procfile.

Required environment variables:
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT signing key
- See `.env.example` for full list
