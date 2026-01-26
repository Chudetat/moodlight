"""
Authentication router - login, logout, and session management.
Replaces streamlit_authenticator with JWT + httponly cookies.
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import auth as auth_service
from app.services.tier import get_user_tier, get_tier_display_name

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

# Cookie settings
COOKIE_NAME = "moodlight_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days
SESSION_COOKIE_NAME = "moodlight_session"


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[dict]:
    """
    Dependency to get the current authenticated user from JWT cookie.
    Returns None if not authenticated (doesn't raise exception).
    """
    token = request.cookies.get(COOKIE_NAME)
    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    if not token or not session_id:
        return None

    # Decode JWT
    payload = auth_service.decode_access_token(token)
    if not payload:
        return None

    username = payload.get("sub")
    user_id = payload.get("user_id")

    if not username or not user_id:
        return None

    # Validate session (single-session enforcement)
    is_valid = await auth_service.validate_session(db, user_id, session_id)
    if not is_valid:
        return None

    # Get full user object
    user = await auth_service.get_user_by_id(db, user_id)
    if not user:
        return None

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "tier": user.tier,
        "name": user.username,  # For display
    }


async def require_auth(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Dependency that requires authentication.
    Raises HTTPException if not authenticated.
    """
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    error: Optional[str] = None,
    next: Optional[str] = None
):
    """
    Render the login page.
    Redirects to dashboard if already logged in.
    """
    # Check if already authenticated
    user = await get_current_user(request, db)
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "error": error,
            "next": next or "/dashboard"
        }
    )


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/dashboard")
):
    """
    Handle login form submission.
    Sets JWT token and session cookies on success.
    """
    # Authenticate user
    user = await auth_service.authenticate_user(db, username, password)

    if not user:
        # Return to login page with error
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": "Invalid username or password",
                "next": next
            },
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    # Create session (invalidates previous sessions)
    session_id = await auth_service.create_session(
        db,
        user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )

    # Create JWT token
    token = auth_service.create_access_token({
        "sub": user.username,
        "user_id": user.id,
        "email": user.email,
        "session_id": session_id
    })

    # Set cookies and redirect
    redirect_response = RedirectResponse(url=next, status_code=status.HTTP_302_FOUND)

    redirect_response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False  # Set to True in production with HTTPS
    )

    redirect_response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False
    )

    return redirect_response


@router.get("/logout")
@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Log out the current user.
    Invalidates session and clears cookies.
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    if session_id:
        await auth_service.invalidate_session(db, session_id)

    # Clear cookies and redirect to login
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(COOKIE_NAME)
    response.delete_cookie(SESSION_COOKIE_NAME)

    return response


@router.get("/me")
async def get_me(
    user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user info (JSON API endpoint).
    """
    tier_info = await get_user_tier(db, user["username"])

    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "tier": user["tier"],
        "tier_display": get_tier_display_name(user["tier"]),
        "briefs_used": tier_info["briefs_used"],
        "briefs_limit": tier_info.get("briefs_limit", 5)
    }


@router.get("/session-check")
async def check_session(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    HTMX endpoint to check if session is still valid.
    Returns 401 if session was invalidated (logged in elsewhere).
    Used for real-time session enforcement.
    """
    user = await get_current_user(request, db)

    if not user:
        # Return HX-Redirect header to trigger client-side redirect
        response = Response(status_code=status.HTTP_401_UNAUTHORIZED)
        response.headers["HX-Redirect"] = "/auth/login?error=session_expired"
        return response

    return {"status": "valid", "username": user["username"]}


@router.get("/kicked", response_class=HTMLResponse)
async def kicked_page(request: Request):
    """
    Page shown when user is logged out due to another login.
    """
    return templates.TemplateResponse(
        "auth/kicked.html",
        {"request": request}
    )
