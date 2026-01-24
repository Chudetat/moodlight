"""
Briefs Router - Strategic brief generation endpoints.
"""
from datetime import date
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, Brief
from app.routers.auth import require_auth
from app.services.tier import get_tier_config, can_generate_brief, increment_brief_count
from app.services.brief_generator import generate_strategic_brief, get_available_frameworks
from app.services.email import send_brief_email
from app.utils.constants import EMOTION_COLORS

router = APIRouter(prefix="/briefs", tags=["briefs"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def briefs_page(
    request: Request,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Strategic briefs page."""
    tier_config = get_tier_config(user.tier)
    can_generate = can_generate_brief(user)

    # Get user's brief history
    from sqlalchemy import select
    stmt = select(Brief).where(
        Brief.user_id == user.id
    ).order_by(Brief.created_at.desc()).limit(10)

    result = await db.execute(stmt)
    recent_briefs = result.scalars().all()

    # Calculate remaining briefs
    if tier_config["brief_limit"] == -1:
        briefs_remaining = "Unlimited"
    else:
        briefs_remaining = max(0, tier_config["brief_limit"] - user.briefs_used)

    return templates.TemplateResponse(
        "briefs.html",
        {
            "request": request,
            "user": user,
            "tier_config": tier_config,
            "can_generate": can_generate,
            "briefs_remaining": briefs_remaining,
            "recent_briefs": recent_briefs,
            "frameworks": get_available_frameworks(),
            "emotion_colors": EMOTION_COLORS,
        }
    )


@router.post("/generate", response_class=HTMLResponse)
async def generate_brief(
    request: Request,
    user_need: str = Form(...),
    send_email: bool = Form(False),
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Generate a strategic brief."""
    # Check if user can generate
    if not can_generate_brief(user):
        tier_config = get_tier_config(user.tier)
        return templates.TemplateResponse(
            "partials/brief_limit_reached.html",
            {
                "request": request,
                "tier": user.tier,
                "limit": tier_config["brief_limit"],
            }
        )

    try:
        # Generate the brief
        brief_content, frameworks_used = await generate_strategic_brief(
            user_need=user_need,
            db=db,
            days=30
        )

        # Save to database
        brief = Brief(
            user_id=user.id,
            prompt=user_need,
            content=brief_content,
            frameworks_used=frameworks_used
        )
        db.add(brief)

        # Increment brief count
        await increment_brief_count(user, db)

        await db.commit()
        await db.refresh(brief)

        # Send email if requested
        email_sent = False
        if send_email and user.email:
            email_sent = await send_brief_email(
                to_email=user.email,
                brief_content=brief_content,
                user_need=user_need,
                frameworks_used=frameworks_used
            )

        return templates.TemplateResponse(
            "partials/brief_result.html",
            {
                "request": request,
                "brief": brief,
                "brief_content": brief_content,
                "frameworks_used": frameworks_used,
                "email_sent": email_sent,
            }
        )

    except Exception as e:
        return templates.TemplateResponse(
            "partials/brief_error.html",
            {
                "request": request,
                "error": str(e),
            }
        )


@router.get("/{brief_id}", response_class=HTMLResponse)
async def view_brief(
    request: Request,
    brief_id: int,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """View a specific brief."""
    from sqlalchemy import select

    stmt = select(Brief).where(
        Brief.id == brief_id,
        Brief.user_id == user.id
    )
    result = await db.execute(stmt)
    brief = result.scalar_one_or_none()

    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")

    return templates.TemplateResponse(
        "brief_detail.html",
        {
            "request": request,
            "user": user,
            "brief": brief,
        }
    )


@router.post("/{brief_id}/email", response_class=HTMLResponse)
async def email_brief(
    request: Request,
    brief_id: int,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Email a brief to the user."""
    from sqlalchemy import select

    stmt = select(Brief).where(
        Brief.id == brief_id,
        Brief.user_id == user.id
    )
    result = await db.execute(stmt)
    brief = result.scalar_one_or_none()

    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")

    email_sent = await send_brief_email(
        to_email=user.email,
        brief_content=brief.content,
        user_need=brief.prompt,
        frameworks_used=brief.frameworks_used or []
    )

    return templates.TemplateResponse(
        "partials/email_status.html",
        {
            "request": request,
            "success": email_sent,
        }
    )
