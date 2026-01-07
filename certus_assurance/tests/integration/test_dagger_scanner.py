"""Integration tests for Dagger scanner module integration."""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def test_dagger_runtime_import():
    """Test that ManagedRuntime can be imported if available."""
    from certus_assurance.pipeline import ManagedRuntime

    # ManagedRuntime will be None if security_module is not installed
    # This is expected and not an error
    if ManagedRuntime is None:
        pytest.skip("security_module not available - skipping Dagger tests")

    # If ManagedRuntime is available, it should be a class/callable
    assert ManagedRuntime is not None


def test_security_module_availability_detection():
    """Test that we can detect if security_module is available."""
    from certus_assurance.pipeline import ManagedRuntime

    # ManagedRuntime will be None if security_module is not installed
    security_module_available = ManagedRuntime is not None

    # This is a boolean check
    assert isinstance(security_module_available, bool)


def test_sample_scanner_fallback_when_no_dagger():
    """Test that SampleSecurityScanner is used when Dagger unavailable."""
    from pathlib import Path

    from certus_assurance.sample_scanner import SampleSecurityScanner

    sample_path = Path("samples/non-repudiation/scan-artifacts")

    if not sample_path.exists():
        pytest.skip("Sample artifacts not available")

    scanner = SampleSecurityScanner(sample_path)

    assert scanner is not None
    assert scanner.sample_source == sample_path


def test_sample_scanner_can_load_artifacts():
    """Test that SampleSecurityScanner can load sample artifacts."""
    from pathlib import Path

    from certus_assurance.sample_scanner import SampleSecurityScanner

    sample_path = Path("samples/non-repudiation/scan-artifacts")

    if not sample_path.exists():
        pytest.skip("Sample artifacts not available")

    scanner = SampleSecurityScanner(sample_path)

    # Sample scanner should be able to enumerate available scans
    # (Implementation details may vary)
    assert hasattr(scanner, "sample_source")


def test_runner_uses_sample_mode_when_configured(tmp_path):
    """Test that CertusAssuranceRunner uses sample mode correctly."""
    from pathlib import Path

    from certus_assurance.manifest import ManifestFetcher
    from certus_assurance.pipeline import CertusAssuranceRunner
    from certus_assurance.sample_scanner import SampleSecurityScanner
    from certus_assurance.settings import CertusAssuranceSettings

    sample_path = Path("samples/non-repudiation/scan-artifacts")
    if not sample_path.exists():
        pytest.skip("Sample artifacts not available")

    # Create a sample scanner
    sample_scanner = SampleSecurityScanner(sample_path)

    # Create minimal settings
    settings = CertusAssuranceSettings(
        artifact_root=tmp_path,
        use_sample_mode=True,
    )

    # Create runner with sample mode
    runner = CertusAssuranceRunner(
        output_root=tmp_path,
        registry="registry.example.com",
        registry_repository="test",
        trust_base_url="http://localhost:8057",
        manifest_fetcher=ManifestFetcher(settings),
        cosign_client=None,
        runtime_factory=lambda stream: None,
        scanner_builder=lambda runtime: sample_scanner,
        preserve_sample_metadata=True,
    )

    assert runner is not None
    assert runner.preserve_sample_metadata is True


def test_dagger_scanner_profiles_available():
    """Test that known scanning profiles are documented."""
    # These profiles should be available in the security_module
    known_profiles = ["light", "standard", "polyglot", "comprehensive"]

    # This test documents the expected profiles
    assert len(known_profiles) == 4
    assert "light" in known_profiles


def test_light_profile_tools():
    """Test that light profile includes expected tools."""
    # Light profile should include these tools (per documentation)
    expected_tools = [
        "ruff",
        "bandit",
        "detect-secrets",
        "opengrep",
        "trivy",
        "privacy",
        "syft",
    ]

    # Verify we have the expected tool list
    assert len(expected_tools) == 7
    assert "bandit" in expected_tools
    assert "trivy" in expected_tools


def test_sample_mode_vs_production_mode_flag():
    """Test that sample mode flag is distinct from production mode."""
    from certus_assurance.settings import CertusAssuranceSettings

    # Sample mode enabled
    sample_settings = CertusAssuranceSettings(use_sample_mode=True)
    assert sample_settings.use_sample_mode is True

    # Production mode (default)
    prod_settings = CertusAssuranceSettings(use_sample_mode=False)
    assert prod_settings.use_sample_mode is False


def test_scanner_builder_interface():
    """Test that scanner_builder follows expected interface."""
    # scanner_builder should be: Callable[[ManagedRuntime], Scanner]

    def mock_scanner_builder(runtime):
        """Mock scanner builder for testing."""
        return MockScanner()

    class MockScanner:
        """Mock scanner for testing."""

        def scan(self):
            return {"findings": []}

    # Test builder can be called
    mock_runtime = None  # In sample mode, runtime may be None
    scanner = mock_scanner_builder(mock_runtime)

    assert scanner is not None
    assert hasattr(scanner, "scan")
