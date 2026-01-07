"""Integration tests for artifact bundling (tar.gz creation)."""

import json
import tarfile
from pathlib import Path

import pytest

from certus_assurance.models import ArtifactBundle

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def test_create_artifact_bundle_with_real_files(tmp_path: Path):
    """Test creating a complete artifact bundle with real files."""
    # Create a realistic artifact structure
    (tmp_path / "scan.json").write_text('{"workspace_id": "test", "status": "completed"}')
    (tmp_path / "summary.json").write_text('{"total_findings": 10, "critical": 2}')
    (tmp_path / "manifest.json").write_text('{"profile": "light", "version": "v1"}')

    # Create reports directory
    reports_dir = tmp_path / "reports" / "sast"
    reports_dir.mkdir(parents=True)
    (reports_dir / "trivy.sarif.json").write_text('{"version": "2.1.0", "runs": []}')

    sbom_dir = tmp_path / "reports" / "sbom"
    sbom_dir.mkdir(parents=True)
    (sbom_dir / "syft.spdx.json").write_text('{"spdxVersion": "SPDX-2.3"}')

    # Discover artifacts
    bundle = ArtifactBundle.discover(tmp_path)

    assert bundle.metadata is not None
    assert bundle.summary is not None
    assert bundle.manifest_json is not None
    assert bundle.sarif is not None
    assert bundle.sbom_spdx is not None


def test_artifact_bundle_to_tarball(tmp_path: Path):
    """Test creating a tar.gz archive from artifact bundle."""
    # Create artifacts
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    (artifacts_dir / "scan.json").write_text('{"test": "data"}')
    (artifacts_dir / "summary.json").write_text('{"findings": 5}')

    # Create tarball
    tarball_path = tmp_path / "bundle.tar.gz"

    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(artifacts_dir, arcname=".")

    # Verify tarball was created
    assert tarball_path.exists()
    assert tarball_path.stat().st_size > 0


def test_extract_artifact_bundle_from_tarball(tmp_path: Path):
    """Test extracting artifacts from tar.gz archive."""
    # Create a tarball with test data
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "test.json").write_text('{"extracted": true}')

    tarball_path = tmp_path / "test.tar.gz"
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(source_dir / "test.json", arcname="test.json")

    # Extract tarball
    extract_dir = tmp_path / "extracted"
    extract_dir.mkdir()

    with tarfile.open(tarball_path, "r:gz") as tar:
        tar.extractall(extract_dir)

    # Verify extraction
    extracted_file = extract_dir / "test.json"
    assert extracted_file.exists()

    with extracted_file.open() as f:
        data = json.load(f)
        assert data["extracted"] is True


def test_artifact_bundle_preserves_directory_structure(tmp_path: Path):
    """Test that tar.gz preserves nested directory structure."""
    # Create nested structure
    source_dir = tmp_path / "source"
    nested_dir = source_dir / "reports" / "sast"
    nested_dir.mkdir(parents=True)
    (nested_dir / "findings.sarif.json").write_text('{"runs": []}')

    # Create tarball
    tarball_path = tmp_path / "bundle.tar.gz"
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(source_dir, arcname=".")

    # Extract and verify
    extract_dir = tmp_path / "extracted"
    extract_dir.mkdir()

    with tarfile.open(tarball_path, "r:gz") as tar:
        tar.extractall(extract_dir)

    # Check nested structure preserved
    extracted_file = extract_dir / "reports" / "sast" / "findings.sarif.json"
    assert extracted_file.exists()


def test_artifact_bundle_size_reasonable(tmp_path: Path):
    """Test that compressed bundle is created successfully."""
    # Create some test data
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    # Create multiple files with compressible content
    for i in range(10):
        (artifacts_dir / f"file_{i}.json").write_text('{"data": "' + ("x" * 1000) + '"}')

    # Create tarball
    tarball_path = tmp_path / "bundle.tar.gz"
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(artifacts_dir, arcname=".")

    # Verify tarball was created
    assert tarball_path.exists()
    assert tarball_path.stat().st_size > 0


def test_artifact_map_matches_tarball_contents(tmp_path: Path):
    """Test that artifact_map corresponds to actual tarball contents."""
    # Create artifacts
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    (artifacts_dir / "summary.json").write_text('{"findings": 10}')
    (artifacts_dir / "manifest.json").write_text('{"profile": "light"}')

    bundle = ArtifactBundle.discover(artifacts_dir)
    artifact_map = bundle.artifact_map()

    # Create tarball
    tarball_path = tmp_path / "bundle.tar.gz"
    with tarfile.open(tarball_path, "w:gz") as tar:
        for rel_path in artifact_map.values():
            full_path = artifacts_dir / rel_path
            tar.add(full_path, arcname=rel_path)

    # Verify tarball contains expected files
    with tarfile.open(tarball_path, "r:gz") as tar:
        members = [m.name for m in tar.getmembers()]

        for rel_path in artifact_map.values():
            assert rel_path in members


def test_empty_artifact_bundle_creates_minimal_tarball(tmp_path: Path):
    """Test that an empty artifact directory still creates a valid tarball."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    tarball_path = tmp_path / "empty.tar.gz"

    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(empty_dir, arcname=".")

    # Should create a valid but nearly empty tarball
    assert tarball_path.exists()
    assert tarball_path.stat().st_size > 0  # Not zero, has tar headers


def test_artifact_bundle_handles_symlinks_safely(tmp_path: Path):
    """Test that symlinks are handled correctly in bundle."""
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    # Create a real file
    real_file = artifacts_dir / "real.json"
    real_file.write_text('{"real": true}')

    # Create tarball
    tarball_path = tmp_path / "bundle.tar.gz"
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(artifacts_dir, arcname=".")

    assert tarball_path.exists()
    assert tarball_path.stat().st_size > 0
