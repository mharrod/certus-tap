#!/usr/bin/env python3
"""Placeholder DAST runner used for Phase 2 stack testing."""

from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timezone


def main(artifact_root: str, base_url: str | None = None) -> None:
    """Write a deterministic placeholder DAST report."""
    artifact_dir = pathlib.Path(artifact_root)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    target = base_url or "http://localhost:8005"
    findings = [
        {
            "id": "DAST-001",
            "severity": "medium",
            "description": "Simulated SQL injection probe",
            "target": target,
        }
    ]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": target,
        "findings": findings,
    }
    (artifact_dir / "dast-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <artifact_root> [stack_base_url]", file=sys.stderr)
        sys.exit(1)
    root = sys.argv[1]
    url = sys.argv[2] if len(sys.argv) > 2 else None
    main(root, url)
