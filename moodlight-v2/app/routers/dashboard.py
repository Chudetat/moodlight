"""
Dashboard router - main dashboard page and data API endpoints.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Request, Query, Body
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
    mode: str = "strategic",
    brand: Optional[str] = None
):
    """
    Render the main dashboard page - single scrollable view like v1.
    """
    from datetime import datetime

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

    # Calculate all metrics for v1-style dashboard
    world_mood = compute_world_mood(df)
    emotions = get_emotion_distribution(df)
    topics = get_topic_distribution(df)
    sources = get_source_distribution(df)
    headlines = get_trending_headlines(df, limit=100)  # Show many headlines, scrollable like v1
    mood_history = get_mood_history(df)
    geo_data = get_geographic_distribution(df)

    # Brand-specific analysis if requested
    brand_data = None
    if brand:
        brand_df = df[df["text"].str.contains(brand, case=False, na=False)]
        if not brand_df.empty:
            brand_data = calculate_brand_vlds(brand_df)

    # Global VLDS calculations
    vlds_data = calculate_global_vlds(df)

    # Topic-level VLDS for scatter chart
    topic_vlds = calculate_topic_vlds(df, top_n=10)

    # Current date formatted
    current_date = datetime.now().strftime("%B %d, %Y")

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
            "sources": sources,
            "headlines": headlines,
            "mood_history": mood_history,
            "geo_data": geo_data,
            "emotion_colors": EMOTION_COLORS,
            "total_items": len(df),
            "current_date": current_date,
            "brand_query": brand,
            "brand_data": brand_data,
            "market_data": None,  # TODO: Add stock data integration
            "vlds_data": vlds_data,
            "topic_vlds": topic_vlds
        }
    )


def calculate_brand_vlds(df) -> dict:
    """Calculate VLDS metrics for a filtered brand dataset."""
    import pandas as pd

    if df.empty or len(df) < 5:
        return None

    total_posts = len(df)
    results = {"total_posts": total_posts}

    # Velocity - recent vs older activity
    if "created_at" in df.columns:
        df_copy = df.copy()
        df_copy["date"] = df_copy["created_at"].dt.date
        daily_counts = df_copy.groupby("date").size()

        if len(daily_counts) >= 2:
            recent = daily_counts.tail(2).mean()
            older = daily_counts.head(max(1, len(daily_counts) - 2)).mean()
            velocity = (recent / older) if older > 0 else 1.0
            velocity_score = min(velocity / 2.0, 1.0)
        else:
            velocity_score = 0.5

        results["velocity"] = round(velocity_score, 2)
        results["velocity_label"] = "Rising Fast" if velocity_score > 0.7 else "Stable" if velocity_score > 0.4 else "Declining"

        # Longevity - span of days
        unique_days = df_copy["date"].nunique()
        longevity_score = min(unique_days / 7.0, 1.0)
        results["longevity"] = round(longevity_score, 2)
        results["longevity_label"] = "Sustained" if longevity_score > 0.7 else "Moderate" if longevity_score > 0.4 else "Flash"

    # Density - concentration
    if "source" in df.columns:
        density_score = min(total_posts / 100.0, 1.0)
        results["density"] = round(density_score, 2)
        results["density_label"] = "Saturated" if density_score > 0.7 else "Moderate" if density_score > 0.3 else "White Space"

        # Scarcity - inverse of density
        results["scarcity"] = round(1.0 - density_score, 2)
        results["scarcity_label"] = "High Opportunity" if results["scarcity"] > 0.7 else "Some Opportunity" if results["scarcity"] > 0.4 else "Crowded"

    # Top emotions
    if "emotion_top_1" in df.columns:
        emotion_counts = df["emotion_top_1"].value_counts()
        top_emotions = []
        for emotion, count in emotion_counts.head(5).items():
            if pd.notna(emotion):
                top_emotions.append({
                    "emotion": emotion,
                    "count": int(count),
                    "percentage": round((count / total_posts) * 100, 1)
                })
        results["top_emotions_detailed"] = top_emotions

    return results


def calculate_global_vlds(df) -> dict:
    """Calculate global VLDS metrics from the full dataset."""
    import pandas as pd

    if df.empty or len(df) < 5:
        return None

    total_posts = len(df)
    results = {"total_posts": total_posts}

    if "created_at" not in df.columns:
        return None

    df_copy = df.copy()
    df_copy["date"] = df_copy["created_at"].dt.date
    daily_counts = df_copy.groupby("date").size()

    # Velocity - recent activity trend
    if len(daily_counts) >= 2:
        recent = daily_counts.tail(2).mean()
        older = daily_counts.head(max(1, len(daily_counts) - 2)).mean()
        velocity = (recent / older) if older > 0 else 1.0
        velocity_score = min(velocity / 2.0, 1.0)
    else:
        velocity_score = 0.5

    results["velocity"] = round(velocity_score, 2)
    results["velocity_label"] = "Rising Fast" if velocity_score > 0.7 else "Stable" if velocity_score > 0.4 else "Declining"

    # Longevity - span of days covered
    unique_days = df_copy["date"].nunique()
    longevity_score = min(unique_days / 7.0, 1.0)
    results["longevity"] = round(longevity_score, 2)
    results["longevity_label"] = "Sustained" if longevity_score > 0.7 else "Moderate" if longevity_score > 0.4 else "Flash"

    # Density - average posts per day
    avg_daily = daily_counts.mean()
    density_score = min(avg_daily / 50.0, 1.0)
    results["density"] = round(density_score, 2)
    results["density_label"] = "Saturated" if density_score > 0.7 else "Moderate" if density_score > 0.3 else "White Space"

    # Scarcity - opportunity space (inverse of density)
    results["scarcity"] = round(1.0 - density_score, 2)
    results["scarcity_label"] = "High Opportunity" if results["scarcity"] > 0.7 else "Some Opportunity" if results["scarcity"] > 0.4 else "Crowded"

    return results


def calculate_topic_vlds(df, top_n: int = 10) -> list:
    """
    Calculate VLDS metrics per topic for scatter chart.
    Returns list of topics with velocity, longevity, density scores.
    """
    import pandas as pd

    if df.empty or "topic" not in df.columns or "created_at" not in df.columns:
        return []

    df_copy = df.copy()
    df_copy["date"] = df_copy["created_at"].dt.date

    results = []
    topic_counts = df["topic"].value_counts()

    for topic in topic_counts.head(top_n).index:
        if pd.isna(topic):
            continue

        topic_df = df_copy[df_copy["topic"] == topic]
        if len(topic_df) < 2:
            continue

        daily_counts = topic_df.groupby("date").size()

        # Velocity
        if len(daily_counts) >= 2:
            recent = daily_counts.tail(2).mean()
            older = daily_counts.head(max(1, len(daily_counts) - 2)).mean()
            velocity = (recent / older) if older > 0 else 1.0
            velocity_score = min(velocity / 2.0, 1.0)
        else:
            velocity_score = 0.5

        # Longevity
        unique_days = topic_df["date"].nunique()
        longevity_score = min(unique_days / 7.0, 1.0)

        # Density (posts count normalized)
        density_score = min(len(topic_df) / 50.0, 1.0)

        results.append({
            "topic": topic,
            "count": int(topic_counts[topic]),
            "velocity": round(velocity_score * 100, 1),
            "longevity": round(longevity_score * 100, 1),
            "density": round(density_score * 100, 1)
        })

    return results


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


# ============================================
# Stock Data Endpoints
# ============================================

@router.get("/api/stock/search")
async def search_stock_ticker(
    brand: str = Query(..., description="Brand/company name to search"),
    user: dict = Depends(require_auth)
):
    """
    Search for a stock ticker symbol.
    """
    from app.services.stock import search_ticker

    ticker = await search_ticker(brand)
    if ticker:
        return {"ticker": ticker, "brand": brand}
    return {"ticker": None, "brand": brand, "message": "No ticker found"}


@router.get("/api/stock/quote")
async def get_stock_quote(
    ticker: str = Query(..., description="Stock ticker symbol"),
    user: dict = Depends(require_auth)
):
    """
    Get stock quote data.
    """
    from app.services.stock import fetch_stock_data

    data = await fetch_stock_data(ticker)
    if data:
        return data
    return {"error": f"No data available for {ticker}"}


@router.get("/api/stock/brand")
async def get_brand_stock(
    brand: str = Query(..., description="Brand/company name"),
    user: dict = Depends(require_auth)
):
    """
    Search for brand ticker and get stock data in one call.
    """
    from app.services.stock import get_brand_stock_data

    data = await get_brand_stock_data(brand)
    if data:
        return data
    return {"error": f"No stock data available for {brand}"}


@router.get("/api/stock/market")
async def get_market_index(
    user: dict = Depends(require_auth)
):
    """
    Get S&P 500 (SPY) as market index.
    """
    from app.services.stock import get_market_index

    data = await get_market_index()
    if data:
        return data
    return {"error": "Market index data unavailable"}


@router.get("/api/mood-vs-market")
async def get_mood_vs_market(
    request: Request,
    db: AsyncSession = Depends(get_db),
    mode: str = Query("strategic"),
    brand: Optional[str] = Query(None, description="Optional brand for stock comparison"),
    user: dict = Depends(require_auth)
):
    """
    Get mood vs market comparison data.
    """
    from app.services.stock import get_brand_stock_data, get_market_index, stock_change_to_mood_score

    view_config = VIEW_MODES.get(mode, VIEW_MODES["strategic"])
    df = await load_data(db, days=view_config["days"])

    # Get social mood
    world_mood = compute_world_mood(df)
    social_mood = world_mood["score"]

    # Get market data
    market_label = "S&P 500"
    market_mood = 50  # Neutral default

    if brand:
        stock_data = await get_brand_stock_data(brand)
        if stock_data:
            market_label = f"{stock_data['symbol']} Stock"
            market_mood = stock_change_to_mood_score(stock_data["change_percent"])
        else:
            # Fallback to market index
            market_data = await get_market_index()
            if market_data:
                market_mood = stock_change_to_mood_score(market_data["change_percent"])
    else:
        market_data = await get_market_index()
        if market_data:
            market_mood = stock_change_to_mood_score(market_data["change_percent"])

    # Calculate divergence
    divergence = abs(social_mood - market_mood)
    if divergence > 20:
        divergence_status = "high"
        divergence_message = "High divergence - opportunity or risk signal"
    elif divergence > 10:
        divergence_status = "moderate"
        divergence_message = "Moderate divergence - worth monitoring"
    else:
        divergence_status = "low"
        divergence_message = "Markets and mood aligned"

    return {
        "social_mood": social_mood,
        "market_mood": market_mood,
        "market_label": market_label,
        "divergence": divergence,
        "divergence_status": divergence_status,
        "divergence_message": divergence_message,
        "brand": brand
    }


# ============================================
# Ask Moodlight Chat Endpoint
# ============================================

@router.post("/api/chat")
async def chat_with_data(
    request: Request,
    db: AsyncSession = Depends(get_db),
    payload: dict = Body(...),
    user: dict = Depends(require_auth)
):
    """
    Chat with Moodlight - answer questions about the data.
    Uses the current data context to provide insights.
    """
    message = payload.get("message", "").strip().lower()

    if not message:
        return {"response": "Please ask me a question about the data."}

    # Load current data for context
    df = await load_data(db, days=30)

    if df.empty:
        return {"response": "No data is currently available. Try again later."}

    # Get context metrics
    world_mood = compute_world_mood(df)
    emotions = get_emotion_distribution(df)
    topics = get_topic_distribution(df)
    sources = get_source_distribution(df)

    # Simple pattern matching for common questions
    response = None

    # Mood/sentiment questions
    if any(word in message for word in ["mood", "sentiment", "feeling", "vibe", "pulse"]):
        if world_mood and world_mood.get("score") is not None:
            response = f"The current global mood score is {world_mood['score']}/100 ({world_mood['label']}). This is based on analysis of {len(df)} recent items."
        else:
            response = "Unable to calculate mood score from current data."

    # Trending/popular topics
    elif any(word in message for word in ["trending", "popular", "hot", "top topic", "what's happening"]):
        if topics:
            top_topics = [t["topic"] for t in topics[:5]]
            response = f"Top trending topics right now: {', '.join(top_topics)}. The #1 topic '{topics[0]['topic']}' accounts for {topics[0]['percentage']}% of discussions."
        else:
            response = "No topic data available."

    # Emotion questions
    elif any(word in message for word in ["emotion", "feel", "angry", "happy", "sad", "fear"]):
        if emotions:
            top_emotions = [f"{e['emotion']} ({e['percentage']}%)" for e in emotions[:5]]
            response = f"Top emotions in the data: {', '.join(top_emotions)}. The dominant emotion is '{emotions[0]['emotion']}'."
        else:
            response = "No emotion data available."

    # Source questions
    elif any(word in message for word in ["source", "where", "platform", "social media"]):
        if sources:
            source_list = [f"{s['display_name']} ({s['count']} items)" for s in sources[:5]]
            response = f"Data sources: {', '.join(source_list)}."
        else:
            response = "No source data available."

    # Stats/numbers
    elif any(word in message for word in ["how many", "count", "total", "stats", "statistics"]):
        response = f"Currently analyzing {len(df)} items from {len(sources) if sources else 0} sources. Top topic: {topics[0]['topic'] if topics else 'N/A'}. Dominant emotion: {emotions[0]['emotion'] if emotions else 'N/A'}."

    # Headlines
    elif any(word in message for word in ["headline", "news", "story", "stories"]):
        headlines = get_trending_headlines(df, limit=3)
        if headlines:
            headline_texts = [f"• {h['text'][:80]}..." for h in headlines]
            response = f"Top headlines:\n" + "\n".join(headline_texts)
        else:
            response = "No headlines available."

    # Brand mentions
    elif "brand" in message or "company" in message or "mention" in message:
        response = "To track a specific brand, use the Brand Tracking input in the sidebar. Enter a brand name to see its VLDS metrics and sentiment analysis."

    # Help
    elif any(word in message for word in ["help", "what can you", "how do i"]):
        response = "I can answer questions about: trending topics, emotions, mood/sentiment, sources, headlines, and statistics. Try asking 'What's trending?' or 'How's the mood today?'"

    # Default response
    if not response:
        response = f"Based on {len(df)} items analyzed: Global mood is {world_mood['score'] if world_mood.get('score') else 'N/A'}/100. Top topic: {topics[0]['topic'] if topics else 'N/A'}. Dominant emotion: {emotions[0]['emotion'] if emotions else 'N/A'}. Ask me about specific topics, emotions, or trends!"

    return {"response": response}
