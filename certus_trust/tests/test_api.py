"""Tests for Certus-Trust API endpoints."""


def test_root_endpoint(client):
    """Test root endpoint returns service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Certus-Trust"
    assert data["version"] == "0.1.0"
    assert "/docs" in data["docs_url"]


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_readiness_check(client):
    """Test readiness probe."""
    response = client.get("/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert "ready" in data
    assert "checks" in data
    assert "timestamp" in data
    # All checks should have bool values
    assert all(isinstance(v, bool) for v in data["checks"].values())


# ============================================================================
# Phase 1: Sign Endpoint Tests
# ============================================================================


def test_sign_artifact(client):
    """Test signing an artifact."""
    request_body = {
        "artifact": "sha256:abc123def456",
        "artifact_type": "sbom",
        "subject": "myapp:v1.0.0",
        "predicates": {"timestamp": "2025-12-02T00:00:00Z", "signer": "ci@example.com"},
    }

    response = client.post("/v1/sign", json=request_body)
    assert response.status_code == 202
    data = response.json()

    # Verify response structure
    assert "entry_id" in data
    assert "signature" in data
    assert "certificate" in data
    assert "transparency_entry" in data

    # Verify transparency entry
    entry = data["transparency_entry"]
    assert "uuid" in entry
    assert "index" in entry
    assert "timestamp" in entry

    return data["entry_id"]  # Return for use in other tests


def test_sign_artifact_response_format(client):
    """Test sign endpoint returns correct response format."""
    request_body = {"artifact": "sha256:test123", "artifact_type": "image", "subject": "test:latest"}

    response = client.post("/v1/sign", json=request_body)
    assert response.status_code == 202

    data = response.json()
    assert isinstance(data["entry_id"], str)
    assert isinstance(data["signature"], str)
    assert isinstance(data["transparency_entry"]["index"], int)
    assert isinstance(data["transparency_entry"]["timestamp"], str)


def test_sign_artifact_missing_fields(client):
    """Test sign endpoint with missing required fields."""
    request_body = {
        "artifact": "sha256:abc123",
        # Missing artifact_type and subject
    }

    response = client.post("/v1/sign", json=request_body)
    assert response.status_code == 422  # Validation error


# ============================================================================
# Phase 2: Verify Endpoint Tests
# ============================================================================


def test_verify_signature(client):
    """Test verifying a signature."""
    # First sign an artifact
    sign_request = {"artifact": "sha256:verify-test", "artifact_type": "sbom", "subject": "app:v1.0"}
    sign_response = client.post("/v1/sign", json=sign_request)
    assert sign_response.status_code == 202
    sign_data = sign_response.json()

    # Then verify it
    verify_request = {"artifact": "sha256:verify-test", "signature": sign_data["signature"]}
    verify_response = client.post("/v1/verify", json=verify_request)
    assert verify_response.status_code == 200

    data = verify_response.json()
    assert data["valid"] is True
    assert "signer" in data
    assert "verified_at" in data
    assert "transparency_index" in data


def test_verify_invalid_signature(client):
    """Test verifying an invalid signature."""
    verify_request = {"artifact": "sha256:nonexistent", "signature": "invalid-signature"}

    response = client.post("/v1/verify", json=verify_request)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False


def test_verify_with_identity_check(client):
    """Test verifying signature with identity requirement."""
    # Sign an artifact
    sign_request = {"artifact": "sha256:identity-test", "artifact_type": "report", "subject": "app:v2.0"}
    sign_response = client.post("/v1/sign", json=sign_request)
    sign_data = sign_response.json()

    # Verify with correct identity
    verify_request = {
        "artifact": "sha256:identity-test",
        "signature": sign_data["signature"],
        "identity": "certus-trust@certus.cloud",
    }
    response = client.post("/v1/verify", json=verify_request)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True


# ============================================================================
# Phase 3: Transparency Log Tests
# ============================================================================


def test_get_transparency_entry(client):
    """Test retrieving a transparency log entry."""
    # First sign an artifact
    sign_request = {"artifact": "sha256:transparency-test", "artifact_type": "sbom", "subject": "app:v1.0"}
    sign_response = client.post("/v1/sign", json=sign_request)
    sign_data = sign_response.json()
    entry_id = sign_data["transparency_entry"]["uuid"]

    # Then retrieve it
    response = client.get(f"/v1/transparency/{entry_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["entry_id"] == entry_id
    assert "artifact" in data
    assert "timestamp" in data
    assert "signer" in data
    assert "signature" in data


def test_get_nonexistent_transparency_entry(client):
    """Test retrieving non-existent transparency entry."""
    response = client.get("/v1/transparency/nonexistent-id")
    assert response.status_code == 404


def test_query_transparency_log(client):
    """Test querying transparency log with filters."""
    # Sign a few artifacts
    for i in range(3):
        sign_request = {"artifact": f"sha256:query-test-{i}", "artifact_type": "sbom", "subject": f"app:v{i}"}
        client.post("/v1/sign", json=sign_request)

    # Query with limit
    response = client.get("/v1/transparency?limit=2")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 2
    # Check entry structure
    if len(data) > 0:
        assert "entry_id" in data[0]
        assert "timestamp" in data[0]


def test_query_transparency_log_with_signer_filter(client):
    """Test querying transparency log filtered by signer."""
    # Sign an artifact
    sign_request = {"artifact": "sha256:signer-filter-test", "artifact_type": "sbom", "subject": "app:v1.0"}
    client.post("/v1/sign", json=sign_request)

    # Query with signer filter
    response = client.get("/v1/transparency?signer=certus-trust@certus.cloud")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    # All entries should be from the specified signer
    for entry in data:
        assert entry["signer"] == "certus-trust@certus.cloud"


# ============================================================================
# Non-Repudiation Endpoints (Phase 4-5 placeholder tests)
# ============================================================================


def test_sign_artifact_dual_signature(client):
    """Test signing artifact with dual signatures."""
    request_body = {
        "artifact_locations": {
            "s3": {"uri": "s3://customer-bucket/uuid-123/", "digest": "sha256:s3digest"},
            "registry": {"uri": "registry.example.com/certus/assessments/...:v1.0.0", "digest": "sha256:regdigest"},
        },
        "inner_signatures": {
            "signer": "certus-assurance@certus.cloud",
            "timestamp": "2025-12-03T00:45:10Z",
            "signature": "mock-inner-sig",
            "files": [{"path": "SECURITY/trivy.json", "signature": "sig1", "verified": True}],
        },
        "assessment_metadata": {
            "assessment_id": "uuid-123",
            "client_id": "client-abc",
            "assessment_type": "unified_risk_assessment",
            "domains": ["security", "supply_chain"],
        },
    }

    response = client.post("/v1/sign-artifact", json=request_body)
    assert response.status_code == 202

    data = response.json()
    assert data["status"] == "signed"
    assert data["assessment_id"] == "uuid-123"
    assert "outer_signature" in data
    assert "verification_proof" in data

    # Verify outer signature structure
    outer_sig = data["outer_signature"]
    assert outer_sig["signer"] == "certus-trust@certus.cloud"
    assert "signature" in outer_sig
    assert "sigstore_entry_id" in outer_sig

    # Verify verification proof
    proof = data["verification_proof"]
    assert "inner_signatures_verified" in proof
    assert "artifact_locations_valid" in proof
    assert "chain_of_custody" in proof


def test_verify_chain(client):
    """Test verifying non-repudiation chain."""
    request_body = {
        "artifact_locations": {"s3": "s3://bucket/uuid/", "registry": "registry.../v1.0.0@sha256:digest"},
        "signatures": {
            "inner": {
                "signer": "certus-assurance@certus.cloud",
                "timestamp": "2025-12-03T00:45:10Z",
                "signature": "inner-sig",
            },
            "outer": {
                "signer": "certus-trust@certus.cloud",
                "timestamp": "2025-12-03T01:30:00Z",
                "signature": "outer-sig",
            },
        },
        "sigstore_entry_id": "rekor-entry-12345",
    }

    response = client.post("/v1/verify-chain", json=request_body)
    assert response.status_code == 200

    data = response.json()
    assert data["chain_verified"] is True
    assert data["inner_signature_valid"] is True
    assert data["outer_signature_valid"] is True
    assert data["chain_unbroken"] is True

    # Check non-repudiation guarantee
    assert "non_repudiation" in data
    nr = data["non_repudiation"]
    assert nr["assurance_accountable"] is True
    assert nr["trust_verified"] is True
    assert nr["timestamp_authority"] == "sigstore"


# ============================================================================
# TUF Endpoints Tests
# ============================================================================


def test_get_tuf_root(client):
    """Test TUF root metadata endpoint."""
    response = client.get("/v1/keys/root.json")
    assert response.status_code == 200

    data = response.json()
    assert "signed" in data
    assert "signatures" in data
    assert data["signed"]["_type"] == "root"


def test_get_tuf_targets(client):
    """Test TUF targets metadata endpoint."""
    response = client.get("/v1/keys/targets.json")
    assert response.status_code == 200

    data = response.json()
    assert "signed" in data
    assert data["signed"]["_type"] == "targets"


def test_get_tuf_timestamp(client):
    """Test TUF timestamp metadata endpoint."""
    response = client.get("/v1/keys/timestamp.json")
    assert response.status_code == 200

    data = response.json()
    assert "signed" in data
    assert data["signed"]["_type"] == "timestamp"


def test_get_tuf_snapshot(client):
    """Test TUF snapshot metadata endpoint."""
    response = client.get("/v1/keys/snapshot.json")
    assert response.status_code == 200

    data = response.json()
    assert "signed" in data
    assert data["signed"]["_type"] == "snapshot"
