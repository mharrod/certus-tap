#!/usr/bin/env python3
"""Privacy data scanner for detecting PII patterns in sample files."""

import json
import pathlib
import re
import sys


def main(privacy_base: str, artifact_root: str) -> None:
    """Scan privacy sample files for PII patterns.

    Args:
        privacy_base: Directory containing privacy sample files to scan
        artifact_root: Directory to write findings JSON
    """
    base = pathlib.Path(privacy_base)
    artifact = pathlib.Path(artifact_root) / "privacy-findings.json"

    patterns = {
        "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "phone": r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",
    }

    results = []

    if base.exists():
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".txt", ".md", ".json", ".csv", ".log"}:
                continue
            try:
                content = path.read_text(errors="ignore")
            except Exception:
                continue
            for label, pattern in patterns.items():
                for match in re.finditer(pattern, content):
                    snippet = content[max(0, match.start() - 20) : match.end() + 20]
                    results.append({
                        "file": str(path),
                        "label": label,
                        "match": match.group(0),
                        "snippet": snippet.strip(),
                        "start": match.start(),
                        "end": match.end(),
                    })

    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps({"results": results}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <privacy_base> <artifact_root>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
