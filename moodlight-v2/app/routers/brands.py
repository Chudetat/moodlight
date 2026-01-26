"""
Brands router - Brand analysis with VLDS metrics.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Request, Query, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.auth import get_current_user, require_auth
from app.services.tier import get_user_tier, get_tier_display_name, get_brief_limit, has_feature_access
from app.services.data_loader import load_data, compute_world_mood, get_emotion_distribution, get_topic_distribution
from app.services.vlds import calculate_brand_vlds, get_vlds_summary
from app.utils.constants import VIEW_MODES, EMOTION_COLORS

router = APIRouter(prefix="/brands", tags=["brands"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def brands_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    brand: Optional[str] = None,
    mode: str = "strategic"
):
    """
    Render the brand analysis page.
    """
    user = await get_current_user(request, db)
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/auth/login", status_code=302)

    tier_info = await get_user_tier(db, user["username"])
    brief_limit = get_brief_limit(tier_info["tier"], tier_info["extra_briefs_addon"])

    # Check feature access
    can_use_brand_focus = has_feature_access(tier_info["tier"], "brand_focus")

    view_config = VIEW_MODES.get(mode, VIEW_MODES["strategic"])
    days = view_config["days"]

    # Load base data
    df = await load_data(db, days=days)

    brand_data = None
    vlds = None
    filtered_df = df

    if brand and can_use_brand_focus:
        # Filter data for brand
        brand_lower = brand.lower()
        filtered_df = df[
            df["text"].str.lower().str.contains(brand_lower, na=False)
        ]

        if not filtered_df.empty:
            brand_data = {
                "name": brand,
                "mention_count": len(filtered_df),
                "world_mood": compute_world_mood(filtered_df),
                "emotions": get_emotion_distribution(filtered_df),
                "topics": get_topic_distribution(filtered_df)
            }

            # Calculate VLDS
            vlds = calculate_brand_vlds(filtered_df)

    return templates.TemplateResponse(
        "brands.html",
        {
            "request": request,
            "user": user,
            "tier_display": get_tier_display_name(user["tier"]),
            "briefs_used": tier_info["briefs_used"],
            "briefs_remaining": brief_limit - tier_info["briefs_used"],
            "view_mode": mode,
            "view_modes": VIEW_MODES,
            "brand": brand,
            "brand_data": brand_data,
            "vlds": vlds,
            "can_use_brand_focus": can_use_brand_focus,
            "emotion_colors": EMOTION_COLORS,
            "total_items": len(df)
        }
    )


@router.post("/analyze", response_class=HTMLResponse)
async def analyze_brand(
    request: Request,
    db: AsyncSession = Depends(get_db),
    brand: str = Form(...),
    mode: str = Form("strategic"),
    user: dict = Depends(require_auth)
):
    """
    Analyze a brand and return results partial.
    """
    tier_info = await get_user_tier(db, user["username"])

    if not has_feature_access(tier_info["tier"], "brand_focus"):
        return templates.TemplateResponse(
            "partials/upgrade_required.html",
            {
                "request": request,
                "feature": "Brand Focus",
                "required_tier": "Pro"
            }
        )

    view_config = VIEW_MODES.get(mode, VIEW_MODES["strategic"])
    df = await load_data(db, days=view_config["days"])

    # Filter for brand
    brand_lower = brand.lower()
    filtered_df = df[
        df["text"].str.lower().str.contains(brand_lower, na=False)
    ]

    if filtered_df.empty:
        return templates.TemplateResponse(
            "partials/brand_no_results.html",
            {
                "request": request,
                "brand": brand
            }
        )

    brand_data = {
        "name": brand,
        "mention_count": len(filtered_df),
        "world_mood": compute_world_mood(filtered_df),
        "emotions": get_emotion_distribution(filtered_df),
        "topics": get_topic_distribution(filtered_df)
    }

    vlds = calculate_brand_vlds(filtered_df)

    return templates.TemplateResponse(
        "partials/brand_results.html",
        {
            "request": request,
            "brand_data": brand_data,
            "vlds": vlds,
            "emotion_colors": EMOTION_COLORS
        }
    )


@router.get("/api/vlds")
async def get_vlds_api(
    db: AsyncSession = Depends(get_db),
    brand: str = Query(...),
    mode: str = Query("strategic"),
    user: dict = Depends(require_auth)
):
    """
    Get VLDS metrics for a brand as JSON.
    """
    tier_info = await get_user_tier(db, user["username"])

    if not has_feature_access(tier_info["tier"], "brand_focus"):
        return {
            "error": "Feature requires Pro tier",
            "upgrade_url": "/upgrade"
        }

    view_config = VIEW_MODES.get(mode, VIEW_MODES["strategic"])
    df = await load_data(db, days=view_config["days"])

    brand_lower = brand.lower()
    filtered_df = df[
        df["text"].str.lower().str.contains(brand_lower, na=False)
    ]

    if filtered_df.empty:
        return {
            "brand": brand,
            "error": "No mentions found",
            "mention_count": 0
        }

    vlds = calculate_brand_vlds(filtered_df)

    return {
        "brand": brand,
        "mention_count": len(filtered_df),
        "vlds": vlds,
        "summary": get_vlds_summary(vlds) if vlds else None
    }
