#!/usr/bin/env python
"""
api_server.py — FastAPI data API for the Moodlight platform.

Serves read-only data endpoints for the future Next.js frontend.
Thin wrappers around existing DB query functions in db_helper.py and
patterns from app.py. Deployed as a separate Railway service.

Start locally:
    uvicorn api_server:app --reload --port 8001
"""

import os
import json
import secrets
import pandas as pd
import bcrypt
import stripe
from datetime import datetime, timezone, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text as sql_text

from db_helper import (
    get_engine,
    load_df_from_db,
    load_metric_trends,
    load_economic_data,
    load_commodity_data,
    load_brand_stock_data,
)
from vlds_helper import calculate_brand_vlds
from auth_helper import (
    create_access_token, verify_password, lookup_user,
    is_admin_email, require_auth, _DUMMY_HASH,
    create_session, validate_session, clear_session,
)
from tier_helper import (
    ACTIVE_TIERS, TIER_FEATURES, TIER_LIMITS, log_user_event,
    mark_alert_read, mark_all_alerts_read,
    get_user_alert_preferences, update_user_alert_preferences,
    bulk_update_alert_sensitivity,
    get_user_preferences, update_user_preferences,
    get_report_schedules, create_report_schedule,
    toggle_report_schedule, delete_report_schedule,
    get_user_team, get_team_members, invite_team_member,
    remove_team_member, get_team_watchlist_brands, get_team_watchlist_topics,
    decrement_brief_credits,
)
from alert_feedback import record_feedback
from competitor_discovery import ensure_competitor_tables, ensure_competitors_cached

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
_stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

app = FastAPI(title="Moodlight Data API", docs_url="/api/docs", redoc_url=None)

# CORS — allow Next.js frontend and localhost dev
ALLOWED_ORIGINS = [
    "https://moodlight.app",
    "https://moodlightintel.com",
    "https://www.moodlightintel.com",
    "http://localhost:3000",
    "http://localhost:8001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.up\.railway\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to JSON-safe list of dicts."""
    if df.empty:
        return []
    # Convert timestamps to ISO strings for JSON serialization
    for col in df.select_dtypes(include=["datetime64[ns, UTC]", "datetime64[ns]"]).columns:
        df[col] = df[col].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    # Use orient="records" then sanitize NaN/Infinity which aren't JSON-safe
    import math
    records = df.to_dict("records")
    for row in records:
        for k, v in row.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                row[k] = None
    return records


def _require_engine():
    """Get DB engine or raise 503."""
    engine = get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Database not available")
    return engine


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    """Health check — mirrors webhook_server.py pattern."""
    result = {
        "status": "ok",
        "service": "moodlight-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        engine = get_engine()
        if engine:
            with engine.connect() as conn:
                conn.execute(sql_text("SELECT 1"))
            result["database"] = "connected"
        else:
            result["database"] = "not configured"
            result["status"] = "degraded"
    except Exception as e:
        result["database"] = f"error: {e}"
        result["status"] = "degraded"
    return result


# ---------------------------------------------------------------------------
# Core data
# ---------------------------------------------------------------------------

@app.get("/api/data/combined")
def get_combined_data(days: int = Query(default=7, ge=1, le=30)):
    """Return news_scored + social_scored union (df_all equivalent).

    Text is truncated to 200 chars to keep payload manageable for browsers.
    """
    engine = _require_engine()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    # Select only columns the frontend uses — truncate text to keep payload small
    cols = """
        LEFT(text, 140) AS text, created_at, source, topic,
        COALESCE(engagement, 0) AS engagement,
        country, intensity, empathy_score,
        emotion_top_1, emotion_top_2, emotion_top_3
    """

    frames = []
    for table in ("news_scored", "social_scored"):
        try:
            df = pd.read_sql(
                sql_text(
                    f"SELECT {cols} FROM {table} "
                    f"WHERE created_at >= :cutoff "
                    f"ORDER BY created_at DESC LIMIT 5000"
                ),
                engine,
                params={"cutoff": cutoff},
            )
            if not df.empty:
                df["_source_table"] = table
                frames.append(df)
        except Exception:
            pass

    if not frames:
        return {"data": [], "count": 0}

    combined = pd.concat(frames, ignore_index=True)
    if "created_at" in combined.columns:
        combined["created_at"] = pd.to_datetime(
            combined["created_at"], utc=True, errors="coerce"
        )
    return {"data": _df_to_records(combined), "count": len(combined)}


@app.get("/api/data/markets")
def get_markets(days: int = Query(default=7, ge=1, le=730)):
    """Return market index data."""
    engine = _require_engine()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        df = pd.read_sql(
            sql_text("SELECT * FROM markets WHERE latest_trading_day >= :cutoff"),
            engine,
            params={"cutoff": cutoff},
        )
        return {"data": _df_to_records(df), "count": len(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metrics/{scope}")
def get_metrics(
    scope: str,
    scope_name: Optional[str] = None,
    metric_name: Optional[str] = None,
    days: int = Query(default=30, ge=1, le=730),
):
    """Return metric_snapshots filtered by scope (global, brand, topic, economic, commodity)."""
    df = load_metric_trends(scope=scope, scope_name=scope_name, metric_name=metric_name, days=days)
    return {"data": _df_to_records(df), "count": len(df)}


# ---------------------------------------------------------------------------
# Brand & topic watchlists
# ---------------------------------------------------------------------------

@app.get("/api/brands/{username}")
def get_brands(username: str):
    """Return brand watchlist for a user."""
    engine = _require_engine()
    try:
        df = pd.read_sql(
            sql_text("SELECT brand_name, created_at FROM brand_watchlist WHERE username = :user"),
            engine,
            params={"user": username},
        )
        return {"brands": df["brand_name"].tolist(), "count": len(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/topics/{username}")
def get_topics(username: str):
    """Return topic watchlist for a user."""
    engine = _require_engine()
    try:
        df = pd.read_sql(
            sql_text(
                "SELECT topic_name, is_category, created_at "
                "FROM topic_watchlist WHERE username = :user"
            ),
            engine,
            params={"user": username},
        )
        return {"topics": _df_to_records(df), "count": len(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# VLDS
# ---------------------------------------------------------------------------

@app.get("/api/vlds/brand/{brand}")
def get_brand_vlds(brand: str, days: int = Query(default=7, ge=1, le=30)):
    """Compute VLDS v2 scores for a brand."""
    engine = _require_engine()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    brand_lower = brand.lower()

    frames = []
    for table in ("news_scored", "social_scored"):
        try:
            df = pd.read_sql(
                sql_text(
                    f"SELECT * FROM {table} "
                    f"WHERE created_at >= :cutoff AND LOWER(text) LIKE :pattern"
                ),
                engine,
                params={"cutoff": cutoff, "pattern": f"%{brand_lower}%"},
            )
            if not df.empty:
                frames.append(df)
        except Exception:
            pass

    if not frames:
        return {"brand": brand, "vlds": None, "reason": "no data"}

    combined = pd.concat(frames, ignore_index=True)
    if "created_at" in combined.columns:
        combined["created_at"] = pd.to_datetime(
            combined["created_at"], utc=True, errors="coerce"
        )
        combined = combined.dropna(subset=["created_at"])

    vlds = calculate_brand_vlds(combined)
    return {"brand": brand, "vlds": vlds}


@app.get("/api/vlds/topics")
def get_topic_vlds():
    """Return topic-level VLDS scores (longevity, density, scarcity tables)."""
    engine = _require_engine()
    result = {}
    for table in ("topic_longevity", "topic_density", "topic_scarcity"):
        try:
            df = pd.read_sql(f"SELECT * FROM {table}", engine)
            result[table] = _df_to_records(df)
        except Exception:
            result[table] = []
    return result


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@app.get("/api/alerts/{username}")
def get_alerts(
    username: str,
    days: int = Query(default=7, ge=1, le=90),
    severity: Optional[str] = None,
):
    """Return alerts with read status for a user."""
    engine = _require_engine()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    query = """
        SELECT a.*,
               CASE WHEN rs.id IS NOT NULL THEN TRUE ELSE FALSE END AS is_read
        FROM alerts a
        LEFT JOIN alert_read_status rs ON rs.alert_id = a.id AND rs.username = :user
        WHERE a.timestamp > :cutoff
          AND (a.username IS NULL OR a.username = :user)
    """
    params = {"cutoff": cutoff, "user": username}

    if severity and severity != "all":
        query += " AND a.severity = :severity"
        params["severity"] = severity

    query += " ORDER BY a.timestamp DESC LIMIT 200"

    try:
        df = pd.read_sql(sql_text(query), engine, params=params)
        return {"data": _df_to_records(df), "count": len(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Economic / commodity / stock data
# ---------------------------------------------------------------------------

@app.get("/api/economic")
def get_economic(days: int = Query(default=730, ge=1, le=730)):
    """Return economic indicator data."""
    df = load_economic_data(days=days)
    return {"data": _df_to_records(df), "count": len(df)}


@app.get("/api/commodities")
def get_commodities(days: int = Query(default=7, ge=1, le=90)):
    """Return commodity price data."""
    df = load_commodity_data(days=days)
    return {"data": _df_to_records(df), "count": len(df)}


@app.get("/api/brand-stocks/{ticker}")
def get_brand_stocks(ticker: str, days: int = Query(default=2, ge=1, le=7)):
    """Return intraday brand stock data."""
    df = load_brand_stock_data(ticker=ticker, days=days)
    return {"data": _df_to_records(df), "count": len(df)}


# ---------------------------------------------------------------------------
# Competitive
# ---------------------------------------------------------------------------

@app.get("/api/competitive/{brand}")
def get_competitive(brand: str):
    """Return latest competitive snapshot for a brand."""
    engine = _require_engine()
    brand_lower = brand.lower()
    try:
        df = pd.read_sql(
            sql_text(
                "SELECT * FROM competitive_snapshots "
                "WHERE LOWER(brand_name) = :subject "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            engine,
            params={"subject": brand_lower},
        )
        if df.empty:
            return {"brand": brand, "snapshot": None}

        row = df.iloc[0]
        snapshot_raw = row.get("snapshot_data", "{}")
        if isinstance(snapshot_raw, str):
            try:
                snapshot = json.loads(snapshot_raw)
            except (json.JSONDecodeError, TypeError):
                snapshot = {}
        else:
            snapshot = snapshot_raw

        return {
            "brand": brand,
            "snapshot": snapshot,
            "created_at": str(row.get("created_at", "")),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Pipeline health (for admin/monitoring)
# ---------------------------------------------------------------------------

@app.get("/api/pipeline-health")
def get_pipeline_health():
    """Return recent pipeline run status — mirrors webhook_server.py health check."""
    engine = _require_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(sql_text("""
                SELECT DISTINCT ON (pipeline_name)
                    pipeline_name, status, row_count, started_at, completed_at,
                    LEFT(error_message, 100) AS error_preview
                FROM pipeline_runs
                ORDER BY pipeline_name, started_at DESC
            """)).fetchall()

        pipelines = {}
        for row in rows:
            name, status, row_count, started_at, completed_at = row[:5]
            error_preview = row[5] if len(row) > 5 else None
            age_hours = None
            if completed_at:
                age_hours = round(
                    (datetime.now(timezone.utc) - completed_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600,
                    1,
                )
            pipelines[name] = {
                "status": status,
                "row_count": row_count,
                "last_run": started_at.isoformat() if started_at else None,
                "age_hours": age_hours,
                "error_preview": error_preview,
            }
        return {"pipelines": pipelines}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Authentication (Phase 0D)
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    email: str
    tier: str
    is_admin: bool
    expires_in: int


class SessionResponse(BaseModel):
    username: str
    email: str
    tier: str
    brief_credits: int = 0
    extra_seats: int = 0
    is_admin: bool


@app.post("/api/auth/login", response_model=LoginResponse)
def auth_login(req: LoginRequest):
    """Validate credentials and return a JWT."""
    if not req.email and not req.username:
        raise HTTPException(status_code=400, detail="email or username required")

    engine = _require_engine()
    user = lookup_user(engine, email=req.email, username=req.username)

    if not user:
        # Timing-attack mitigation: still run bcrypt on dummy hash
        verify_password(req.password, _DUMMY_HASH)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    sid = create_session(engine, user["username"])
    token = create_access_token(user["username"], user["email"], session_id=sid)
    log_user_event(user["username"], "login", f"via API ({req.email or req.username})")

    return LoginResponse(
        access_token=token,
        username=user["username"],
        email=user["email"],
        tier=user["tier"],
        is_admin=is_admin_email(user["email"]),
        expires_in=24 * 3600,
    )


@app.get("/api/auth/session", response_model=SessionResponse)
def auth_session(payload: dict = Depends(require_auth)):
    """Validate JWT and return current user info (tier from DB live)."""
    engine = _require_engine()
    user = lookup_user(engine, username=payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")

    # Check session is still active (not superseded by another login)
    if not validate_session(engine, payload["sub"], payload.get("sid", "")):
        raise HTTPException(status_code=401, detail="Session expired — logged in from another location")

    return SessionResponse(
        username=user["username"],
        email=user["email"],
        tier=user["tier"],
        brief_credits=user.get("brief_credits", 0),
        extra_seats=user.get("extra_seats", 0),
        is_admin=is_admin_email(user["email"]),
    )


@app.post("/api/auth/logout")
def auth_logout(payload: dict = Depends(require_auth)):
    """Clear session and log the event."""
    engine = _require_engine()
    clear_session(engine, payload["sub"])
    log_user_event(payload["sub"], "logout", "via API")
    return {"status": "ok"}


def _require_active_tier(payload: dict, feature: str):
    """Single DB query: check user exists + tier allows feature.
    Raises 401 if user deleted, 403 if tier lacks access."""
    engine = _require_engine()
    user = lookup_user(engine, username=payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    allowed_tiers = TIER_FEATURES.get(feature, ACTIVE_TIERS)
    if user["tier"] not in allowed_tiers:
        raise HTTPException(
            status_code=403,
            detail=f"Your account ({user['tier']}) does not have access to {feature}",
        )


# ---------------------------------------------------------------------------
# Claude-powered endpoints (Phase 0C)
# ---------------------------------------------------------------------------

class ReportRequest(BaseModel):
    subject: str
    subject_type: str = "brand"
    days: int = 7
    email_recipient: Optional[str] = None


@app.post("/api/report")
def generate_report(req: ReportRequest, payload: dict = Depends(require_auth)):
    """Generate an on-demand intelligence report for a brand or topic."""
    _require_active_tier(payload, "intelligence_reports")
    engine = _require_engine()

    from generate_report import generate_intelligence_report, email_report

    report_text = generate_intelligence_report(
        engine, req.subject, days=min(req.days, 30), subject_type=req.subject_type
    )
    if report_text.startswith("Error"):
        raise HTTPException(status_code=500, detail=report_text)

    email_sent = False
    if req.email_recipient:
        email_sent = email_report(
            report_text, req.subject, req.email_recipient, days=req.days
        )

    return {"report": report_text, "email_sent": email_sent}


class StrategicBriefRequest(BaseModel):
    user_need: str
    username: str = "admin"
    email_recipient: Optional[str] = None


class AgentRequest(BaseModel):
    user_input: str
    username: str = "admin"
    email_recipient: Optional[str] = None


@app.post("/api/agents/creative-director")
def agent_creative_director(req: AgentRequest, payload: dict = Depends(require_auth)):
    """Creative Director Agent — generates a creative brief with cultural intelligence."""
    _require_active_tier(payload, "strategic_brief")
    from agents import CreativeDirectorAgent
    agent = CreativeDirectorAgent()
    result = agent.run({"user_input": req.user_input, "username": payload["sub"]})

    if req.email_recipient:
        from generate_strategic_brief import send_strategic_brief_email
        send_strategic_brief_email(req.email_recipient, req.user_input, result["output"])

    return result


@app.post("/api/agents/strategy")
def agent_strategy(req: AgentRequest, payload: dict = Depends(require_auth)):
    """Strategy Agent — generates a strategic recommendation with positioning and timing."""
    _require_active_tier(payload, "strategic_brief")
    from agents import StrategyAgent
    agent = StrategyAgent()
    result = agent.run({"user_input": req.user_input, "username": payload["sub"]})

    if req.email_recipient:
        from generate_strategic_brief import send_strategic_brief_email
        send_strategic_brief_email(req.email_recipient, req.user_input, result["output"])

    return result


@app.post("/api/agents/comms-planner")
def agent_comms_planner(req: AgentRequest, payload: dict = Depends(require_auth)):
    """Comms Planner Agent — generates a channel/timing plan based on real-time signals."""
    _require_active_tier(payload, "strategic_brief")
    from agents import CommsPlannerAgent
    agent = CommsPlannerAgent()
    result = agent.run({"user_input": req.user_input, "username": payload["sub"]})

    if req.email_recipient:
        from generate_strategic_brief import send_strategic_brief_email
        send_strategic_brief_email(req.email_recipient, req.user_input, result["output"])

    return result


@app.post("/api/agents/full-deploy")
def agent_full_deploy(req: AgentRequest, payload: dict = Depends(require_auth)):
    """Full Deploy — all three agents as one cohesive team."""
    _require_active_tier(payload, "strategic_brief")
    from agents import FullDeployAgent
    agent = FullDeployAgent()
    result = agent.run({"user_input": req.user_input, "username": payload["sub"]})

    if req.email_recipient:
        from generate_strategic_brief import send_strategic_brief_email
        send_strategic_brief_email(req.email_recipient, req.user_input, result["output"])

    return result


# ---------------------------------------------------------------------------
# Public Agent Marketplace (Squarespace — open access, email capture)
# ---------------------------------------------------------------------------

class MarketplaceRequest(BaseModel):
    agent: str  # "cco", "cso", "comms-planner", "full-deploy"
    email: str
    product: str
    audience: str = ""
    markets: str = ""
    challenge: str = ""
    timeline: str = ""

_MARKETPLACE_AGENTS = {
    "cco": ("agents", "CreativeDirectorAgent"),
    "cso": ("agents", "StrategyAgent"),
    "comms-planner": ("agents", "CommsPlannerAgent"),
    "full-deploy": ("agents", "FullDeployAgent"),
    "brand-auditor": ("agents", "BrandAuditorAgent"),
    "brief-critic": ("agents", "BriefCriticAgent"),
    "trend-forecaster": ("agents", "TrendForecasterAgent"),
    "copywriter": ("agents", "CopywriterAgent"),
}

_AGENT_LABELS = {
    "cco": "Chief Creative Officer",
    "cso": "The Cultural Strategist",
    "comms-planner": "Comms Planner",
    "full-deploy": "Full Deploy",
    "brand-auditor": "The Brand Auditor",
    "brief-critic": "The Brief Critic",
    "trend-forecaster": "The Trend Forecaster",
    "copywriter": "The Copywriter",
}


_marketplace_rate: dict = {}  # {email: [timestamp, ...]}

def _check_marketplace_rate(email: str) -> bool:
    """Allow max 3 marketplace runs per email per hour."""
    import time
    now = time.time()
    key = email.lower().strip()
    times = _marketplace_rate.get(key, [])
    times = [t for t in times if now - t < 3600]
    if len(times) >= 3:
        return False
    times.append(now)
    _marketplace_rate[key] = times
    return True


def _capture_marketplace_email(email: str, engine):
    """Capture email for marketplace lead. Upserts into marketplace_access."""
    try:
        with engine.connect() as conn:
            conn.execute(
                sql_text("""
                    INSERT INTO marketplace_access (email, active, created_at)
                    VALUES (:email, true, NOW())
                    ON CONFLICT (email) DO NOTHING
                """),
                {"email": email.lower().strip()},
            )
            conn.commit()
    except Exception:
        pass


def _log_marketplace_run(email: str, agent: str, user_input: str, engine):
    """Log a marketplace agent run for analytics."""
    try:
        with engine.connect() as conn:
            conn.execute(
                sql_text("""
                    INSERT INTO marketplace_runs (email, agent, user_input, created_at)
                    VALUES (:email, :agent, :input, NOW())
                """),
                {"email": email.lower().strip(), "agent": agent, "input": user_input[:500]},
            )
            conn.commit()
    except Exception:
        pass


def _build_marketplace_input(req: MarketplaceRequest) -> str:
    """Assemble form fields into a single user_input string."""
    parts = [f"launch/promote {req.product}"]
    if req.audience:
        parts.append(f"targeting {req.audience}")
    if req.markets:
        parts.append(f"in {req.markets}")
    if req.challenge:
        parts.append(f"with the challenge of {req.challenge}")
    if req.timeline:
        parts.append(f"timeline/budget: {req.timeline}")
    return " ".join(parts)


def _email_marketplace_result(email: str, user_input: str, output: str, label: str, agent_id: str = None):
    """Background task: email the full agent result."""
    from generate_strategic_brief import send_strategic_brief_email
    send_strategic_brief_email(email.strip(), user_input, output, frameworks=[label], agent_id=agent_id)


@app.post("/api/marketplace/run")
def marketplace_run(req: MarketplaceRequest, background_tasks: BackgroundTasks):
    """Public endpoint for the Moodlight Agent Marketplace on Squarespace.
    Runs agent synchronously, returns preview, emails full brief."""
    import importlib

    if req.agent not in _MARKETPLACE_AGENTS:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {req.agent}")

    if not req.product.strip():
        raise HTTPException(status_code=400, detail="Product / service is required")

    if not req.email.strip() or "@" not in req.email:
        raise HTTPException(status_code=400, detail="Valid email is required")

    engine = get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    # Rate limit — 3 per email per hour
    if not _check_marketplace_rate(req.email):
        raise HTTPException(status_code=429, detail="You've reached the limit. Please try again in an hour.")

    # Capture email (open access — no whitelist)
    _capture_marketplace_email(req.email, engine)

    # Run agent synchronously so we can return a preview
    try:
        module_name, class_name = _MARKETPLACE_AGENTS[req.agent]
        mod = importlib.import_module(module_name)
        agent_cls = getattr(mod, class_name)
        agent = agent_cls()

        user_input = _build_marketplace_input(req)
        result = agent.run({"user_input": user_input})
        output = result["output"]
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Our agents are temporarily unavailable. Please try again in a few minutes.")

    # Log the run
    _log_marketplace_run(req.email, req.agent, user_input, engine)

    # Email full brief in background (don't block response)
    label = _AGENT_LABELS.get(req.agent, req.agent)
    background_tasks.add_task(_email_marketplace_result, req.email, user_input, output, label, req.agent)

    # Return preview — first ~600 chars, cut at last newline for clean break
    preview = output[:600]
    last_newline = preview.rfind("\n")
    if last_newline > 200:
        preview = preview[:last_newline]

    return {
        "status": "done",
        "preview": preview,
        "message": f"Full brief sent to {req.email}",
    }


@app.post("/api/strategic-brief")
def strategic_brief(req: StrategicBriefRequest, payload: dict = Depends(require_auth)):
    """Generate a strategic campaign brief powered by Claude."""
    _require_active_tier(payload, "strategic_brief")
    req.username = payload["sub"]  # JWT username overrides request body
    engine = _require_engine()

    from generate_strategic_brief import generate_strategic_brief, send_strategic_brief_email

    # Load combined data (same as /api/data/combined)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    frames = []
    for table in ("news_scored", "social_scored"):
        try:
            df = pd.read_sql(
                sql_text(f"SELECT * FROM {table} WHERE created_at >= :cutoff"),
                engine,
                params={"cutoff": cutoff},
            )
            if not df.empty:
                frames.append(df)
        except Exception:
            pass

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if "created_at" in combined.columns:
        combined["created_at"] = pd.to_datetime(
            combined["created_at"], utc=True, errors="coerce"
        )

    brief_text, framework_names = generate_strategic_brief(
        req.user_need, combined, username=req.username
    )

    email_sent = False
    if req.email_recipient:
        email_sent = send_strategic_brief_email(
            req.email_recipient, req.user_need, brief_text, frameworks=framework_names
        )

    return {"brief": brief_text, "frameworks": framework_names, "email_sent": email_sent}


@app.get("/api/prediction-markets")
def prediction_markets(payload: dict = Depends(require_auth)):
    """Fetch live prediction market data with social sentiment divergence."""
    _require_active_tier(payload, "prediction_markets")
    engine = _require_engine()

    from polymarket_helper import fetch_polymarket_markets, calculate_sentiment_divergence

    markets = fetch_polymarket_markets(limit=25, min_volume=1000)
    if not markets:
        return {"markets": [], "divergence": None}

    # Compute average social sentiment from last 7 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    avg_social = 50.0  # default
    try:
        with engine.connect() as conn:
            row = conn.execute(
                sql_text(
                    "SELECT AVG(empathy_score) FROM ("
                    "  SELECT empathy_score FROM news_scored WHERE created_at >= :cutoff"
                    "  UNION ALL"
                    "  SELECT empathy_score FROM social_scored WHERE created_at >= :cutoff"
                    ") sub"
                ),
                {"cutoff": cutoff},
            ).fetchone()
            if row and row[0] is not None:
                raw = float(row[0])
                # Piecewise normalization (matches app.py)
                if raw <= 0.04:
                    avg_social = round(raw / 0.04 * 50)
                elif raw <= 0.10:
                    avg_social = round(50 + (raw - 0.04) / 0.06 * 15)
                elif raw <= 0.30:
                    avg_social = round(65 + (raw - 0.10) / 0.20 * 20)
                else:
                    avg_social = round(85 + (raw - 0.30) / 0.70 * 15)
                avg_social = min(100.0, max(0.0, avg_social))
    except Exception:
        pass

    top10 = markets[:10]
    avg_market = sum(max(m["yes_odds"], m["no_odds"]) for m in top10) / len(top10)
    divergence = calculate_sentiment_divergence(avg_market, avg_social)

    return {
        "markets": top10,
        "avg_market_confidence": round(avg_market, 1),
        "avg_social_mood": avg_social,
        "divergence": divergence,
    }


class ReportPdfRequest(BaseModel):
    report_text: str
    subject: str
    days: int = 7


@app.post("/api/report/pdf")
def report_pdf(req: ReportPdfRequest, payload: dict = Depends(require_auth)):
    """Generate a branded PDF from an intelligence report."""
    from fastapi.responses import Response
    from pdf_export import generate_report_pdf

    pdf_bytes = generate_report_pdf(req.report_text, req.subject, days=req.days)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="moodlight_report.pdf"'},
    )


class BriefPdfRequest(BaseModel):
    brief_text: str
    product: str


@app.post("/api/brief/pdf")
def brief_pdf(req: BriefPdfRequest, payload: dict = Depends(require_auth)):
    """Generate a branded PDF from a strategic brief."""
    from fastapi.responses import Response
    from pdf_export import generate_brief_pdf

    pdf_bytes = generate_brief_pdf(req.brief_text, req.product)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="moodlight_strategic_brief.pdf"'},
    )


class ChartExplainRequest(BaseModel):
    chart_type: str
    data_summary: str


@app.post("/api/chart/explain")
def chart_explain(req: ChartExplainRequest, payload: dict = Depends(require_auth)):
    """Generate an AI explanation for a dashboard chart."""
    _require_active_tier(payload, "intelligence_dashboard")
    engine = _require_engine()

    from chart_explainer import generate_chart_explanation

    # Load combined data for headline retrieval
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    frames = []
    for table in ("news_scored", "social_scored"):
        try:
            df = pd.read_sql(
                sql_text(f"SELECT * FROM {table} WHERE created_at >= :cutoff"),
                engine,
                params={"cutoff": cutoff},
            )
            if not df.empty:
                frames.append(df)
        except Exception:
            pass

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if "created_at" in combined.columns:
        combined["created_at"] = pd.to_datetime(
            combined["created_at"], utc=True, errors="coerce"
        )

    explanation = generate_chart_explanation(req.chart_type, req.data_summary, combined)
    return {"explanation": explanation}


class AskRequest(BaseModel):
    message: str
    username: str = "admin"
    conversation_history: list[dict] = []
    last_search_info: Optional[dict] = None


@app.post("/api/ask")
def ask(req: AskRequest, payload: dict = Depends(require_auth)):
    """Ask Moodlight chat endpoint for authenticated dashboard users."""
    _require_active_tier(payload, "ask_moodlight")
    req.username = payload["sub"]  # JWT username overrides request body
    engine = _require_engine()

    from ask_engine import ask_moodlight

    result = ask_moodlight(
        message=req.message,
        username=req.username,
        conversation_history=req.conversation_history,
        last_search_info=req.last_search_info,
        engine=engine,
    )
    return result


# ---------------------------------------------------------------------------
# Admin helpers
# ---------------------------------------------------------------------------

def _require_admin(payload: dict):
    """Check JWT payload belongs to an admin. Raises 403 if not."""
    if not is_admin_email(payload.get("email", "")):
        raise HTTPException(status_code=403, detail="Admin access required")


# ---------------------------------------------------------------------------
# Admin — Customer CRUD (Phase 0E, Step 1)
# ---------------------------------------------------------------------------

class CreateCustomerRequest(BaseModel):
    email: str
    name: str = ""
    tier: str = "monthly"
    initial_credits: int = 0


class CreateCustomerResponse(BaseModel):
    username: str
    email: str
    tier: str
    temp_password: str


class UpdateCustomerRequest(BaseModel):
    tier: Optional[str] = None
    extra_seats: Optional[int] = None


class AddCreditsRequest(BaseModel):
    credits: int


@app.get("/api/admin/customers")
def admin_list_customers(payload: dict = Depends(require_auth)):
    """List all customers."""
    _require_admin(payload)
    engine = _require_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(sql_text(
                "SELECT email, username, tier, brief_credits, "
                "stripe_customer_id, stripe_subscription_id, extra_seats, created_at "
                "FROM users ORDER BY created_at DESC"
            )).fetchall()
        customers = []
        for r in rows:
            customers.append({
                "email": r[0],
                "username": r[1],
                "tier": r[2],
                "brief_credits": r[3],
                "stripe_customer_id": r[4],
                "stripe_subscription_id": r[5],
                "extra_seats": r[6],
                "created_at": r[7].isoformat() if r[7] else None,
            })
        return {"customers": customers, "count": len(customers)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/customers", response_model=CreateCustomerResponse)
def admin_create_customer(req: CreateCustomerRequest, payload: dict = Depends(require_auth)):
    """Create a new customer. Returns a temporary password."""
    _require_admin(payload)
    engine = _require_engine()

    clean_email = req.email.strip().lower()
    clean_name = req.name.strip() if req.name.strip() else clean_email.split("@")[0]
    new_username = clean_name.lower().replace(" ", "_")

    try:
        with engine.connect() as conn:
            # Check duplicate email
            existing = conn.execute(
                sql_text("SELECT 1 FROM users WHERE email = :email"),
                {"email": clean_email},
            ).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail="User already exists")

            # Ensure username uniqueness
            existing_usernames = {
                r[0] for r in conn.execute(sql_text("SELECT username FROM users")).fetchall()
            }
            if new_username in existing_usernames:
                suffix = 1
                while f"{new_username}_{suffix}" in existing_usernames:
                    suffix += 1
                new_username = f"{new_username}_{suffix}"

            temp_password = secrets.token_urlsafe(12)
            password_hash = bcrypt.hashpw(temp_password.encode(), bcrypt.gensalt()).decode()

            conn.execute(sql_text(
                "INSERT INTO users (username, email, password_hash, tier, brief_credits) "
                "VALUES (:username, :email, :password_hash, :tier, :credits)"
            ), {
                "username": new_username,
                "email": clean_email,
                "password_hash": password_hash,
                "tier": req.tier,
                "credits": req.initial_credits,
            })
            conn.commit()

        return CreateCustomerResponse(
            username=new_username,
            email=clean_email,
            tier=req.tier,
            temp_password=temp_password,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/admin/customers/{username}")
def admin_update_customer(username: str, req: UpdateCustomerRequest, payload: dict = Depends(require_auth)):
    """Update a customer's tier and/or extra_seats."""
    _require_admin(payload)
    engine = _require_engine()

    if req.tier is None and req.extra_seats is None:
        raise HTTPException(status_code=400, detail="Nothing to update")

    try:
        with engine.connect() as conn:
            existing = conn.execute(
                sql_text("SELECT 1 FROM users WHERE username = :u"),
                {"u": username},
            ).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="User not found")

            if req.tier is not None:
                conn.execute(sql_text(
                    "UPDATE users SET tier = :tier, updated_at = CURRENT_TIMESTAMP "
                    "WHERE username = :u"
                ), {"tier": req.tier, "u": username})

            if req.extra_seats is not None:
                conn.execute(sql_text(
                    "UPDATE users SET extra_seats = :seats, updated_at = CURRENT_TIMESTAMP "
                    "WHERE username = :u"
                ), {"seats": req.extra_seats, "u": username})

            conn.commit()
        return {"status": "ok", "username": username}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/customers/{username}")
def admin_delete_customer(username: str, payload: dict = Depends(require_auth)):
    """Delete a customer. Cannot delete your own account."""
    _require_admin(payload)
    engine = _require_engine()

    if username == payload["sub"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    try:
        with engine.connect() as conn:
            existing = conn.execute(
                sql_text("SELECT 1 FROM users WHERE username = :u"),
                {"u": username},
            ).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="User not found")

            conn.execute(
                sql_text("DELETE FROM users WHERE username = :u"),
                {"u": username},
            )
            conn.commit()
        return {"status": "ok", "username": username}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/customers/{username}/credits")
def admin_add_credits(username: str, req: AddCreditsRequest, payload: dict = Depends(require_auth)):
    """Add credits to a customer."""
    _require_admin(payload)
    engine = _require_engine()

    try:
        with engine.connect() as conn:
            existing = conn.execute(
                sql_text("SELECT 1 FROM users WHERE username = :u"),
                {"u": username},
            ).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="User not found")

            conn.execute(sql_text(
                "UPDATE users SET brief_credits = brief_credits + :credits, "
                "updated_at = CURRENT_TIMESTAMP WHERE username = :u"
            ), {"credits": req.credits, "u": username})
            conn.commit()
        return {"status": "ok", "username": username, "credits_added": req.credits}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Admin — Analytics (Phase 0E, Step 2)
# ---------------------------------------------------------------------------

@app.get("/api/admin/analytics")
def admin_analytics(payload: dict = Depends(require_auth)):
    """Active users, feature usage, last activity, and feature adoption."""
    _require_admin(payload)
    engine = _require_engine()

    try:
        with engine.connect() as conn:
            # Active users (7d and 30d)
            active_7d = conn.execute(sql_text(
                "SELECT COUNT(DISTINCT username) FROM user_events "
                "WHERE created_at >= NOW() - INTERVAL '7 days'"
            )).scalar() or 0

            active_30d = conn.execute(sql_text(
                "SELECT COUNT(DISTINCT username) FROM user_events "
                "WHERE created_at >= NOW() - INTERVAL '30 days'"
            )).scalar() or 0

            # Feature usage (last 30 days)
            usage_rows = conn.execute(sql_text(
                "SELECT event_type, COUNT(*) AS total, COUNT(DISTINCT username) AS unique_users "
                "FROM user_events WHERE created_at >= NOW() - INTERVAL '30 days' "
                "GROUP BY event_type ORDER BY total DESC"
            )).fetchall()
            feature_usage = [
                {"event_type": r[0], "total": r[1], "unique_users": r[2]}
                for r in usage_rows
            ]

            # Last activity per user
            activity_rows = conn.execute(sql_text(
                "SELECT username, MAX(created_at) AS last_active, COUNT(*) AS total_events "
                "FROM user_events GROUP BY username ORDER BY last_active DESC"
            )).fetchall()
            now = datetime.now(timezone.utc)
            user_activity = []
            for r in activity_rows:
                last_active = r[1]
                if last_active and last_active.tzinfo is None:
                    last_active = last_active.replace(tzinfo=timezone.utc)
                days_ago = (now - last_active).days if last_active else None
                user_activity.append({
                    "username": r[0],
                    "last_active": last_active.isoformat() if last_active else None,
                    "total_events": r[2],
                    "status": "At Risk" if days_ago is not None and days_ago >= 14 else "Active",
                })

            # Feature adoption counts
            brand_watchlist_users = conn.execute(sql_text(
                "SELECT COUNT(DISTINCT username) FROM brand_watchlist"
            )).scalar() or 0
            topic_watchlist_users = conn.execute(sql_text(
                "SELECT COUNT(DISTINCT username) FROM topic_watchlist"
            )).scalar() or 0
            feedback_users = conn.execute(sql_text(
                "SELECT COUNT(DISTINCT username) FROM alert_feedback"
            )).scalar() or 0

        return {
            "active_users_7d": active_7d,
            "active_users_30d": active_30d,
            "feature_usage": feature_usage,
            "user_activity": user_activity,
            "adoption": {
                "brand_watchlist_users": brand_watchlist_users,
                "topic_watchlist_users": topic_watchlist_users,
                "alert_feedback_users": feedback_users,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/ask-queries")
def admin_ask_queries(payload: dict = Depends(require_auth)):
    """Widget analytics: query list, counts, unique visitors, top brands."""
    _require_admin(payload)
    engine = _require_engine()

    try:
        with engine.connect() as conn:
            rows = conn.execute(sql_text(
                "SELECT id, question, detected_brand, detected_topic, "
                "is_paid, ip_hash, created_at "
                "FROM ask_queries ORDER BY created_at DESC LIMIT 200"
            )).fetchall()

        queries = []
        paid_count = 0
        ip_hashes = set()
        brands = []
        for r in rows:
            queries.append({
                "id": r[0],
                "question": r[1],
                "detected_brand": r[2],
                "detected_topic": r[3],
                "is_paid": r[4],
                "ip_hash": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
            })
            if r[4]:
                paid_count += 1
            if r[5]:
                ip_hashes.add(r[5])
            if r[2]:
                brands.append(r[2])

        # Top 10 brands by frequency
        brand_counts: dict[str, int] = {}
        for b in brands:
            brand_counts[b] = brand_counts.get(b, 0) + 1
        top_brands = sorted(brand_counts, key=brand_counts.get, reverse=True)[:10]

        return {
            "queries": queries,
            "total": len(queries),
            "paid": paid_count,
            "free": len(queries) - paid_count,
            "unique_visitors": len(ip_hashes),
            "top_brands": top_brands,
        }
    except Exception as e:
        # Graceful fallback if ask_queries table doesn't exist
        if "does not exist" in str(e).lower() or "relation" in str(e).lower():
            return {
                "queries": [],
                "total": 0,
                "paid": 0,
                "free": 0,
                "unique_visitors": 0,
                "top_brands": [],
            }
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Admin — Teams (Phase 0E, Step 3)
# ---------------------------------------------------------------------------

class CreateTeamRequest(BaseModel):
    team_name: str
    owner_username: str


@app.get("/api/admin/teams")
def admin_list_teams(payload: dict = Depends(require_auth)):
    """List all teams with member counts."""
    _require_admin(payload)
    engine = _require_engine()

    try:
        with engine.connect() as conn:
            rows = conn.execute(sql_text(
                "SELECT t.id, t.team_name, t.owner_username, "
                "COUNT(tm.id) AS member_count, t.created_at "
                "FROM teams t "
                "LEFT JOIN team_members tm ON t.id = tm.team_id "
                "GROUP BY t.id, t.team_name, t.owner_username, t.created_at "
                "ORDER BY t.created_at DESC"
            )).fetchall()

        teams = [
            {
                "id": r[0],
                "team_name": r[1],
                "owner_username": r[2],
                "member_count": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]
        return {"teams": teams, "count": len(teams)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/teams")
def admin_create_team(req: CreateTeamRequest, payload: dict = Depends(require_auth)):
    """Create a team. Validates owner exists and doesn't already own a team."""
    _require_admin(payload)
    engine = _require_engine()

    try:
        with engine.connect() as conn:
            # Validate owner exists
            owner = conn.execute(
                sql_text("SELECT 1 FROM users WHERE username = :u"),
                {"u": req.owner_username},
            ).fetchone()
            if not owner:
                raise HTTPException(status_code=404, detail="Owner not found")

            # Check owner doesn't already own a team
            existing = conn.execute(
                sql_text("SELECT 1 FROM teams WHERE owner_username = :u"),
                {"u": req.owner_username},
            ).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail="Owner already has a team")

            # Create team
            result = conn.execute(sql_text(
                "INSERT INTO teams (team_name, owner_username) "
                "VALUES (:name, :owner) RETURNING id"
            ), {"name": req.team_name, "owner": req.owner_username})
            team_id = result.scalar()

            # Add owner as member
            conn.execute(sql_text(
                "INSERT INTO team_members (team_id, username, role) "
                "VALUES (:team_id, :username, 'owner')"
            ), {"team_id": team_id, "username": req.owner_username})

            conn.commit()

        return {"status": "ok", "team_id": team_id, "team_name": req.team_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Watchlist CRUD (Phase 2, Step 0A)
# ---------------------------------------------------------------------------

class AddBrandRequest(BaseModel):
    brand_name: str


class AddTopicRequest(BaseModel):
    topic_name: str
    is_category: bool = False


@app.post("/api/watchlist/brands")
def add_brand_to_watchlist(req: AddBrandRequest, payload: dict = Depends(require_auth)):
    """Add a brand to the user's watchlist. Triggers competitor discovery."""
    username = payload["sub"]
    engine = _require_engine()
    brand = req.brand_name.strip()

    if not brand or len(brand) > 100:
        raise HTTPException(status_code=400, detail="Brand name must be 1-100 characters")

    try:
        with engine.connect() as conn:
            # Check current count against tier limit
            count = conn.execute(
                sql_text("SELECT COUNT(*) FROM brand_watchlist WHERE username = :u"),
                {"u": username},
            ).scalar() or 0

            max_brands = TIER_LIMITS.get("brand_watchlist_max", {})
            user_row = conn.execute(
                sql_text("SELECT tier FROM users WHERE username = :u"),
                {"u": username},
            ).fetchone()
            user_tier = user_row[0] if user_row else "free"
            limit = max_brands.get(user_tier, 5)

            if count >= limit:
                raise HTTPException(status_code=400, detail=f"Maximum {limit} brands reached")

            # Check duplicate
            existing = conn.execute(
                sql_text("SELECT 1 FROM brand_watchlist WHERE username = :u AND brand_name = :b"),
                {"u": username, "b": brand},
            ).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail="Brand already in watchlist")

            conn.execute(
                sql_text("INSERT INTO brand_watchlist (username, brand_name) VALUES (:u, :b)"),
                {"u": username, "b": brand},
            )
            conn.commit()

        log_user_event(username, "add_brand", brand)

        # Trigger competitor discovery (non-fatal)
        try:
            ensure_competitor_tables(engine)
            ensure_competitors_cached(engine, brand)
        except Exception:
            pass

        return {"status": "ok", "brand_name": brand}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/watchlist/brands/{brand_name}")
def remove_brand_from_watchlist(brand_name: str, payload: dict = Depends(require_auth)):
    """Remove a brand from the user's watchlist."""
    username = payload["sub"]
    engine = _require_engine()

    try:
        with engine.connect() as conn:
            result = conn.execute(
                sql_text("DELETE FROM brand_watchlist WHERE username = :u AND brand_name = :b"),
                {"u": username, "b": brand_name},
            )
            conn.commit()
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Brand not found in watchlist")

        log_user_event(username, "remove_brand", brand_name)
        return {"status": "ok", "brand_name": brand_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/watchlist/topics")
def add_topic_to_watchlist(req: AddTopicRequest, payload: dict = Depends(require_auth)):
    """Add a topic to the user's watchlist."""
    username = payload["sub"]
    engine = _require_engine()
    topic = req.topic_name.strip()

    if not topic or len(topic) > 100:
        raise HTTPException(status_code=400, detail="Topic name must be 1-100 characters")

    try:
        with engine.connect() as conn:
            # Check current count against tier limit
            count = conn.execute(
                sql_text("SELECT COUNT(*) FROM topic_watchlist WHERE username = :u"),
                {"u": username},
            ).scalar() or 0

            max_topics = TIER_LIMITS.get("topic_watchlist_max", {})
            user_row = conn.execute(
                sql_text("SELECT tier FROM users WHERE username = :u"),
                {"u": username},
            ).fetchone()
            user_tier = user_row[0] if user_row else "free"
            limit = max_topics.get(user_tier, 10)

            if count >= limit:
                raise HTTPException(status_code=400, detail=f"Maximum {limit} topics reached")

            # Check duplicate
            existing = conn.execute(
                sql_text("SELECT 1 FROM topic_watchlist WHERE username = :u AND topic_name = :t"),
                {"u": username, "t": topic},
            ).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail="Topic already in watchlist")

            conn.execute(
                sql_text(
                    "INSERT INTO topic_watchlist (username, topic_name, is_category) "
                    "VALUES (:u, :t, :is_cat)"
                ),
                {"u": username, "t": topic, "is_cat": req.is_category},
            )
            conn.commit()

        log_user_event(username, "add_topic", topic)
        return {"status": "ok", "topic_name": topic, "is_category": req.is_category}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/watchlist/topics/{topic_name}")
def remove_topic_from_watchlist(topic_name: str, payload: dict = Depends(require_auth)):
    """Remove a topic from the user's watchlist."""
    username = payload["sub"]
    engine = _require_engine()

    try:
        with engine.connect() as conn:
            result = conn.execute(
                sql_text("DELETE FROM topic_watchlist WHERE username = :u AND topic_name = :t"),
                {"u": username, "t": topic_name},
            )
            conn.commit()
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Topic not found in watchlist")

        log_user_event(username, "remove_topic", topic_name)
        return {"status": "ok", "topic_name": topic_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Alert Management (Phase 2, Step 0B)
# ---------------------------------------------------------------------------

@app.post("/api/alerts/{alert_id}/mark-read")
def api_mark_alert_read(alert_id: int, payload: dict = Depends(require_auth)):
    """Mark a single alert as read."""
    username = payload["sub"]
    mark_alert_read(username, alert_id)
    return {"status": "ok", "alert_id": alert_id}


@app.post("/api/alerts/mark-all-read")
def api_mark_all_alerts_read(payload: dict = Depends(require_auth)):
    """Mark all alerts as read for the current user."""
    username = payload["sub"]
    mark_all_alerts_read(username)
    return {"status": "ok"}


class AlertFeedbackRequest(BaseModel):
    action: str  # "expanded", "thumbs_up", or "thumbs_down"


@app.post("/api/alerts/{alert_id}/feedback")
def api_alert_feedback(alert_id: int, req: AlertFeedbackRequest, payload: dict = Depends(require_auth)):
    """Record user feedback on an alert."""
    username = payload["sub"]
    if req.action not in ("expanded", "thumbs_up", "thumbs_down"):
        raise HTTPException(status_code=400, detail="Action must be expanded, thumbs_up, or thumbs_down")
    engine = _require_engine()
    record_feedback(engine, alert_id, username, req.action)
    log_user_event(username, f"alert_{req.action}", str(alert_id))
    return {"status": "ok", "alert_id": alert_id, "action": req.action}


# ---------------------------------------------------------------------------
# User Preferences (Phase 2, Step 0C)
# ---------------------------------------------------------------------------

@app.get("/api/user/alert-preferences")
def api_get_alert_preferences(payload: dict = Depends(require_auth)):
    """Get per-alert-type preferences for the current user."""
    username = payload["sub"]
    prefs = get_user_alert_preferences(username)
    return {"preferences": prefs}


class UpdateAlertPreferencesRequest(BaseModel):
    alert_type: Optional[str] = None
    enabled: Optional[bool] = None
    sensitivity: Optional[str] = None  # "low", "medium", "high"


@app.patch("/api/user/alert-preferences")
def api_update_alert_preferences(req: UpdateAlertPreferencesRequest, payload: dict = Depends(require_auth)):
    """Update alert preferences. If alert_type is provided, update that type.
    If only sensitivity is provided (no alert_type), bulk-update all types."""
    username = payload["sub"]

    if req.sensitivity and req.sensitivity not in ("low", "medium", "high"):
        raise HTTPException(status_code=400, detail="Sensitivity must be low, medium, or high")

    if req.alert_type:
        update_user_alert_preferences(
            username,
            req.alert_type,
            enabled=req.enabled if req.enabled is not None else True,
            sensitivity=req.sensitivity or "medium",
        )
    elif req.sensitivity:
        bulk_update_alert_sensitivity(username, req.sensitivity)
    else:
        raise HTTPException(status_code=400, detail="Provide alert_type or sensitivity")

    log_user_event(username, "update_alert_preferences")
    return {"status": "ok"}


class UpdateUserPreferencesRequest(BaseModel):
    digest_daily: Optional[bool] = None
    digest_weekly: Optional[bool] = None
    alert_emails: Optional[bool] = None


@app.get("/api/user/preferences")
def api_get_user_preferences(payload: dict = Depends(require_auth)):
    """Get email/digest preferences for the current user."""
    username = payload["sub"]
    return get_user_preferences(username)


@app.patch("/api/user/preferences")
def api_update_user_preferences(req: UpdateUserPreferencesRequest, payload: dict = Depends(require_auth)):
    """Update email/digest preferences for the current user."""
    username = payload["sub"]
    current = get_user_preferences(username)
    update_user_preferences(
        username,
        digest_daily=req.digest_daily if req.digest_daily is not None else current["digest_daily"],
        digest_weekly=req.digest_weekly if req.digest_weekly is not None else current["digest_weekly"],
        alert_emails=req.alert_emails if req.alert_emails is not None else current["alert_emails"],
    )
    log_user_event(username, "update_preferences")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Report Schedules (Phase 2, Step 0D)
# ---------------------------------------------------------------------------

@app.get("/api/user/report-schedules")
def api_get_report_schedules(payload: dict = Depends(require_auth)):
    """Get all report schedules for the current user."""
    username = payload["sub"]
    rows = get_report_schedules(username)
    schedules = []
    for r in rows:
        schedules.append({
            "id": r[0],
            "subject": r[1],
            "subject_type": r[2],
            "frequency": r[3],
            "days_lookback": r[4],
            "enabled": r[5],
            "last_run": r[6].isoformat() if r[6] else None,
            "next_run": r[7].isoformat() if r[7] else None,
        })
    return {"schedules": schedules, "count": len(schedules)}


class CreateReportScheduleRequest(BaseModel):
    subject: str
    subject_type: str = "brand"  # "brand" or "topic"
    frequency: str = "weekly"  # "daily" or "weekly"
    days_lookback: int = 7


@app.post("/api/user/report-schedules")
def api_create_report_schedule(req: CreateReportScheduleRequest, payload: dict = Depends(require_auth)):
    """Create a new report schedule."""
    username = payload["sub"]
    if req.frequency not in ("daily", "weekly"):
        raise HTTPException(status_code=400, detail="Frequency must be daily or weekly")
    if req.subject_type not in ("brand", "topic"):
        raise HTTPException(status_code=400, detail="Subject type must be brand or topic")
    if not req.subject.strip():
        raise HTTPException(status_code=400, detail="Subject is required")

    ok = create_report_schedule(
        username, req.subject.strip(), req.subject_type,
        req.frequency, req.days_lookback,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to create schedule")
    log_user_event(username, "create_report_schedule", req.subject.strip())
    return {"status": "ok"}


class ToggleReportScheduleRequest(BaseModel):
    enabled: bool


@app.patch("/api/user/report-schedules/{schedule_id}")
def api_toggle_report_schedule(schedule_id: int, req: ToggleReportScheduleRequest, payload: dict = Depends(require_auth)):
    """Enable or disable a report schedule."""
    toggle_report_schedule(schedule_id, req.enabled)
    return {"status": "ok", "schedule_id": schedule_id, "enabled": req.enabled}


@app.delete("/api/user/report-schedules/{schedule_id}")
def api_delete_report_schedule(schedule_id: int, payload: dict = Depends(require_auth)):
    """Delete a report schedule."""
    delete_report_schedule(schedule_id)
    log_user_event(payload["sub"], "delete_report_schedule", str(schedule_id))
    return {"status": "ok", "schedule_id": schedule_id}


# ---------------------------------------------------------------------------
# Team Management (Phase 2, Step 0E)
# ---------------------------------------------------------------------------

@app.get("/api/user/team")
def api_get_user_team(payload: dict = Depends(require_auth)):
    """Get the current user's team info."""
    username = payload["sub"]
    team = get_user_team(username)
    if not team:
        return {"team": None}
    return {"team": team}


@app.get("/api/teams/{team_id}/members")
def api_get_team_members(team_id: int, payload: dict = Depends(require_auth)):
    """Get members of a team."""
    rows = get_team_members(team_id)
    members = []
    for r in rows:
        members.append({
            "username": r[0],
            "role": r[1],
            "joined_at": r[2].isoformat() if r[2] else None,
            "email": r[3],
        })
    return {"members": members, "count": len(members)}


class InviteTeamMemberRequest(BaseModel):
    email: str
    name: str = ""


@app.post("/api/teams/{team_id}/members")
def api_invite_team_member(team_id: int, req: InviteTeamMemberRequest, payload: dict = Depends(require_auth)):
    """Invite a new member to the team."""
    username = payload["sub"]
    if not req.email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    ok, msg = invite_team_member(team_id, req.email, req.name, username)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    log_user_event(username, "invite_team_member", req.email)
    return {"status": "ok", "message": msg}


@app.delete("/api/teams/{team_id}/members/{member_username}")
def api_remove_team_member(team_id: int, member_username: str, payload: dict = Depends(require_auth)):
    """Remove a member from the team."""
    removed = remove_team_member(team_id, member_username)
    if not removed:
        raise HTTPException(status_code=400, detail="Cannot remove member (may be owner or not found)")
    log_user_event(payload["sub"], "remove_team_member", member_username)
    return {"status": "ok", "username": member_username}


@app.get("/api/teams/{team_id}/watchlists")
def api_get_team_watchlists(team_id: int, payload: dict = Depends(require_auth)):
    """Get the team owner's shared watchlists."""
    brands = get_team_watchlist_brands(team_id)
    topics = get_team_watchlist_topics(team_id)
    return {
        "brands": brands,
        "topics": [{"topic_name": t[0], "is_category": t[1]} for t in topics],
    }


# ---------------------------------------------------------------------------
# Remaining Endpoints (Phase 2, Step 0F)
# ---------------------------------------------------------------------------

@app.post("/api/user/brief-credits/decrement")
def api_decrement_brief_credits(payload: dict = Depends(require_auth)):
    """Decrement brief credits by 1 after generation."""
    username = payload["sub"]
    decrement_brief_credits(username)
    return {"status": "ok"}


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    plan: str = "monthly"  # "monthly" or "annually"


@app.post("/api/auth/signup")
def api_signup(req: SignupRequest):
    """Create a pending signup and return the Stripe payment link."""
    import re
    from urllib.parse import quote as url_quote

    engine = _require_engine()
    name = req.name.strip()
    email = req.email.strip().lower()
    password = req.password.strip()

    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if req.plan not in ("monthly", "annually"):
        raise HTTPException(status_code=400, detail="Plan must be monthly or annually")

    try:
        with engine.connect() as conn:
            # Ensure pending_signups table exists
            conn.execute(sql_text("""
                CREATE TABLE IF NOT EXISTS pending_signups (
                    id SERIAL PRIMARY KEY,
                    signup_token VARCHAR(64) UNIQUE NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    username VARCHAR(100) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    tier VARCHAR(20) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.commit()

            # Check existing user
            existing = conn.execute(
                sql_text("SELECT 1 FROM users WHERE email = :email"),
                {"email": email},
            ).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail="An account with this email already exists")

            # Generate username
            username = re.sub(r'[^a-z0-9_]', '', name.lower().replace(" ", "_"))
            if not username:
                username = email.split("@")[0]
            ex_user = conn.execute(
                sql_text("SELECT 1 FROM users WHERE username = :u"),
                {"u": username},
            ).fetchone()
            if ex_user:
                username = f"{username}_{secrets.randbelow(999)}"

            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            signup_token = secrets.token_urlsafe(32)

            conn.execute(sql_text(
                "INSERT INTO pending_signups (signup_token, name, email, username, password_hash, tier) "
                "VALUES (:token, :name, :email, :username, :hash, :tier)"
            ), {
                "token": signup_token, "name": name, "email": email,
                "username": username, "hash": password_hash, "tier": req.plan,
            })
            conn.commit()

        # Build Stripe payment link
        stripe_link_env = "STRIPE_MONTHLY_LINK" if req.plan == "monthly" else "STRIPE_ANNUAL_LINK"
        stripe_link = os.getenv(stripe_link_env, "")
        stripe_url = None
        if stripe_link:
            stripe_url = f"{stripe_link}?prefilled_email={url_quote(email)}&client_reference_id={signup_token}"

        return {
            "status": "ok",
            "signup_token": signup_token,
            "stripe_url": stripe_url,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ActivateRequest(BaseModel):
    signup_token: str


@app.post("/api/auth/activate")
def api_activate(req: ActivateRequest):
    """Check pending signup status and create user if payment completed."""
    engine = _require_engine()

    try:
        with engine.connect() as conn:
            row = conn.execute(sql_text(
                "SELECT status, name, email, username, password_hash, tier "
                "FROM pending_signups WHERE signup_token = :token"
            ), {"token": req.signup_token}).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Signup token not found")

            status, name, email, username, password_hash, tier = row

            if status == "synced":
                return {"status": "already_active", "message": "Account already active. Please log in."}

            if status != "completed":
                return {"status": "pending", "message": "Payment not confirmed yet."}

            # Payment confirmed — create user in users table
            existing_user = conn.execute(
                sql_text("SELECT 1 FROM users WHERE email = :email"),
                {"email": email},
            ).fetchone()
            if not existing_user:
                conn.execute(sql_text(
                    "INSERT INTO users (username, email, password_hash, tier) "
                    "VALUES (:username, :email, :hash, :tier)"
                ), {
                    "username": username, "email": email,
                    "hash": password_hash, "tier": tier,
                })

            # Mark as synced
            conn.execute(sql_text(
                "UPDATE pending_signups SET status = 'synced' WHERE signup_token = :token"
            ), {"token": req.signup_token})
            conn.commit()

        return {"status": "activated", "message": "Account activated. Please log in."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UserEventRequest(BaseModel):
    event_type: str
    event_data: Optional[str] = None


@app.post("/api/user/events")
def api_log_user_event(req: UserEventRequest, payload: dict = Depends(require_auth)):
    """Log a user event for analytics."""
    username = payload["sub"]
    log_user_event(username, req.event_type, req.event_data)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Support Email
# ---------------------------------------------------------------------------

class SupportRequest(BaseModel):
    message: str


@app.post("/api/support")
def api_send_support(req: SupportRequest, payload: dict = Depends(require_auth)):
    """Send a support email to intel@moodlightintel.com."""
    username = payload["sub"]
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    import smtplib
    from email.mime.text import MIMEText

    sender = os.getenv("EMAIL_ADDRESS", "")
    password = os.getenv("EMAIL_PASSWORD", "")
    if not sender or not password:
        raise HTTPException(status_code=503, detail="Email service unavailable. Please email intel@moodlightintel.com directly.")

    try:
        body = f"Support request from: {username}\n\n{message}"
        msg = MIMEText(body, "plain")
        msg["Subject"] = f"[Moodlight Support] {username}"
        msg["From"] = sender
        msg["To"] = "intel@moodlightintel.com"
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            srv.login(sender, password)
            srv.send_message(msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not send: {e}")

    log_user_event(username, "support_request")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Signal Log (Prediction Outcome Tracking)
# ---------------------------------------------------------------------------

@app.get("/api/signal-log")
def get_signal_log(days: int = Query(default=90, ge=1, le=730)):
    """Return signal log entries with market outcomes."""
    engine = _require_engine()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        df = pd.read_sql(
            sql_text(
                "SELECT * FROM signal_log "
                "WHERE signal_date >= :cutoff "
                "ORDER BY signal_date DESC"
            ),
            engine,
            params={"cutoff": cutoff},
        )
        return {"data": _df_to_records(df), "count": len(df)}
    except Exception as e:
        if "does not exist" in str(e).lower():
            return {"data": [], "count": 0}
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Cultural Signal API (Phase 1 — Proof of Value)
# ---------------------------------------------------------------------------

def _read_vlds_csvs():
    """Read VLDS data from PostgreSQL tables (longevity, density, scarcity)."""
    engine = _require_engine()

    try:
        vel_df = pd.read_sql(
            sql_text("SELECT topic, velocity_score, longevity_score FROM topic_longevity"),
            engine,
        )
    except Exception:
        vel_df = pd.DataFrame()

    try:
        den_df = pd.read_sql(
            sql_text("SELECT topic, density_score FROM topic_density"),
            engine,
        )
    except Exception:
        den_df = pd.DataFrame()

    try:
        scar_df = pd.read_sql(
            sql_text("SELECT topic, scarcity_score FROM topic_scarcity"),
            engine,
        )
    except Exception:
        scar_df = pd.DataFrame()

    # Collect all topics
    topics = set()
    for df in [vel_df, den_df, scar_df]:
        if not df.empty and "topic" in df.columns:
            topics.update(df["topic"].tolist())

    if not topics:
        return pd.DataFrame()

    merged = pd.DataFrame({"topic": list(topics)})

    if not vel_df.empty and "topic" in vel_df.columns:
        if "velocity_score" in vel_df.columns:
            merged = merged.merge(
                vel_df[["topic", "velocity_score"]].rename(columns={"velocity_score": "velocity"}),
                on="topic", how="left",
            )
        if "longevity_score" in vel_df.columns:
            merged = merged.merge(
                vel_df[["topic", "longevity_score"]].rename(columns={"longevity_score": "longevity"}),
                on="topic", how="left",
            )

    if not den_df.empty and "topic" in den_df.columns and "density_score" in den_df.columns:
        merged = merged.merge(
            den_df[["topic", "density_score"]].rename(columns={"density_score": "density"}),
            on="topic", how="left",
        )

    if not scar_df.empty and "topic" in scar_df.columns and "scarcity_score" in scar_df.columns:
        merged = merged.merge(
            scar_df[["topic", "scarcity_score"]].rename(columns={"scarcity_score": "scarcity"}),
            on="topic", how="left",
        )

    # Ensure columns exist
    for col in ["velocity", "longevity", "density", "scarcity"]:
        if col not in merged.columns:
            merged[col] = None

    # Labels
    merged["velocity_label"] = merged["velocity"].apply(
        lambda v: "Accelerating" if pd.notna(v) and v > 0.7 else "Stable" if pd.notna(v) and v > 0.4 else "Declining"
    )
    merged["longevity_label"] = merged["longevity"].apply(
        lambda v: "Sustained" if pd.notna(v) and v > 0.7 else "Moderate" if pd.notna(v) and v > 0.4 else "Flash"
    )
    merged["density_label"] = merged["density"].apply(
        lambda v: "Saturated" if pd.notna(v) and v > 0.7 else "Moderate" if pd.notna(v) and v > 0.3 else "White Space"
    )
    merged["scarcity_label"] = merged["scarcity"].apply(
        lambda v: "High Opportunity" if pd.notna(v) and v > 0.7 else "Some Coverage" if pd.notna(v) and v > 0.4 else "Well Covered"
    )

    # Opportunity score
    merged["opportunity_score"] = merged.apply(
        lambda r: (r["scarcity"] or 0) * (r["velocity"] or 0) / max(r["density"] or 0.1, 0.1)
        if pd.notna(r.get("scarcity")) and pd.notna(r.get("velocity"))
        else None,
        axis=1,
    )

    return merged


@app.get("/api/signals/topics")
def get_signal_topics():
    """Current VLDS scores for all tracked topics with strategic labels."""
    merged = _read_vlds_csvs()
    if merged.empty:
        return {"topics": [], "count": 0, "updated_at": datetime.now(timezone.utc).isoformat()}

    merged = merged.sort_values("opportunity_score", ascending=False, na_position="last")
    records = _df_to_records(merged)
    return {
        "topics": records,
        "count": len(records),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/signals/emotions")
def get_signal_emotions(hours: int = Query(default=48, ge=1, le=168)):
    """Real-time emotional climate — emotion distribution + empathy score."""
    engine = _require_engine()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    try:
        # Emotion distribution
        emo_df = pd.read_sql(
            sql_text("""
                SELECT emotion_top_1 AS emotion, COUNT(*) AS count
                FROM news_scored
                WHERE created_at >= :cutoff AND emotion_top_1 IS NOT NULL
                GROUP BY emotion_top_1
                ORDER BY count DESC
            """),
            engine,
            params={"cutoff": cutoff},
        )

        # Empathy score
        emp_df = pd.read_sql(
            sql_text("""
                SELECT AVG(empathy_score) AS avg_empathy, COUNT(*) AS total
                FROM news_scored
                WHERE created_at >= :cutoff
            """),
            engine,
            params={"cutoff": cutoff},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Emotion breakdown
    total_posts = int(emp_df["total"].iloc[0]) if not emp_df.empty else 0
    emotions = []
    if not emo_df.empty:
        emo_total = emo_df["count"].sum()
        for _, row in emo_df.iterrows():
            emotions.append({
                "emotion": row["emotion"],
                "count": int(row["count"]),
                "percentage": round(float(row["count"]) / emo_total * 100, 1),
            })

    # Piecewise empathy normalization
    raw_empathy = float(emp_df["avg_empathy"].iloc[0]) if not emp_df.empty and pd.notna(emp_df["avg_empathy"].iloc[0]) else 0
    if raw_empathy <= 0.04:
        normalized = 50
    elif raw_empathy <= 0.10:
        normalized = 50 + (raw_empathy - 0.04) / (0.10 - 0.04) * (65 - 50)
    elif raw_empathy <= 0.30:
        normalized = 65 + (raw_empathy - 0.10) / (0.30 - 0.10) * (85 - 65)
    else:
        normalized = min(95, 85 + (raw_empathy - 0.30) / 0.20 * 10)

    if normalized >= 75:
        empathy_label = "High Empathy"
    elif normalized >= 60:
        empathy_label = "Moderate"
    elif normalized >= 45:
        empathy_label = "Low"
    else:
        empathy_label = "Very Low"

    return {
        "emotions": emotions,
        "empathy": {
            "raw": round(raw_empathy, 4),
            "normalized": round(normalized, 1),
            "label": empathy_label,
        },
        "window_hours": hours,
        "total_posts": total_posts,
    }


@app.get("/api/signals/opportunities")
def get_signal_opportunities():
    """Cultural opportunity zones, rising edges, and saturated topics."""
    merged = _read_vlds_csvs()
    if merged.empty:
        return {"opportunities": [], "rising_edges": [], "saturated": []}

    def _to_list(df_slice):
        cols = [c for c in ["topic", "velocity", "longevity", "density", "scarcity", "opportunity_score", "density_label"] if c in df_slice.columns]
        out = df_slice[cols].copy()
        if "density_label" in out.columns:
            out = out.rename(columns={"density_label": "label"})
        return _df_to_records(out)

    # Opportunities: high scarcity + low density
    opps = merged.dropna(subset=["scarcity", "density"])
    opps = opps[(opps["scarcity"] > 0.5) & (opps["density"] < 0.5)]
    opps = opps.sort_values("scarcity", ascending=False).head(10)

    # Rising edges: high velocity + low density
    edges = merged.dropna(subset=["velocity", "density"])
    edges = edges[(edges["velocity"] > 0.5) & (edges["density"] < 0.5)]
    edges = edges.sort_values("velocity", ascending=False).head(10)

    # Saturated: high density
    sat = merged.dropna(subset=["density"])
    sat = sat[sat["density"] > 0.7].sort_values("density", ascending=False).head(10)

    return {
        "opportunities": _to_list(opps),
        "rising_edges": _to_list(edges),
        "saturated": _to_list(sat),
    }


@app.get("/api/signals/alerts")
def get_signal_alerts(days: int = Query(default=7, ge=1, le=30)):
    """Active predictive signals with outcome data."""
    engine = _require_engine()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        df = pd.read_sql(
            sql_text("""
                SELECT a.id, a.alert_type, a.severity, a.title, a.summary,
                       a.timestamp, a.topic, a.brand, a.data,
                       sl.spy_change_1d, sl.spy_change_3d, sl.spy_change_5d
                FROM alerts a
                LEFT JOIN signal_log sl ON sl.alert_id = a.id
                WHERE (a.alert_type LIKE 'predictive_%%' OR a.alert_type = 'market_mood_divergence')
                  AND a.timestamp >= :cutoff
                ORDER BY a.timestamp DESC
            """),
            engine,
            params={"cutoff": cutoff},
        )
    except Exception as e:
        if "does not exist" in str(e).lower():
            return {"alerts": [], "count": 0}
        raise HTTPException(status_code=500, detail=str(e))

    # Extract confidence from data JSON
    records = _df_to_records(df)
    for rec in records:
        data_field = rec.get("data")
        confidence = None
        if isinstance(data_field, str):
            try:
                data_field = json.loads(data_field)
            except Exception:
                data_field = {}
        if isinstance(data_field, dict):
            confidence = data_field.get("confidence")
        rec["confidence"] = confidence
        rec.pop("data", None)

    return {"alerts": records, "count": len(records)}


# ---------------------------------------------------------------------------
# Case Study Generator
# ---------------------------------------------------------------------------

class CaseStudyRequest(BaseModel):
    topic: str
    lookback_days: int = 30


@app.post("/api/case-study/generate")
def generate_case_study(req: CaseStudyRequest, payload: dict = Depends(require_auth)):
    """Generate a retrospective case study for a cultural moment."""
    from anthropic import Anthropic

    engine = _require_engine()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=req.lookback_days)).strftime("%Y-%m-%d")
    topic = req.topic

    # 1. Headlines about this topic
    try:
        headlines_df = pd.read_sql(
            sql_text("""
                SELECT text, empathy_score, emotion_top_1, intensity, source, created_at
                FROM news_scored
                WHERE topic ILIKE :topic AND created_at >= :cutoff
                ORDER BY intensity DESC LIMIT 20
            """),
            engine,
            params={"topic": f"%{topic}%", "cutoff": cutoff},
        )
    except Exception:
        headlines_df = pd.DataFrame()

    # 2. Emotion distribution
    try:
        emotions_df = pd.read_sql(
            sql_text("""
                SELECT emotion_top_1, COUNT(*) as cnt
                FROM news_scored
                WHERE topic ILIKE :topic AND created_at >= :cutoff AND emotion_top_1 IS NOT NULL
                GROUP BY emotion_top_1
                ORDER BY cnt DESC LIMIT 5
            """),
            engine,
            params={"topic": f"%{topic}%", "cutoff": cutoff},
        )
    except Exception:
        emotions_df = pd.DataFrame()

    # 3. Related alerts
    try:
        alerts_df = pd.read_sql(
            sql_text("""
                SELECT alert_type, severity, title, summary, timestamp
                FROM alerts
                WHERE (topic ILIKE :topic OR title ILIKE :topic_title)
                  AND timestamp >= :cutoff
                ORDER BY timestamp DESC LIMIT 10
            """),
            engine,
            params={"topic": f"%{topic}%", "topic_title": f"%{topic}%", "cutoff": cutoff},
        )
    except Exception:
        alerts_df = pd.DataFrame()

    # 4. Signal log entries with outcomes
    try:
        signals_df = pd.read_sql(
            sql_text("""
                SELECT alert_type, title, summary, signal_date,
                       spy_change_1d, spy_change_3d, spy_change_5d,
                       brand_ticker, brand_change_1d
                FROM signal_log
                WHERE (topic ILIKE :topic OR title ILIKE :topic_title)
                  AND signal_date >= :cutoff
                ORDER BY signal_date DESC LIMIT 10
            """),
            engine,
            params={"topic": f"%{topic}%", "topic_title": f"%{topic}%", "cutoff": cutoff},
        )
    except Exception:
        signals_df = pd.DataFrame()

    # Build context
    context_parts = [f"TOPIC: {topic}", f"PERIOD: Last {req.lookback_days} days", ""]

    if not headlines_df.empty:
        context_parts.append(f"HEADLINES ({len(headlines_df)} stories):")
        for _, row in headlines_df.head(10).iterrows():
            context_parts.append(
                f"  - {row.get('text', '')[:200]} | emotion: {row.get('emotion_top_1', 'N/A')} | "
                f"intensity: {row.get('intensity', 0):.1f} | empathy: {row.get('empathy_score', 0):.3f}"
            )
        avg_emp = headlines_df["empathy_score"].mean() if "empathy_score" in headlines_df.columns else 0
        avg_int = headlines_df["intensity"].mean() if "intensity" in headlines_df.columns else 0
        context_parts.append(f"  Average empathy: {avg_emp:.3f} | Average intensity: {avg_int:.1f}")
        context_parts.append("")

    if not emotions_df.empty:
        context_parts.append("EMOTION DISTRIBUTION:")
        total = emotions_df["cnt"].sum()
        for _, row in emotions_df.iterrows():
            pct = row["cnt"] / total * 100
            context_parts.append(f"  - {row['emotion_top_1']}: {pct:.0f}%")
        context_parts.append("")

    if not alerts_df.empty:
        context_parts.append(f"MOODLIGHT ALERTS ({len(alerts_df)}):")
        for _, row in alerts_df.iterrows():
            context_parts.append(
                f"  - [{row.get('severity', 'info')}] {row.get('title', '')} ({row.get('timestamp', '')})"
            )
            context_parts.append(f"    {row.get('summary', '')[:200]}")
        context_parts.append("")

    if not signals_df.empty:
        context_parts.append(f"PREDICTION SIGNALS WITH OUTCOMES ({len(signals_df)}):")
        for _, row in signals_df.iterrows():
            outcome = ""
            if pd.notna(row.get("spy_change_1d")):
                outcome = f" | SPY 1d: {row['spy_change_1d']:+.2f}%, 3d: {row.get('spy_change_3d', 'pending')}, 5d: {row.get('spy_change_5d', 'pending')}"
            context_parts.append(
                f"  - {row.get('title', '')} ({row.get('signal_date', '')}){outcome}"
            )
        context_parts.append("")

    context = "\n".join(context_parts)

    if headlines_df.empty and alerts_df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for topic '{topic}' in the last {req.lookback_days} days.")

    # Generate via Claude
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2000,
        system="""You write concise, data-backed retrospective case studies for Moodlight, a cultural intelligence platform.

Your output must follow this exact structure with these section headers:

## THE MOMENT
What happened culturally — 2-3 sentences setting the scene. Be specific about what shifted in public conversation.

## WHAT MOODLIGHT SAW
What signals Moodlight detected, when, and at what intensity/confidence. Reference specific alert types, empathy scores, and emotion distributions from the data. Be precise with numbers.

## THE OPPORTUNITY
What a brand could have done if they'd acted on these signals — 2-3 concrete, specific actions (not vague "engage with the conversation" advice). Reference the emotional register and timing.

## THE NUMBERS
3-5 key data points from the context in a bullet list. Include empathy scores, emotion percentages, intensity levels, and market outcomes if available.

## THE TAKEAWAY
One sentence — the strategic lesson a media planner should remember.

Be concise. No filler. Every sentence must contain a data point or a specific insight.""",
        messages=[{
            "role": "user",
            "content": f"Generate a retrospective case study from this Moodlight data:\n\n{context}",
        }],
    )

    raw_text = response.content[0].text

    # Parse sections
    sections = {}
    current_section = None
    current_lines = []
    for line in raw_text.split("\n"):
        if line.startswith("## "):
            if current_section:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_section:
        sections[current_section] = "\n".join(current_lines).strip()

    return {
        "case_study": {
            "topic": topic,
            "period": f"Last {req.lookback_days} days",
            "sections": sections,
        },
        "raw_text": raw_text,
    }


# ---------------------------------------------------------------------------
# Stripe Webhooks (migrated from webhook_server.py)
# ---------------------------------------------------------------------------

# Map Stripe price IDs to tiers
_STRIPE_PRICE_TO_TIER = {
    "price_1SyI3P1OGs3ZkUZa8IwdSO85": "monthly",     # $899/mo
    "price_1Szgi81OGs3ZkUZaZlFrKOAw": "annually",     # $8,999/yr
}


def _activate_pending_signup(signup_token: str, customer_id: str = None, subscription_id: str = None):
    """Activate a self-service signup: create user in DB from pending_signups."""
    engine = _require_engine()
    with engine.connect() as conn:
        row = conn.execute(sql_text(
            "SELECT name, email, username, password_hash, tier FROM pending_signups "
            "WHERE signup_token = :token AND status = 'pending'"
        ), {"token": signup_token}).fetchone()
        if not row:
            print(f"No pending signup found for token {signup_token[:8]}...")
            return

        name, email, username, password_hash, tier = row

        existing = conn.execute(sql_text(
            "SELECT id FROM users WHERE email = :email OR username = :username"
        ), {"email": email, "username": username}).fetchone()
        if existing:
            print(f"User {email} already exists, skipping creation")
            conn.execute(sql_text(
                "UPDATE pending_signups SET status = 'completed' WHERE signup_token = :token"
            ), {"token": signup_token})
            conn.commit()
            return

        conn.execute(sql_text("""
            INSERT INTO users (username, email, password_hash, tier, stripe_customer_id, stripe_subscription_id)
            VALUES (:username, :email, :password_hash, :tier, :customer_id, :subscription_id)
        """), {
            "username": username, "email": email, "password_hash": password_hash,
            "tier": tier, "customer_id": customer_id, "subscription_id": subscription_id,
        })

        conn.execute(sql_text(
            "UPDATE pending_signups SET status = 'completed' WHERE signup_token = :token"
        ), {"token": signup_token})
        conn.commit()
        print(f"Self-service signup activated: {email} ({tier})")


@app.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, _stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email") or session.get("customer_details", {}).get("email")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        client_ref = session.get("client_reference_id")

        if client_ref:
            _activate_pending_signup(client_ref, customer_id, subscription_id)

        if subscription_id:
            subscription = stripe.Subscription.retrieve(subscription_id)
            price_id = subscription["items"]["data"][0]["price"]["id"]
            tier = _STRIPE_PRICE_TO_TIER.get(price_id, "monthly")

            if customer_email:
                engine = _require_engine()
                with engine.connect() as conn:
                    conn.execute(sql_text("""
                        UPDATE users
                        SET tier = :tier, stripe_customer_id = :customer_id,
                            stripe_subscription_id = :subscription_id,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE email = :email
                    """), {
                        "email": customer_email, "tier": tier,
                        "customer_id": customer_id, "subscription_id": subscription_id,
                    })
                    conn.commit()
                print(f"Updated {customer_email} to {tier}")

    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        subscription_id = subscription["id"]
        price_id = subscription["items"]["data"][0]["price"]["id"]
        tier = _STRIPE_PRICE_TO_TIER.get(price_id, "monthly")

        engine = _require_engine()
        with engine.connect() as conn:
            conn.execute(sql_text("""
                UPDATE users SET tier = :tier, updated_at = CURRENT_TIMESTAMP
                WHERE stripe_subscription_id = :subscription_id
            """), {"tier": tier, "subscription_id": subscription_id})
            conn.commit()
        print(f"Updated subscription {subscription_id} to {tier}")

    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        subscription_id = subscription["id"]
        engine = _require_engine()
        with engine.connect() as conn:
            conn.execute(sql_text("""
                UPDATE users
                SET tier = 'cancelled', stripe_subscription_id = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE stripe_subscription_id = :subscription_id
            """), {"subscription_id": subscription_id})
            conn.commit()
        print(f"Downgraded subscription {subscription_id}")

    return {"status": "success"}


# Serve static files LAST (mount is greedy — must come after all routes)
from fastapi.staticfiles import StaticFiles
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
