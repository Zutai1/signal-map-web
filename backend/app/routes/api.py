"""API routes for the Signal Map Web service."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
import hashlib, json

from ..main import get_db, manager
from ..models.database import Location, Fingerprint, Scan, Agent
from ..services.matcher import record_scan

router = APIRouter()


class ScanRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=100)
    radio: str = Field(default="wifi", pattern="^(wifi|ble|cell)$")
    fingerprint: list = Field(default=[])
    label: Optional[str] = Field(default=None, max_length=100)
    gps: Optional[dict] = None


class LocationResponse(BaseModel):
    id: int
    label: str
    lat: Optional[float]
    lon: Optional[float]
    scan_count: int
    has_wifi: bool
    has_ble: bool
    has_cell: bool
    first_seen: datetime
    last_seen: datetime

    class Config:
        from_attributes = True


@router.post("/scan")
async def scan(request: ScanRequest, db: Session = Depends(get_db)):
    result = record_scan(db, request.model_dump())
    await manager.broadcast({"type": "scan", "data": result})
    return result


@router.get("/locations")
def list_locations(db: Session = Depends(get_db), skip: int = 0, limit: int = 100):
    locations = db.query(Location).offset(skip).limit(limit).all()
    return [LocationResponse.model_validate(loc) for loc in locations]


@router.get("/locations/{label}")
def get_location(label: str, db: Session = Depends(get_db)):
    loc = db.query(Location).filter(Location.label == label).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    return LocationResponse.model_validate(loc)


@router.post("/locations")
def create_location(label: str, lat: Optional[float] = None, lon: Optional[float] = None,
                   db: Session = Depends(get_db)):
    existing = db.query(Location).filter(Location.label == label).first()
    if existing:
        raise HTTPException(status_code=409, detail="Location already exists")
    loc = Location(label=label, lat=lat, lon=lon)
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return LocationResponse.model_validate(loc)


@router.get("/agents")
def list_agents(db: Session = Depends(get_db)):
    agents = db.query(Agent).all()
    return [
        {
            "agent_id": a.agent_id,
            "location": a.location.label if a.location else "unknown",
            "confidence": a.confidence,
            "lat": a.lat,
            "lon": a.lon,
            "method": a.method,
            "radio": a.radio,
            "last_seen": a.last_seen.isoformat() if a.last_seen else None,
        }
        for a in agents
    ]


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    return {
        "known_locations": db.query(Location).count(),
        "total_scans": db.query(Scan).count(),
        "total_agents": db.query(Agent).count(),
        "total_fingerprints": db.query(Fingerprint).count(),
    }


@router.get("/health")
def health():
    return {"status": "ok", "service": "signal-map-web"}
