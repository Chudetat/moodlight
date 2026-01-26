"""
Markets router - Polymarket prediction market integration.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.auth import get_current_user, require_auth
from app.services.tier import get_user_tier, get_tier_display_name, get_brief_limit
from app.services.polymarket import (
    fetch_polymarket_markets,
    calculate_sentiment_divergence,
    get_markets_by_topic
)
from app.services.data_loader import load_data, compute_world_mood

router = APIRouter(prefix="/markets", tags=["markets"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def markets_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    topic: Optional[str] = None
):
    """
    Render the markets page with Polymarket data.
    """
    user = await get_current_user(request, db)
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/auth/login", status_code=302)

    tier_info = await get_user_tier(db, user["username"])
    brief_limit = get_brief_limit(tier_info["tier"], tier_info["extra_briefs_addon"])

    # Fetch prediction markets
    if topic:
        markets = await get_markets_by_topic(topic, limit=20)
    else:
        markets = await fetch_polymarket_markets(limit=20)

    # Get social mood for divergence calculation
    df = await load_data(db, days=30)
    world_mood = compute_world_mood(df)
    social_score = world_mood.get("score", 50) or 50

    # Calculate divergence for each market
    for market in markets:
        divergence = calculate_sentiment_divergence(
            market["yes_odds"],
            social_score
        )
        market["divergence"] = divergence

    # Group markets by category
    categories = {}
    for market in markets:
        cat = market.get("category", "General")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(market)

    return templates.TemplateResponse(
        "markets.html",
        {
            "request": request,
            "user": user,
            "tier_display": get_tier_display_name(user["tier"]),
            "briefs_used": tier_info["briefs_used"],
            "briefs_remaining": brief_limit - tier_info["briefs_used"],
            "markets": markets,
            "categories": categories,
            "world_mood": world_mood,
            "topic_filter": topic
        }
    )


@router.get("/api/markets")
async def get_markets_api(
    db: AsyncSession = Depends(get_db),
    topic: Optional[str] = None,
    limit: int = Query(20, ge=1, le=50),
    user: dict = Depends(require_auth)
):
    """
    Get prediction markets as JSON.
    """
    if topic:
        markets = await get_markets_by_topic(topic, limit=limit)
    else:
        markets = await fetch_polymarket_markets(limit=limit)

    # Get social mood for divergence
    df = await load_data(db, days=30)
    world_mood = compute_world_mood(df)
    social_score = world_mood.get("score", 50) or 50

    for market in markets:
        market["divergence"] = calculate_sentiment_divergence(
            market["yes_odds"],
            social_score
        )

    return {
        "markets": markets,
        "world_mood": world_mood,
        "total": len(markets)
    }


@router.get("/api/divergence")
async def get_divergence(
    db: AsyncSession = Depends(get_db),
    market_odds: float = Query(..., ge=0, le=100),
    user: dict = Depends(require_auth)
):
    """
    Calculate sentiment divergence for a specific market odds value.
    """
    df = await load_data(db, days=30)
    world_mood = compute_world_mood(df)
    social_score = world_mood.get("score", 50) or 50

    divergence = calculate_sentiment_divergence(market_odds, social_score)

    return {
        "divergence": divergence,
        "world_mood": world_mood
    }
