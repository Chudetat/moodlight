"""Event management API routes."""
import secrets
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Event, Participant
from ..schemas import EventCreate, EventUpdate, EventResponse, EventDetail
from ..services.qr import QRService, get_qr_service
from ..config import get_settings

router = APIRouter(prefix="/api/events", tags=["events"])
settings = get_settings()


def generate_opt_in_code() -> str:
    """Generate a unique opt-in code for event QR codes."""
    return secrets.token_urlsafe(8)[:12]


@router.post("", response_model=EventResponse)
def create_event(event: EventCreate, db: Session = Depends(get_db)):
    """Create a new event."""
    db_event = Event(
        name=event.name,
        description=event.description,
        location=event.location,
        start_time=event.start_time,
        end_time=event.end_time,
        opt_in_code=generate_opt_in_code(),
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    return EventResponse(
        id=db_event.id,
        name=db_event.name,
        description=db_event.description,
        location=db_event.location,
        start_time=db_event.start_time,
        end_time=db_event.end_time,
        opt_in_code=db_event.opt_in_code,
        created_at=db_event.created_at,
        participant_count=0,
    )


@router.get("", response_model=List[EventResponse])
def list_events(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all events."""
    events = db.query(Event).offset(skip).limit(limit).all()
    return [
        EventResponse(
            id=e.id,
            name=e.name,
            description=e.description,
            location=e.location,
            start_time=e.start_time,
            end_time=e.end_time,
            opt_in_code=e.opt_in_code,
            created_at=e.created_at,
            participant_count=len(e.participants),
        )
        for e in events
    ]


@router.get("/{event_id}", response_model=EventDetail)
def get_event(event_id: str, db: Session = Depends(get_db), qr: QRService = Depends(get_qr_service)):
    """Get event details with QR code URL."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return EventDetail(
        id=event.id,
        name=event.name,
        description=event.description,
        location=event.location,
        start_time=event.start_time,
        end_time=event.end_time,
        opt_in_code=event.opt_in_code,
        created_at=event.created_at,
        participant_count=len(event.participants),
        qr_code_url=f"{settings.app_url}/api/events/{event.id}/qr",
        opt_in_url=qr.get_opt_in_url(event.opt_in_code),
    )


@router.patch("/{event_id}", response_model=EventResponse)
def update_event(event_id: str, event: EventUpdate, db: Session = Depends(get_db)):
    """Update an event."""
    db_event = db.query(Event).filter(Event.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")

    update_data = event.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_event, field, value)

    db.commit()
    db.refresh(db_event)

    return EventResponse(
        id=db_event.id,
        name=db_event.name,
        description=db_event.description,
        location=db_event.location,
        start_time=db_event.start_time,
        end_time=db_event.end_time,
        opt_in_code=db_event.opt_in_code,
        created_at=db_event.created_at,
        participant_count=len(db_event.participants),
    )


@router.delete("/{event_id}")
def delete_event(event_id: str, db: Session = Depends(get_db)):
    """Delete an event and all associated data."""
    db_event = db.query(Event).filter(Event.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")

    db.delete(db_event)
    db.commit()
    return {"status": "deleted"}


@router.get("/{event_id}/qr")
def get_event_qr(event_id: str, db: Session = Depends(get_db), qr: QRService = Depends(get_qr_service)):
    """Get QR code image for event opt-in page."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    qr_image = qr.generate_opt_in_qr(event.opt_in_code)
    return Response(content=qr_image, media_type="image/png")
