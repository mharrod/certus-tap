from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import requests

pytestmark = pytest.mark.smoke

TUTORIAL_SINGLE_PHRASE = "enterprise-grade document ingestion"
TUTORIAL_FOLDER_PHRASE = "Document Ingestion Endpoints"


def _ingest_single_document(
    session: requests.Session,
    api_base: str,
    workspace_id: str,
    document_path: Path,
    timeout: int,
) -> dict[str, Any]:
    url = f"{api_base}/v1/{workspace_id}/index/"
    with document_path.open("rb") as payload:
        files = {
            "uploaded_file": (document_path.name, payload, "text/plain"),
        }
        response = session.post(url, files=files, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    assert "ingestion_id" in data, "Single document ingestion response missing ingestion_id"
    assert data.get("document_count", 0) >= 1, "Document count not reported in single ingestion response"
    return data


def _ingest_folder(
    session: requests.Session,
    api_base: str,
    workspace_id: str,
    directory: str,
    timeout: int,
) -> dict[str, Any]:
    url = f"{api_base}/v1/{workspace_id}/index_folder/"
    response = session.post(
        url,
        json={"local_directory": directory},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    assert data.get("processed_files", 0) >= 1, "Folder ingestion did not report any processed files"
    return data


def test_ingestion_tutorial_end_to_end(
    http_session: requests.Session,
    api_base: str,
    os_endpoint: str,
    workspace_id: str,
    workspace_index: str,
    tutorial_sample_file: Path,
    tutorial_samples_dir_container: str,
    request_timeout: int,
    wait_for_phrase: Callable[[str, str, int, float], dict[str, Any]],
) -> None:
    """
    Replicate docs/learn/basics/ingestion-pipelines.md via API calls.

    Steps:
    1. Upload single document through `/v1/{workspace}/index/`
    2. Upload the tutorial folder via `/v1/{workspace}/index_folder/` (using container path)
    3. Confirm that tutorial phrases are queryable in OpenSearch
    """
    single_response = _ingest_single_document(
        http_session,
        api_base,
        workspace_id,
        tutorial_sample_file,
        request_timeout,
    )
    assert single_response["message"], "Single document response missing message"

    folder_response = _ingest_folder(
        http_session,
        api_base,
        workspace_id,
        tutorial_samples_dir_container,
        timeout=request_timeout * 2,
    )
    assert folder_response["ingestion_id"], "Folder ingestion did not return ingestion_id"

    single_hits = wait_for_phrase(workspace_index, TUTORIAL_SINGLE_PHRASE)
    assert single_hits["hits"]["total"]["value"] > 0, "No hits for single document phrase"

    folder_hits = wait_for_phrase(workspace_index, TUTORIAL_FOLDER_PHRASE)
    assert folder_hits["hits"]["total"]["value"] > 0, "No hits for folder ingestion phrase"
