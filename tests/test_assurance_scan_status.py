from certus_assurance.api import _serialize_job
from certus_assurance.jobs import ScanJob


def test_scan_status_response_includes_verification_proof():
    job = ScanJob(
        test_id="scan_test123",
        workspace_id="test-workspace",
        component_id="test-component",
        assessment_id="test-assessment",
        git_url="https://example.com/repo.git",
        branch="main",
        commit=None,
        requested_by="tester@example.com",
    )
    job.upload_status = "uploaded"
    job.upload_permission_id = "perm_123"
    job.verification_proof = {"chain_verified": True, "signer_outer": "certus-trust@certus.cloud"}

    response = _serialize_job(job)

    assert response.verification_proof is not None
    assert response.verification_proof["chain_verified"] is True
    assert response.upload_permission_id == "perm_123"
