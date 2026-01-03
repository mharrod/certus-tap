import pytest

from certus_transform.routers.verification import (
    ArtifactInfoRequest,
    ExecuteUploadRequestModel,
    ScanMetadataRequest,
    StorageConfigRequest,
    execute_upload,
)

pytestmark = pytest.mark.integration


class StubS3Client:
    def __init__(self):
        self.put_calls = []

    def put_object(self, Bucket, Key, Body, ContentType=None, Metadata=None, Tagging=None, **kwargs):
        self.put_calls.append({"Bucket": Bucket, "Key": Key, "Body": Body})


@pytest.fixture
def stub_s3(monkeypatch):
    client = StubS3Client()
    monkeypatch.setattr(
        "certus_transform.routers.verification.get_s3_client",
        lambda: client,
    )
    return client


def _base_request(**kwargs):
    return ExecuteUploadRequestModel(
        upload_permission_id="perm_123",
        scan_id="scan_abc123",
        tier="verified",
        artifacts=[ArtifactInfoRequest(name="trivy.sarif.json", hash="sha256:abc", size=100)],
        metadata=ScanMetadataRequest(
            git_url="https://github.com/example/repo",
            branch="main",
            commit="abcdef1234567890",
            requested_by="tester@example.com",
        ),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_execute_upload_s3_only(stub_s3):
    request = _base_request(
        storage_config=StorageConfigRequest(
            raw_s3_bucket="raw",
            raw_s3_prefix="security-scans/scan_abc123",
            upload_to_s3=True,
            upload_to_oci=False,
        )
    )

    response = await execute_upload(request)

    assert response.status == "success"
    assert response.oci_reference is None
    assert response.uploaded_artifacts[0].s3_path == "security-scans/scan_abc123/trivy.sarif.json"
    assert response.uploaded_artifacts[0].oci_reference is None
    assert len(stub_s3.put_calls) == 1


@pytest.mark.asyncio
async def test_execute_upload_oci_only(monkeypatch, stub_s3):
    monkeypatch.setattr(
        "certus_transform.routers.verification._push_to_oci_registry",
        lambda artifact_name, artifact_hash, oci_registry, oci_repository, scan_id: "registry/repo:tag",
    )

    request = _base_request(
        storage_config=StorageConfigRequest(
            raw_s3_bucket="raw",
            raw_s3_prefix="unused",
            oci_registry="registry.test",
            oci_repository="scans/example",
            upload_to_s3=False,
            upload_to_oci=True,
        )
    )

    response = await execute_upload(request)

    assert response.status == "success"
    assert response.oci_reference == "registry/repo:tag"
    assert response.uploaded_artifacts[0].s3_path is None
    assert response.uploaded_artifacts[0].oci_reference == "registry/repo:tag"
    assert len(stub_s3.put_calls) == 0


@pytest.mark.asyncio
async def test_execute_upload_both_targets(monkeypatch, stub_s3):
    monkeypatch.setattr(
        "certus_transform.routers.verification._push_to_oci_registry",
        lambda artifact_name, artifact_hash, oci_registry, oci_repository, scan_id: "registry/repo:tag",
    )

    request = _base_request(
        storage_config=StorageConfigRequest(
            raw_s3_bucket="raw",
            raw_s3_prefix="security-scans/scan_abc123",
            oci_registry="registry.test",
            oci_repository="scans/example",
            upload_to_s3=True,
            upload_to_oci=True,
        )
    )

    response = await execute_upload(request)

    assert response.status == "success"
    assert response.oci_reference == "registry/repo:tag"
    assert response.uploaded_artifacts[0].s3_path.endswith("trivy.sarif.json")
    assert response.uploaded_artifacts[0].oci_reference == "registry/repo:tag"
    assert len(stub_s3.put_calls) == 1
