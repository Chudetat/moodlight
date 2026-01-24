"""
Dashboard router - main dashboard page and data API endpoints.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.auth import get_current_user, require_auth
from app.services.tier import get_user_tier, get_tier_display_name, get_brief_limit
from app.services.data_loader import (
    load_data,
    compute_world_mood,
    get_emotion_distribution,
    get_topic_distribution,
    get_source_distribution,
    get_trending_headlines,
    get_mood_history,
    get_geographic_distribution,
)
from app.utils.constants import VIEW_MODES, EMOTION_COLORS

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    mode: str = "strategic"
):
    """
    Render the main dashboard page.
    """
    user = await get_current_user(request, db)
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/auth/login", status_code=302)

    tier_info = await get_user_tier(db, user["username"])
    brief_limit = get_brief_limit(tier_info["tier"], tier_info["extra_briefs_addon"])

    # Get view mode config
    view_config = VIEW_MODES.get(mode, VIEW_MODES["strategic"])
    days = view_config["days"]

    # Load data
    df = await load_data(db, days=days)

    # Calculate metrics
    world_mood = compute_world_mood(df)
    emotions = get_emotion_distribution(df)
    topics = get_topic_distribution(df)
    headlines = get_trending_headlines(df, limit=5)
    mood_history = get_mood_history(df)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "tier_display": get_tier_display_name(user["tier"]),
            "briefs_used": tier_info["briefs_used"],
            "briefs_remaining": brief_limit - tier_info["briefs_used"],
            "view_mode": mode,
            "view_modes": VIEW_MODES,
            "world_mood": world_mood,
            "emotions": emotions,
            "topics": topics,
            "headlines": headlines,
            "mood_history": mood_history,
            "emotion_colors": EMOTION_COLORS,
            "total_items": len(df),
        }
    )


# ============================================
# API Endpoints for HTMX partial updates
# ============================================

@router.get("/api/dashboard")
async def get_dashboard_data(
    request: Request,
    db: AsyncSession = Depends(get_db),
    mode: str = Query("strategic", description="View mode: breaking or strategic"),
    user: dict = Depends(require_auth)
):
    """
    Get dashboard data as JSON (for HTMX updates).
    """
    view_config = VIEW_MODES.get(mode, VIEW_MODES["strategic"])
    days = view_config["days"]

    df = await load_data(db, days=days)

    return {
        "world_mood": compute_world_mood(df),
        "emotions": get_emotion_distribution(df),
        "topics": get_topic_distribution(df),
        "sources": get_source_distribution(df),
        "mood_history": get_mood_history(df),
        "total_items": len(df),
        "mode": mode,
        "days": days
    }


@router.get("/api/dashboard/mood", response_class=HTMLResponse)
async def get_mood_partial(
    request: Request,
    db: AsyncSession = Depends(get_db),
    mode: str = Query("strategic"),
    user: dict = Depends(require_auth)
):
    """
    Get world mood gauge partial (HTMX).
    """
    view_config = VIEW_MODES.get(mode, VIEW_MODES["strategic"])
    df = await load_data(db, days=view_config["days"])
    world_mood = compute_world_mood(df)

    return templates.TemplateResponse(
        "partials/mood_gauge.html",
        {
            "request": request,
            "world_mood": world_mood
        }
    )


@router.get("/api/dashboard/emotions", response_class=HTMLResponse)
async def get_emotions_partial(
    request: Request,
    db: AsyncSession = Depends(get_db),
    mode: str = Query("strategic"),
    user: dict = Depends(require_auth)
):
    """
    Get emotion distribution chart data partial (HTMX).
    """
    view_config = VIEW_MODES.get(mode, VIEW_MODES["strategic"])
    df = await load_data(db, days=view_config["days"])
    emotions = get_emotion_distribution(df)

    return templates.TemplateResponse(
        "partials/emotion_chart.html",
        {
            "request": request,
            "emotions": emotions,
            "emotion_colors": EMOTION_COLORS
        }
    )


@router.get("/api/dashboard/topics", response_class=HTMLResponse)
async def get_topics_partial(
    request: Request,
    db: AsyncSession = Depends(get_db),
    mode: str = Query("strategic"),
    user: dict = Depends(require_auth)
):
    """
    Get topic distribution chart data partial (HTMX).
    """
    view_config = VIEW_MODES.get(mode, VIEW_MODES["strategic"])
    df = await load_data(db, days=view_config["days"])
    topics = get_topic_distribution(df)

    return templates.TemplateResponse(
        "partials/topic_chart.html",
        {
            "request": request,
            "topics": topics
        }
    )


@router.get("/api/headlines")
async def get_headlines(
    db: AsyncSession = Depends(get_db),
    mode: str = Query("strategic"),
    limit: int = Query(10, ge=1, le=50),
    topic: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    user: dict = Depends(require_auth)
):
    """
    Get trending headlines as JSON.
    """
    view_config = VIEW_MODES.get(mode, VIEW_MODES["strategic"])
    df = await load_data(db, days=view_config["days"], source_filter=source)

    # Filter by topic if specified
    if topic and "topic" in df.columns:
        df = df[df["topic"] == topic]

    headlines = get_trending_headlines(df, limit=limit)

    return {
        "headlines": headlines,
        "total": len(headlines),
        "mode": mode,
        "filters": {
            "topic": topic,
            "source": source
        }
    }


@router.get("/api/headlines/partial", response_class=HTMLResponse)
async def get_headlines_partial(
    request: Request,
    db: AsyncSession = Depends(get_db),
    mode: str = Query("strategic"),
    limit: int = Query(5, ge=1, le=20),
    user: dict = Depends(require_auth)
):
    """
    Get trending headlines as HTML partial (HTMX).
    """
    view_config = VIEW_MODES.get(mode, VIEW_MODES["strategic"])
    df = await load_data(db, days=view_config["days"])
    headlines = get_trending_headlines(df, limit=limit)

    return templates.TemplateResponse(
        "partials/headlines_list.html",
        {
            "request": request,
            "headlines": headlines
        }
    )


@router.get("/api/mood-history")
async def get_mood_history_data(
    db: AsyncSession = Depends(get_db),
    days: int = Query(7, ge=1, le=30),
    user: dict = Depends(require_auth)
):
    """
    Get mood history for trend chart.
    """
    df = await load_data(db, days=days)
    history = get_mood_history(df, days=days)

    return {
        "history": history,
        "days": days
    }


@router.get("/api/geographic")
async def get_geographic_data(
    db: AsyncSession = Depends(get_db),
    mode: str = Query("strategic"),
    limit: int = Query(10, ge=1, le=50),
    user: dict = Depends(require_auth)
):
    """
    Get geographic distribution data.
    """
    view_config = VIEW_MODES.get(mode, VIEW_MODES["strategic"])
    df = await load_data(db, days=view_config["days"])
    geo = get_geographic_distribution(df, top_n=limit)

    return {
        "countries": geo,
        "total": len(geo)
    }


@router.get("/api/sources")
async def get_sources_data(
    db: AsyncSession = Depends(get_db),
    mode: str = Query("strategic"),
    user: dict = Depends(require_auth)
):
    """
    Get source distribution data.
    """
    view_config = VIEW_MODES.get(mode, VIEW_MODES["strategic"])
    df = await load_data(db, days=view_config["days"])
    sources = get_source_distribution(df)

    return {
        "sources": sources,
        "total": len(sources)
    }


@router.post("/api/refresh")
async def refresh_data(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth)
):
    """
    Trigger data refresh (runs fetch + score pipeline).
    Note: In production, this should be a background job.
    """
    # TODO: Implement background job for data refresh
    # For now, just return success - actual refresh happens via GitHub Actions

    return {
        "status": "ok",
        "message": "Data refresh scheduled. New data will appear shortly."
    }
