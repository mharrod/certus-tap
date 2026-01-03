from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import requests

from tests.smoke.utils import post_file

pytestmark = pytest.mark.smoke

REPO_ROOT = Path(os.getenv("SMOKE_REPO_ROOT", Path(__file__).resolve().parents[3]))
WORKFLOW_SCRIPT = Path(os.getenv("WORKFLOW_SCRIPT", REPO_ROOT / "scripts/attestations-workflow.sh"))
OCI_BASE_OUTPUT = Path(os.getenv("SMOKE_OCI_ARTIFACT_ROOT", "/tmp/oci-attestations-smoke"))
OCI_PRODUCT_NAME = os.getenv("SMOKE_OCI_PRODUCT", "Smoke Product")
OCI_PRODUCT_VERSION = os.getenv("SMOKE_OCI_VERSION", "9.9.9")
OCI_REGISTRY_URL = os.getenv("SMOKE_OCI_REGISTRY", "http://local-oci-registry:5000")
OCI_REGISTRY_REPO = os.getenv("SMOKE_OCI_REPO", "product-acquisition/attestations")

SARIF_PHRASE = "SQL Injection vulnerability detected in database query handling"
ATTESTATION_TEXT = f"Build successful for {OCI_PRODUCT_NAME} v{OCI_PRODUCT_VERSION}"
PROVENANCE_TEXT = "Build completed successfully. All tests passed."


def _sanitize_workspace(name: str) -> str:
    sanitized = re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-")
    return sanitized or "default"


def _run_workflow(output_dir: Path) -> None:
    env = os.environ.copy()
    env.update({
        "OUTPUT_DIR": str(output_dir),
        "PRODUCT_NAME": OCI_PRODUCT_NAME,
        "PRODUCT_VERSION": OCI_PRODUCT_VERSION,
        "REGISTRY_URL": OCI_REGISTRY_URL,
        "REGISTRY_REPO": OCI_REGISTRY_REPO,
    })
    result = subprocess.run(
        ["/bin/bash", str(WORKFLOW_SCRIPT)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            "Attestations workflow failed:\n"
            f"STDOUT:\n{result.stdout or '(empty)'}\n\nSTDERR:\n{result.stderr or '(empty)'}"
        )


@pytest.mark.usefixtures("http_session")
def test_oci_attestations_workflow(
    http_session: requests.Session,
    api_base: str,
    request_timeout: int,
    workspace_id: str,
    wait_for_phrase,
) -> None:
    """
    Mirror docs/learn/provenance/oci-attestations-tutorial.md.

    Generates signed artifacts, mimics the OCI push/pull handoff, and ingests the bundle.
    """
    workspace = f"{workspace_id}-oci-attestations"
    workspace_index = f"ask_certus_{_sanitize_workspace(workspace)}"

    timestamp = int(time.time())
    output_dir = OCI_BASE_OUTPUT / f"{_sanitize_workspace(workspace)}-{timestamp}"
    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    _run_workflow(output_dir)

    sbom_file = output_dir / "sbom/product.spdx.json"
    attestation_file = output_dir / "attestations/build.intoto.json"
    sarif_file = output_dir / "scans/vulnerability.sarif"
    provenance_file = output_dir / "provenance/slsa-provenance.json"

    for artifact in (sbom_file, attestation_file, sarif_file, provenance_file):
        assert artifact.exists(), f"Expected workflow artifact missing: {artifact}"
        assert artifact.stat().st_size > 0, f"Artifact file empty: {artifact}"

    ingest_base = f"{api_base}/v1/{workspace}/index/"
    security_endpoint = f"{api_base}/v1/{workspace}/index/security"

    for file_path in (sbom_file, attestation_file, provenance_file):
        response = post_file(http_session, ingest_base, file_path, request_timeout)
        assert response.get("ingestion_id"), f"Ingestion response missing id for {file_path.name}: {response}"

    security_response = post_file(http_session, security_endpoint, sarif_file, request_timeout)
    assert security_response.get("ingestion_id"), "Security ingestion did not return ingestion_id"

    assert ATTESTATION_TEXT in attestation_file.read_text(), "Attestation file missing expected log line"
    assert PROVENANCE_TEXT in provenance_file.read_text(), "Provenance file missing expected log content"

    sarif_hits = wait_for_phrase(workspace_index, SARIF_PHRASE)
    assert sarif_hits["hits"]["total"]["value"] > 0, "SARIF findings missing from index"
