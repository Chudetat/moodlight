"""Participant management API routes."""
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Event, Participant, HeartRateData
from ..schemas import ParticipantCreate, ParticipantResponse, HeartRateResponse, HeartRatePoint
from ..services.oura import OuraService, get_oura_service
from ..config import get_settings

router = APIRouter(prefix="/api/participants", tags=["participants"])
settings = get_settings()


@router.post("/event/{opt_in_code}", response_model=ParticipantResponse)
def create_participant(
    opt_in_code: str,
    participant: ParticipantCreate,
    db: Session = Depends(get_db),
):
    """Register a new participant for an event via opt-in code."""
    event = db.query(Event).filter(Event.opt_in_code == opt_in_code).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    db_participant = Participant(
        event_id=event.id,
        display_name=participant.display_name,
        email=participant.email,
    )
    db.add(db_participant)
    db.commit()
    db.refresh(db_participant)

    return ParticipantResponse(
        id=db_participant.id,
        event_id=db_participant.event_id,
        display_name=db_participant.display_name,
        email=db_participant.email,
        opted_in_at=db_participant.opted_in_at,
        consent_given=db_participant.consent_given,
        has_oura_connected=bool(db_participant.oura_access_token),
    )


@router.get("/event/{event_id}", response_model=List[ParticipantResponse])
def list_event_participants(event_id: str, db: Session = Depends(get_db)):
    """List all participants for an event."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return [
        ParticipantResponse(
            id=p.id,
            event_id=p.event_id,
            display_name=p.display_name,
            email=p.email,
            opted_in_at=p.opted_in_at,
            consent_given=p.consent_given,
            has_oura_connected=bool(p.oura_access_token),
        )
        for p in event.participants
    ]


@router.get("/{participant_id}", response_model=ParticipantResponse)
def get_participant(participant_id: str, db: Session = Depends(get_db)):
    """Get participant details."""
    participant = db.query(Participant).filter(Participant.id == participant_id).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    return ParticipantResponse(
        id=participant.id,
        event_id=participant.event_id,
        display_name=participant.display_name,
        email=participant.email,
        opted_in_at=participant.opted_in_at,
        consent_given=participant.consent_given,
        has_oura_connected=bool(participant.oura_access_token),
    )


@router.delete("/{participant_id}")
def delete_participant(participant_id: str, db: Session = Depends(get_db)):
    """Delete a participant and their data (for GDPR compliance)."""
    participant = db.query(Participant).filter(Participant.id == participant_id).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    db.delete(participant)
    db.commit()
    return {"status": "deleted"}


@router.post("/{participant_id}/sync")
async def sync_heart_rate(
    participant_id: str,
    db: Session = Depends(get_db),
    oura: OuraService = Depends(get_oura_service),
):
    """Sync heart rate data from Oura for a participant."""
    participant = db.query(Participant).filter(Participant.id == participant_id).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    if not participant.oura_access_token:
        raise HTTPException(status_code=400, detail="Oura not connected")

    event = participant.event

    # Check if token needs refresh
    if participant.oura_token_expires_at and participant.oura_token_expires_at < datetime.utcnow():
        if participant.oura_refresh_token:
            token_data = await oura.refresh_access_token(participant.oura_refresh_token)
            participant.oura_access_token = token_data["access_token"]
            if "refresh_token" in token_data:
                participant.oura_refresh_token = token_data["refresh_token"]
            db.commit()
        else:
            raise HTTPException(status_code=401, detail="Token expired, reconnect Oura")

    try:
        # Fetch heart rate data for event duration
        hr_data = await oura.get_heart_rate(
            participant.oura_access_token,
            event.start_time,
            event.end_time,
        )

        # Clear existing data and store new
        db.query(HeartRateData).filter(HeartRateData.participant_id == participant_id).delete()

        for point in hr_data:
            db_hr = HeartRateData(
                participant_id=participant_id,
                timestamp=datetime.fromisoformat(point["timestamp"].replace("Z", "+00:00")),
                bpm=point["bpm"],
                source="oura",
            )
            db.add(db_hr)

        db.commit()

        return {"status": "synced", "points": len(hr_data)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/{participant_id}/heart-rate", response_model=HeartRateResponse)
def get_participant_heart_rate(participant_id: str, db: Session = Depends(get_db)):
    """Get heart rate data for a participant."""
    participant = db.query(Participant).filter(Participant.id == participant_id).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    hr_data = (
        db.query(HeartRateData)
        .filter(HeartRateData.participant_id == participant_id)
        .order_by(HeartRateData.timestamp)
        .all()
    )

    if not hr_data:
        return HeartRateResponse(
            participant_id=participant_id,
            data=[],
        )

    bpm_values = [h.bpm for h in hr_data]

    return HeartRateResponse(
        participant_id=participant_id,
        data=[
            HeartRatePoint(
                timestamp=h.timestamp,
                bpm=h.bpm,
                source=h.source,
            )
            for h in hr_data
        ],
        avg_bpm=sum(bpm_values) / len(bpm_values),
        max_bpm=max(bpm_values),
        min_bpm=min(bpm_values),
    )
