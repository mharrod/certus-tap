#!/usr/bin/env python3
"""Sign security scan artifacts with cosign."""

import pathlib
import subprocess
import sys
from typing import Optional


def sign_artifact(
    artifact_path: pathlib.Path, cosign_bin: str = "/usr/local/bin/cosign", key_path: Optional[str] = None
) -> bool:
    """Sign a single artifact with cosign.

    Args:
        artifact_path: Path to artifact file to sign
        cosign_bin: Path to cosign binary
        key_path: Path to cosign private key (optional, uses keyless if not provided)

    Returns:
        True if signing succeeded, False otherwise
    """
    if not artifact_path.exists():
        print(f"Artifact not found: {artifact_path}", file=sys.stderr)
        return False

    try:
        cmd = [cosign_bin, "sign-blob"]

        if key_path:
            cmd.extend(["--key", key_path])
        else:
            # Keyless signing requires OIDC authentication
            # For CI/CD, use key-based signing instead
            print(f"Warning: Keyless signing not implemented for {artifact_path}", file=sys.stderr)
            return False

        cmd.extend([
            "--output-signature",
            f"{artifact_path}.sig",
            "--output-certificate",
            f"{artifact_path}.cert",
            str(artifact_path),
        ])

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode == 0:
            print(f"✓ Signed: {artifact_path.name}")
            return True
        else:
            print(f"✗ Failed to sign {artifact_path.name}: {result.stderr}", file=sys.stderr)
            return False

    except Exception as e:
        print(f"✗ Error signing {artifact_path.name}: {e}", file=sys.stderr)
        return False


def sign_all_artifacts(
    artifact_root: str, cosign_bin: str = "/usr/local/bin/cosign", key_path: Optional[str] = None
) -> int:
    """Sign all artifacts in the directory.

    Args:
        artifact_root: Directory containing artifacts
        cosign_bin: Path to cosign binary
        key_path: Path to cosign private key (optional)

    Returns:
        Number of successfully signed artifacts
    """
    artifact_dir = pathlib.Path(artifact_root)

    # Known artifact files to sign
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
        "attestation.intoto.json",
    ]

    signed_count = 0

    for artifact_file in artifact_files:
        file_path = artifact_dir / artifact_file
        if file_path.exists():
            if sign_artifact(file_path, cosign_bin, key_path):
                signed_count += 1

    return signed_count


def main(artifact_root: str, key_path: Optional[str] = None) -> None:
    """Sign all security scan artifacts.

    Args:
        artifact_root: Directory containing artifacts to sign
        key_path: Path to cosign private key (optional)
    """
    if not key_path:
        print("Note: Signing disabled (no key provided)", file=sys.stderr)
        print("To enable signing, provide cosign private key path", file=sys.stderr)
        return

    key_file = pathlib.Path(key_path)
    if not key_file.exists():
        print(f"Error: Key file not found: {key_path}", file=sys.stderr)
        sys.exit(1)

    signed_count = sign_all_artifacts(artifact_root, key_path=key_path)

    if signed_count > 0:
        print(f"\n✓ Successfully signed {signed_count} artifacts")
    else:
        print("\n✗ No artifacts were signed", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            f"Usage: {sys.argv[0]} <artifact_root> [key_path]",
            file=sys.stderr,
        )
        sys.exit(1)

    artifact_root = sys.argv[1]
    key_path = sys.argv[2] if len(sys.argv) > 2 else None

    main(artifact_root, key_path)
