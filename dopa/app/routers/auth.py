"""Oura OAuth authentication routes."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Event, Participant
from ..services.oura import OuraService, get_oura_service
from ..config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.get("/oura/authorize")
async def oura_authorize(
    participant_id: str,
    oura: OuraService = Depends(get_oura_service),
    db: Session = Depends(get_db),
):
    """Initiate Oura OAuth flow for a participant."""
    participant = db.query(Participant).filter(Participant.id == participant_id).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    # Use participant_id as state for callback verification
    auth_url = oura.get_authorization_url(state=participant_id)
    return RedirectResponse(url=auth_url)


@router.get("/oura/callback")
async def oura_callback(
    code: str = Query(...),
    state: str = Query(...),
    oura: OuraService = Depends(get_oura_service),
    db: Session = Depends(get_db),
):
    """Handle Oura OAuth callback."""
    # State contains participant_id
    participant = db.query(Participant).filter(Participant.id == state).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    try:
        # Exchange code for tokens
        token_data = await oura.exchange_code_for_token(code)

        # Store tokens
        participant.oura_access_token = token_data["access_token"]
        participant.oura_refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 86400)
        participant.oura_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        participant.consent_given = True

        db.commit()

        # Redirect back to opt-in page with success
        return RedirectResponse(
            url=f"{settings.app_url}/opt-in/{participant.event.opt_in_code}?success=true&participant={participant.id}"
        )

    except Exception as e:
        return RedirectResponse(
            url=f"{settings.app_url}/opt-in/{participant.event.opt_in_code}?error=auth_failed"
        )


@router.post("/oura/refresh/{participant_id}")
async def refresh_oura_token(
    participant_id: str,
    oura: OuraService = Depends(get_oura_service),
    db: Session = Depends(get_db),
):
    """Refresh Oura access token for a participant."""
    participant = db.query(Participant).filter(Participant.id == participant_id).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    if not participant.oura_refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token available")

    try:
        token_data = await oura.refresh_access_token(participant.oura_refresh_token)

        participant.oura_access_token = token_data["access_token"]
        if "refresh_token" in token_data:
            participant.oura_refresh_token = token_data["refresh_token"]
        expires_in = token_data.get("expires_in", 86400)
        participant.oura_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        db.commit()

        return {"status": "refreshed"}

    except Exception as e:
        raise HTTPException(status_code=400, detail="Token refresh failed")
