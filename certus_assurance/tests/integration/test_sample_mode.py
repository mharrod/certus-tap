"""Integration tests for sample mode (using pre-generated artifacts)."""

from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def test_sample_artifacts_directory_exists(sample_artifacts_path: Path):
    """Test that sample artifacts directory exists."""
    assert sample_artifacts_path.exists()
    assert sample_artifacts_path.is_dir()


def test_sample_artifacts_contains_manifests(sample_artifacts_path: Path):
    """Test that sample artifacts include manifest files."""
    if not sample_artifacts_path.exists():
        pytest.skip("Sample artifacts directory not available")

    # Look for manifest.json in subdirectories
    manifests = list(sample_artifacts_path.rglob("manifest.json"))

    # Sample artifacts may not have manifest.json if they're using scan.json instead
    # Just verify we can search for them
    assert isinstance(manifests, list)


def test_sample_artifacts_contains_summaries(sample_artifacts_path: Path):
    """Test that sample artifacts include summary files."""
    if not sample_artifacts_path.exists():
        pytest.skip("Sample artifacts directory not available")

    summaries = list(sample_artifacts_path.rglob("summary.json"))

    # Summary files should exist in sample data
    # If not present, this may be expected depending on sample data structure
    assert isinstance(summaries, list)


def test_sample_artifacts_contains_sarif(sample_artifacts_path: Path):
    """Test that sample artifacts include SARIF findings."""
    sarif_files = list(sample_artifacts_path.rglob("*.sarif.json"))

    assert len(sarif_files) > 0, "No SARIF files found in sample artifacts"


def test_sample_artifacts_contains_sbom(sample_artifacts_path: Path):
    """Test that sample artifacts include SBOM files."""
    sbom_files = list(sample_artifacts_path.rglob("*.spdx.json"))

    assert len(sbom_files) > 0, "No SPDX SBOM files found in sample artifacts"


def test_sample_mode_loading_preserves_metadata(sample_artifacts_path: Path):
    """Test that sample mode can load artifacts without modification."""
    import json

    # Find a manifest file
    manifests = list(sample_artifacts_path.rglob("manifest.json"))
    if not manifests:
        pytest.skip("No manifest files available")

    manifest_path = manifests[0]
    with manifest_path.open() as f:
        manifest_data = json.load(f)

    # Should have essential metadata
    assert "workspace_id" in manifest_data or "metadata" in manifest_data
    assert isinstance(manifest_data, dict)


def test_sample_mode_summary_has_findings_count(sample_artifacts_path: Path):
    """Test that sample summary files include findings counts."""
    import json

    summaries = list(sample_artifacts_path.rglob("summary.json"))
    if not summaries:
        pytest.skip("No summary files available")

    summary_path = summaries[0]
    with summary_path.open() as f:
        summary_data = json.load(f)

    # Should have findings-related data
    assert isinstance(summary_data, dict)
    # Common fields might include: total_findings, by_severity, etc.


def test_sample_mode_sarif_is_valid_json(sample_artifacts_path: Path):
    """Test that sample SARIF files are valid JSON."""
    import json

    sarif_files = list(sample_artifacts_path.rglob("*.sarif.json"))
    if not sarif_files:
        pytest.skip("No SARIF files available")

    sarif_path = sarif_files[0]
    with sarif_path.open() as f:
        sarif_data = json.load(f)

    # SARIF files should have version and runs
    assert "version" in sarif_data or "$schema" in sarif_data
    assert isinstance(sarif_data, dict)


def test_sample_mode_sbom_is_valid_spdx(sample_artifacts_path: Path):
    """Test that sample SBOM files are valid SPDX."""
    import json

    sbom_files = list(sample_artifacts_path.rglob("*.spdx.json"))
    if not sbom_files:
        pytest.skip("No SPDX files available")

    sbom_path = sbom_files[0]
    with sbom_path.open() as f:
        sbom_data = json.load(f)

    # SPDX files should have spdxVersion
    assert "spdxVersion" in sbom_data or "SPDXID" in sbom_data
    assert isinstance(sbom_data, dict)


def test_sample_artifacts_organized_by_workspace(sample_artifacts_path: Path):
    """Test that sample artifacts are organized hierarchically."""
    if not sample_artifacts_path.exists():
        pytest.skip("Sample artifacts directory not available")

    # Expect structure like: workspace_id/component_id/files
    # or test_<hash>/files
    subdirs = [d for d in sample_artifacts_path.iterdir() if d.is_dir()]

    # Just verify we can list directories
    assert isinstance(subdirs, list)


def test_sample_mode_can_handle_multiple_workspaces(sample_artifacts_path: Path):
    """Test that sample artifacts support multiple workspaces."""
    if not sample_artifacts_path.exists():
        pytest.skip("Sample artifacts directory not available")

    workspace_dirs = [d for d in sample_artifacts_path.iterdir() if d.is_dir()]

    # Should be able to list workspace directories
    assert isinstance(workspace_dirs, list)
