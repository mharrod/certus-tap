from __future__ import annotations

import json
from pathlib import Path

from certus_assurance.models import ArtifactBundle, PipelineResult
from certus_assurance.storage import DockerRegistryPublisher, RegistryMirrorPublisher, TransformArtifactPublisher


class DummyS3Client:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, str, dict]] = []
        self.copies: list[tuple[dict, str, str, dict]] = []

    def upload_file(  # pragma: no cover - boto3 parity
        self, filename: str, bucket: str, key: str, ExtraArgs: dict | None = None
    ) -> None:
        self.uploads.append((filename, bucket, key, ExtraArgs or {}))

    def copy(  # pragma: no cover - boto3 parity
        self, copy_source: dict, bucket: str, key: str, ExtraArgs: dict | None = None
    ) -> None:
        self.copies.append((copy_source, bucket, key, ExtraArgs or {}))


def _fake_pipeline_result(
    tmp_path: Path, test_id: str = "test_sample", image_reference: str | None = None
) -> PipelineResult:
    root = tmp_path / test_id
    root.mkdir(parents=True, exist_ok=True)

    def write(rel: str, content: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    write(
        "scan.json",
        json.dumps({
            "test_id": test_id,
            "workspace_id": "workspace-1",
            "component_id": "component-1",
            "assessment_id": "assessment-1",
            "artifacts": {},
        }),
    )
    write("manifest-info.json", json.dumps({"profile": "light"}))
    write("manifest.json", json.dumps({"profiles": []}))
    write("logs/runner.log", "log-line")
    write("reports/sast/trivy.sarif.json", "{}")
    write("reports/sbom/sbom.spdx.json", "{}")
    write("reports/sbom/sbom.cyclonedx.json", "{}")
    write("reports/dast/dast-results.json", "{}")
    write("reports/signing/attestation.intoto.json", "{}")
    image_ref = image_reference or f"registry.example.com/certus/{test_id}:latest"
    write("artifacts/image.txt", image_ref)
    write("artifacts/image.digest", "sha256:digest")

    bundle = ArtifactBundle.discover(root)
    metadata = {
        "test_id": test_id,
        "workspace_id": "workspace-1",
        "component_id": "component-1",
        "assessment_id": "assessment-1",
        "artifacts": bundle.artifact_map(),
    }
    return PipelineResult(
        test_id=test_id,
        workspace_id="workspace-1",
        component_id="component-1",
        assessment_id="assessment-1",
        status="SUCCEEDED",
        artifacts=bundle,
        steps=[],
        metadata=metadata,
        manifest_digest="abc123",
        manifest_metadata={"profile": "light"},
    )


def test_transform_uploader_stages_and_promotes(tmp_path: Path) -> None:
    result = _fake_pipeline_result(tmp_path, "scan_test_remote")

    client = DummyS3Client()
    uploader = TransformArtifactPublisher(
        client=client,
        raw_bucket="raw-bucket",
        golden_bucket="gold-bucket",
        raw_prefix="raw",
        golden_prefix="golden",
    )
    remote = uploader.stage_and_promote(result, manifest_digest="abc123")

    assert client.uploads, "expected raw uploads"
    assert client.copies, "expected promotions"
    uploaded_keys = {key for _, _, key, _ in client.uploads}
    assert any(key.endswith("scan.json") for key in uploaded_keys)
    assert remote["raw"]["scan.json"].startswith("s3://raw-bucket/")
    assert remote["golden"]["scan.json"].startswith("s3://gold-bucket/")
    assert client.uploads[0][3]["Metadata"]["manifest_digest"] == "abc123"
    assert client.copies[0][3]["Metadata"]["manifest_digest"] == "abc123"


def test_registry_mirror_copies_artifacts(tmp_path: Path) -> None:
    result = _fake_pipeline_result(tmp_path, "scan_test")

    publisher = RegistryMirrorPublisher(tmp_path / "registry")
    info = publisher.publish(result)

    dest = Path(info["mirror_path"])
    assert dest.exists()
    assert (dest / "image.txt").exists()
    assert (dest / "image.digest").exists()
    assert info["image_reference"] in (dest / "image.txt").read_text(encoding="utf-8")
    assert info["manifest"]["path"].endswith("manifest.json")
    assert (dest / "policy" / "manifest.json").exists()


def test_docker_registry_publisher_invokes_docker(tmp_path: Path) -> None:
    result = _fake_pipeline_result(
        tmp_path,
        "scan_test",
        image_reference="localhost:5000/secure/scan_test:latest",
    )

    commands: list[list[str]] = []

    def fake_run(cmd: list[str]) -> None:
        commands.append(cmd)

    class StubCosign:
        def __init__(self) -> None:
            self.calls: list[tuple[str, Path]] = []

        def sign(self, image: str, key_ref: str, password: str | None = None) -> None:
            self.calls.append(("sign", Path(image)))

        def attest(
            self,
            image: str,
            predicate_path: Path,
            key_ref: str,
            password: str | None = None,
            predicate_type: str = "https://slsa.dev/provenance/v1",
        ) -> None:
            self.calls.append(("attest", predicate_path))

        def sign_blob(self, blob: Path, key_ref: str, output_signature: Path, password: str | None = None) -> None:
            output_signature.write_text("signature", encoding="utf-8")
            self.calls.append(("sign-blob", blob))

    cosign_stub = StubCosign()
    publisher = DockerRegistryPublisher(
        registry="localhost:5000",
        repository="secure",
        run_cmd=fake_run,
        cosign=cosign_stub,
        cosign_key_ref="cosign.key",
    )
    info = publisher.publish(result)

    assert commands[0][:2] == ["docker", "build"]
    assert commands[-1][:2] == ["docker", "push"]
    assert info["image_reference"].startswith("localhost:5000/secure/")
    assert info["cosign"]["signed"] is True
    assert len(cosign_stub.calls) == 3
    assert any(call[0] == "sign-blob" for call in cosign_stub.calls)
    assert info["manifest"]["path"].endswith("manifest.json")
    assert info["manifest"]["signature"].endswith("manifest.sig")
