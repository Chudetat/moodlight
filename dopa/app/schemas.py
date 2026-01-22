"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


# Event schemas
class EventCreate(BaseModel):
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: datetime
    end_time: datetime


class EventUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class EventResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    location: Optional[str]
    start_time: datetime
    end_time: datetime
    opt_in_code: str
    created_at: datetime
    participant_count: int = 0

    class Config:
        from_attributes = True


class EventDetail(EventResponse):
    qr_code_url: str
    opt_in_url: str


# Participant schemas
class ParticipantCreate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[EmailStr] = None


class ParticipantResponse(BaseModel):
    id: str
    event_id: str
    display_name: Optional[str]
    email: Optional[str]
    opted_in_at: datetime
    consent_given: bool
    has_oura_connected: bool = False

    class Config:
        from_attributes = True


# Heart rate schemas
class HeartRatePoint(BaseModel):
    timestamp: datetime
    bpm: int
    source: str = "oura"


class HeartRateResponse(BaseModel):
    participant_id: str
    data: List[HeartRatePoint]
    avg_bpm: Optional[float] = None
    max_bpm: Optional[int] = None
    min_bpm: Optional[int] = None


# Report schemas
class PeakMoment(BaseModel):
    timestamp: datetime
    avg_bpm: float
    participant_count: int
    description: Optional[str] = None


class EventReport(BaseModel):
    event: EventResponse
    participants: List[ParticipantResponse]
    timeline: List[HeartRatePoint]
    peaks: List[PeakMoment]
    overall_avg_bpm: float
    overall_max_bpm: int


# OAuth schemas
class OuraAuthResponse(BaseModel):
    auth_url: str


class OuraTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
