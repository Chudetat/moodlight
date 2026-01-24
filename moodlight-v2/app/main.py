"""
Moodlight v2 - FastAPI + HTMX Application
Main entry point and app configuration.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import init_db, close_db
from app.routers import auth, dashboard, headlines, markets, brands, briefs

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Cultural Intelligence Platform",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(headlines.router)
app.include_router(markets.router)
app.include_router(brands.router)
app.include_router(briefs.router)


# ============================================
# Root routes
# ============================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root route - redirect to dashboard or login."""
    from app.routers.auth import get_current_user
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        user = await get_current_user(request, db)

    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/auth/login", status_code=302)


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway/monitoring."""
    return {"status": "healthy", "app": settings.app_name, "version": "2.0.0"}


# ============================================
# Error handlers
# ============================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 page."""
    return templates.TemplateResponse(
        "errors/404.html",
        {"request": request},
        status_code=404
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    """Custom 500 page."""
    return templates.TemplateResponse(
        "errors/500.html",
        {"request": request},
        status_code=500
    )
