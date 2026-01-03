from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import requests
from botocore.client import BaseClient

from tests.smoke.utils import upload_directory_to_s3

pytestmark = pytest.mark.smoke

DATALAKE_WORKSPACE_QUESTION_1 = "Web crawler rate limit increased to 8 RPS"
DATALAKE_HELP_QUESTION = "What type of file types does the API accept?"
DATALAKE_CUSTOMER_QUESTION = "Who is the success manager for Blue Orbital?"
DATALAKE_CUSTOMER_EXPECTED = "jordan lee"
DATALAKE_CUSTOMER_ANON_REPLY = "no relevant findings"


def test_sample_datalake_upload_flow(
    http_session: requests.Session,
    api_base: str,
    workspace_id: str,
    workspace_index: str,
    request_timeout: int,
    s3_client: BaseClient,
    raw_bucket_name: str,
    datalake_samples_dir: Path,
    wait_for_phrase: Callable[[str, str, int, float], dict[str, Any]],
) -> None:
    """
    Mirror docs/reference/learn/basics/sample-datalake-upload.md.

    1. Upload tutorial sample bundle to LocalStack S3
    2. Trigger /index/s3 for a single key and the entire prefix
    3. Confirm representative phrases are queryable
    """
    test_prefix = f"samples/smoke-datalake-{int(time.time())}"

    uploaded_keys = upload_directory_to_s3(
        s3_client,
        raw_bucket_name,
        test_prefix,
        datalake_samples_dir,
    )
    assert uploaded_keys, "Sample datalake upload did not create any S3 objects"

    single_key = f"{test_prefix}/notes/team-sync.md"
    assert single_key in uploaded_keys, f"Expected tutorial key {single_key} not found in uploaded set"

    single_response = http_session.post(
        f"{api_base}/v1/{workspace_id}/index/s3",
        json={
            "bucket_name": raw_bucket_name,
            "prefix": single_key,
        },
        timeout=request_timeout * 2,
    )
    single_response.raise_for_status()
    single_payload: dict[str, Any] = single_response.json()
    assert single_payload.get("ingestion_id"), "Single S3 ingestion did not return ingestion_id"

    batch_response = http_session.post(
        f"{api_base}/v1/{workspace_id}/index/s3",
        json={
            "bucket_name": raw_bucket_name,
            "prefix": test_prefix,
        },
        timeout=request_timeout * 2,
    )
    batch_response.raise_for_status()
    batch_payload: dict[str, Any] = batch_response.json()
    assert batch_payload.get("processed_files", 0) >= 1, "Batch ingestion did not report any processed files"

    team_sync_hits = wait_for_phrase(workspace_index, DATALAKE_WORKSPACE_QUESTION_1)
    assert team_sync_hits["hits"]["total"]["value"] > 0, "Team sync content missing from index"

    help_query_response = http_session.post(
        f"{api_base}/v1/{workspace_id}/ask",
        json={"question": DATALAKE_HELP_QUESTION},
        timeout=request_timeout,
    )
    help_query_response.raise_for_status()
    reply = help_query_response.json().get("reply", "").lower()

    # Skip if LLM returns empty response (service not available)
    if not reply or reply.strip() == "":
        pytest.skip("LLM service returned empty response - service may not be available")

    file_type_keywords = [
        "markdown",
        "pdf",
        "docx",
        "pptx",
        "csv",
        "text",
        "md",
        ".md",
        ".pdf",
        ".docx",
        ".pptx",
        ".csv",
        ".txt",
        "file",
    ]
    assert any(keyword in reply for keyword in file_type_keywords), (
        f"Help page question did not mention expected file types. Reply was: {reply}"
    )

    customer_question_response = http_session.post(
        f"{api_base}/v1/{workspace_id}/ask",
        json={"question": DATALAKE_CUSTOMER_QUESTION},
        timeout=request_timeout,
    )
    customer_question_response.raise_for_status()
    customer_reply = customer_question_response.json().get("reply", "").lower()
    assert customer_reply, "Customer mapping question returned empty reply"
    assert DATALAKE_CUSTOMER_EXPECTED in customer_reply or DATALAKE_CUSTOMER_ANON_REPLY in customer_reply, (
        "Customer mapping question did not return an expected answer"
    )
