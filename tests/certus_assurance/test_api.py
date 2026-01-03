from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

import git
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from certus_assurance import ScanRequest
from certus_assurance.api import (
    get_artifact_uploader,
    get_job_manager,
    get_registry_publisher,
    get_runner,
    get_settings,
    router,
)
from certus_assurance.jobs import ScanJobManager
from certus_assurance.pipeline import CertusAssuranceRunner
from certus_assurance.settings import CertusAssuranceSettings


@dataclass
class FakeRuntimeResult:
    bundle_id: str
    artifacts: Path
    export_dir: Path


class StubRuntime:
    def __init__(self, export_root: Path):
        self.export_root = export_root

    async def run(self, request: ScanRequest) -> FakeRuntimeResult:
        bundle_id = request.test_id
        export_dir = self.export_root
        export_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = export_dir / bundle_id
        bundle_path.mkdir(parents=True, exist_ok=True)

        files = {
            "trivy.sarif.json": "{}",
            "sbom.spdx.json": "{}",
            "sbom.cyclonedx.json": "{}",
            "dast-results.json": "{}",
            "attestation.intoto.json": "{}",
            "summary.json": '{"executed": ["ruff"]}',
        }
        for name, payload in files.items():
            (bundle_path / name).write_text(payload, encoding="utf-8")

        manifest_digest = hashlib.sha256((request.manifest_text or "").encode("utf-8")).hexdigest()
        manifest_info = {
            "manifest_digest": manifest_digest,
            "profile_requested": request.profile,
            "tools_selected": ["ruff"],
        }
        (bundle_path / "manifest-info.json").write_text(json.dumps(manifest_info), encoding="utf-8")
        (bundle_path / "manifest.json").write_text(request.manifest_text or "{}", encoding="utf-8")

        return FakeRuntimeResult(bundle_id=bundle_id, artifacts=bundle_path, export_dir=export_dir)


class StubScanner:
    def __init__(self, runtime: StubRuntime):
        self._runtime = runtime

    async def run(
        self,
        *,
        profile: str,
        workspace: Path,
        manifest_text: str,
        export_dir: Path,
        bundle_id: str,
        **_: object,
    ):
        scan_request = ScanRequest(
            test_id=bundle_id,
            workspace_id="workspace-1",
            component_id="component-1",
            assessment_id="assessment-1",
            git_url=str(workspace),
            manifest_text=manifest_text,
            profile=profile,
        )
        return await self._runtime.run(scan_request)


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "api-repo"
    repo = git.Repo.init(repo_path)
    (repo_path / "README.md").write_text("# API Repo\n", encoding="utf-8")
    repo.index.add(["README.md"])
    repo.index.commit("init")
    return repo_path


@pytest.fixture()
def manifest_payload() -> dict[str, object]:
    return {
        "product": "certus",
        "profiles": [
            {
                "name": "light",
                "tools": ["ruff"],
            }
        ],
    }


@pytest.fixture()
def api_client(tmp_path: Path):
    app = FastAPI()
    app.include_router(router)

    cfg = CertusAssuranceSettings(artifact_root=tmp_path / "artifacts", enable_s3_upload=True)
    manager = ScanJobManager(max_workers=1)
    stub_runtime = StubRuntime(cfg.artifact_root)
    runner = CertusAssuranceRunner(
        output_root=cfg.artifact_root,
        runtime_factory=lambda _: stub_runtime,
        scanner_builder=lambda runtime: StubScanner(runtime),
    )

    app.dependency_overrides[get_settings] = lambda: cfg
    app.dependency_overrides[get_job_manager] = lambda: manager
    app.dependency_overrides[get_runner] = lambda: runner
    app.dependency_overrides[get_artifact_uploader] = lambda: None
    app.dependency_overrides[get_registry_publisher] = lambda: None

    client = TestClient(app)
    try:
        yield client
    finally:
        manager.shutdown()
        client.close()


def _init_repo(path: Path) -> str:
    repo = git.Repo.init(path)
    (path / "README.md").write_text("# Repo\n", encoding="utf-8")
    repo.index.add(["README.md"])
    repo.index.commit("init")
    return str(path)


def test_submit_and_poll_scan(api_client: TestClient, git_repo: Path, manifest_payload: dict[str, object]) -> None:
    response = api_client.post(
        "/v1/security-scans",
        json={
            "workspace_id": "workspace-1",
            "component_id": "component-1",
            "assessment_id": "assessment-1",
            "git_url": str(git_repo),
            "requested_by": "api@test",
            "manifest": manifest_payload,
        },
    )
    assert response.status_code == 202
    body = response.json()
    test_id = body["test_id"]
    assert body["profile"] == "light"
    assert body["stream_url"].endswith(f"/{test_id}/stream")

    data = _wait_for_status(api_client, test_id)
    if data["status"] != "SUCCEEDED":
        print(data)
    assert data["status"] == "SUCCEEDED", data
    assert data["artifacts"]["sarif"].endswith("trivy.sarif.json")
    assert data["requested_by"] == "api@test"
    assert data["manifest_digest"]


def test_missing_scan_returns_404(api_client: TestClient) -> None:
    resp = api_client.get("/v1/security-scans/test_missing")
    assert resp.status_code == 404


def test_scan_response_includes_remote_metadata(tmp_path: Path, manifest_payload: dict[str, object]) -> None:
    class StubUploader:
        def stage_and_promote(self, result, manifest_digest=None):
            return {
                "raw": {"scan.json": "s3://raw/scan.json"},
                "golden": {"scan.json": "s3://golden/scan.json"},
            }

    class StubRegistry:
        def publish(self, _):
            return {"image_reference": "registry/ref", "digest": "sha256:abc"}

    app = FastAPI()
    app.include_router(router)

    cfg = CertusAssuranceSettings(artifact_root=tmp_path / "artifacts", enable_s3_upload=True)
    manager = ScanJobManager(max_workers=1)
    stub_runtime = StubRuntime(cfg.artifact_root)
    runner = CertusAssuranceRunner(
        output_root=cfg.artifact_root,
        runtime_factory=lambda _: stub_runtime,
        scanner_builder=lambda runtime: StubScanner(runtime),
    )

    app.dependency_overrides[get_settings] = lambda: cfg
    app.dependency_overrides[get_job_manager] = lambda: manager
    app.dependency_overrides[get_runner] = lambda: runner
    app.dependency_overrides[get_artifact_uploader] = lambda: StubUploader()
    app.dependency_overrides[get_registry_publisher] = lambda: StubRegistry()

    repo_dir = _init_repo(tmp_path / "repo-remote")

    client = TestClient(app)
    try:
        response = client.post(
            "/v1/security-scans",
            json={
                "workspace_id": "workspace-1",
                "component_id": "component-1",
                "assessment_id": "assessment-1",
                "git_url": repo_dir,
                "manifest": manifest_payload,
            },
        )
        test_id = response.json()["test_id"]
        data = _wait_for_status(client, test_id)
        if data["status"] != "SUCCEEDED":
            print(data)
        assert data["status"] == "SUCCEEDED", data

        # Trigger upload request to populate remote_artifacts
        upload_response = client.post(
            f"/v1/security-scans/{test_id}/upload-request",
            json={"tier": "verified", "requested_by": "test@example.com"},
        )
        upload_response.raise_for_status()

        # Wait for upload to complete
        data = _wait_for_upload_status(client, test_id)
        assert data["remote_artifacts"]["raw"]["scan.json"].startswith("s3://raw")
        assert data["registry"]["image_reference"] == "registry/ref"
    finally:
        manager.shutdown()
        client.close()


def test_manifest_uri_requires_signature(api_client: TestClient, git_repo: Path) -> None:
    response = api_client.post(
        "/v1/security-scans",
        json={
            "workspace_id": "workspace-1",
            "component_id": "component-1",
            "assessment_id": "assessment-1",
            "git_url": str(git_repo),
            "manifest_uri": "s3://bucket/policy.json",
        },
    )
    assert response.status_code == 422


def _wait_for_status(client: TestClient, test_id: str) -> dict:
    for _ in range(200):
        resp = client.get(f"/v1/security-scans/{test_id}")
        resp.raise_for_status()
        data = resp.json()
        if data["status"] in {"SUCCEEDED", "FAILED"}:
            return data
        time.sleep(0.01)
    raise AssertionError("scan did not reach terminal state")


def _wait_for_upload_status(client: TestClient, test_id: str) -> dict:
    for _ in range(200):
        resp = client.get(f"/v1/security-scans/{test_id}")
        resp.raise_for_status()
        data = resp.json()
        if data.get("upload_status") == "uploaded":
            return data
        time.sleep(0.01)
    raise AssertionError("upload did not complete")
