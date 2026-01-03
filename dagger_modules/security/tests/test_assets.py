from pathlib import Path

from security_module import artifacts, constants


def test_privacy_sample_copied():
    privacy_dir = constants.PRIVACY_SAMPLE_DIR
    assert privacy_dir.exists(), "Bundled privacy sample directory missing"
    files = list(privacy_dir.rglob("*"))
    assert any(f.is_file() for f in files), "Privacy sample directory should contain files"


def test_semgrep_baseline_exists():
    config = constants.SEMGRP_CONFIG
    assert config.exists(), "Semgrep baseline config missing"
    content = config.read_text().strip()
    assert "rules" in content and "python-eval-audit" in content


def test_privacy_scan_script_exists():
    """Test that the privacy scan script exists and is valid Python."""
    script_path = constants.MODULE_ROOT / "security_module" / "scripts" / "privacy_scan.py"
    assert script_path.exists(), "Privacy scan script missing"
    content = script_path.read_text()
    assert "def main" in content
    assert "privacy_base" in content and "artifact_root" in content


def test_summary_script_exists():
    """Test that the summary generation script exists and is valid Python."""
    script_path = constants.MODULE_ROOT / "security_module" / "scripts" / "generate_summary.py"
    assert script_path.exists(), "Summary generation script missing"
    content = script_path.read_text()
    assert "def main" in content
    assert "executed" in content and "skipped" in content and "bundle_id" in content


def test_ensure_export_dir(tmp_path: Path):
    """Test the ensure_export_dir helper function."""
    test_dir = tmp_path / "nested" / "export" / "path"
    result = artifacts.ensure_export_dir(test_dir)
    assert result.exists()
    assert result.is_dir()
    assert result == test_dir
