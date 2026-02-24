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
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
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

load_dotenv()

app = FastAPI(title="Moodlight Data API", docs_url="/api/docs", redoc_url=None)

# CORS — allow Streamlit dashboard, future Next.js, and localhost dev
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
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
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
    return df.to_dict("records")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
