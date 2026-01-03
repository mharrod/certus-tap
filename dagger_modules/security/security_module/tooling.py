"""Shared tooling helpers for the security module."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from security_module.constants import MODULE_ROOT
from security_module.manifest import ManifestProfileConfig

PRIVACY_SCRIPT_PATH = MODULE_ROOT / "security_module" / "scripts" / "privacy_scan.py"
SUMMARY_SCRIPT_PATH = MODULE_ROOT / "security_module" / "scripts" / "generate_summary.py"
ATTESTATION_SCRIPT_PATH = MODULE_ROOT / "security_module" / "scripts" / "generate_attestation.py"

TRIVY_SKIP_DIRS = [
    ".git",
    ".venv",
    "dist",
    "build",
    "node_modules",
    "site",
]


@dataclass
class ToolCommand:
    name: str
    command: Sequence[str]
    description: str


PROFILE_TOOLS = {
    "smoke": ["ruff"],
    "fast": ["ruff", "bandit", "detect-secrets"],
    "medium": ["ruff", "bandit", "detect-secrets", "opengrep", "attestation"],
    "standard": ["ruff", "bandit", "detect-secrets", "trivy", "sbom", "attestation"],
    "full": [
        "ruff",
        "bandit",
        "detect-secrets",
        "opengrep",
        "trivy",
        "privacy",
        "sbom",
        "attestation",
    ],
    "javascript": [
        "eslint-security",
        "retire-js",
        "detect-secrets",
        "trivy",
        "sbom",
        "attestation",
    ],
    "attestation-test": ["ruff", "sbom", "attestation"],
    "sbom-only": ["sbom"],
    "light": ["ruff", "bandit", "detect-secrets", "opengrep", "trivy", "privacy", "sbom", "attestation"],
    "heavy": [
        "ruff",
        "bandit",
        "detect-secrets",
        "opengrep",
        "trivy",
        "privacy",
        "sbom",
        "dast",
        "attestation",
    ],
}

SUPPORTED_TOOLS = {
    "ruff",
    "bandit",
    "opengrep",
    "detect-secrets",
    "trivy",
    "privacy",
    "eslint-security",
    "retire-js",
    "sbom",
    "attestation",
    "dast",
}

STACK_REQUIRED_PROFILES = {"heavy"}


def validate_profile_name(profile: str, has_manifest: bool) -> None:
    """Validate profile name. Custom names are only allowed when a manifest is provided."""
    if has_manifest:
        # With manifest, any profile name is allowed
        return

    # Without manifest, profile must be a built-in name
    if profile not in PROFILE_TOOLS:
        valid_profiles = ", ".join(sorted(PROFILE_TOOLS.keys()))
        raise ValueError(
            f"Unknown profile '{profile}'. Built-in profiles: {valid_profiles}. "
            f"To use custom profile names, provide a --manifest with a matching profile entry."
        )


def resolve_tools(profile: str, manifest_profile: ManifestProfileConfig | None) -> tuple[list[str], list[str]]:
    """Return (selected_tools, unsupported_tools)."""
    if manifest_profile:
        selected: list[str] = []
        unsupported: list[str] = []
        for tool in manifest_profile.tools:
            if tool in SUPPORTED_TOOLS:
                selected.append(tool)
            else:
                unsupported.append(tool)
        if selected:
            return selected, unsupported
        return PROFILE_TOOLS.get(profile, PROFILE_TOOLS["light"]), unsupported
    return PROFILE_TOOLS.get(profile, PROFILE_TOOLS["light"]), []


def profile_requires_stack(
    profile: str,
    manifest_profile: ManifestProfileConfig | None,
    selected_tools: list[str],
) -> bool:
    if manifest_profile and manifest_profile.requires_stack:
        return True
    if "dast" in selected_tools:
        return True
    return profile in STACK_REQUIRED_PROFILES


def build_manifest_metadata(
    manifest_profile: ManifestProfileConfig | None,
    profile_name: str,
    selected_tools: list[str],
    unsupported: list[str],
) -> dict[str, object]:
    return {
        "product": manifest_profile.product if manifest_profile else None,
        "version": manifest_profile.version if manifest_profile else None,
        "profile_requested": profile_name,
        "profile_resolved": (manifest_profile.profile_name if manifest_profile else profile_name),
        "tools_selected": selected_tools,
        "manifest_digest": manifest_profile.digest if manifest_profile else None,
        "unsupported_manifest_tools": unsupported,
        "policy_thresholds": (manifest_profile.thresholds if manifest_profile else None),
        "requires_stack": (
            manifest_profile.requires_stack if manifest_profile else profile_name in STACK_REQUIRED_PROFILES
        ),
    }
