"""Dopa - Biometric Event Measurement Platform."""
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
import os

from .database import get_db, init_db
from .models import Event, Participant
from .config import get_settings
from .routers import events, auth, participants, reports

settings = get_settings()

app = FastAPI(
    title="Dopa",
    description="Biometric Event Measurement Platform - Measure collective emotional engagement through heart rate data",
    version="0.1.0",
)

# Setup templates
templates_path = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_path)

# Setup static files
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# Include routers
app.include_router(events.router)
app.include_router(auth.router)
app.include_router(participants.router)
app.include_router(reports.router)


@app.on_event("startup")
def startup():
    """Initialize database on startup."""
    init_db()


@app.get("/", response_class=HTMLResponse)
async def root():
    """API root - redirect to docs."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dopa - Biometric Event Measurement</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                min-height: 100vh;
                margin: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
            }
            .container {
                text-align: center;
                padding: 2rem;
            }
            h1 {
                font-size: 4rem;
                margin-bottom: 0.5rem;
                background: linear-gradient(135deg, #e94560, #ff6b6b);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            p {
                font-size: 1.25rem;
                color: #a0a0a0;
                margin-bottom: 2rem;
            }
            .links a {
                display: inline-block;
                padding: 0.75rem 1.5rem;
                margin: 0.5rem;
                background: #e94560;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                transition: transform 0.2s, background 0.2s;
            }
            .links a:hover {
                background: #ff6b6b;
                transform: translateY(-2px);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Dopa</h1>
            <p>Biometric Event Measurement Platform</p>
            <div class="links">
                <a href="/docs">API Documentation</a>
                <a href="/redoc">ReDoc</a>
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/opt-in/{opt_in_code}", response_class=HTMLResponse)
async def opt_in_page(
    request: Request,
    opt_in_code: str,
    success: bool = False,
    error: str = None,
    participant: str = None,
    db: Session = Depends(get_db),
):
    """Display opt-in page for an event."""
    event = db.query(Event).filter(Event.opt_in_code == opt_in_code).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return templates.TemplateResponse(
        "opt_in.html",
        {
            "request": request,
            "event": event,
            "opt_in_code": opt_in_code,
            "app_url": settings.app_url,
            "success": success,
            "error": error,
            "participant_id": participant,
        },
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "dopa"}
