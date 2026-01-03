import asyncio

import pytest
from security_module.runtime import RuntimeResult, ScanRequest
from security_module.scanner import SecurityScanner


class DummyRuntime:
    def __init__(self) -> None:
        self.requests: list[ScanRequest] = []

    async def run(self, request: ScanRequest) -> RuntimeResult:
        self.requests.append(request)
        return RuntimeResult(bundle_id="demo", artifacts="/tmp/demo")


def test_scanner_populates_manifest_profile(tmp_path):
    manifest_text = """
    {
        "product": "demo",
        "version": "1.0.0",
        "owners": ["dev@certus.dev"],
        "profiles": [{
            "name": "light",
            "tools": ["ruff", "bandit"]
        }]
    }
    """

    runtime = DummyRuntime()
    scanner = SecurityScanner(runtime)

    result = asyncio.run(
        scanner.run(
            profile="light",
            workspace=tmp_path,
            export_dir=tmp_path / "artifacts",
            manifest_text=manifest_text,
        )
    )

    assert result.bundle_id == "demo"
    assert runtime.requests, "ScanRequest should be recorded"

    request = runtime.requests[0]
    assert request.manifest_profile
    assert request.manifest_profile.product == "demo"
    assert request.selected_tools == ["ruff", "bandit"]
    assert request.requires_stack is False


def test_scanner_sets_stack_flag_when_manifest_requires(tmp_path):
    manifest_text = """
    {
        "product": "demo",
        "version": "1.0.0",
        "owners": ["dev@certus.dev"],
        "profiles": [{
            "name": "custom",
            "tools": ["dast"],
            "requiresStack": true,
            "thresholds": {"high": 0},
            "stackBaseUrl": "http://example-stack:8080"
        }]
    }
    """

    runtime = DummyRuntime()
    scanner = SecurityScanner(runtime)

    asyncio.run(
        scanner.run(
            profile="custom",
            workspace=tmp_path,
            export_dir=tmp_path / "artifacts",
            manifest_text=manifest_text,
        )
    )

    request = runtime.requests[0]
    assert request.requires_stack is True
    assert request.stack_base_url == "http://example-stack:8080"


def test_scanner_allows_custom_profile_name_with_manifest(tmp_path):
    """Custom profile names should work when a manifest is provided."""
    manifest_text = """
    {
        "product": "demo",
        "version": "1.0.0",
        "profiles": [{
            "name": "my-custom-ci-profile",
            "tools": ["ruff", "bandit"]
        }]
    }
    """

    runtime = DummyRuntime()
    scanner = SecurityScanner(runtime)

    result = asyncio.run(
        scanner.run(
            profile="my-custom-ci-profile",
            workspace=tmp_path,
            export_dir=tmp_path / "artifacts",
            manifest_text=manifest_text,
        )
    )

    assert result.bundle_id == "demo"
    request = runtime.requests[0]
    assert request.profile == "my-custom-ci-profile"
    assert request.selected_tools == ["ruff", "bandit"]


def test_scanner_rejects_unknown_profile_without_manifest(tmp_path):
    """Unknown profile names should be rejected when no manifest is provided."""
    runtime = DummyRuntime()
    scanner = SecurityScanner(runtime)

    with pytest.raises(ValueError, match="Unknown profile 'invalid-profile'"):
        asyncio.run(
            scanner.run(
                profile="invalid-profile",
                workspace=tmp_path,
                export_dir=tmp_path / "artifacts",
            )
        )


def test_scanner_accepts_builtin_profile_without_manifest(tmp_path):
    """Built-in profile names should work without a manifest."""
    runtime = DummyRuntime()
    scanner = SecurityScanner(runtime)

    result = asyncio.run(
        scanner.run(
            profile="fast",
            workspace=tmp_path,
            export_dir=tmp_path / "artifacts",
        )
    )

    assert result.bundle_id == "demo"
    request = runtime.requests[0]
    assert request.profile == "fast"
    assert "ruff" in request.selected_tools
    assert "bandit" in request.selected_tools
    assert "detect-secrets" in request.selected_tools
