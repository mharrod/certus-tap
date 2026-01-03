#!/usr/bin/env python3
"""Embed manifest metadata inside generated artifacts."""

from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timezone

SARIF_FILES = {"bandit.json", "opengrep.sarif.json", "trivy.sarif.json", "eslint-security.sarif.json"}
GENERAL_JSON_FILES = {
    "detect-secrets.json",
    "privacy-findings.json",
    "summary.json",
    "ruff.txt",  # skipped (not json)
}
SBOM_SPDX = {"sbom.spdx.json"}
SBOM_CYCLONEDX = {"sbom.cyclonedx.json"}
ATTESTATION_FILES = {"attestation.intoto.json"}


def load_metadata(metadata_json: str) -> dict:
    return json.loads(metadata_json)


def annotate_sarif(data: dict, metadata: dict) -> dict:
    props = data.setdefault("properties", {})
    props["certus_manifest"] = metadata
    return data


def annotate_general(data: dict, metadata: dict) -> dict:
    data["_certus_manifest"] = metadata
    return data


def annotate_spdx(data: dict, metadata: dict) -> dict:
    annotations = data.setdefault("annotations", [])
    timestamp = datetime.now(timezone.utc).isoformat()
    annotations = [ann for ann in annotations if ann.get("comment") and "certus_manifest" in ann.get("comment", "")]
    annotations.append({
        "annotationType": "OTHER",
        "annotator": "Certus Security Module",
        "comment": json.dumps({"certus_manifest": metadata}),
        "timestamp": timestamp,
    })
    data["annotations"] = annotations
    return data


def annotate_cyclonedx(data: dict, metadata: dict) -> dict:
    meta = data.setdefault("metadata", {})
    props = meta.setdefault("properties", [])
    props = [prop for prop in props if prop.get("name") != "certus_manifest"]
    props.append({"name": "certus_manifest", "value": json.dumps(metadata, sort_keys=True)})
    meta["properties"] = props
    data["metadata"] = meta
    return data


def annotate_attestation(data: dict, metadata: dict) -> dict:
    predicate = data.setdefault("predicate", {})
    pred_meta = predicate.setdefault("metadata", {})
    pred_meta["certus_manifest"] = metadata
    predicate["metadata"] = pred_meta
    data["predicate"] = predicate
    return data


def annotate_file(file_path: pathlib.Path, metadata: dict) -> None:
    if not file_path.exists():
        return

    target = file_path.name
    try:
        if target == "ruff.txt":
            return  # not JSON
        data = json.loads(file_path.read_text())
    except json.JSONDecodeError:
        return

    if target in SARIF_FILES:
        data = annotate_sarif(data, metadata)
    elif target in SBOM_SPDX:
        data = annotate_spdx(data, metadata)
    elif target in SBOM_CYCLONEDX:
        data = annotate_cyclonedx(data, metadata)
    elif target in ATTESTATION_FILES:
        data = annotate_attestation(data, metadata)
    else:
        data = annotate_general(data, metadata)

    file_path.write_text(json.dumps(data, indent=2))


def main(artifact_root: str, metadata_json: str) -> None:
    artifact_dir = pathlib.Path(artifact_root)
    metadata = load_metadata(metadata_json)

    targets = {
        "summary.json",
        "bandit.json",
        "opengrep.sarif.json",
        "detect-secrets.json",
        "trivy.sarif.json",
        "privacy-findings.json",
        "sbom.spdx.json",
        "sbom.cyclonedx.json",
        "attestation.intoto.json",
        "eslint-security.sarif.json",
        "retire.json",
    }

    for filename in targets:
        annotate_file(artifact_dir / filename, metadata)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <artifact_root> <metadata_json>", file=sys.stderr)
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
