"""Shared fixtures for Certus-Trust tests."""

import pytest
import requests


@pytest.fixture(scope="session")
def http_session():
    """HTTP session for smoke/integration tests."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    yield session
    session.close()


@pytest.fixture(scope="session")
def request_timeout() -> int:
    """Default timeout for HTTP requests in tests."""
    return 60
