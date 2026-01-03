#!/usr/bin/env python3
"""Generate in-toto attestation for security scan results."""

import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone
from typing import Any


def compute_sha256(file_path: pathlib.Path) -> str:
    """Compute SHA256 digest of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def generate_attestation(
    artifact_root: str,
    bundle_id: str,
    executed_tools: list[str],
    source_repo: str = "",
    source_ref: str = "",
) -> dict[str, Any]:
    """Generate in-toto attestation for scan results.

    Args:
        artifact_root: Directory containing scan artifacts
        bundle_id: Unique identifier for this scan bundle
        executed_tools: List of tools that were executed
        source_repo: Source repository URL (optional)
        source_ref: Source git reference/commit (optional)

    Returns:
        in-toto attestation dictionary
    """
    artifact_dir = pathlib.Path(artifact_root)

    # Collect subjects (artifacts with digests)
    subjects = []

    # Known artifact files to include
    artifact_files = [
        "summary.json",
        "ruff.txt",
        "bandit.json",
        "opengrep.sarif.json",
        "detect-secrets.json",
        "trivy.sarif.json",
        "privacy-findings.json",
        "sbom.spdx.json",
        "sbom.cyclonedx.json",
    ]

    for artifact_file in artifact_files:
        file_path = artifact_dir / artifact_file
        if file_path.exists():
            digest = compute_sha256(file_path)
            subjects.append({"name": artifact_file, "digest": {"sha256": digest}})

    # Build materials (inputs to the scan)
    materials = []
    if source_repo:
        materials.append({"uri": source_repo, "digest": {"gitCommit": source_ref} if source_ref else {}})

    # Build predicate
    predicate = {
        "buildType": "https://certus.dev/security-scan/v1",
        "builder": {"id": "https://certus.dev/dagger-security-module/v1"},
        "invocation": {
            "configSource": {"entryPoint": "security.full" if "sbom" in executed_tools else "security.standard"},
            "parameters": {"bundleId": bundle_id, "executedTools": executed_tools},
            "environment": {"timestamp": datetime.now(timezone.utc).isoformat()},
        },
        "metadata": {
            "buildStartedOn": datetime.now(timezone.utc).isoformat(),
            "buildFinishedOn": datetime.now(timezone.utc).isoformat(),
            "completeness": {
                "parameters": True,
                "environment": False,  # Not capturing full environment
                "materials": bool(materials),
            },
            "reproducible": False,  # Security scans are not reproducible
        },
        "materials": materials,
    }

    # Generate in-toto statement
    attestation = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": subjects,
        "predicateType": "https://in-toto.io/attestation/v1",
        "predicate": predicate,
    }

    return attestation


def main(artifact_root: str, executed_json: str, bundle_id: str, source_repo: str = "", source_ref: str = "") -> None:
    """Generate in-toto attestation file.

    Args:
        artifact_root: Directory to write attestation
        executed_json: JSON string of executed tools
        bundle_id: Bundle identifier
        source_repo: Source repository URL (optional)
        source_ref: Source git reference (optional)
    """
    executed_tools = json.loads(executed_json)

    attestation = generate_attestation(artifact_root, bundle_id, executed_tools, source_repo, source_ref)

    artifact_dir = pathlib.Path(artifact_root)
    attestation_file = artifact_dir / "attestation.intoto.json"
    attestation_file.write_text(json.dumps(attestation, indent=2))

    print(f"Generated attestation: {attestation_file}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(
            f"Usage: {sys.argv[0]} <artifact_root> <executed_json> <bundle_id> [source_repo] [source_ref]",
            file=sys.stderr,
        )
        sys.exit(1)

    artifact_root = sys.argv[1]
    executed_json = sys.argv[2]
    bundle_id = sys.argv[3]
    source_repo = sys.argv[4] if len(sys.argv) > 4 else ""
    source_ref = sys.argv[5] if len(sys.argv) > 5 else ""

    main(artifact_root, executed_json, bundle_id, source_repo, source_ref)
