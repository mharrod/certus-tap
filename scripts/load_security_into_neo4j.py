#!/usr/bin/env python3
"""Utility script for loading SARIF and SBOM samples into Neo4j."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from certus_ask.pipelines.neo4j_loaders import SarifToNeo4j, SpdxToNeo4j


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load SARIF/SBOM artifacts into Neo4j.")
    parser.add_argument("--workspace", default="neo4j-security-scans", help="Workspace/tag suffix for scan IDs.")
    parser.add_argument(
        "--neo4j-uri",
        default="neo4j://localhost:7687",
        help="Bolt URI for Neo4j (use neo4j://neo4j:7687 when running inside docker).",
    )
    parser.add_argument("--neo4j-user", default="neo4j", help="Neo4j username.")
    parser.add_argument("--neo4j-password", default="password", help="Neo4j password.")
    parser.add_argument(
        "--sarif",
        default="samples/security-scans/sarif/security-findings.sarif",
        help="Path to the SARIF file to ingest.",
    )
    parser.add_argument(
        "--sbom",
        default="samples/security-scans/spdx/sbom-example.spdx.json",
        help="Path to the SPDX JSON file to ingest.",
    )
    parser.add_argument("--skip-sarif", action="store_true", help="Skip SARIF ingestion.")
    parser.add_argument("--skip-sbom", action="store_true", help="Skip SBOM ingestion.")

    args = parser.parse_args()

    sarif_stats = None
    sbom_stats = None

    if not args.skip_sarif:
        sarif_path = Path(args.sarif).expanduser().resolve()
        sarif_data = load_json(sarif_path)
        sarif_loader = SarifToNeo4j(args.neo4j_uri, args.neo4j_user, args.neo4j_password)
        scan_id = f"{args.workspace}-scan"
        sarif_stats = sarif_loader.load(sarif_data, scan_id)
        sarif_loader.close()
        print(f"SARIF ingest complete -> scan_id={scan_id} stats={sarif_stats}")
    else:
        print("Skipping SARIF ingestion")

    if not args.skip_sbom:
        sbom_path = Path(args.sbom).expanduser().resolve()
        sbom_data = load_json(sbom_path)
        spdx_loader = SpdxToNeo4j(args.neo4j_uri, args.neo4j_user, args.neo4j_password)
        sbom_id = f"{args.workspace}-sbom"
        sbom_stats = spdx_loader.load(sbom_data, sbom_id)
        spdx_loader.close()
        print(f"SBOM ingest complete -> sbom_id={sbom_id} stats={sbom_stats}")
    else:
        print("Skipping SBOM ingestion")

    if sarif_stats is None and sbom_stats is None:
        print("No ingestion performed. Provide at least one artifact.")


if __name__ == "__main__":
    main()
