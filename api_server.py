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
from datetime import datetime, timezone, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
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

app = FastAPI(title="Moodlight Data API", docs_url="/api/docs", redoc_url=None)

# CORS — allow Streamlit dashboard, Next.js frontend, and localhost dev
ALLOWED_ORIGINS = [
    "https://moodlight.up.railway.app",
    "https://moodlight.app",
    "http://localhost:3000",
    "http://localhost:8501",
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
    """Return news_scored + social_scored union (df_all equivalent)."""
    engine = _require_engine()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    frames = []
    for table in ("news_scored", "social_scored"):
        try:
            df = pd.read_sql(
                sql_text(f"SELECT * FROM {table} WHERE created_at >= :cutoff"),
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
def get_markets():
    """Return market index data."""
    engine = _require_engine()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
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
                    pipeline_name, status, row_count, started_at, completed_at
                FROM pipeline_runs
                ORDER BY pipeline_name, started_at DESC
            """)).fetchall()

        pipelines = {}
        for row in rows:
            name, status, row_count, started_at, completed_at = row
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

    token = create_access_token(user["username"], user["email"])
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

    return SessionResponse(
        username=user["username"],
        email=user["email"],
        tier=user["tier"],
        brief_credits=user.get("brief_credits", 0),
        is_admin=is_admin_email(user["email"]),
    )


@app.post("/api/auth/logout")
def auth_logout(payload: dict = Depends(require_auth)):
    """Log the logout event. Stateless JWT — no server-side invalidation."""
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
