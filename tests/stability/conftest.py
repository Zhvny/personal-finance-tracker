import pytest
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@pytest.fixture(scope="session")
def market_api_url():
    """Base URL for the Finance Tracker API."""
    return "http://127.0.0.1:8444/api"


@pytest.fixture(scope="session")
def api_session():
    """A requests session with built-in retries for stability testing."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


@pytest.fixture
def bbca_ticker():
    """Standard ticker for testing."""
    return "BBCA.JK"
