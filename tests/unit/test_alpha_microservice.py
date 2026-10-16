import sys
from pathlib import Path

import pytest

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from apps.api.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_liveness_endpoint(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert data["service"] == "alpha-microservice"

def test_info_endpoint(client):
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Alpha Microservice API"
    assert data["version"] == "2.1.1"

def test_config_endpoint(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "fx_rate" in data

def test_readiness_endpoint(client):
    response = client.get("/health/ready")
    assert response.status_code in (200, 503)
