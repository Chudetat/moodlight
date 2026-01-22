"""Report generation API routes."""
from datetime import datetime, timedelta
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Event, Participant, HeartRateData
from ..schemas import EventReport, ParticipantResponse, HeartRatePoint, PeakMoment
from ..services.pdf import PDFReportService, get_pdf_service
from ..services.oura import OuraService, get_oura_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/{event_id}/sync-all")
async def sync_all_participants(
    event_id: str,
    db: Session = Depends(get_db),
    oura: OuraService = Depends(get_oura_service),
):
    """Sync heart rate data for all participants in an event."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    results = {"synced": 0, "failed": 0, "skipped": 0}

    for participant in event.participants:
        if not participant.oura_access_token:
            results["skipped"] += 1
            continue

        try:
            # Check and refresh token if needed
            if participant.oura_token_expires_at and participant.oura_token_expires_at < datetime.utcnow():
                if participant.oura_refresh_token:
                    token_data = await oura.refresh_access_token(participant.oura_refresh_token)
                    participant.oura_access_token = token_data["access_token"]
                    if "refresh_token" in token_data:
                        participant.oura_refresh_token = token_data["refresh_token"]
                    db.commit()
                else:
                    results["failed"] += 1
                    continue

            hr_data = await oura.get_heart_rate(
                participant.oura_access_token,
                event.start_time,
                event.end_time,
            )

            # Clear and store new data
            db.query(HeartRateData).filter(HeartRateData.participant_id == participant.id).delete()

            for point in hr_data:
                db_hr = HeartRateData(
                    participant_id=participant.id,
                    timestamp=datetime.fromisoformat(point["timestamp"].replace("Z", "+00:00")),
                    bpm=point["bpm"],
                    source="oura",
                )
                db.add(db_hr)

            db.commit()
            results["synced"] += 1

        except Exception:
            results["failed"] += 1

    return results


@router.get("/{event_id}/data")
def get_event_report_data(event_id: str, db: Session = Depends(get_db)):
    """Get aggregated report data for an event."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Get all heart rate data for the event
    hr_data = (
        db.query(HeartRateData)
        .join(Participant)
        .filter(Participant.event_id == event_id)
        .order_by(HeartRateData.timestamp)
        .all()
    )

    if not hr_data:
        return {
            "event": {
                "id": event.id,
                "name": event.name,
                "start_time": event.start_time,
                "end_time": event.end_time,
            },
            "participants": len(event.participants),
            "timeline": [],
            "peaks": [],
            "overall_avg_bpm": 0,
            "overall_max_bpm": 0,
        }

    # Aggregate by minute
    timeline = _aggregate_by_minute(hr_data)
    peaks = _find_peaks(timeline)

    all_bpm = [h.bpm for h in hr_data]

    return {
        "event": {
            "id": event.id,
            "name": event.name,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "location": event.location,
        },
        "participants": len(event.participants),
        "timeline": timeline,
        "peaks": peaks,
        "overall_avg_bpm": sum(all_bpm) / len(all_bpm),
        "overall_max_bpm": max(all_bpm),
    }


@router.get("/{event_id}/pdf")
def download_event_report_pdf(
    event_id: str,
    db: Session = Depends(get_db),
    pdf: PDFReportService = Depends(get_pdf_service),
):
    """Download event report as PDF."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Get all heart rate data
    hr_data = (
        db.query(HeartRateData)
        .join(Participant)
        .filter(Participant.event_id == event_id)
        .order_by(HeartRateData.timestamp)
        .all()
    )

    # Process data
    timeline = _aggregate_by_minute(hr_data) if hr_data else []
    peaks = _find_peaks(timeline) if timeline else []

    all_bpm = [h.bpm for h in hr_data] if hr_data else [0]
    overall_avg = sum(all_bpm) / len(all_bpm) if all_bpm else 0
    overall_max = max(all_bpm) if all_bpm else 0

    # Convert peaks to expected format
    peak_dicts = [
        {
            "timestamp": p["timestamp"],
            "avg_bpm": p["avg_bpm"],
            "description": f"Peak engagement ({p['avg_bpm']:.0f} BPM average)",
        }
        for p in peaks
    ]

    # Generate PDF
    pdf_bytes = pdf.generate_report(
        event_name=event.name,
        event_start=event.start_time,
        event_end=event.end_time,
        location=event.location,
        participant_count=len(event.participants),
        heart_rate_timeline=[{"timestamp": t["timestamp"], "bpm": t["avg_bpm"]} for t in timeline],
        peak_moments=peak_dicts,
        overall_avg_bpm=overall_avg,
        overall_max_bpm=overall_max,
    )

    filename = f"dopa_report_{event.name.replace(' ', '_')}_{event.start_time.strftime('%Y%m%d')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _aggregate_by_minute(hr_data: List[HeartRateData]) -> List[Dict[str, Any]]:
    """Aggregate heart rate data by minute."""
    if not hr_data:
        return []

    minute_buckets: Dict[datetime, List[int]] = {}

    for h in hr_data:
        # Round to minute
        minute = h.timestamp.replace(second=0, microsecond=0)
        if minute not in minute_buckets:
            minute_buckets[minute] = []
        minute_buckets[minute].append(h.bpm)

    return [
        {
            "timestamp": minute,
            "avg_bpm": sum(bpms) / len(bpms),
            "count": len(bpms),
        }
        for minute, bpms in sorted(minute_buckets.items())
    ]


def _find_peaks(timeline: List[Dict[str, Any]], threshold_percentile: float = 0.9) -> List[Dict[str, Any]]:
    """Find peak moments where heart rate was above threshold."""
    if not timeline:
        return []

    avg_bpms = [t["avg_bpm"] for t in timeline]
    sorted_bpms = sorted(avg_bpms)
    threshold_idx = int(len(sorted_bpms) * threshold_percentile)
    threshold = sorted_bpms[threshold_idx] if threshold_idx < len(sorted_bpms) else sorted_bpms[-1]

    peaks = [t for t in timeline if t["avg_bpm"] >= threshold]

    # Sort by BPM descending
    return sorted(peaks, key=lambda x: x["avg_bpm"], reverse=True)[:10]
