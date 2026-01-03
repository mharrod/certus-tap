"""Shared fixtures for Certus-Assurance tests."""

from pathlib import Path
from typing import Any

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


@pytest.fixture
def sample_artifacts_path() -> Path:
    """Path to sample scan artifacts for testing."""
    return Path("samples/non-repudiation/scan-artifacts")


@pytest.fixture
def mock_scan_request() -> dict[str, Any]:
    """Sample scan request payload."""
    return {
        "workspace_id": "test-workspace",
        "component_id": "test-component",
        "repository_url": "https://github.com/test/repo.git",
        "branch": "main",
        "commit": "abc123",
        "manifest": {
            "profile": "light",
            "tools": ["bandit", "semgrep", "trivy"],
        },
    }


@pytest.fixture
def mock_manifest() -> dict[str, Any]:
    """Sample manifest configuration."""
    return {
        "version": "v1",
        "profile": "light",
        "metadata": {
            "name": "test-manifest",
            "description": "Test manifest for unit tests",
        },
        "tools": [
            {
                "name": "bandit",
                "enabled": True,
                "config": {"severity": "medium"},
            },
            {
                "name": "semgrep",
                "enabled": True,
                "config": {"rules": ["python"]},
            },
            {
                "name": "trivy",
                "enabled": True,
                "config": {"severity": ["HIGH", "CRITICAL"]},
            },
        ],
        "thresholds": {
            "critical": 0,
            "high": 5,
            "medium": 50,
        },
    }


@pytest.fixture
def assurance_base_url() -> str:
    """Base URL for Certus Assurance API."""
    return "http://localhost:8056"


@pytest.fixture
def test_workspace_id() -> str:
    """Test workspace identifier."""
    return "test-workspace"


@pytest.fixture
def test_component_id() -> str:
    """Test component identifier."""
    return "test-component"


@pytest.fixture
def test_assessment_id() -> str:
    """Test assessment identifier."""
    return "assess_test123"
