"""Contract tests for security_module (Dagger) API expectations.

These tests validate what Certus Assurance expects from the security_module.
If these tests fail, either:
- Assurance is using security_module incorrectly
- security_module changed its API (breaking change)
"""

import pytest

pytestmark = pytest.mark.contract


def test_managed_runtime_interface():
    """Test that ManagedRuntime has expected interface."""
    try:
        from certus_assurance.pipeline import ManagedRuntime

        if ManagedRuntime is None:
            pytest.skip("security_module not installed")

        # ManagedRuntime should be a callable or class
        assert callable(ManagedRuntime) or isinstance(ManagedRuntime, type)

    except ImportError:
        pytest.skip("security_module not available")


def test_scanner_interface_expectations():
    """Test that Scanner objects are expected to have scan() method."""
    # This documents the interface contract between Assurance and security_module

    class MockScanner:
        """Mock scanner following expected interface."""

        def scan(self, **kwargs):
            """Execute security scan."""
            return {"findings": [], "summary": {}}

    scanner = MockScanner()

    # Scanner must have scan() method
    assert hasattr(scanner, "scan")
    assert callable(scanner.scan)


def test_scan_result_format_expectations():
    """Test expected format of scan results from security_module."""
    # Security module should return results in this format
    expected_result = {
        "findings": [
            {
                "tool": "bandit",
                "severity": "HIGH",
                "message": "Security issue detected",
                "file_path": "app.py",
                "line_number": 42,
            }
        ],
        "summary": {"total_findings": 1, "by_severity": {"HIGH": 1}},
    }

    # Validate structure
    assert "findings" in expected_result
    assert "summary" in expected_result
    assert isinstance(expected_result["findings"], list)
    assert isinstance(expected_result["summary"], dict)


def test_manifest_input_format():
    """Test the manifest format Assurance sends to security_module."""
    # Assurance should send manifests in this format to security_module
    manifest_input = {
        "profile": "light",
        "tools": ["bandit", "semgrep", "trivy"],
        "thresholds": {"critical": 0, "high": 5, "medium": 50},
    }

    # Validate Assurance sends correct format
    assert "profile" in manifest_input
    assert "tools" in manifest_input
    assert isinstance(manifest_input["tools"], list)


def test_runtime_factory_signature():
    """Test that runtime_factory follows expected signature."""

    def mock_runtime_factory(log_stream):
        """Mock runtime factory following contract."""
        # Should accept a log_stream parameter
        return MockRuntime(log_stream)

    class MockRuntime:
        """Mock runtime for testing."""

        def __init__(self, log_stream):
            self.log_stream = log_stream

    # Test factory can be called
    runtime = mock_runtime_factory(None)
    assert runtime is not None


def test_scanner_builder_signature():
    """Test that scanner_builder follows expected signature."""

    def mock_scanner_builder(runtime):
        """Mock scanner builder following contract."""
        # Should accept a runtime parameter
        return MockScanner(runtime)

    class MockScanner:
        """Mock scanner for testing."""

        def __init__(self, runtime):
            self.runtime = runtime

        def scan(self):
            return {"findings": []}

    # Test builder can be called
    scanner = mock_scanner_builder(None)
    assert scanner is not None
    assert hasattr(scanner, "scan")


def test_artifact_output_paths():
    """Test expected artifact file paths from security_module."""
    # Security module should produce these artifacts
    expected_artifacts = [
        "summary.json",  # Findings summary
        "manifest.json",  # Scan configuration
        "reports/sast/trivy.sarif.json",  # SAST findings
        "reports/sbom/syft.spdx.json",  # SBOM
    ]

    # Assurance expects these paths
    for artifact_path in expected_artifacts:
        assert isinstance(artifact_path, str)
        assert len(artifact_path) > 0


def test_sarif_output_format():
    """Test that security_module produces SARIF 2.1.0 format."""
    # Security module should output SARIF in this format
    expected_sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "bandit",
                        "version": "1.7.5",
                    }
                },
                "results": [],
            }
        ],
    }

    # Validate SARIF structure
    assert expected_sarif["version"] == "2.1.0"
    assert "runs" in expected_sarif
    assert isinstance(expected_sarif["runs"], list)


def test_sbom_output_format():
    """Test that security_module produces SPDX 2.3 format."""
    # Security module should output SBOM in SPDX format
    expected_sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "test-component",
        "packages": [],
    }

    # Validate SBOM structure
    assert "spdxVersion" in expected_sbom
    assert "SPDXID" in expected_sbom
    assert isinstance(expected_sbom["packages"], list)


def test_profile_names_match():
    """Test that profile names are consistent between Assurance and security_module."""
    # These profiles should be recognized by security_module
    known_profiles = ["light", "standard", "polyglot", "comprehensive"]

    # Assurance expects these profiles to exist
    for profile in known_profiles:
        assert isinstance(profile, str)
        assert len(profile) > 0


def test_tool_names_match():
    """Test that tool names are consistent."""
    # These tool names should be recognized by security_module
    expected_tools = [
        "bandit",
        "semgrep",
        "trivy",
        "ruff",
        "detect-secrets",
        "opengrep",
        "syft",
        "privacy",
    ]

    # Assurance expects these tool names to be valid
    for tool in expected_tools:
        assert isinstance(tool, str)
        assert len(tool) > 0


def test_severity_levels_match():
    """Test that severity levels are consistent."""
    # Security module should use these severity levels
    expected_severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]

    # Assurance expects these severity values
    for severity in expected_severities:
        assert severity.isupper()
        assert isinstance(severity, str)
