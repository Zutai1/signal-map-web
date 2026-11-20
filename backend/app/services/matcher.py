"""Location matching service."""
import hashlib
import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ..models.database import Location, Fingerprint, Scan, Agent


def fingerprint_hash(entries):
    data = json.dumps(entries, sort_keys=True).encode()
    return hashlib.md5(data).hexdigest()[:16]


def similarity(fp1, fp2):
    if not fp1 or not fp2:
        return 0.0
    bssids1 = {n["bssid"]: n.get("signal", 0) for n in fp1}
    bssids2 = {n["bssid"]: n.get("signal", 0) for n in fp2}
    shared = set(bssids1.keys()) & set(bssids2.keys())
    if not shared:
        return 0.0
    union = set(bssids1.keys()) | set(bssids2.keys())
    jaccard = len(shared) / len(union) if union else 0.0
    signal_diff = sum(abs(bssids1[b] - bssids2[b]) for b in shared)
    signal_sim = 1.0 - (signal_diff / (len(shared) * 100.0)) if shared else 0.0
    signal_sim = max(0.0, signal_sim)
    return (jaccard * 0.6 + signal_sim * 0.4)


def create_fingerprint(entries):
    sorted_nets = sorted(entries, key=lambda x: x.get("signal", 0), reverse=True)
    return sorted_nets[:10]


def match_location(db: Session, incoming: list):
    best_match = None
    best_sim = 0.0
    for loc in db.query(Location).all():
        for fp in loc.fingerprints:
            sim = similarity(incoming, fp.entries)
            if sim > best_sim:
                best_sim = sim
                best_match = loc
    return best_match, round(best_sim, 3)


def record_scan(db: Session, data: dict):
    agent_id = data.get("agent_id", "android")
    radio = data.get("radio", "wifi")
    fingerprint = data.get("fingerprint", [])
    label = data.get("label")
    gps = data.get("gps")

    incoming = create_fingerprint(fingerprint)
    best_match, best_sim = None, 0.0
    if incoming:
        best_match, best_sim = match_location(db, incoming)

    method = "none"
    lat = lon = None
    confidence = 0.0
    location_name = "unknown"

    if gps and gps.get("lat") is not None and (gps.get("age_s", 999) or 999) < 300:
        lat, lon, method, confidence = gps["lat"], gps["lon"], "gps", 0.95
        location_name = best_match.label if best_match and best_sim > 0.5 else "gps-fix"
    elif best_match and best_sim > 0.3:
        location_name, confidence, method = best_match.label, best_sim, "fingerprint"
        lat, lon = best_match.lat, best_match.lon
    else:
        location_name = "unknown"

    if label and incoming:
        loc = db.query(Location).filter(Location.label == label).first()
        if not loc:
            loc = Location(label=label, lat=lat, lon=lon)
            db.add(loc)
            db.flush()
        fp = Fingerprint(location_id=loc.id, radio=radio, entries=incoming)
        db.add(fp)
        loc.scan_count += 1
        loc.last_seen = datetime.now(timezone.utc)
        if lat is not None:
            loc.lat, loc.lon = lat, lon
        if radio == "wifi":
            loc.has_wifi = True
        elif radio == "ble":
            loc.has_ble = True
        elif radio == "cell":
            loc.has_cell = True
        db.flush()

    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        agent = Agent(agent_id=agent_id)
        db.add(agent)
    agent.location_id = best_match.id if best_match else None
    agent.confidence = confidence
    agent.lat = lat
    agent.lon = lon
    agent.method = method
    agent.radio = radio
    agent.last_seen = datetime.now(timezone.utc)
    agent.fingerprint_hash = fingerprint_hash(incoming) if incoming else None

    scan = Scan(
        agent_id=agent_id, radio=radio,
        matched_location_id=best_match.id if best_match else None,
        confidence=confidence, lat=lat, lon=lon, method=method,
        fingerprint_hash=fingerprint_hash(incoming) if incoming else None,
        raw_fingerprint=incoming, gps=gps,
    )
    db.add(scan)
    db.commit()

    return {
        "status": "recorded",
        "agent_id": agent_id,
        "radio": radio,
        "location": location_name,
        "confidence": round(confidence, 3),
        "lat": lat,
        "lon": lon,
        "method": method,
        "label_stored": label is not None,
    }
