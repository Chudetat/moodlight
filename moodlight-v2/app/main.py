"""
Moodlight v2 - FastAPI + HTMX Application
Main entry point and app configuration.
Version: 2.0.3 - Debug startup
"""
import sys
print("=== MOODLIGHT STARTUP ===", flush=True)
print(f"Python version: {sys.version}", flush=True)

try:
    from contextlib import asynccontextmanager
    print("1. asynccontextmanager imported", flush=True)

    from fastapi import FastAPI, Request
    from fastapi.responses import RedirectResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    print("2. FastAPI imports done", flush=True)

    from app.config import get_settings
    print("3. config imported", flush=True)

    from app.database import init_db, close_db
    print("4. database imported", flush=True)

    from app.routers import auth, dashboard, headlines, markets, brands, briefs, webhooks
    print("5. routers imported", flush=True)

    settings = get_settings()
    print(f"6. settings loaded, db_url exists: {bool(settings.database_url)}", flush=True)
except Exception as e:
    print(f"STARTUP ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()
    raise


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
app.include_router(webhooks.router)


# ============================================
# Root routes
# ============================================

@app.get("/")
async def root():
    """Root route - redirect to login page."""
    return RedirectResponse(url="/auth/login", status_code=302)


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway/monitoring."""
    return {"status": "healthy", "app": settings.app_name, "version": "2.0.2"}


@app.get("/test")
async def test_route():
    """Test route to verify deployment."""
    return {"test": "success", "version": "2.0.2"}


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
