"""Smoke tests for Rekor transparency log integration."""

from __future__ import annotations

import os

import pytest
import requests

pytestmark = pytest.mark.smoke

REKOR_URL = os.getenv("REKOR_URL", "http://localhost:3001")


def _check_rekor_health(session: requests.Session, timeout: int) -> dict:
    """Verify Rekor transparency log is accessible."""
    response = session.get(f"{REKOR_URL}/api/v1/log", timeout=timeout)
    response.raise_for_status()
    log_info = response.json()
    assert "treeSize" in log_info, f"Unexpected Rekor response: {log_info}"
    return log_info


def test_rekor_transparency_log(http_session: requests.Session, request_timeout: int) -> None:
    """Verify Rekor transparency log is operational (Trust prerequisite)."""
    log_info = _check_rekor_health(http_session, request_timeout)
    assert isinstance(log_info.get("treeSize"), int), "Rekor tree size should be integer"
    assert log_info.get("treeID"), "Rekor should have tree ID"
    print(f"✓ Rekor operational: treeSize={log_info['treeSize']}, treeID={log_info['treeID']}")
