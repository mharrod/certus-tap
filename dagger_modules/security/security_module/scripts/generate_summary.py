#!/usr/bin/env python3
"""Generate summary.json for security scan results."""

import json
import pathlib
import sys
from datetime import datetime, timezone


def main(artifact_root: str, executed: list[str], skipped: list[str], bundle_id: str) -> None:
    """Generate summary JSON file.

    Args:
        artifact_root: Directory to write summary.json
        executed: List of tools that were executed
        skipped: List of tools that were skipped
        bundle_id: Identifier for this bundle
    """
    artifact = pathlib.Path(artifact_root)
    artifact.mkdir(parents=True, exist_ok=True)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "executed": executed,
        "skipped": skipped,
        "bundle_id": bundle_id,
    }

    target = artifact / "summary.json"
    target.write_text(json.dumps(summary, indent=2))

    # Ensure privacy findings file exists even if scan was skipped
    privacy = artifact / "privacy-findings.json"
    if not privacy.exists():
        privacy.write_text(json.dumps({"results": []}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(
            f"Usage: {sys.argv[0]} <artifact_root> <executed_json> <skipped_json> <bundle_id>",
            file=sys.stderr,
        )
        sys.exit(1)

    executed = json.loads(sys.argv[2])
    skipped = json.loads(sys.argv[3])
    main(sys.argv[1], executed, skipped, sys.argv[4])
