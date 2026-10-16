import sys
from pathlib import Path

from fastapi.testclient import TestClient

# Setup paths
_HERE = Path(__file__).resolve().parent
_GUI = _HERE.parent
_PROJECT_ROOT = _GUI.parent

if str(_GUI) not in sys.path: sys.path.insert(0, str(_GUI))
if str(_PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(_PROJECT_ROOT))

from api_server import app

client = TestClient(app)

def test_favorites_lifecycle():
    # 1. Clear existing for a specific test ticker
    test_ticker = "TEST_TICKER"
    client.delete(f"/api/stocks/favorites/{test_ticker}")

    # 2. Get favorites - should not contain test_ticker
    response = client.get("/api/stocks/favorites")
    assert response.status_code == 200
    favorites = response.json()
    assert test_ticker not in favorites

    # 3. Add favorite
    response = client.post(f"/api/stocks/favorites/{test_ticker}")
    assert response.status_code == 200
    assert response.json() == {"status": "success", "ticker": test_ticker}

    # 4. Get favorites - should contain test_ticker
    response = client.get("/api/stocks/favorites")
    assert response.status_code == 200
    favorites = response.json()
    assert test_ticker in favorites

    # 5. Add duplicate - should not fail (ON CONFLICT DO NOTHING)
    response = client.post(f"/api/stocks/favorites/{test_ticker}")
    assert response.status_code == 200

    # 6. Delete favorite
    response = client.delete(f"/api/stocks/favorites/{test_ticker}")
    assert response.status_code == 200
    assert response.json() == {"status": "success", "ticker": test_ticker}

    # 7. Get favorites - should not contain test_ticker
    response = client.get("/api/stocks/favorites")
    assert response.status_code == 200
    favorites = response.json()
    assert test_ticker not in favorites

def test_get_favorites_structure():
    response = client.get("/api/stocks/favorites")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
