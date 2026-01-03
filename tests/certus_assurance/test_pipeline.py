from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import git
import pytest

from certus_assurance import CertusAssuranceRunner, ScanRequest


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "sample-repo"
    repo = git.Repo.init(repo_path)
    (repo_path / "README.md").write_text("# Sample\n", encoding="utf-8")
    repo.index.add(["README.md"])
    repo.index.commit("initial commit")
    return repo_path


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
            "summary.json": json.dumps({"executed": ["ruff"]}),
        }
        for name, content in files.items():
            (bundle_path / name).write_text(content, encoding="utf-8")

        manifest_digest = hashlib.sha256((request.manifest_text or "").encode("utf-8")).hexdigest()
        manifest_info = {
            "profile_requested": request.profile,
            "manifest_digest": manifest_digest,
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


class StubManifestFetcher:
    def __init__(self, tmp_path: Path, manifest_text: str, signature_text: str = "signature"):
        self.manifest_path = tmp_path / "fetched-manifest.json"
        self.signature_path = tmp_path / "fetched-manifest.sig"
        self.manifest_path.write_text(manifest_text, encoding="utf-8")
        self.signature_path.write_text(signature_text, encoding="utf-8")

    def fetch(self, uri: str, signature_uri: str | None = None):
        return self.manifest_path, self.signature_path, (lambda: None)


class StubCosign:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, Path, str]] = []

    def verify_blob(self, blob_path: Path, signature_path: Path, key_ref: str) -> None:
        self.calls.append((blob_path, signature_path, key_ref))


@pytest.fixture()
def manifest_json() -> str:
    return json.dumps({
        "product": "certus",
        "profiles": [
            {
                "name": "light",
                "tools": ["ruff"],
            }
        ],
    })


def test_pipeline_creates_all_artifacts(tmp_path: Path, git_repo: Path, manifest_json: str) -> None:
    output_root = tmp_path / "certus_assurance-artifacts"
    stub_runtime = StubRuntime(output_root)
    runner = CertusAssuranceRunner(
        output_root=output_root,
        runtime_factory=lambda _stream: stub_runtime,
        scanner_builder=lambda runtime: StubScanner(runtime),
    )
    request = ScanRequest(
        test_id="test_scan",
        workspace_id="workspace-1",
        component_id="component-1",
        assessment_id="assessment-1",
        git_url=str(git_repo),
        manifest_text=manifest_json,
    )

    result = runner.run(request)

    assert result.status == "SUCCEEDED"
    artifacts = result.artifacts
    # Metadata
    metadata = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert metadata["test_id"] == "test_scan"
    assert metadata["artifacts"]["sarif"] == "reports/sast/trivy.sarif.json"
    # Files exist
    assert artifacts.sarif.exists()
    assert artifacts.dast_json.exists()
    assert artifacts.attestation.exists()
    assert artifacts.image_reference.exists()
    assert artifacts.image_digest.exists()
    assert artifacts.logs.exists()


def test_pipeline_respects_output_root_isolated(tmp_path: Path, git_repo: Path, manifest_json: str) -> None:
    stub_runtime = StubRuntime(tmp_path / "artifacts-a")
    runner = CertusAssuranceRunner(
        output_root=tmp_path / "artifacts-a",
        runtime_factory=lambda _: stub_runtime,
        scanner_builder=lambda runtime: StubScanner(runtime),
    )
    runner.run(
        ScanRequest(
            test_id="test_a",
            workspace_id="workspace-1",
            component_id="component-1",
            assessment_id="assessment-1",
            git_url=str(git_repo),
            manifest_text=manifest_json,
        )
    )

    second_stub = StubRuntime(tmp_path / "artifacts-b")
    second_runner = CertusAssuranceRunner(
        output_root=tmp_path / "artifacts-b",
        runtime_factory=lambda _: second_stub,
        scanner_builder=lambda runtime: StubScanner(runtime),
    )
    second_runner.run(
        ScanRequest(
            test_id="test_b",
            workspace_id="workspace-1",
            component_id="component-1",
            assessment_id="assessment-1",
            git_url=str(git_repo),
            manifest_text=manifest_json,
        )
    )

    assert (tmp_path / "artifacts-a" / "test_a").exists()
    assert not (tmp_path / "artifacts-a" / "test_b").exists()
    assert (tmp_path / "artifacts-b" / "test_b").exists()


def test_pipeline_fetches_and_verifies_manifest_uri(tmp_path: Path, git_repo: Path, manifest_json: str) -> None:
    fetcher = StubManifestFetcher(tmp_path, manifest_json)
    cosign = StubCosign()
    stub_runtime = StubRuntime(tmp_path / "artifacts-fetch")
    runner = CertusAssuranceRunner(
        output_root=tmp_path / "artifacts-fetch",
        runtime_factory=lambda _: stub_runtime,
        scanner_builder=lambda runtime: StubScanner(runtime),
        manifest_fetcher=fetcher,
        cosign_client=cosign,
        manifest_key_ref="cosign.pub",
        require_manifest_verification=True,
    )
    request = ScanRequest(
        test_id="test_fetch",
        workspace_id="workspace-1",
        component_id="component-1",
        assessment_id="assessment-1",
        git_url=str(git_repo),
        manifest_uri="file:///tmp/remote-manifest",
        manifest_signature_uri="file:///tmp/remote-manifest.sig",
    )

    result = runner.run(request)

    assert cosign.calls == [(fetcher.manifest_path, fetcher.signature_path, "cosign.pub")]
    assert result.artifacts.manifest_signature is not None
    assert result.artifacts.manifest_signature.read_text(encoding="utf-8") == "signature"


def test_pipeline_preserves_sample_metadata_when_enabled(tmp_path: Path, manifest_json: str) -> None:
    sample_dir = tmp_path / "sample-artifacts"
    sample_dir.mkdir()
    sample_metadata = {
        "git_url": "https://github.com/mharrod/certus-TAP.git",
        "branch": "main",
        "artifacts": {
            "sarif": "reports/sast/trivy.sarif.json",
            "sbom": "reports/sbom/syft.spdx.json",
        },
    }
    (sample_dir / "scan.json").write_text(json.dumps(sample_metadata), encoding="utf-8")

    class CopyScanner:
        def __init__(self, source: Path):
            self.source = source

        async def run(
            self,
            *,
            profile: str,
            workspace: Path,
            manifest_text: str,
            export_dir: Path,
            bundle_id: str,
            **_: object,
        ) -> SimpleNamespace:
            dest = Path(export_dir) / bundle_id
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(self.source, dest)
            return SimpleNamespace(artifacts=dest)

    runner = CertusAssuranceRunner(
        output_root=tmp_path / "output",
        runtime_factory=lambda _stream: None,
        scanner_builder=lambda _runtime: CopyScanner(sample_dir),
        preserve_sample_metadata=True,
    )
    request = ScanRequest(
        test_id="sample-test",
        workspace_id="ws-1",
        component_id="component",
        assessment_id="assessment",
        git_url="https://github.com/octocat/Hello-World.git",
        manifest_text=manifest_json,
    )

    result = runner.run(request)

    metadata = result.metadata
    assert metadata["git_url"] == sample_metadata["git_url"]
    assert metadata["test_id"] == "sample-test"
    assert metadata["workspace_id"] == "ws-1"
    assert metadata["artifacts"] == sample_metadata["artifacts"]
