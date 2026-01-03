"""Unit tests for artifact generation and bundling."""

from pathlib import Path

import pytest

from certus_assurance.models import ArtifactBundle


def test_artifact_bundle_discover_with_no_files(tmp_path: Path):
    """Test that ArtifactBundle.discover handles empty directory."""
    bundle = ArtifactBundle.discover(tmp_path)

    assert bundle.root == tmp_path
    assert bundle.metadata is None
    assert bundle.summary is None
    assert bundle.sarif is None
    assert bundle.sbom_spdx is None


def test_artifact_bundle_discover_finds_metadata(tmp_path: Path):
    """Test that ArtifactBundle.discover finds scan.json."""
    metadata_file = tmp_path / "scan.json"
    metadata_file.write_text('{"test": "data"}')

    bundle = ArtifactBundle.discover(tmp_path)

    assert bundle.metadata == metadata_file
    assert bundle.metadata.exists()


def test_artifact_bundle_discover_finds_summary(tmp_path: Path):
    """Test that ArtifactBundle.discover finds summary.json."""
    summary_file = tmp_path / "summary.json"
    summary_file.write_text('{"findings": 10}')

    bundle = ArtifactBundle.discover(tmp_path)

    assert bundle.summary == summary_file
    assert bundle.summary.exists()


def test_artifact_bundle_discover_finds_manifest(tmp_path: Path):
    """Test that ArtifactBundle.discover finds manifest.json."""
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text('{"profile": "light"}')

    bundle = ArtifactBundle.discover(tmp_path)

    assert bundle.manifest_json == manifest_file
    assert bundle.manifest_json.exists()


def test_artifact_bundle_discover_finds_sarif_in_reports(tmp_path: Path):
    """Test that ArtifactBundle.discover finds SARIF in reports/sast/."""
    reports_dir = tmp_path / "reports" / "sast"
    reports_dir.mkdir(parents=True)
    sarif_file = reports_dir / "trivy.sarif.json"
    sarif_file.write_text('{"version": "2.1.0"}')

    bundle = ArtifactBundle.discover(tmp_path)

    assert bundle.sarif == sarif_file
    assert bundle.sarif.exists()


def test_artifact_bundle_discover_finds_sarif_in_root(tmp_path: Path):
    """Test that ArtifactBundle.discover finds SARIF in root directory."""
    sarif_file = tmp_path / "trivy.sarif.json"
    sarif_file.write_text('{"version": "2.1.0"}')

    bundle = ArtifactBundle.discover(tmp_path)

    assert bundle.sarif == sarif_file


def test_artifact_bundle_discover_finds_sbom_in_reports(tmp_path: Path):
    """Test that ArtifactBundle.discover finds SBOM in reports/sbom/."""
    reports_dir = tmp_path / "reports" / "sbom"
    reports_dir.mkdir(parents=True)
    sbom_file = reports_dir / "syft.spdx.json"
    sbom_file.write_text('{"spdxVersion": "SPDX-2.3"}')

    bundle = ArtifactBundle.discover(tmp_path)

    assert bundle.sbom_spdx == sbom_file
    assert bundle.sbom_spdx.exists()


def test_artifact_bundle_discover_finds_sbom_in_root(tmp_path: Path):
    """Test that ArtifactBundle.discover finds SBOM in root directory."""
    sbom_file = tmp_path / "sbom.spdx.json"
    sbom_file.write_text('{"spdxVersion": "SPDX-2.3"}')

    bundle = ArtifactBundle.discover(tmp_path)

    assert bundle.sbom_spdx == sbom_file


def test_artifact_bundle_discover_finds_manifest_signature(tmp_path: Path):
    """Test that ArtifactBundle.discover finds manifest signature."""
    sig_file = tmp_path / "manifest.sig"
    sig_file.write_text("signature-data")

    bundle = ArtifactBundle.discover(tmp_path)

    assert bundle.manifest_signature == sig_file


def test_artifact_bundle_discover_prefers_manifest_sig_over_json_sig(tmp_path: Path):
    """Test that manifest.sig is preferred over manifest.json.sig."""
    sig1 = tmp_path / "manifest.sig"
    sig1.write_text("preferred")

    sig2 = tmp_path / "manifest.json.sig"
    sig2.write_text("fallback")

    bundle = ArtifactBundle.discover(tmp_path)

    assert bundle.manifest_signature == sig1


def test_artifact_bundle_artifact_map_empty(tmp_path: Path):
    """Test that artifact_map returns empty dict for empty bundle."""
    bundle = ArtifactBundle.discover(tmp_path)

    artifact_map = bundle.artifact_map()

    assert artifact_map == {}


def test_artifact_bundle_artifact_map_includes_existing_files(tmp_path: Path):
    """Test that artifact_map includes only existing files."""
    # Create some artifacts
    (tmp_path / "summary.json").write_text('{"findings": 5}')
    (tmp_path / "manifest.json").write_text('{"profile": "light"}')

    bundle = ArtifactBundle.discover(tmp_path)
    artifact_map = bundle.artifact_map()

    assert "summary" in artifact_map
    assert "manifest_json" in artifact_map
    assert artifact_map["summary"] == "summary.json"
    assert artifact_map["manifest_json"] == "manifest.json"


def test_artifact_bundle_artifact_map_uses_relative_paths(tmp_path: Path):
    """Test that artifact_map returns paths relative to root."""
    reports_dir = tmp_path / "reports" / "sast"
    reports_dir.mkdir(parents=True)
    sarif_file = reports_dir / "trivy.sarif.json"
    sarif_file.write_text('{"version": "2.1.0"}')

    bundle = ArtifactBundle.discover(tmp_path)
    artifact_map = bundle.artifact_map()

    assert "sarif" in artifact_map
    assert artifact_map["sarif"] == "reports/sast/trivy.sarif.json"


def test_artifact_bundle_discovers_image_reference(tmp_path: Path):
    """Test that ArtifactBundle discovers image.txt."""
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    image_file = artifacts_dir / "image.txt"
    image_file.write_text("registry.example.com/app:v1.0")

    bundle = ArtifactBundle.discover(tmp_path)

    assert bundle.image_reference == image_file


def test_artifact_bundle_discovers_image_digest(tmp_path: Path):
    """Test that ArtifactBundle discovers image.digest."""
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    digest_file = artifacts_dir / "image.digest"
    digest_file.write_text("sha256:abc123...")

    bundle = ArtifactBundle.discover(tmp_path)

    assert bundle.image_digest == digest_file
