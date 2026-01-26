"""
Headlines router - full headlines page with filtering and search.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.auth import get_current_user, require_auth
from app.services.tier import get_user_tier, get_tier_display_name, get_brief_limit
from app.services.data_loader import load_data, get_trending_headlines
from app.utils.constants import VIEW_MODES, TOPIC_CATEGORIES, EMOTION_COLORS

router = APIRouter(prefix="/headlines", tags=["headlines"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def headlines_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    mode: str = "strategic",
    topic: Optional[str] = None,
    source: Optional[str] = None,
    emotion: Optional[str] = None,
    page: int = 1,
    per_page: int = 20
):
    """
    Render the full headlines page with filtering.
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

    # Load data with optional source filter
    df = await load_data(db, days=days, source_filter=source)

    # Apply topic filter
    if topic and "topic" in df.columns:
        df = df[df["topic"] == topic]

    # Apply emotion filter
    if emotion and "emotion_top_1" in df.columns:
        df = df[df["emotion_top_1"] == emotion]

    # Get total count before pagination
    total_count = len(df)

    # Get headlines with pagination
    offset = (page - 1) * per_page
    headlines = get_trending_headlines(df, limit=per_page + offset)
    headlines = headlines[offset:offset + per_page]

    # Calculate pagination
    total_pages = (total_count + per_page - 1) // per_page

    # Get available filters
    available_topics = sorted(df["topic"].dropna().unique().tolist()) if "topic" in df.columns else []
    available_sources = sorted(df["source"].dropna().unique().tolist()) if "source" in df.columns else []
    available_emotions = sorted(df["emotion_top_1"].dropna().unique().tolist()) if "emotion_top_1" in df.columns else []

    return templates.TemplateResponse(
        "headlines.html",
        {
            "request": request,
            "user": user,
            "tier_display": get_tier_display_name(user["tier"]),
            "briefs_used": tier_info["briefs_used"],
            "briefs_remaining": brief_limit - tier_info["briefs_used"],
            "view_mode": mode,
            "view_modes": VIEW_MODES,
            "headlines": headlines,
            "total_count": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "filters": {
                "topic": topic,
                "source": source,
                "emotion": emotion
            },
            "available_topics": available_topics,
            "available_sources": available_sources,
            "available_emotions": available_emotions,
            "emotion_colors": EMOTION_COLORS
        }
    )


@router.get("/partial", response_class=HTMLResponse)
async def headlines_partial(
    request: Request,
    db: AsyncSession = Depends(get_db),
    mode: str = "strategic",
    topic: Optional[str] = None,
    source: Optional[str] = None,
    emotion: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    user: dict = Depends(require_auth)
):
    """
    Get headlines list as HTML partial for HTMX updates.
    """
    view_config = VIEW_MODES.get(mode, VIEW_MODES["strategic"])
    df = await load_data(db, days=view_config["days"], source_filter=source)

    if topic and "topic" in df.columns:
        df = df[df["topic"] == topic]

    if emotion and "emotion_top_1" in df.columns:
        df = df[df["emotion_top_1"] == emotion]

    total_count = len(df)
    offset = (page - 1) * per_page
    headlines = get_trending_headlines(df, limit=per_page + offset)
    headlines = headlines[offset:offset + per_page]
    total_pages = (total_count + per_page - 1) // per_page

    return templates.TemplateResponse(
        "partials/headlines_full.html",
        {
            "request": request,
            "headlines": headlines,
            "total_count": total_count,
            "page": page,
            "total_pages": total_pages,
            "emotion_colors": EMOTION_COLORS
        }
    )
