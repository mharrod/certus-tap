#!/usr/bin/env python3
"""
Smoke test for ingestion logging.

Steps:
1. POST the sample policy document to /v1/index/.
2. Poll OpenSearch until a document.indexed log appears for that doc_id.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

BASE_URL = "http://localhost:8000"
OPENSEARCH_URL = "http://localhost:9200"
SAMPLE_PATH = Path("samples/datalake-demo/policies/usage-policy.txt")
DOC_ID = SAMPLE_PATH.name
WAIT_SECONDS = 30


def ingest_sample() -> None:
    """Upload the sample policy document to /v1/index/."""
    if not SAMPLE_PATH.exists():
        raise FileNotFoundError(f"Sample file {SAMPLE_PATH} not found. Run from repo root or adjust SAMPLE_PATH.")

    with SAMPLE_PATH.open("rb") as handle:
        response = requests.post(
            f"{BASE_URL}/v1/index/",
            files={"uploaded_file": (DOC_ID, handle, "text/plain")},
            timeout=120,
        )
    response.raise_for_status()
    print("Ingestion response:", response.status_code, response.text[:200])


def search_latest_log(query: dict[str, Any]) -> list[dict[str, Any]]:
    """Execute a search query against logs-certus-tap."""
    response = requests.post(
        f"{OPENSEARCH_URL}/logs-certus-tap/_search",
        json=query,
        timeout=15,
    )
    response.raise_for_status()
    return response.json().get("hits", {}).get("hits", [])


def wait_for_document_indexed() -> dict[str, Any]:
    """Poll OpenSearch until document.indexed log for the sample doc appears."""
    deadline = time.time() + WAIT_SECONDS
    query = {
        "size": 1,
        "sort": [{"timestamp": {"order": "desc"}}],
        "query": {
            "bool": {
                "must": [
                    {"term": {"doc_id.keyword": DOC_ID}},
                    {"term": {"event.keyword": "document.indexed"}},
                ]
            }
        },
    }

    while time.time() < deadline:
        hits = search_latest_log(query)
        if hits:
            return hits[0]["_source"]
        time.sleep(2)

    raise RuntimeError(
        f"Timed out waiting for document.indexed log for doc_id={DOC_ID}. Ensure backend and OpenSearch are running."
    )


def main() -> int:
    try:
        ingest_sample()
        log_entry = wait_for_document_indexed()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print("Found log entry:")
    print(json.dumps(log_entry, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
