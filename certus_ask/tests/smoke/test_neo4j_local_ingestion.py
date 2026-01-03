from __future__ import annotations

import os
import subprocess
from typing import Any

import pytest
import requests
from requests.auth import HTTPBasicAuth

pytestmark = pytest.mark.smoke


def _run_cypher(
    session: requests.Session,
    statement: str,
    timeout: int,
    params: dict[str, Any] | None = None,
) -> list[dict]:
    neo4j_url = os.getenv("NEO4J_HTTP_URL", "http://neo4j:7474/db/neo4j/tx/commit")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    payload = {
        "statements": [
            {
                "statement": statement,
                "parameters": params or {},
            }
        ]
    }
    response = session.post(
        neo4j_url,
        json=payload,
        auth=HTTPBasicAuth(neo4j_user, neo4j_password),
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    rows: list[dict] = []
    for result in data.get("results", []):
        columns = result.get("columns", [])
        for entry in result.get("data", []):
            row_data = entry.get("row", [])
            rows.append(dict(zip(columns, row_data)))
    return rows


def test_neo4j_local_ingestion(
    http_session: requests.Session,
    request_timeout: int,
    workspace_id: str,
) -> None:
    """
    Mirror docs/learn/security-workflows/neo4j-local-ingestion.md.

    Execute the loader script and validate the graph contents via Cypher.
    """
    workspace = f"{workspace_id}-neo4j"
    scan_id = f"{workspace}-scan"
    sbom_id = f"{workspace}-sbom"

    cmd = [
        "python",
        "scripts/load_security_into_neo4j.py",
        "--workspace",
        workspace,
        "--neo4j-uri",
        os.getenv("NEO4J_BOLT_URI", "neo4j://neo4j:7687"),
        "--neo4j-user",
        os.getenv("NEO4J_USER", "neo4j"),
        "--neo4j-password",
        os.getenv("NEO4J_PASSWORD", "password"),
    ]
    try:
        subprocess.run(cmd, check=True, cwd=".", capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise AssertionError(
            f"Neo4j loader failed:\nSTDOUT:\n{exc.stdout or '(empty)'}\n\nSTDERR:\n{exc.stderr or '(empty)'}"
        ) from exc

    findings = _run_cypher(
        http_session,
        """
        MATCH (:SecurityScan {id: $scan_id})-[:CONTAINS]->(f:Finding)
        RETURN count(f) AS findings
        """,
        request_timeout,
        params={"scan_id": scan_id},
    )
    assert findings and findings[0].get("findings", 0) > 0, "Neo4j SecurityScan has no findings"

    severity_distribution = _run_cypher(
        http_session,
        """
        MATCH (:SecurityScan {id: $scan_id})-[:CONTAINS]->(f:Finding)
        RETURN f.severity AS severity, count(f) AS count
        """,
        request_timeout,
        params={"scan_id": scan_id},
    )
    assert severity_distribution, "Severity distribution query returned no rows"

    packages = _run_cypher(
        http_session,
        """
        MATCH (:SBOM {id: $sbom_id})-[:CONTAINS]->(pkg:Package)
        RETURN count(pkg) AS packages
        """,
        request_timeout,
        params={"sbom_id": sbom_id},
    )
    assert packages and packages[0].get("packages", 0) > 0, "SBOM packages missing from Neo4j"

    license_counts = _run_cypher(
        http_session,
        """
        MATCH (:SBOM {id: $sbom_id})-[:CONTAINS]->(pkg:Package)-[:USES_LICENSE]->(lic:License)
        RETURN lic.name AS license, count(pkg) AS usage
        """,
        request_timeout,
        params={"sbom_id": sbom_id},
    )
    assert license_counts, "License query returned no results"
