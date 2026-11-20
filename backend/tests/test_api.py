"""Tests for the Signal Map Web API."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app, get_db
from app.models.database import Base

TEST_DB_URL = "sqlite:///./test_signal_map_web.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


client = TestClient(app)


class TestHealth:
    def test_health(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestLocations:
    def test_create_and_list(self):
        client.post("/api/locations", params={"label": "home", "lat": 34.0, "lon": -118.0})
        resp = client.get("/api/locations")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["label"] == "home"

    def test_get_location(self):
        client.post("/api/locations", params={"label": "office", "lat": 34.1, "lon": -118.1})
        resp = client.get("/api/locations/office")
        assert resp.status_code == 200
        assert resp.json()["label"] == "office"

    def test_location_not_found(self):
        resp = client.get("/api/locations/nonexistent")
        assert resp.status_code == 404

    def test_duplicate_location(self):
        client.post("/api/locations", params={"label": "dup", "lat": 34.0, "lon": -118.0})
        resp = client.post("/api/locations", params={"label": "dup", "lat": 34.0, "lon": -118.0})
        assert resp.status_code == 409


class TestScan:
    def test_scan_with_gps(self):
        resp = client.post("/api/scan", json={
            "agent_id": "test",
            "radio": "wifi",
            "fingerprint": [{"bssid": "aa:bb:cc:00:00:01", "signal": -55}],
            "gps": {"lat": 34.0, "lon": -118.0, "accuracy": 10, "age_s": 5}
        })
        assert resp.status_code == 200
        assert resp.json()["method"] == "gps"

    def test_scan_matches_location(self):
        client.post("/api/locations", params={"label": "home", "lat": 34.0, "lon": -118.0})
        # Add fingerprint
        from app.models.database import Location, Fingerprint
        from app.main import SessionLocal
        db = TestSessionLocal()
        loc = db.query(Location).filter(Location.label == "home").first()
        db.add(Fingerprint(location_id=loc.id, radio="wifi", entries=[{"bssid": "aa:bb:cc:00:00:01", "signal": -55}]))
        db.commit()
        db.close()

        resp = client.post("/api/scan", json={
            "agent_id": "test",
            "radio": "wifi",
            "fingerprint": [{"bssid": "aa:bb:cc:00:00:01", "signal": -55}]
        })
        assert resp.status_code == 200
        assert resp.json()["location"] == "home"

    def test_scan_unknown(self):
        resp = client.post("/api/scan", json={
            "agent_id": "test",
            "radio": "wifi",
            "fingerprint": [{"bssid": "zz:zz:zz:zz:zz:zz", "signal": -80}]
        })
        assert resp.status_code == 200
        assert resp.json()["location"] == "unknown"


class TestStats:
    def test_stats(self):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "known_locations" in data
        assert "total_scans" in data
        assert "total_agents" in data
        assert "total_fingerprints" in data


class TestAgents:
    def test_agents_empty(self):
        resp = client.get("/api/agents")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_agent_registered_after_scan(self):
        client.post("/api/scan", json={
            "agent_id": "test-agent",
            "radio": "wifi",
            "fingerprint": [{"bssid": "aa:bb:cc:00:00:01", "signal": -55}],
            "gps": {"lat": 34.0, "lon": -118.0, "accuracy": 10, "age_s": 5}
        })
        resp = client.get("/api/agents")
        assert resp.status_code == 200
        agents = resp.json()
        assert len(agents) == 1
        assert agents[0]["agent_id"] == "test-agent"
        assert agents[0]["method"] == "gps"
