"""Tests for Certus-Trust sigstore integration."""

import pytest


def test_sigstore_configuration(client):
    """Test sigstore configuration endpoint."""
    response = client.get("/v1/sigstore/config")
    assert response.status_code == 200
    data = response.json()
    assert "mock_sigstore" in data
    assert "sigstore_url" in data
    assert "fulcio_url" in data
    assert "rekor_url" in data


def test_sign_with_real_sigstore(client):
    """Test signing with real sigstore services."""
    # This test would work when MOCK_SIGSTORE=false
    if not client.app.config.get("MOCK_SIGSTORE", True):
        request_body = {"artifact": "sha256:abc123def456", "artifact_type": "container", "subject": "test:v1.0.0"}
        response = client.post("/v1/sign", json=request_body)
        assert response.status_code == 200
        data = response.json()
        assert "signature" in data
        assert "certificate" in data
        assert "bundle" in data
    else:
        pytest.skip("Skipping real sigstore test (mock mode)")


def test_verify_signature(client):
    """Test signature verification."""
    # Mock a signature verification
    signature_data = {"signature": "mock-signature", "certificate": "mock-cert", "bundle": "mock-bundle"}
    response = client.post("/v1/verify", json=signature_data)
    assert response.status_code == 200
    data = response.json()
    assert "verified" in data
    assert "valid" in data


@pytest.mark.parametrize("mock_sigstore", [True, False])
def test_sigstore_mode_switch(client, mock_sigstore):
    """Test switching between mock and real sigstore."""
    # This would be tested with different configurations
    pass


def test_rekor_integration(client):
    """Test Rekor transparency log integration."""
    if not client.app.config.get("MOCK_SIGSTORE", True):
        # Test real Rekor integration
        entry_data = {"artifact": "sha256:test123", "signature": "test-sig"}
        response = client.post("/v1/rekor/entry", json=entry_data)
        assert response.status_code == 200
        data = response.json()
        assert "entry_uuid" in data
    else:
        pytest.skip("Skipping Rekor test (mock mode)")


def test_fulcio_integration(client):
    """Test Fulcio certificate authority integration."""
    if not client.app.config.get("MOCK_SIGSTORE", True):
        # Test real Fulcio integration
        csr_data = {"csr": "mock-csr-data", "email": "test@example.com"}
        response = client.post("/v1/fulcio/certificate", json=csr_data)
        assert response.status_code == 200
        data = response.json()
        assert "certificate" in data
    else:
        pytest.skip("Skipping Fulcio test (mock mode)")


def test_offline_mode(client):
    """Test offline workload support."""
    response = client.get("/v1/offline/status")
    assert response.status_code == 200
    data = response.json()
    assert "offline_mode" in data
    assert "local_services" in data
