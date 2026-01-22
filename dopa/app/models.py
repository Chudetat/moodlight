"""SQLAlchemy database models."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, Integer, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from .database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Event(Base):
    """Event where biometric data is collected."""
    __tablename__ = "events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # QR code and opt-in page
    opt_in_code = Column(String(12), unique=True, nullable=False)

    # Relationships
    participants = relationship("Participant", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Event {self.name}>"


class Participant(Base):
    """Event participant who opts in to share biometric data."""
    __tablename__ = "participants"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(36), ForeignKey("events.id"), nullable=False)

    # Optional display name (for anonymized reports)
    display_name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)

    # Oura OAuth tokens
    oura_access_token = Column(Text, nullable=True)
    oura_refresh_token = Column(Text, nullable=True)
    oura_token_expires_at = Column(DateTime, nullable=True)

    # Consent tracking
    opted_in_at = Column(DateTime, default=datetime.utcnow)
    consent_given = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    event = relationship("Event", back_populates="participants")
    heart_rate_data = relationship("HeartRateData", back_populates="participant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Participant {self.display_name or self.id}>"


class HeartRateData(Base):
    """Heart rate measurements from Oura ring."""
    __tablename__ = "heart_rate_data"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    participant_id = Column(String(36), ForeignKey("participants.id"), nullable=False)

    timestamp = Column(DateTime, nullable=False, index=True)
    bpm = Column(Integer, nullable=False)
    source = Column(String(50), default="oura")  # For future Apple Health support

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    participant = relationship("Participant", back_populates="heart_rate_data")

    def __repr__(self):
        return f"<HeartRateData {self.timestamp}: {self.bpm}bpm>"
