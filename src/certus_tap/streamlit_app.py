"""Streamlit-based operations console for Certus TAP.

Provides a lightweight UI for:
- Single document ingestion via the FastAPI backend.
- Batch ingestion of multiple uploaded files.
- Uploading files/archives to the raw S3 bucket (LocalStack or AWS).
- Triggering S3 batch ingestion and raw→golden promotions through existing APIs.
- Monitoring health/logs, metadata lookups, and ad-hoc `/v1/ask` smoke tests.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import zipfile
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import boto3
import requests
import streamlit as st
from botocore.exceptions import ClientError

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from certus_ask.services.presidio import get_analyzer, get_anonymizer

DEFAULT_API_BASE = os.getenv("DOCOPS_API_BASE", "http://localhost:8000")


def _normalize_local_endpoint(value: str | None, target: str) -> str:
    if not value:
        return target
    if "localhost" in value:
        return value
    hostname = value.split("//")[-1].split(":")[0]
    if "localstack" in hostname:
        return value.replace(hostname, "localhost")
    if "opensearch" in hostname:
        return value.replace(hostname, "localhost")
    return value


DEFAULT_S3_ENDPOINT = _normalize_local_endpoint(
    os.getenv("S3_ENDPOINT_URL", "http://localhost:4566"), "http://localhost:4566"
)
DEFAULT_REGION = os.getenv("AWS_REGION", "us-east-1")
DEFAULT_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "test")
DEFAULT_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
DEFAULT_RAW_BUCKET = os.getenv("DATALAKE_RAW_BUCKET", "raw")
DEFAULT_GOLDEN_BUCKET = os.getenv("DATALAKE_GOLDEN_BUCKET", "golden")
DEFAULT_OS_ENDPOINT = _normalize_local_endpoint(
    os.getenv("OPENSEARCH_ENDPOINT", os.getenv("OPENSEARCH_HOST", "http://localhost:9200")),
    "http://localhost:9200",
)
DEFAULT_DOCS_INDEX = os.getenv("OPENSEARCH_INDEX_PATTERN", os.getenv("OPENSEARCH_INDEX", "ask_certus*"))
DEFAULT_LOGS_INDEX = os.getenv("LOGS_INDEX", "logs-certus-tap")


LOGO_PATH = Path(__file__).resolve().parents[2] / "docs" / "assets" / "images" / "logo.png"

st.set_page_config(page_title="Certus TAP Console", layout="wide")
st.title("Certus TAP Control Room")
st.caption("Ingest content, manage S3 uploads, and promote datasets without leaving the browser.")


@st.cache_resource(show_spinner=False)
def _get_s3_client(
    *,
    endpoint_url: str,
    region: str,
    access_key: str,
    secret_key: str,
):
    endpoint_url = _normalize_local_endpoint(endpoint_url, "http://localhost:4566")
    session = boto3.session.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )
    return session.client("s3", endpoint_url=endpoint_url)


def ensure_bucket(client, bucket_name: str, region: str) -> None:
    """Ensure the bucket exists before uploading."""

    try:
        client.head_bucket(Bucket=bucket_name)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code not in {"404", "NoSuchBucket"}:
            raise
        create_kwargs = {"Bucket": bucket_name}
        if region != "us-east-1":
            create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
        client.create_bucket(**create_kwargs)


def upload_payloads(
    client,
    bucket: str,
    prefix: str,
    objects: Iterable[tuple[str, bytes]],
    region: str,
) -> list[str]:
    """Upload each payload to S3 and return uploaded keys."""

    ensure_bucket(client, bucket, region)
    keys: list[str] = []
    prefix = prefix.strip().strip("/")

    for name, data in objects:
        normalized = "/".join(part for part in name.split("/") if part)
        key = f"{prefix}/{normalized}" if prefix else normalized
        client.put_object(Bucket=bucket, Key=key, Body=data)
        keys.append(key)

    return keys


def extract_uploaded_files(uploaded_files, *, unzip_archives: bool) -> list[tuple[str, bytes]]:
    """Return tuples of (key, bytes) for each UploadedFile."""

    payloads: list[tuple[str, bytes]] = []

    for uploaded in uploaded_files:
        data = uploaded.getvalue()
        if unzip_archives and uploaded.name.lower().endswith(".zip"):
            base_name = uploaded.name.rsplit(".", 1)[0]
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    payloads.append((f"{base_name}/{member.filename}", archive.read(member)))
        else:
            payloads.append((uploaded.name, data))

    return payloads


def post_file(
    api_base: str, endpoint: str, uploaded_file, metadata: dict[str, str] | None = None, workspace_id: str = "default"
):
    """POST multipart data to FastAPI ingestion endpoints."""

    files = {
        "uploaded_file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }

    data = metadata or {}
    # Insert workspace_id into endpoint path: /v1/index/ -> /v1/default/index/
    if endpoint.startswith("/v1/"):
        endpoint = f"/v1/{workspace_id}{endpoint[3:]}"
    response = requests.post(f"{api_base}{endpoint}", files=files, data=data, timeout=120)
    response.raise_for_status()
    return response.json()


def post_json(api_base: str, endpoint: str, payload: dict, *, timeout: int = 120, workspace_id: str = "default"):
    # Insert workspace_id into endpoint path: /v1/ask -> /v1/default/ask
    if endpoint.startswith("/v1/"):
        endpoint = f"/v1/{workspace_id}{endpoint[3:]}"
    response = requests.post(f"{api_base}{endpoint}", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_health_checks(api_base: str) -> dict[str, tuple[bool, str]]:
    endpoints = {
        "Core": "/v1/health",
        "Ingestion": "/v1/health/ingestion",
        "Evaluation": "/v1/health/evaluation",
        "Embedder": "/v1/health/embedder",
        "Datalake": "/v1/health/datalake",
    }
    results: dict[str, tuple[bool, str]] = {}
    for name, path in endpoints.items():
        try:
            resp = requests.get(f"{api_base}{path}", timeout=10)
            resp.raise_for_status()
        except requests.RequestException as exc:
            results[name] = (False, str(exc))
        else:
            results[name] = (True, "OK")
    return results


@st.cache_data(ttl=60)
def fetch_existing_workspaces(os_endpoint: str) -> list[str]:
    """Fetch list of existing workspaces by querying OpenSearch for ask_certus_* indices."""
    url = f"{os_endpoint.rstrip('/')}/_cat/indices?format=json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return ["default"]

    try:
        indices = resp.json()
        workspaces = []
        for index in indices:
            index_name = index.get("index", "")
            if index_name.startswith("ask_certus_"):
                workspace_id = index_name.replace("ask_certus_", "")
                workspaces.append(workspace_id)

        # Always include "default" if not present
        if "default" not in workspaces:
            workspaces.insert(0, "default")
        return sorted(workspaces)
    except (ValueError, KeyError):
        return ["default"]


def fetch_logs(os_endpoint: str, index_pattern: str, limit: int = 5):
    url = f"{os_endpoint.rstrip('/')}/{index_pattern}/_search"
    payload = {"size": limit, "sort": [{"timestamp": {"order": "desc"}}]}
    try:
        resp = requests.get(url, json=payload, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return [], str(exc)
    hits = resp.json().get("hits", {}).get("hits", [])
    logs = [
        {
            "timestamp": hit.get("_source", {}).get("timestamp"),
            "level": hit.get("_source", {}).get("level"),
            "message": hit.get("_source", {}).get("message"),
        }
        for hit in hits
    ]
    return logs, ""


def _normalize_index_pattern(value: str) -> str:
    value = value.strip()
    if not value:
        return "*"
    return value if "*" in value else f"{value}*"


def search_metadata_envelope(os_endpoint: str, index_pattern: str, ingestion_id: str, workspace_id: str = "default"):
    # Use workspace-specific index
    pattern = f"ask_certus_{workspace_id}"
    url = f"{os_endpoint.rstrip('/')}/{pattern}/_search"
    query = {
        "size": 5,
        "_source": ["meta.metadata_envelope", "metadata_envelope"],
        "query": {
            "bool": {
                "should": [
                    {"match": {"meta.ingestion_id": ingestion_id}},
                    {"match": {"metadata_envelope.ingestion_id": ingestion_id}},
                    {"match": {"meta.metadata_envelope.ingestion_id": ingestion_id}},
                ],
                "minimum_should_match": 1,
            }
        },
    }
    try:
        resp = requests.post(
            url,
            json=query,
            params={"allow_no_indices": "true", "ignore_unavailable": "true"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        detail = getattr(exc.response, "text", str(exc))
        return None, detail

    hits = resp.json().get("hits", {}).get("hits", [])
    envelopes = [
        hit.get("_source", {}).get("meta", {}).get("metadata_envelope")
        or hit.get("_source", {}).get("metadata_envelope")
        for hit in hits
    ]
    envelopes = [env for env in envelopes if env]
    return {"hits": len(hits), "envelopes": envelopes}, ""


def search_by_filename(os_endpoint: str, index_pattern: str, filename: str, workspace_id: str = "default"):
    """Search documents by filename in metadata_envelope.extra.filename"""
    pattern = f"ask_certus_{workspace_id}"
    url = f"{os_endpoint.rstrip('/')}/{pattern}/_search"
    query = {
        "size": 10,
        "_source": ["meta.metadata_envelope", "metadata_envelope", "file_path"],
        "query": {
            "bool": {
                "should": [
                    {"match": {"metadata_envelope.extra.filename": filename}},
                    {"match": {"meta.metadata_envelope.extra.filename": filename}},
                    {"match": {"file_path": filename}},
                ],
                "minimum_should_match": 1,
            }
        },
    }
    try:
        resp = requests.post(
            url,
            json=query,
            params={"allow_no_indices": "true", "ignore_unavailable": "true"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        detail = getattr(exc.response, "text", str(exc))
        return None, detail

    hits = resp.json().get("hits", {}).get("hits", [])
    documents = [
        {
            "id": hit.get("_id"),
            "file_path": hit.get("_source", {}).get("file_path"),
            "metadata_envelope": (
                hit.get("_source", {}).get("meta", {}).get("metadata_envelope")
                or hit.get("_source", {}).get("metadata_envelope")
            ),
        }
        for hit in hits
    ]
    return {"hits": len(hits), "documents": documents}, ""


def search_pii_anonymized(os_endpoint: str, index_pattern: str, workspace_id: str = "default"):
    """Search documents that have PII anonymized"""
    pattern = f"ask_certus_{workspace_id}"
    url = f"{os_endpoint.rstrip('/')}/{pattern}/_search"
    query = {
        "size": 20,
        "_source": ["meta.metadata_envelope", "metadata_envelope", "file_path", "pii_anonymized", "pii_count"],
        "query": {"term": {"pii_anonymized": True}},
        "sort": [{"pii_count": {"order": "desc"}}],
    }
    try:
        resp = requests.post(
            url,
            json=query,
            params={"allow_no_indices": "true", "ignore_unavailable": "true"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        detail = getattr(exc.response, "text", str(exc))
        return None, detail

    hits = resp.json().get("hits", {}).get("hits", [])
    documents = [
        {
            "file_path": hit.get("_source", {}).get("file_path"),
            "pii_count": hit.get("_source", {}).get("pii_count", 0),
            "ingestion_id": (
                hit.get("_source", {}).get("meta", {}).get("metadata_envelope", {}).get("ingestion_id")
                or hit.get("_source", {}).get("metadata_envelope", {}).get("ingestion_id")
            ),
            "source": (
                hit.get("_source", {}).get("meta", {}).get("metadata_envelope", {}).get("source")
                or hit.get("_source", {}).get("metadata_envelope", {}).get("source")
            ),
        }
        for hit in hits
    ]
    return {"hits": len(hits), "documents": documents}, ""


def fetch_recent_ingestions(os_endpoint: str, index_pattern: str, limit: int = 5, workspace_id: str = "default"):
    pattern = f"ask_certus_{workspace_id}"
    url = f"{os_endpoint.rstrip('/')}/{pattern}/_search"
    size = max(limit * 10, limit)
    query = {
        "size": size,
        "_source": [
            "meta.metadata_envelope.ingestion_id",
            "meta.metadata_envelope.captured_at",
            "meta.metadata_envelope.source",
            "meta.metadata_envelope.source_location",
            "metadata_envelope",
        ],
        "sort": [{"_id": {"order": "desc"}}],
    }
    try:
        resp = requests.post(
            url,
            json=query,
            params={"allow_no_indices": "true", "ignore_unavailable": "true"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        detail = getattr(exc.response, "text", str(exc))
        return None, detail

    hits = resp.json().get("hits", {}).get("hits", [])
    seen: set[str] = set()
    results: list[dict[str, str | None]] = []
    for hit in hits:
        env = hit.get("_source", {}).get("meta", {}).get("metadata_envelope") or hit.get("_source", {}).get(
            "metadata_envelope"
        )
        if not env:
            continue
        ingestion_id = env.get("ingestion_id")
        if not ingestion_id or ingestion_id in seen:
            continue
        seen.add(ingestion_id)
        results.append({
            "ingestion_id": ingestion_id,
            "captured_at": env.get("captured_at"),
            "source": env.get("source"),
            "source_location": env.get("source_location"),
        })
        if len(results) >= limit:
            break
    return results, ""


def export_to_csv(data: list[dict], filename: str = "export.csv") -> bytes:
    """Convert list of dicts to CSV bytes"""
    if not data:
        return b""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    return output.getvalue().encode()


def fetch_index_statistics(os_endpoint: str, index_pattern: str, workspace_id: str = "default"):
    """Get overall index statistics"""
    pattern = f"ask_certus_{workspace_id}"
    url = f"{os_endpoint.rstrip('/')}/{pattern}/_search"
    query = {
        "size": 0,
        "aggs": {
            "total_docs": {"value_count": {"field": "_id"}},
            "by_source": {"terms": {"field": "metadata_envelope.source", "size": 100}},
            "by_pii": {"terms": {"field": "pii_anonymized", "size": 10}},
            "total_pii_entities": {"sum": {"field": "pii_count"}},
        },
    }
    try:
        resp = requests.post(
            url,
            json=query,
            params={"allow_no_indices": "true", "ignore_unavailable": "true"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return None, str(exc)

    result = resp.json()
    total_hits = result.get("hits", {}).get("total", {}).get("value", 0)
    aggs = result.get("aggregations", {})

    return {
        "total_documents": total_hits,
        "by_source": aggs.get("by_source", {}).get("buckets", []),
        "pii_stats": aggs.get("by_pii", {}).get("buckets", []),
        "total_pii_entities": int(aggs.get("total_pii_entities", {}).get("value", 0)),
    }, ""


def fetch_ingestion_timeline(os_endpoint: str, index_pattern: str, days: int = 30, workspace_id: str = "default"):
    """Get ingestion activity over time"""
    pattern = f"ask_certus_{workspace_id}"
    url = f"{os_endpoint.rstrip('/')}/{pattern}/_search"
    query = {
        "size": 0,
        "aggs": {
            "ingestions_over_time": {
                "date_histogram": {
                    "field": "metadata_envelope.captured_at",
                    "calendar_interval": "day",
                    "min_doc_count": 0,
                },
                "aggs": {
                    "unique_ingestions": {"cardinality": {"field": "metadata_envelope.ingestion_id"}},
                    "doc_count_per_day": {"value_count": {"field": "_id"}},
                },
            }
        },
        "query": {"range": {"metadata_envelope.captured_at": {"gte": f"now-{days}d"}}},
    }
    try:
        resp = requests.post(
            url,
            json=query,
            params={"allow_no_indices": "true", "ignore_unavailable": "true"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return None, str(exc)

    result = resp.json()
    buckets = result.get("aggregations", {}).get("ingestions_over_time", {}).get("buckets", [])
    timeline = []
    for b in buckets:
        # key_as_string is already formatted, just extract the date part
        date_str = b.get("key_as_string", "")
        if date_str:
            # Extract just the date part (YYYY-MM-DD) from ISO format
            date_str = date_str.split("T")[0]
        timeline.append({
            "date": date_str,
            "ingestions": b.get("unique_ingestions", {}).get("value", 0),
            "documents": b.get("doc_count_per_day", {}).get("value", 0),
        })
    return timeline, ""


def fetch_connector_health(os_endpoint: str, index_pattern: str, workspace_id: str = "default"):
    """Get health stats per connector type"""
    pattern = f"ask_certus_{workspace_id}"
    url = f"{os_endpoint.rstrip('/')}/{pattern}/_search"
    query = {
        "size": 0,
        "aggs": {
            "by_source": {
                "terms": {"field": "metadata_envelope.source", "size": 100},
                "aggs": {
                    "doc_count": {"value_count": {"field": "_id"}},
                    "last_ingestion": {"max": {"field": "metadata_envelope.captured_at"}},
                    "avg_pii": {"avg": {"field": "pii_count"}},
                },
            }
        },
    }
    try:
        resp = requests.post(
            url,
            json=query,
            params={"allow_no_indices": "true", "ignore_unavailable": "true"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return None, str(exc)

    result = resp.json()
    buckets = result.get("aggregations", {}).get("by_source", {}).get("buckets", [])
    return [
        {
            "source": b.get("key"),
            "documents": b.get("doc_count", {}).get("value", 0),
            "last_ingestion": datetime.fromtimestamp(b.get("last_ingestion", {}).get("value", 0) / 1000).strftime(
                "%Y-%m-%d %H:%M"
            )
            if b.get("last_ingestion", {}).get("value")
            else "N/A",
            "avg_pii_per_doc": round(b.get("avg_pii", {}).get("value", 0), 2),
        }
        for b in buckets
    ], ""


def search_with_content_preview(
    os_endpoint: str, index_pattern: str, query_dict: dict, limit: int = 10, workspace_id: str = "default"
):
    """Execute search and return content snippets"""
    pattern = f"ask_certus_{workspace_id}"
    url = f"{os_endpoint.rstrip('/')}/{pattern}/_search"
    query_dict["size"] = limit
    query_dict["_source"] = ["content", "file_path", "metadata_envelope"]

    try:
        resp = requests.post(
            url,
            json=query_dict,
            params={"allow_no_indices": "true", "ignore_unavailable": "true"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return None, str(exc)

    hits = resp.json().get("hits", {}).get("hits", [])
    results = []
    for hit in hits:
        source = hit.get("_source", {})
        content = source.get("content", "")
        snippet = content[:300] + "..." if len(content) > 300 else content
        results.append({
            "file": source.get("file_path", "N/A"),
            "snippet": snippet,
            "metadata": (source.get("metadata_envelope") or source.get("meta", {}).get("metadata_envelope")),
        })
    return results, ""


def create_alert(os_endpoint: str, alert_type: str, severity: str, context: dict):
    """Store an alert in OpenSearch"""
    url = f"{os_endpoint.rstrip('/')}/alerts-certus-tap/_doc"
    alert_doc = {
        "alert_type": alert_type,
        "severity": severity,
        "timestamp": datetime.utcnow().isoformat(),
        "context": context,
        "resolved": False,
    }
    try:
        resp = requests.post(url, json=alert_doc, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return False, str(exc)
    return True, ""


def search_logs(
    os_endpoint: str,
    index_pattern: str,
    search_query: str,
    log_level: str | None = None,
    days: int = 7,
    limit: int = 50,
):
    """Search logs with optional filtering by level and date range"""
    url = f"{os_endpoint.rstrip('/')}/{index_pattern}/_search"
    filters = [{"range": {"timestamp": {"gte": f"now-{days}d"}}}]

    if log_level:
        filters.append({"term": {"level": log_level}})

    query = {
        "size": limit,
        "sort": [{"timestamp": {"order": "desc"}}],
        "_source": ["timestamp", "level", "message", "logger"],
        "query": {
            "bool": {
                "must": [{"multi_match": {"query": search_query, "fields": ["message", "logger"]}}]
                if search_query
                else [{"match_all": {}}],
                "filter": filters,
            }
        },
    }

    try:
        resp = requests.post(
            url,
            json=query,
            params={"allow_no_indices": "true", "ignore_unavailable": "true"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return [], str(exc)

    hits = resp.json().get("hits", {}).get("hits", [])
    return [
        {
            "timestamp": hit.get("_source", {}).get("timestamp"),
            "level": hit.get("_source", {}).get("level"),
            "message": hit.get("_source", {}).get("message"),
            "logger": hit.get("_source", {}).get("logger"),
        }
        for hit in hits
    ], ""


def fetch_error_dashboard(os_endpoint: str, index_pattern: str, days: int = 7):
    """Get error statistics and recent errors"""
    url = f"{os_endpoint.rstrip('/')}/{index_pattern}/_search"
    query = {
        "size": 0,
        "query": {
            "bool": {"filter": [{"term": {"level": "ERROR"}}, {"range": {"timestamp": {"gte": f"now-{days}d"}}}]}
        },
        "aggs": {
            "error_count": {"value_count": {"field": "_id"}},
            "by_logger": {
                "terms": {"field": "logger.keyword", "size": 20},
                "aggs": {"count": {"value_count": {"field": "_id"}}},
            },
            "errors_over_time": {
                "date_histogram": {
                    "field": "timestamp",
                    "calendar_interval": "day",
                    "min_doc_count": 0,
                },
                "aggs": {"error_count": {"value_count": {"field": "_id"}}},
            },
        },
    }

    try:
        resp = requests.post(
            url,
            json=query,
            params={"allow_no_indices": "true", "ignore_unavailable": "true"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return None, str(exc)

    result = resp.json()
    aggs = result.get("aggregations", {})

    # Get recent errors
    url_recent = f"{os_endpoint.rstrip('/')}/{index_pattern}/_search"
    query_recent = {
        "size": 10,
        "sort": [{"timestamp": {"order": "desc"}}],
        "_source": ["timestamp", "message", "logger"],
        "query": {"term": {"level": "ERROR"}},
    }

    resp_recent = requests.post(url_recent, json=query_recent, timeout=10)
    recent_errors = [hit.get("_source", {}) for hit in resp_recent.json().get("hits", {}).get("hits", [])]

    return {
        "total_errors": aggs.get("error_count", {}).get("value", 0),
        "by_logger": aggs.get("by_logger", {}).get("buckets", []),
        "over_time": aggs.get("errors_over_time", {}).get("buckets", []),
        "recent_errors": recent_errors,
    }, ""


def fetch_log_aggregations(os_endpoint: str, index_pattern: str, days: int = 7):
    """Get log stats by source/connector and API endpoints"""
    url = f"{os_endpoint.rstrip('/')}/{index_pattern}/_search"
    query = {"size": 0, "aggs": {"by_level": {"terms": {"field": "level", "size": 10}}}}

    try:
        resp = requests.post(
            url,
            json=query,
            params={"allow_no_indices": "true", "ignore_unavailable": "true"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return None, str(exc)

    result = resp.json()
    aggs = result.get("aggregations", {})

    return {
        "by_level": aggs.get("by_level", {}).get("buckets", []),
        "by_logger": [],
    }, ""


def delete_old_logs(os_endpoint: str, index_pattern: str, days: int = 30) -> tuple[bool, str]:
    """Delete logs older than specified days"""
    url = f"{os_endpoint.rstrip('/')}/{index_pattern}/_delete_by_query"
    query = {"query": {"range": {"timestamp": {"lt": f"now-{days}d"}}}}

    try:
        resp = requests.post(url, json=query, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        deleted = result.get("deleted", 0)
        return True, f"Deleted {deleted} log entries"
    except requests.RequestException as exc:
        return False, str(exc)


def fetch_active_alerts(os_endpoint: str, limit: int = 20):
    """Fetch unresolved alerts"""
    url = f"{os_endpoint.rstrip('/')}/alerts-certus-tap/_search"
    query = {
        "size": limit,
        "query": {"term": {"resolved": False}},
        "sort": [{"timestamp": {"order": "desc"}}],
    }
    try:
        resp = requests.post(
            url,
            json=query,
            params={"allow_no_indices": "true", "ignore_unavailable": "true"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return [], str(exc)

    hits = resp.json().get("hits", {}).get("hits", [])
    return [
        {
            "id": hit.get("_id"),
            "type": hit.get("_source", {}).get("alert_type"),
            "severity": hit.get("_source", {}).get("severity"),
            "timestamp": hit.get("_source", {}).get("timestamp"),
            "context": hit.get("_source", {}).get("context"),
        }
        for hit in hits
    ], ""


def _apply_recent_selection():
    selected = st.session_state.get("metadata_recent_select")
    if selected:
        st.session_state["metadata_lookup_id"] = selected


if "workspace_id" not in st.session_state:
    st.session_state["workspace_id"] = "default"
if "metadata_recent_ingestions" not in st.session_state:
    st.session_state["metadata_recent_ingestions"] = []
if "metadata_lookup_id" not in st.session_state:
    st.session_state["metadata_lookup_id"] = ""
if "quarantine_objects" not in st.session_state:
    st.session_state["quarantine_objects"] = []
if "quarantine_selection" not in st.session_state:
    st.session_state["quarantine_selection"] = []

MENU_GROUPS = {
    "Learning": [
        "Security Analyst Capstone",
    ],
    "Security": [
        "Security Dashboard",
        "Finding Browser",
        "Scan History",
    ],
    "Query": [
        "Ask Certus",
        "Neo4j Cypher Query",
        "Neo4j Graph Explorer",
        "Semantic Search",
        "OpenSearch Query",
        "Search with Preview",
        "Query Templates",
    ],
    "Ingestion": [
        "Single Document Ingestion",
        "Batch Ingestion",
        "Security Files Upload",
        "Batch Ingest from S3",
        "Promote Raw → Golden",
    ],
    "S3": [
        "Upload to Raw Bucket",
        "Browse S3",
        "Manage Buckets",
    ],
    "Privacy": [
        "Privacy Scan",
        "Quarantine Review",
    ],
    "Observability": [
        "Monitoring",
        "Metadata Lookup",
        "Document Statistics",
        "Ingestion Timeline",
        "Connector Health",
        "Alerts",
        "Error Dashboard",
        "Log Search",
        "Log Aggregations",
        "Log Cleanup",
    ],
    "Batch Operations": [
        "Bulk Delete",
        "Re-index Documents",
        "Tag Documents",
    ],
}
ALL_SECTIONS = [item for group in MENU_GROUPS.values() for item in group]
DEFAULT_SECTION = "Ask Certus"
if "selected_section" not in st.session_state:
    st.session_state["selected_section"] = DEFAULT_SECTION if DEFAULT_SECTION in ALL_SECTIONS else ALL_SECTIONS[0]


@st.cache_resource(show_spinner=False)
def _get_privacy_services():
    analyzer = get_analyzer()
    anonymizer = get_anonymizer()
    return analyzer, anonymizer


def run_privacy_scan(text: str):
    analyzer, _ = _get_privacy_services()
    return analyzer.analyze(text=text, language="en")


def anonymize_text(text: str, results):
    _, anonymizer = _get_privacy_services()
    return anonymizer.anonymize(text=text, analyzer_results=results).text


def scan_s3_prefix_for_privacy(
    client,
    *,
    bucket: str,
    source_prefix: str,
    quarantine_prefix: str,
    limit: int | None = None,
):
    paginator = client.get_paginator("list_objects_v2")
    analyzer, _ = _get_privacy_services()
    scanned = 0
    quarantined = 0
    findings_report: list[dict[str, object]] = []
    source_prefix = source_prefix.lstrip("/")
    quarantine_prefix = quarantine_prefix.lstrip("/")

    for page in paginator.paginate(Bucket=bucket, Prefix=source_prefix):
        contents = page.get("Contents") or []
        for item in contents:
            key = item["Key"]
            if key.endswith("/"):
                continue
            scanned += 1

            obj = client.get_object(Bucket=bucket, Key=key)
            body = obj["Body"].read().decode("utf-8", errors="ignore")
            findings = analyzer.analyze(text=body, language="en")
            if findings:
                remainder = key[len(source_prefix) :] if source_prefix and key.startswith(source_prefix) else key
                remainder = remainder.lstrip("/")
                quarantine_key = (
                    f"{quarantine_prefix.rstrip('/')}/{remainder}" if quarantine_prefix else f"quarantine/{remainder}"
                )
                client.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": key}, Key=quarantine_key)
                client.delete_object(Bucket=bucket, Key=key)
                status = "quarantined"
                quarantined += 1
            else:
                status = "clean"

            findings_report.append({
                "key": key,
                "status": status,
                "pii_count": len(findings),
            })

            if limit and scanned >= limit:
                return findings_report, scanned, quarantined

    return findings_report, scanned, quarantined


def _set_section(option: str):
    st.session_state["selected_section"] = option


with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)

    # Display current workspace at the top
    current_workspace_top = st.session_state.get("workspace_id", "default")
    st.caption(f"📍 Current Workspace - **{current_workspace_top}**")
    st.divider()

    selected_section = st.session_state.get("selected_section", ALL_SECTIONS[0])
    for group_name, options in MENU_GROUPS.items():
        expanded = selected_section in options
        with st.expander(group_name, expanded=expanded):
            for option in options:
                st.button(
                    option,
                    key=f"menu_btn_{option}",
                    type="primary" if option == selected_section else "secondary",
                    use_container_width=True,
                    on_click=_set_section,
                    args=(option,),
                )
    with st.expander("Connection Settings", expanded=False):
        api_base = st.text_input("FastAPI base URL", DEFAULT_API_BASE)
        s3_endpoint = st.text_input("S3 endpoint", DEFAULT_S3_ENDPOINT)
        aws_region = st.text_input("AWS region", DEFAULT_REGION)
        raw_bucket = st.text_input("Raw bucket", DEFAULT_RAW_BUCKET)
        golden_bucket = st.text_input("Golden bucket", DEFAULT_GOLDEN_BUCKET)
        aws_key = st.text_input("AWS access key", DEFAULT_ACCESS_KEY)
        aws_secret = st.text_input("AWS secret key", DEFAULT_SECRET_KEY, type="password")
        os_endpoint = _normalize_local_endpoint(
            st.text_input("OpenSearch endpoint", DEFAULT_OS_ENDPOINT), DEFAULT_OS_ENDPOINT
        )
        docs_index = st.text_input("Docs index (supports wildcards)", DEFAULT_DOCS_INDEX)
        logs_index = st.text_input("Logs index pattern", f"{DEFAULT_LOGS_INDEX}*")

    # Workspace selector (after Connection Settings so os_endpoint is defined)
    st.subheader("Workspace")

    # Fetch existing workspaces from OpenSearch
    existing_workspaces = fetch_existing_workspaces(os_endpoint)

    # Add "Create new..." option at the beginning
    workspace_options = ["➕ Create new workspace...", *existing_workspaces]

    # Get current workspace selection
    current_workspace = st.session_state.get("workspace_id", "default")
    try:
        current_index = workspace_options.index(current_workspace)
    except ValueError:
        # If current workspace not in list, find the matching option or default to first
        current_index = 0 if current_workspace == "default" else 1

    # Selectbox for workspace selection
    selected = st.selectbox(
        "Select Workspace",
        workspace_options,
        index=current_index if current_index > 0 else 1,
        help="Choose an existing workspace or create a new one",
        key="workspace_selectbox",
    )

    # Handle "Create new workspace" option
    if selected == "➕ Create new workspace...":
        new_workspace = st.text_input(
            "Enter new workspace name", placeholder="e.g., product-a, client-xyz", key="new_workspace_input"
        )
        if new_workspace and st.button("Create Workspace", use_container_width=True):
            st.session_state["workspace_id"] = new_workspace.strip()
            # Clear the workspace cache so new workspace appears in dropdown
            fetch_existing_workspaces.clear()
            st.rerun()
    else:
        st.session_state["workspace_id"] = selected

    # Display current workspace
    st.caption(f"📍 Current: **{st.session_state.get('workspace_id', 'default')}**")
    st.divider()

selected_section = st.session_state.get("selected_section", ALL_SECTIONS[0])

if selected_section == "Monitoring":
    st.subheader("Stack Monitoring")
    col_health, col_logs = st.columns(2)
    with col_health:
        st.write("Service Health")
        health_results = fetch_health_checks(api_base)
        for name, (ok, details) in health_results.items():
            status = "✅" if ok else "❌"
            st.write(f"{status} {name} — {details}")
    with col_logs:
        st.write("Recent Logs")
        logs, log_error = fetch_logs(os_endpoint, logs_index)
        if log_error:
            st.error(f"Unable to fetch logs: {log_error}")
        elif logs:
            st.table(logs)
        else:
            st.info("No log entries returned.")

elif selected_section == "Single Document Ingestion":
    st.subheader("Single Document Ingestion")
    st.write("Send a single document through the preprocessing pipeline.")

    upload = st.file_uploader("Select document", type=None, accept_multiple_files=False)
    if st.button("Ingest Document", disabled=upload is None):
        if not upload:
            st.warning("Please choose a document before running ingestion.")
        else:
            with st.spinner("Running ingestion..."):
                try:
                    workspace_id = st.session_state.get("workspace_id", "default")
                    result = post_file(api_base, "/v1/index/", upload, metadata={}, workspace_id=workspace_id)
                except requests.RequestException as exc:
                    st.error(f"Failed to ingest document: {exc}")
                else:
                    st.success(f"Indexed {upload.name}")
                    st.json(result)

elif selected_section == "Batch Ingestion":
    st.subheader("Batch Ingestion")
    st.write("Upload multiple files and ingest them sequentially.")
    batch_uploads = st.file_uploader(
        "Select files",
        type=None,
        accept_multiple_files=True,
        key="batch_ingest_uploader",
    )
    if st.button("Run Batch Ingestion", disabled=not batch_uploads):
        successes: list[dict] = []
        failures: list[tuple[str, str]] = []
        with st.spinner("Processing batch..."):
            workspace_id = st.session_state.get("workspace_id", "default")
            for uploaded in batch_uploads or []:
                try:
                    result = post_file(api_base, "/v1/index/", uploaded, metadata={}, workspace_id=workspace_id)
                    successes.append({"name": uploaded.name, "ingestion_id": result.get("ingestion_id")})
                except requests.RequestException as exc:
                    failures.append((uploaded.name, str(exc)))
        if successes:
            st.success(f"Ingested {len(successes)} documents.")
            st.json(successes)
        if failures:
            st.error(f"{len(failures)} documents failed.")
            st.write(failures)

elif selected_section == "Security Files Upload":
    st.subheader("Security Files Upload")
    st.write("Upload security scanning results and SBOMs. Supports:")
    st.write("- **Pre-registered tools** (zero-config): Bandit, OpenGrep, Trivy")
    st.write("- **SARIF**: Static analysis results from security tools (Snyk, etc.)")
    st.write("- **SPDX**: Software bill of materials (JSON/YAML)")
    st.write("- **Custom JSONPath**: Define your own schema for any JSON security tool")
    st.write("\nFiles are indexed into both Neo4j (for relationships) and OpenSearch (for semantic search).")

    security_upload = st.file_uploader(
        "Select security file",
        type=["sarif", "json", "yaml", "yml", "spdx"],
        accept_multiple_files=False,
        key="security_uploader",
    )

    # Format selection with tool hints
    format_options = [
        "auto (auto-detect)",
        "sarif",
        "spdx",
        "bandit (pre-registered)",
        "opengrep (pre-registered)",
        "trivy (pre-registered)",
    ]

    selected_format_label = st.selectbox(
        "File Format",
        format_options,
        help="Auto-detect based on filename, select standard format, or choose a pre-registered security tool (zero-config)",
    )

    # Extract format and tool_hint from the label
    is_preregistered = "(pre-registered)" in selected_format_label
    base_format = selected_format_label.split(" (")[0] if " (" in selected_format_label else selected_format_label

    # For pre-registered tools, use auto-detect with tool_hint
    # For standard formats, use the format directly
    if is_preregistered:
        file_format = "auto"
        tool_hint = base_format
    else:
        file_format = base_format
        tool_hint = None

    if st.button("Ingest Security File", disabled=security_upload is None):
        if not security_upload:
            st.warning("Please choose a file before ingesting.")
        elif file_format == "auto" and not tool_hint:
            st.warning(
                "⚠️ Cannot auto-detect format for generic `.json` files. Please select a specific format or tool (e.g., 'bandit (pre-registered)')."
            )
        else:
            with st.spinner("Processing security file (Neo4j + OpenSearch)..."):
                try:
                    workspace_id = st.session_state.get("workspace_id", "default")

                    # Build the request with format and optional tool_hint as form fields
                    files = {
                        "uploaded_file": (
                            security_upload.name,
                            security_upload.getvalue(),
                            security_upload.type or "application/octet-stream",
                        )
                    }
                    data = {"format": file_format}
                    if tool_hint:
                        data["tool_hint"] = tool_hint

                    # Construct the URL and send format as form data
                    endpoint = f"/v1/{workspace_id}/index/security"
                    response = requests.post(f"{api_base}{endpoint}", files=files, data=data, timeout=120)
                    response.raise_for_status()
                    result = response.json()

                    st.success(f"✅ Indexed {result.get('findings_indexed', 0)} items from {security_upload.name}")
                    st.info("📊 Data indexed in both Neo4j (relationships) and OpenSearch (for semantic search)")

                    # Display response details
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Items Indexed", result.get("findings_indexed", 0))
                    with col2:
                        st.metric("Total Documents", result.get("document_count", 0))
                    with col3:
                        st.metric("Ingestion ID", result.get("ingestion_id", "")[:8] + "...")

                    st.success("✨ Ready for semantic search and graph queries!")

                except requests.RequestException as exc:
                    error_msg = str(exc)
                    try:
                        if hasattr(exc, "response") and exc.response is not None:
                            error_detail = exc.response.text
                            st.error(f"❌ Failed to ingest file: {error_msg}")
                            st.error(f"**Details:** {error_detail}")
                        else:
                            st.error(f"❌ Failed to ingest file: {error_msg}")
                    except Exception:
                        st.error(f"❌ Failed to ingest file: {error_msg}")

    # Add help section
    with st.expander("ℹ️ Format Guide"):
        st.write("""
        **Auto-detect**: Automatically detects file format from extension (.sarif, .spdx.json, etc.)

        **Pre-registered Tools** (zero configuration):
        - **Bandit**: Python security scanner - just upload your bandit.json
        - **OpenGrep**: Semantic code scanning tool - upload opengrep results
        - **Trivy**: Container/dependency scanner - upload trivy scan JSON

        **SARIF**: Standard security tool format (Snyk, Checkmarx, etc.)

        **SPDX**: Software Bill of Materials for license/dependency tracking

        **Custom JSONPath**: For tools not listed above, you can define a custom schema using JSONPath expressions
        """)


elif selected_section == "Upload to Raw Bucket":
    st.subheader("Upload to Raw Bucket")
    st.write("Send local files or ZIP archives to the raw datalake bucket.")

    s3_files = st.file_uploader(
        "Choose files/archives",
        accept_multiple_files=True,
        key="s3_uploads",
    )
    target_prefix = st.text_input("Target prefix", "uploads/")
    unzip_archives = st.checkbox("Extract ZIP archives", value=True)

    if st.button("Upload to Raw Bucket", disabled=not s3_files):
        payloads = extract_uploaded_files(s3_files or [], unzip_archives=unzip_archives)
        try:
            client = _get_s3_client(
                endpoint_url=s3_endpoint,
                region=aws_region,
                access_key=aws_key,
                secret_key=aws_secret,
            )
            uploaded_keys = upload_payloads(client, raw_bucket, target_prefix, payloads, aws_region)
        except Exception as exc:
            st.error(f"Upload failed: {exc}")
        else:
            st.success(f"Uploaded {len(uploaded_keys)} objects to {raw_bucket}.")
            st.json(uploaded_keys)

elif selected_section == "Batch Ingest from S3":
    st.subheader("Batch Ingest from S3")
    st.write("Trigger the backend ingestion endpoints for single objects or entire prefixes.")

    ingest_mode = st.radio("Ingestion mode", ["Single key", "Prefix"], horizontal=True)
    ingest_target = st.selectbox(
        "Source bucket type",
        options=["raw", "golden", "custom"],
        index=0,
    )
    ingest_bucket = (
        raw_bucket
        if ingest_target == "raw"
        else golden_bucket
        if ingest_target == "golden"
        else st.text_input("Custom bucket name", raw_bucket)
    )
    ingest_bucket = ingest_bucket.strip()

    endpoint = "/v1/datalake/ingest"
    payload = {"bucket": ingest_bucket}
    button_label = "Start Batch Load"

    if ingest_mode == "Single key":
        ingest_key = st.text_input("Object key", "")
        payload["key"] = ingest_key.strip()
        button_label = "Ingest Object"
    else:
        ingest_prefix = st.text_input("Prefix", "uploads/", key="ingest_prefix").strip().lstrip("/")
        payload["prefix"] = ingest_prefix
        endpoint = "/v1/datalake/ingest/batch"

    if st.button(button_label, disabled=not ingest_bucket or (ingest_mode == "Single key" and not payload.get("key"))):
        with st.spinner("Submitting ingest request..."):
            try:
                response = post_json(api_base, endpoint, payload, timeout=600)
            except requests.RequestException as exc:
                st.error(f"Ingest request failed: {exc}")
            else:
                st.success("Ingest completed.")
                st.json(response)

elif selected_section == "Promote Raw → Golden":
    st.subheader("Promote Raw Objects to Golden Bucket")
    st.write("Move single keys or entire prefixes via the preprocessing endpoints.")

    promotion_mode = st.radio("Promotion Mode", ["Single key", "Prefix"], horizontal=True)

    if promotion_mode == "Single key":
        source_key = st.text_input("Raw bucket key", "")
        destination_prefix = st.text_input("Destination prefix (optional)", "")
        if st.button("Promote Object", disabled=not source_key.strip()):
            payload = {"source_key": source_key.strip(), "destination_prefix": destination_prefix.strip() or None}
            try:
                response = post_json(api_base, "/v1/datalake/preprocess", payload, timeout=180)
            except requests.RequestException as exc:
                st.error(f"Promotion failed: {exc}")
            else:
                st.success("Object promoted to golden bucket.")
                st.json(response)
    else:
        source_prefix = st.text_input("Raw prefix", "")
        dest_prefix = st.text_input("Destination prefix (optional)", "")
        if st.button("Promote Prefix", disabled=not source_prefix.strip()):
            payload = {
                "source_prefix": source_prefix.strip(),
                "destination_prefix": dest_prefix.strip() or None,
            }
            try:
                response = post_json(api_base, "/v1/datalake/preprocess/batch", payload, timeout=600)
            except requests.RequestException as exc:
                st.error(f"Batch promotion failed: {exc}")
            else:
                st.success("Batch promotion completed.")
                st.json(response)
elif selected_section == "Browse S3":
    st.subheader("Browse S3 Buckets")
    browse_bucket_type = st.selectbox("Bucket", ["raw", "golden", "custom"], index=0)
    if browse_bucket_type == "raw":
        browse_bucket = raw_bucket
    elif browse_bucket_type == "golden":
        browse_bucket = golden_bucket
    else:
        browse_bucket = st.text_input("Custom bucket name")
    browse_prefix = st.text_input("Prefix filter", "")
    max_keys = st.slider("Items to fetch", min_value=10, max_value=500, value=100, step=10)

    if st.button("List Objects"):
        if not browse_bucket:
            st.warning("Specify a bucket to browse.")
        else:
            try:
                client = _get_s3_client(
                    endpoint_url=s3_endpoint,
                    region=aws_region,
                    access_key=aws_key,
                    secret_key=aws_secret,
                )
                list_kwargs = {"Bucket": browse_bucket, "MaxKeys": max_keys}
                prefix_value = browse_prefix.strip()
                if prefix_value:
                    list_kwargs["Prefix"] = prefix_value
                response = client.list_objects_v2(**list_kwargs)
            except ClientError as exc:
                st.error(f"Failed to list objects: {exc}")
            else:
                contents = response.get("Contents") or []
                if not contents:
                    st.info("No objects matched the filter.")
                else:
                    display_rows = [
                        {
                            "Key": item["Key"],
                            "Size (KB)": round(item["Size"] / 1024, 2),
                            "LastModified": str(item["LastModified"]),
                        }
                        for item in contents
                        if not item["Key"].endswith("/")
                    ]
                    st.dataframe(display_rows, use_container_width=True)
                    selected_key = st.selectbox(
                        "Download object",
                        [""] + [row["Key"] for row in display_rows],
                        label_visibility="collapsed",
                    )
                    if selected_key:
                        try:
                            obj = client.get_object(Bucket=browse_bucket, Key=selected_key)
                            data = obj["Body"].read()
                        except ClientError as exc:
                            st.error(f"Failed to download object: {exc}")
                        else:
                            st.download_button(
                                label=f"Download {selected_key}",
                                data=data,
                                file_name=selected_key.split("/")[-1],
                            )

elif selected_section == "Manage Buckets":
    st.subheader("Manage S3 Buckets")
    client = _get_s3_client(
        endpoint_url=s3_endpoint,
        region=aws_region,
        access_key=aws_key,
        secret_key=aws_secret,
    )
    if st.button("List Buckets"):
        try:
            buckets = client.list_buckets().get("Buckets", [])
        except ClientError as exc:
            st.error(f"Failed to list buckets: {exc}")
        else:
            st.table([{"Name": b["Name"], "CreationDate": str(b["CreationDate"])} for b in buckets])
    col_create, col_delete = st.columns(2)
    with col_create:
        st.write("Create Bucket")
        create_name = st.text_input("New bucket name", "", key="create_bucket")
        if st.button("Create Bucket", disabled=not create_name.strip()):
            try:
                create_args = {"Bucket": create_name.strip()}
                if aws_region != "us-east-1":
                    create_args["CreateBucketConfiguration"] = {"LocationConstraint": aws_region}
                client.create_bucket(**create_args)
            except ClientError as exc:
                st.error(f"Create failed: {exc}")
            else:
                st.success(f"Bucket {create_name.strip()} created.")
    with col_delete:
        st.write("Delete Bucket")
        delete_name = st.text_input("Bucket to delete", "", key="delete_bucket")
        if st.button("Delete Bucket", disabled=not delete_name.strip()):
            try:
                client.delete_bucket(Bucket=delete_name.strip())
            except ClientError as exc:
                st.error(f"Delete failed: {exc}")
            else:
                st.success(f"Bucket {delete_name.strip()} deleted.")

elif selected_section == "Privacy Scan":
    st.subheader("Privacy Scan & Anonymization")
    privacy_input_mode = st.radio("Input type", ["Upload file", "Paste text"], horizontal=True)
    uploaded_privacy_file = None
    privacy_text = ""
    if privacy_input_mode == "Upload file":
        uploaded_privacy_file = st.file_uploader(
            "Select text file",
            type=["txt", "md", "csv", "json", "log", "py"],
            key="privacy_file",
        )
        if uploaded_privacy_file:
            try:
                privacy_text = uploaded_privacy_file.read().decode("utf-8")
            except UnicodeDecodeError:
                privacy_text = uploaded_privacy_file.read().decode("utf-8", errors="ignore")
    else:
        privacy_text = st.text_area("Text to scan", height=200, key="privacy_text")

    if st.button("Run Privacy Scan", disabled=not privacy_text.strip()):
        with st.spinner("Scanning for PII..."):
            try:
                results = run_privacy_scan(privacy_text)
            except Exception as exc:
                st.error(f"Privacy scan failed: {exc}")
                results = []
            else:
                st.success(f"Detected {len(results)} potential entities.")
        if results:
            table_rows = []
            for res in results:
                snippet = privacy_text[res.start : res.end]
                table_rows.append({
                    "entity": getattr(res, "entity_type", "UNKNOWN"),
                    "confidence": round(getattr(res, "score", 0.0), 3),
                    "start": res.start,
                    "end": res.end,
                    "snippet": snippet,
                })
            st.table(table_rows)
            anonymized = anonymize_text(privacy_text, results)
            st.write("Anonymized Text")
            st.code(anonymized)
            st.download_button(
                "Download anonymized text",
                anonymized.encode("utf-8"),
                file_name=f"{uploaded_privacy_file.name if uploaded_privacy_file else 'anonymized'}.txt",
            )
        else:
            st.info("No PII detected.")

    st.markdown("---")
    st.subheader("Documents with PII in Index")
    if st.button("Find All Indexed Documents with PII Anonymized"):
        with st.spinner("Querying OpenSearch..."):
            workspace_id = st.session_state.get("workspace_id", "default")
            result, error = search_pii_anonymized(os_endpoint, docs_index, workspace_id)
        if error:
            st.error(f"Search failed: {error}")
        else:
            st.success(f"Found {result['hits']} documents with PII anonymized.")
            if result["documents"]:
                st.dataframe(result["documents"], use_container_width=True)

                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    total_pii = sum(doc["pii_count"] for doc in result["documents"])
                    st.metric("Total PII Entities", total_pii)
                with col2:
                    avg_pii = total_pii / len(result["documents"]) if result["documents"] else 0
                    st.metric("Avg PII per Document", f"{avg_pii:.1f}")
                with col3:
                    sources = {doc["source"] for doc in result["documents"] if doc["source"]}
                    st.metric("Unique Sources", len(sources))
            else:
                st.info("No documents with PII found in index.")

    st.markdown("---")
    st.subheader("S3 Privacy Scan & Quarantine")
    s3_privacy_bucket_choice = st.selectbox(
        "Bucket",
        options=["raw", "golden", "custom"],
        key="privacy_bucket_choice",
    )
    if s3_privacy_bucket_choice == "raw":
        privacy_bucket = raw_bucket
    elif s3_privacy_bucket_choice == "golden":
        privacy_bucket = golden_bucket
    else:
        privacy_bucket = st.text_input("Custom bucket name", raw_bucket, key="privacy_bucket_custom")

    source_prefix = st.text_input("Source prefix", "privacy-pack/incoming/", key="privacy_source_prefix")
    quarantine_prefix = st.text_input("Quarantine prefix", "privacy-pack/quarantine/", key="privacy_quarantine_prefix")
    scan_limit = st.number_input("Max objects to scan", min_value=1, max_value=2000, value=100, step=10)

    if st.button("Run S3 Privacy Scan", disabled=not privacy_bucket.strip()):
        try:
            client = _get_s3_client(
                endpoint_url=s3_endpoint,
                region=aws_region,
                access_key=aws_key,
                secret_key=aws_secret,
            )
            with st.spinner("Scanning S3 objects..."):
                report, scanned_count, quarantined_count = scan_s3_prefix_for_privacy(
                    client,
                    bucket=privacy_bucket.strip(),
                    source_prefix=source_prefix.strip(),
                    quarantine_prefix=quarantine_prefix.strip(),
                    limit=int(scan_limit),
                )
        except ClientError as exc:
            st.error(f"S3 operation failed: {exc}")
        except Exception as exc:
            st.error(f"Privacy scan failed: {exc}")
        else:
            st.success(f"Scanned {scanned_count} objects. Quarantined {quarantined_count}.")
            if report:
                st.table(report)

elif selected_section == "Quarantine Review":
    st.subheader("Human-in-the-loop Review")
    review_bucket_choice = st.selectbox(
        "Bucket",
        options=["raw", "golden", "custom"],
        key="quarantine_bucket_choice",
    )
    if review_bucket_choice == "raw":
        review_bucket = raw_bucket
    elif review_bucket_choice == "golden":
        review_bucket = golden_bucket
    else:
        review_bucket = st.text_input("Custom bucket name", raw_bucket, key="quarantine_bucket_custom")

    review_quarantine_prefix = st.text_input(
        "Quarantine prefix",
        "privacy-pack/quarantine/",
        key="quarantine_prefix",
    )
    release_prefix = st.text_input(
        "Release back to prefix",
        "privacy-pack/incoming/",
        key="quarantine_release_prefix",
    )
    if st.button("List Quarantine Objects", disabled=not review_bucket.strip()):
        try:
            client = _get_s3_client(
                endpoint_url=s3_endpoint,
                region=aws_region,
                access_key=aws_key,
                secret_key=aws_secret,
            )
            response = client.list_objects_v2(
                Bucket=review_bucket.strip(),
                Prefix=review_quarantine_prefix.strip(),
                MaxKeys=500,
            )
            items = [
                item["Key"] for item in response.get("Contents", []) if item["Key"] and not item["Key"].endswith("/")
            ]
            st.session_state["quarantine_objects"] = items
            st.session_state["quarantine_selection"] = []
        except ClientError as exc:
            st.error(f"Failed to list quarantine objects: {exc}")

    available_quarantine = st.session_state.get("quarantine_objects") or []
    if available_quarantine:
        selected_keys = st.multiselect(
            "Select objects",
            available_quarantine,
            default=st.session_state.get("quarantine_selection") or [],
        )
        st.session_state["quarantine_selection"] = selected_keys

        preview_key = st.selectbox(
            "Preview object",
            ["", *available_quarantine],
            key="quarantine_preview_select",
        )
        if preview_key:
            try:
                client = _get_s3_client(
                    endpoint_url=s3_endpoint,
                    region=aws_region,
                    access_key=aws_key,
                    secret_key=aws_secret,
                )
                obj = client.get_object(Bucket=review_bucket.strip(), Key=preview_key)
                body = obj["Body"].read().decode("utf-8", errors="ignore")
            except ClientError as exc:
                st.error(f"Failed to preview object: {exc}")
            else:
                st.info(f"Previewing {preview_key}")
                st.code(body[:2000] + ("..." if len(body) > 2000 else ""), language="text")

        def _remove_selected():
            remaining = [k for k in available_quarantine if k not in selected_keys]
            st.session_state["quarantine_objects"] = remaining
            st.session_state["quarantine_selection"] = []

        cols = st.columns(2)
        with cols[0]:
            if st.button("Release Selected", disabled=not selected_keys):
                try:
                    client = _get_s3_client(
                        endpoint_url=s3_endpoint,
                        region=aws_region,
                        access_key=aws_key,
                        secret_key=aws_secret,
                    )
                    for key in selected_keys:
                        remainder = key[len(review_quarantine_prefix.strip()) :].lstrip("/")
                        target_key = (
                            f"{release_prefix.strip().rstrip('/')}/{remainder}" if release_prefix.strip() else remainder
                        )
                        client.copy_object(
                            Bucket=review_bucket.strip(),
                            CopySource={"Bucket": review_bucket.strip(), "Key": key},
                            Key=target_key,
                        )
                        client.delete_object(Bucket=review_bucket.strip(), Key=key)
                    st.success(f"Released {len(selected_keys)} objects to {release_prefix.strip() or '/'}")
                    _remove_selected()
                except ClientError as exc:
                    st.error(f"Failed to release objects: {exc}")
        with cols[1]:
            if st.button("Delete Selected", disabled=not selected_keys):
                try:
                    client = _get_s3_client(
                        endpoint_url=s3_endpoint,
                        region=aws_region,
                        access_key=aws_key,
                        secret_key=aws_secret,
                    )
                    for key in selected_keys:
                        client.delete_object(Bucket=review_bucket.strip(), Key=key)
                    st.success(f"Deleted {len(selected_keys)} objects from quarantine.")
                    _remove_selected()
                except ClientError as exc:
                    st.error(f"Failed to delete objects: {exc}")
    else:
        st.info("No quarantine objects listed yet.")

elif selected_section == "Metadata Lookup":
    st.subheader("Metadata Lookup")

    lookup_mode = st.radio(
        "Search by", ["Ingestion ID", "Filename", "PII Anonymized"], horizontal=True, key="metadata_lookup_mode"
    )

    if lookup_mode == "Ingestion ID":
        lookup_ingestion_id = st.text_input("Ingestion ID", key="metadata_lookup_id")
        if st.button("Search Metadata", disabled=not lookup_ingestion_id.strip()):
            with st.spinner("Querying OpenSearch..."):
                result, error = search_metadata_envelope(os_endpoint, docs_index, lookup_ingestion_id.strip())
            if error:
                st.error(f"Lookup failed: {error}")
            else:
                st.success(f"Found {result['hits']} matching documents.")
                st.json(result["envelopes"])

    elif lookup_mode == "Filename":
        search_filename = st.text_input(
            "Filename (partial match supported)", placeholder="e.g., API_VERSIONING", key="metadata_filename_search"
        )
        if st.button("Search by Filename", disabled=not search_filename.strip()):
            with st.spinner("Querying OpenSearch..."):
                workspace_id = st.session_state.get("workspace_id", "default")
                result, error = search_by_filename(os_endpoint, docs_index, search_filename.strip(), workspace_id)
            if error:
                st.error(f"Search failed: {error}")
            else:
                st.success(f"Found {result['hits']} matching documents.")
                if result["documents"]:
                    for doc in result["documents"]:
                        with st.expander(f"📄 {doc['file_path']} ({doc['id'][:8]}...)"):
                            st.json(doc["metadata_envelope"])
                else:
                    st.info("No documents found.")

    elif lookup_mode == "PII Anonymized":
        if st.button("Find Documents with PII"):
            with st.spinner("Querying OpenSearch..."):
                workspace_id = st.session_state.get("workspace_id", "default")
                result, error = search_pii_anonymized(os_endpoint, docs_index, workspace_id)
            if error:
                st.error(f"Search failed: {error}")
            else:
                st.success(f"Found {result['hits']} documents with PII anonymized.")
                if result["documents"]:
                    df_pii = st.dataframe(result["documents"], use_container_width=True)
                else:
                    st.info("No documents with PII found.")

    st.markdown("---")
    st.write("Recent Ingestions")
    recent_limit = st.number_input(
        "How many ingestions?", min_value=1, max_value=50, value=5, step=1, key="metadata_recent_limit"
    )
    if st.button("Fetch Recent Ingestions"):
        with st.spinner("Fetching recent ingestions..."):
            workspace_id = st.session_state.get("workspace_id", "default")
            recent, error = fetch_recent_ingestions(os_endpoint, docs_index, int(recent_limit), workspace_id)
        if error:
            st.error(f"Failed to load ingestions: {error}")
        else:
            st.session_state["metadata_recent_ingestions"] = recent or []
    recent_data = st.session_state.get("metadata_recent_ingestions") or []
    if recent_data:
        st.table(recent_data)
        st.selectbox(
            "Use an ingestion id",
            [""] + [item["ingestion_id"] for item in recent_data],
            key="metadata_recent_select",
            on_change=_apply_recent_selection,
        )

elif selected_section == "OpenSearch Query":
    st.subheader("Ad-hoc OpenSearch Query")
    query_index = st.text_input("Index/pattern", docs_index, key="os_query_index")
    query_size = st.number_input("Result size", min_value=1, max_value=200, value=10, step=1, key="os_query_size")
    sample_queries = {
        "Match All": {
            "query": {"match_all": {}},
        },
        "Most Recent 5": {
            "size": 5,
            "sort": [{"meta.metadata_envelope.captured_at": {"order": "desc"}}],
            "_source": ["content", "meta.metadata_envelope"],
        },
        "By Source (folder)": {
            "query": {"term": {"meta.metadata_envelope.source.keyword": "folder"}},
            "_source": ["meta.metadata_envelope", "content"],
        },
    }
    chosen_sample = st.selectbox(
        "Sample queries", ["Match All", "Most Recent 5", "By Source (folder)"], key="os_query_sample"
    )
    if st.button("Apply Sample Query"):
        st.session_state["os_query_json"] = json.dumps(sample_queries[chosen_sample], indent=2)
    query_json = st.text_area(
        "Query JSON",
        value=st.session_state.get("os_query_json", json.dumps(sample_queries["Match All"], indent=2)),
        height=220,
        key="os_query_json",
    )
    if st.button("Run OpenSearch Query", disabled=not query_index.strip()):
        try:
            payload = json.loads(query_json)
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
        else:
            payload["size"] = int(query_size)
            url = f"{os_endpoint.rstrip('/')}/{_normalize_index_pattern(query_index)}/_search"
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    params={"allow_no_indices": "true", "ignore_unavailable": "true"},
                    timeout=10,
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                st.error(f"Query failed: {getattr(exc.response, 'text', str(exc))}")
            else:
                response_json = resp.json()
                hits = response_json.get("hits", {}).get("hits", [])
                if hits:
                    st.info(f"Returned {len(hits)} hits.")
                    st.json(hits)
                else:
                    st.info("No hits returned.")

elif selected_section == "Document Statistics":
    st.subheader("Document Statistics & Overview")
    if st.button("Fetch Index Statistics"):
        with st.spinner("Gathering statistics..."):
            workspace_id = st.session_state.get("workspace_id", "default")
            stats, error = fetch_index_statistics(os_endpoint, docs_index, workspace_id)
        if error:
            st.error(f"Failed to fetch stats: {error}")
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Documents", stats["total_documents"])
            with col2:
                st.metric("Total PII Entities", stats["total_pii_entities"])
            with col3:
                pii_count = next((b["doc_count"] for b in stats["pii_stats"] if b["key_as_string"] == "true"), 0)
                st.metric("Documents with PII", pii_count)

            st.write("**Documents by Source**")
            source_data = []
            for b in stats["by_source"]:
                doc_count = b.get("doc_count", 0)
                if isinstance(doc_count, dict):
                    doc_count = doc_count.get("value", 0)
                source_data.append({"Source": b.get("key"), "Count": doc_count})
            if source_data:
                st.dataframe(source_data, use_container_width=True)
            else:
                st.info("No source data available")

elif selected_section == "Ingestion Timeline":
    st.subheader("Ingestion Activity Over Time")
    days = st.slider("Days to display", min_value=7, max_value=90, value=30, step=1)
    if st.button("Load Timeline"):
        with st.spinner("Fetching timeline..."):
            workspace_id = st.session_state.get("workspace_id", "default")
            timeline, error = fetch_ingestion_timeline(os_endpoint, docs_index, days, workspace_id)
        if error:
            st.error(f"Failed to fetch timeline: {error}")
        else:
            if timeline:
                st.line_chart(timeline, x="date", y=["ingestions", "documents"])
                st.dataframe(timeline, use_container_width=True)
            else:
                st.info("No ingestion data available for the selected period.")

elif selected_section == "Connector Health":
    st.subheader("Integration Health & Connector Stats")
    if st.button("Fetch Connector Health"):
        with st.spinner("Gathering connector stats..."):
            workspace_id = st.session_state.get("workspace_id", "default")
            health, error = fetch_connector_health(os_endpoint, docs_index, workspace_id)
        if error:
            st.error(f"Failed to fetch health: {error}")
        else:
            if health:
                st.dataframe(health, use_container_width=True)
                st.write("**Summary**")
                col1, col2 = st.columns(2)
                with col1:
                    total_docs = sum(h["documents"] for h in health)
                    st.metric("Total Documents", total_docs)
                with col2:
                    avg_pii = sum(h["avg_pii_per_doc"] for h in health) / len(health) if health else 0
                    st.metric("Avg PII per Document", f"{avg_pii:.2f}")
            else:
                st.info("No connector data available.")

elif selected_section == "Alerts":
    st.subheader("Alerts & Notifications")
    tab1, tab2 = st.tabs(["Active Alerts", "Create Alert"])

    with tab1:
        if st.button("Refresh Alerts"):
            with st.spinner("Fetching alerts..."):
                alerts, error = fetch_active_alerts(os_endpoint)
            if error:
                st.error(f"Failed to fetch alerts: {error}")
            else:
                if alerts:
                    alert_df = [
                        {
                            "Type": a["type"],
                            "Severity": a["severity"],
                            "Timestamp": a["timestamp"],
                            "Context": str(a["context"])[:50] + "...",
                        }
                        for a in alerts
                    ]
                    st.dataframe(alert_df, use_container_width=True)
                else:
                    st.info("No active alerts.")

    with tab2:
        alert_type = st.selectbox("Alert Type", ["high_pii", "failed_ingestion", "quarantine_growth", "custom"])
        severity = st.selectbox("Severity", ["low", "medium", "high", "critical"])
        alert_context = st.text_area("Alert Context (JSON)", "{}")
        if st.button("Create Alert"):
            try:
                context = json.loads(alert_context)
            except json.JSONDecodeError:
                st.error("Invalid JSON in alert context")
            else:
                success, error = create_alert(os_endpoint, alert_type, severity, context)
                if success:
                    st.success("Alert created successfully")
                else:
                    st.error(f"Failed to create alert: {error}")

elif selected_section == "Search with Preview":
    st.subheader("Full Text Search with Content Preview")
    search_query = st.text_input("Search terms", placeholder="e.g., API authentication")
    preview_limit = st.slider("Results to preview", min_value=1, max_value=20, value=5)

    if st.button("Search with Preview", disabled=not search_query.strip()):
        with st.spinner("Searching..."):
            query_dict = {"query": {"multi_match": {"query": search_query.strip(), "fields": ["content", "file_path"]}}}
            workspace_id = st.session_state.get("workspace_id", "default")
            results, error = search_with_content_preview(
                os_endpoint, docs_index, query_dict, preview_limit, workspace_id
            )

        if error:
            st.error(f"Search failed: {error}")
        else:
            st.success(f"Found {len(results)} results")
            for i, result in enumerate(results, 1):
                with st.expander(f"📄 {result['file']} (Result {i})"):
                    st.write("**Snippet:**")
                    st.code(result["snippet"])
                    if result["metadata"]:
                        st.write("**Metadata:**")
                        st.json(result["metadata"])

elif selected_section == "Query Templates":
    st.subheader("Saved Query Templates & History")

    if "query_templates" not in st.session_state:
        st.session_state["query_templates"] = {}
    if "query_history" not in st.session_state:
        st.session_state["query_history"] = []

    tab1, tab2 = st.tabs(["Use Templates", "Create Template"])

    with tab1:
        if st.session_state["query_templates"]:
            template_name = st.selectbox("Select template", list(st.session_state["query_templates"].keys()))
            if template_name:
                template = st.session_state["query_templates"][template_name]
                st.json(template)
                if st.button("Run Template"):
                    with st.spinner("Executing template..."):
                        workspace_id = st.session_state.get("workspace_id", "default")
                        results, error = search_with_content_preview(
                            os_endpoint, docs_index, template, 10, workspace_id
                        )
                    if error:
                        st.error(f"Query failed: {error}")
                    else:
                        st.success(f"Found {len(results)} results")
                        for result in results:
                            with st.expander(result["file"]):
                                st.code(result["snippet"])
        else:
            st.info("No saved templates. Create one in the 'Create Template' tab.")

    with tab2:
        new_template_name = st.text_input("Template name")
        template_json = st.text_area("Query JSON template", "{}")
        if st.button("Save Template"):
            try:
                query = json.loads(template_json)
                st.session_state["query_templates"][new_template_name] = query
                st.success(f"Template '{new_template_name}' saved")
            except json.JSONDecodeError:
                st.error("Invalid JSON")

elif selected_section == "Bulk Delete":
    st.subheader("Bulk Delete Documents")
    st.warning("⚠️ This action is irreversible. Use with caution.")

    delete_mode = st.radio("Delete by", ["Ingestion ID", "Source Type", "Date Range"], horizontal=True)

    if delete_mode == "Ingestion ID":
        ingestion_to_delete = st.text_input("Ingestion ID to delete")
        if st.button("Delete Ingestion", type="secondary"):
            st.warning(f"Would delete all documents from ingestion: {ingestion_to_delete}")
            if st.checkbox("I understand this action cannot be undone"):
                st.info("Deletion API endpoint not yet implemented. Contact admin.")

    elif delete_mode == "Source Type":
        source_to_delete = st.selectbox("Source type", ["upload", "folder", "github", "web", "web_crawl"])
        if st.button("Delete Source", type="secondary"):
            st.warning(f"Would delete all documents from source: {source_to_delete}")
            if st.checkbox("I understand this action cannot be undone"):
                st.info("Deletion API endpoint not yet implemented. Contact admin.")

    elif delete_mode == "Date Range":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start date")
        with col2:
            end_date = st.date_input("End date")
        if st.button("Delete by Date", type="secondary"):
            st.warning(f"Would delete documents ingested between {start_date} and {end_date}")
            if st.checkbox("I understand this action cannot be undone"):
                st.info("Deletion API endpoint not yet implemented. Contact admin.")

elif selected_section == "Re-index Documents":
    st.subheader("Re-index Documents")
    st.info("Re-index documents to apply updated processing pipelines.")

    reindex_mode = st.radio("Re-index", ["By Ingestion ID", "By Source", "All"], horizontal=True)

    if reindex_mode == "By Ingestion ID":
        ingestion_id = st.text_input("Ingestion ID")
        if st.button("Re-index Ingestion"):
            st.info(f"Re-index API for {ingestion_id} not yet implemented")

    elif reindex_mode == "By Source":
        source = st.selectbox("Source type", ["upload", "folder", "github", "web", "web_crawl"])
        if st.button("Re-index Source"):
            st.info(f"Re-index API for source '{source}' not yet implemented")

    else:
        if st.button("Re-index Everything", type="secondary"):
            st.warning("This will re-process all documents. This may take a while.")
            st.info("Bulk re-index API not yet implemented")

elif selected_section == "Tag Documents":
    st.subheader("Tag/Annotate Documents")

    tag_mode = st.radio("Tag by", ["Ingestion ID", "Document ID", "Metadata Filter"], horizontal=True)
    tag_value = st.text_input("Tag value")

    if tag_mode == "Ingestion ID":
        identifier = st.text_input("Ingestion ID")
    elif tag_mode == "Document ID":
        identifier = st.text_input("Document ID")
    else:
        identifier = st.text_input("Metadata filter query (JSON)")

    if st.button("Apply Tag"):
        st.info(f"Tagging API not yet implemented. Would tag documents with: {tag_value}")

elif selected_section == "Error Dashboard":
    st.subheader("Error Dashboard")
    days = st.slider("Days to analyze", min_value=1, max_value=30, value=7, step=1, key="error_days")

    if st.button("Load Error Dashboard"):
        with st.spinner("Fetching error stats..."):
            dashboard, error = fetch_error_dashboard(os_endpoint, logs_index, days)

        if error:
            st.error(f"Failed to load dashboard: {error}")
        else:
            # Metrics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Errors", dashboard["total_errors"])
            with col2:
                st.metric("Days Analyzed", days)

            # Errors by logger
            st.write("**Errors by Logger**")
            logger_data = [
                {"Logger": b.get("key"), "Count": b.get("count", {}).get("value", 0)} for b in dashboard["by_logger"]
            ]
            if logger_data:
                st.dataframe(logger_data, use_container_width=True)

            # Recent errors
            st.write("**Recent Errors**")
            if dashboard["recent_errors"]:
                for err in dashboard["recent_errors"]:
                    with st.expander(f"⚠️ {err.get('timestamp', 'N/A')} - {err.get('logger', 'Unknown')}"):
                        st.code(err.get("message", "No message"))
            else:
                st.info("No errors found.")

elif selected_section == "Log Search":
    st.subheader("Full-Text Log Search")

    col1, col2 = st.columns(2)
    with col1:
        search_query = st.text_input("Search logs", placeholder="e.g., timeout, error, failed")
    with col2:
        log_level = st.selectbox("Log Level", ["All", "ERROR", "WARN", "INFO", "DEBUG"], key="log_level_filter")

    col3, col4 = st.columns(2)
    with col3:
        search_days = st.slider("Days to search", min_value=1, max_value=30, value=7, step=1, key="search_days")
    with col4:
        result_limit = st.slider("Max results", min_value=10, max_value=200, value=50, step=10)

    if st.button("Search Logs"):
        with st.spinner("Searching logs..."):
            level_filter = None if log_level == "All" else log_level
            results, error = search_logs(os_endpoint, logs_index, search_query, level_filter, search_days, result_limit)

        if error:
            st.error(f"Search failed: {error}")
        else:
            st.success(f"Found {len(results)} log entries")
            if results:
                log_df = [
                    {
                        "Timestamp": r.get("timestamp"),
                        "Level": r.get("level"),
                        "Logger": r.get("logger"),
                        "Message": r.get("message", "")[:100] + "..."
                        if len(r.get("message", "")) > 100
                        else r.get("message", ""),
                    }
                    for r in results
                ]
                st.dataframe(log_df, use_container_width=True)

                # Show full messages in expanders
                st.write("**Details**")
                for i, r in enumerate(results[:10], 1):
                    with st.expander(f"Log {i}: {r.get('timestamp')}"):
                        st.write(f"**Level:** {r.get('level')}")
                        st.write(f"**Logger:** {r.get('logger')}")
                        st.code(r.get("message", "No message"))

elif selected_section == "Log Aggregations":
    st.subheader("Log Statistics by Source")
    days = st.slider("Days to analyze", min_value=1, max_value=30, value=7, step=1, key="agg_days")

    if st.button("Load Log Aggregations"):
        with st.spinner("Fetching aggregations..."):
            aggs, error = fetch_log_aggregations(os_endpoint, logs_index, days)

        if error:
            st.error(f"Failed to load aggregations: {error}")
        else:
            # By level
            st.write("**Logs by Level**")
            level_data = [{"Level": b.get("key"), "Count": b.get("doc_count", 0)} for b in aggs["by_level"]]
            if level_data:
                st.dataframe(level_data, use_container_width=True)

            # By logger
            st.write("**Logs by Logger**")
            logger_data = [
                {
                    "Logger": b.get("key"),
                    "Total": b.get("doc_count", 0),
                    "Errors": b.get("errors", {}).get("doc_count", 0),
                }
                for b in aggs["by_logger"][:20]
            ]
            if logger_data:
                st.dataframe(logger_data, use_container_width=True)

elif selected_section == "Log Cleanup":
    st.subheader("Log Retention & Cleanup")
    st.info("Delete old logs to manage index size and improve performance.")

    col1, col2 = st.columns(2)
    with col1:
        days_to_keep = st.slider("Keep logs from last N days", min_value=7, max_value=365, value=30, step=1)
    with col2:
        st.metric("Delete logs older than", f"{days_to_keep} days ago")

    st.warning(
        f"⚠️ This will permanently delete all logs from before {days_to_keep} days ago. This action cannot be undone."
    )

    if st.button("Delete Old Logs", type="secondary"):
        if st.checkbox("I understand this action is permanent", key="confirm_delete_logs"):
            with st.spinner("Deleting old logs..."):
                success, message = delete_old_logs(os_endpoint, logs_index, days_to_keep)

            if success:
                st.success(message)
            else:
                st.error(f"Deletion failed: {message}")

if selected_section == "Security Dashboard":
    st.subheader("Security Findings Dashboard")

    # Fetch all security findings
    url = f"{os_endpoint.rstrip('/')}/ask_certus_{st.session_state.get('workspace_id', 'default')}/_search"
    query = {
        "size": 0,
        "aggs": {
            "by_tool": {"terms": {"field": "source.keyword", "size": 10}},
            "by_severity": {"terms": {"field": "source.keyword", "size": 10}},
        },
    }

    try:
        resp = requests.post(url, json=query, timeout=10)
        resp.raise_for_status()
        result = resp.json()

        # Get basic stats
        total_findings = result.get("hits", {}).get("total", {}).get("value", 0)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Findings", total_findings)
        with col2:
            st.metric("Security Scans", "View below")
        with col3:
            st.metric("Tools Used", len(result.get("aggregations", {}).get("by_tool", {}).get("buckets", [])))

        st.divider()

        # Recent findings
        st.subheader("Recent Findings")
        query_recent = {
            "size": 10,
            "sort": [{"ingestion_id": {"order": "desc"}}],
            "_source": ["source", "content", "ingestion_id", "source_location"],
        }

        resp = requests.post(url, json=query_recent, timeout=10)
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])

        for hit in hits:
            source = hit.get("_source", {})
            with st.expander(
                f"**{source.get('source', 'Unknown').upper()}** - {source.get('source_location', 'N/A')[:50]}"
            ):
                st.write(source.get("content", "")[:500])

    except requests.RequestException as exc:
        st.error(f"Failed to fetch findings: {exc}")

elif selected_section == "Finding Browser":
    st.subheader("Security Finding Browser")

    col1, col2 = st.columns(2)
    with col1:
        tool_filter = st.multiselect(
            "Filter by Tool", ["bandit", "opengrep", "trivy"], default=["bandit", "opengrep", "trivy"]
        )
    with col2:
        search_text = st.text_input("Search findings", placeholder="e.g., hardcoded, SQL injection")

    if st.button("Search Findings"):
        url = f"{os_endpoint.rstrip('/')}/ask_certus_{st.session_state.get('workspace_id', 'default')}/_search"

        filters = []
        if tool_filter:
            filters.append({"terms": {"source": tool_filter}})

        query = {
            "size": 50,
            "_source": ["source", "content", "ingestion_id", "source_location"],
            "query": {
                "bool": {
                    "filter": filters,
                    "must": [{"match": {"content": search_text}}] if search_text else [{"match_all": {}}],
                }
            },
        }

        try:
            resp = requests.post(url, json=query, timeout=10)
            resp.raise_for_status()
            hits = resp.json().get("hits", {}).get("hits", [])

            st.success(f"Found {len(hits)} findings")

            for hit in hits:
                source = hit.get("_source", {})
                with st.expander(f"[{source.get('source', 'Unknown').upper()}] {source.get('source_location', 'N/A')}"):
                    st.write(f"**Ingestion ID:** {source.get('ingestion_id', 'N/A')}")
                    st.write(f"**Content:**\n{source.get('content', '')[:1000]}")
                    if len(source.get("content", "")) > 1000:
                        st.write("... *(truncated)*")

        except requests.RequestException as exc:
            st.error(f"Search failed: {exc}")

elif selected_section == "Scan History":
    st.subheader("Security Scan History & Comparison")

    url = f"{os_endpoint.rstrip('/')}/ask_certus_{st.session_state.get('workspace_id', 'default')}/_search"

    # Fetch all scans grouped by ingestion_id
    query = {"size": 0, "aggs": {"scans": {"terms": {"field": "ingestion_id.keyword", "size": 100}}}}

    try:
        resp = requests.post(url, json=query, timeout=10)
        resp.raise_for_status()
        scans = resp.json().get("aggregations", {}).get("scans", {}).get("buckets", [])

        st.subheader(f"Recent Scans ({len(scans)})")

        scan_options = [f"{s['key'][:8]}... ({s['doc_count']} findings)" for s in scans[:20]]

        col1, col2 = st.columns(2)
        with col1:
            selected_scan1 = st.selectbox("Select Scan 1", scan_options, key="scan1", index=0 if scans else None)
        with col2:
            selected_scan2 = st.selectbox(
                "Select Scan 2 (for comparison)", scan_options, key="scan2", index=1 if len(scans) > 1 else 0
            )

        if st.button("Compare Scans"):
            scan1_id = scans[scan_options.index(selected_scan1)]["key"] if selected_scan1 else None
            scan2_id = scans[scan_options.index(selected_scan2)]["key"] if selected_scan2 else None

            if scan1_id and scan2_id:
                # Fetch findings for both scans
                query1 = {"size": 1000, "_source": ["source", "content"], "query": {"term": {"ingestion_id": scan1_id}}}
                query2 = {"size": 1000, "_source": ["source", "content"], "query": {"term": {"ingestion_id": scan2_id}}}

                resp1 = requests.post(url, json=query1, timeout=10)
                resp2 = requests.post(url, json=query2, timeout=10)

                resp1.raise_for_status()
                resp2.raise_for_status()

                findings1 = {hit["_source"]["content"][:100] for hit in resp1.json().get("hits", {}).get("hits", [])}
                findings2 = {hit["_source"]["content"][:100] for hit in resp2.json().get("hits", {}).get("hits", [])}

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Scan 1 Findings", len(findings1))
                with col2:
                    st.metric("Scan 2 Findings", len(findings2))
                with col3:
                    st.metric("New in Scan 2", len(findings2 - findings1))

                st.divider()

                if findings2 - findings1:
                    st.subheader("New Findings")
                    for finding in list(findings2 - findings1)[:10]:
                        st.write(f"- {finding}...")

                if findings1 - findings2:
                    st.subheader("Fixed Findings")
                    for finding in list(findings1 - findings2)[:10]:
                        st.write(f"- {finding}...")

    except requests.RequestException as exc:
        st.error(f"Failed to fetch scans: {exc}")

elif selected_section == "Ask Certus":
    st.subheader("RAG Smoke Test (/v1/ask)")
    question = st.text_area("Question", "What is the Certus TAP pipeline?")
    if st.button("Ask", disabled=not question.strip()):
        payload = {"question": question.strip()}
        with st.spinner("Querying backend..."):
            try:
                workspace_id = st.session_state.get("workspace_id", "default")
                response = post_json(api_base, "/v1/ask", payload, timeout=60, workspace_id=workspace_id)
            except requests.RequestException as exc:
                st.error(f"Query failed: {exc}")
            else:
                st.success("Received answer from RAG pipeline.")
                st.json(response)


elif selected_section == "Neo4j Cypher Query":
    st.subheader("Neo4j Cypher Query Editor")
    st.write("Query the knowledge graph containing security findings (SARIF) and software inventory (SPDX).")

    neo4j_uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
    # Normalize Neo4j URI for local Streamlit
    if "neo4j://neo4j:" in neo4j_uri:
        neo4j_uri = neo4j_uri.replace("neo4j://neo4j:", "neo4j://localhost:")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

    cypher_templates = {
        "All Scans": "MATCH (scan:Scan) RETURN scan.id as scan_id, scan.timestamp as timestamp LIMIT 10",
        "Findings by Severity": "MATCH (scan:Scan)-[:CONTAINS]->(f:Finding)-[:HAS_SEVERITY]->(sev:Severity) RETURN f.message as message, sev.level as severity, COUNT(*) as count GROUP BY sev.level ORDER BY sev.level DESC",
        "Finding Locations": "MATCH (f:Finding)-[:LOCATED_AT]->(loc:Location) RETURN f.message as finding, loc.uri as file, loc.line as line LIMIT 20",
        "SBOM Packages": "MATCH (sbom:SBOM)-[:CONTAINS]->(pkg:Package) RETURN pkg.name as package, pkg.version as version, COUNT(*) as count LIMIT 20",
        "Package Dependencies": "MATCH (p1:Package)-[:DEPENDS_ON]->(p2:Package) RETURN p1.name as package, p2.name as dependency LIMIT 20",
        "Licenses Used": "MATCH (pkg:Package)-[:USES_LICENSE]->(lic:License) RETURN lic.name as license, COUNT(DISTINCT pkg) as package_count ORDER BY package_count DESC",
        "Tools Used": "MATCH (scan:Scan)-[:SCANNED_WITH]->(tool:Tool) RETURN tool.name as tool_name, tool.version as version, COUNT(DISTINCT scan) as scan_count",
    }

    col1, col2 = st.columns([2, 1])
    with col1:
        chosen_template = st.selectbox("Sample Cypher queries", list(cypher_templates.keys()), key="neo4j_template")
    with col2:
        if st.button("Load Template"):
            st.session_state["neo4j_cypher"] = cypher_templates[chosen_template]

    cypher_query = st.text_area(
        "Cypher Query",
        value=st.session_state.get("neo4j_cypher", cypher_templates["All Scans"]),
        height=200,
        key="neo4j_cypher",
    )

    if st.button("Run Cypher Query", disabled=not cypher_query.strip()):
        try:
            from neo4j import GraphDatabase

            driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
            with driver.session() as session:
                result = session.run(cypher_query)
                records = result.data()
            driver.close()

            if records:
                st.success(f"Query returned {len(records)} records")
                try:
                    import pandas as pd

                    df = pd.DataFrame(records)
                    st.dataframe(df, use_container_width=True)
                except Exception:
                    st.json(records)
            else:
                st.info("No records returned.")
        except Exception as exc:
            st.error(f"Query failed: {exc}")


elif selected_section == "Neo4j Graph Explorer":
    st.subheader("Neo4j Graph Explorer")
    st.write("Explore relationships in the knowledge graph with pre-built analysis queries.")

    neo4j_uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
    # Normalize Neo4j URI for local Streamlit
    if "neo4j://neo4j:" in neo4j_uri:
        neo4j_uri = neo4j_uri.replace("neo4j://neo4j:", "neo4j://localhost:")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

    explorer_queries = {
        "Finding Impact Analysis": {
            "description": "Show all findings with their rules, severity, and locations",
            "query": """MATCH (f:Finding)-[:VIOLATES]->(rule:Rule)
            OPTIONAL MATCH (f)-[:HAS_SEVERITY]->(sev:Severity)
            OPTIONAL MATCH (f)-[:LOCATED_AT]->(loc:Location)
            RETURN f.message as finding, rule.name as rule_name, sev.level as severity, loc.uri as file, loc.line as line
            LIMIT 30""",
        },
        "Transitive Dependencies": {
            "description": "Find all dependencies of a package (including transitive)",
            "query": """MATCH (root:Package {name: $package_name})-[:DEPENDS_ON*1..5]->(dep:Package)
            RETURN DISTINCT dep.name as dependency, dep.version as version
            ORDER BY dep.name""",
        },
        "Vulnerability Chain": {
            "description": "Show vulnerability findings grouped by severity and tool",
            "query": """MATCH (scan:Scan)-[:SCANNED_WITH]->(tool:Tool)
            MATCH (scan)-[:CONTAINS]->(f:Finding)-[:HAS_SEVERITY]->(sev:Severity)
            RETURN tool.name as tool, sev.level as severity, COUNT(f) as findings
            ORDER BY sev.level DESC""",
        },
        "License Compliance": {
            "description": "Find packages with GPL licenses (potential compliance issues)",
            "query": """MATCH (pkg:Package)-[:USES_LICENSE]->(lic:License)
            WHERE lic.name CONTAINS 'GPL'
            RETURN DISTINCT pkg.name as package, pkg.version as version, lic.name as license""",
        },
        "SBOM Snapshot": {
            "description": "Get the full package list from latest SBOM",
            "query": """MATCH (sbom:SBOM)-[:CONTAINS]->(pkg:Package)
            RETURN pkg.name as package, pkg.version as version, pkg.supplier as supplier
            ORDER BY pkg.name
            LIMIT 50""",
        },
    }

    st.subheader("Pre-built Analysis Queries")
    selected_analysis = st.selectbox("Select analysis", list(explorer_queries.keys()), key="neo4j_analysis")
    analysis = explorer_queries[selected_analysis]

    st.write(f"**{selected_analysis}**: {analysis['description']}")

    if "$" in analysis["query"]:
        st.write("**Query Parameters:**")
        params = {}
        if "package_name" in analysis["query"]:
            params["package_name"] = st.text_input("Package name", "flask", key="pkg_param")

        if st.button("Run Analysis"):
            try:
                from neo4j import GraphDatabase

                driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
                with driver.session() as session:
                    result = session.run(analysis["query"], params)
                    records = result.data()
                driver.close()

                if records:
                    st.success(f"Analysis returned {len(records)} records")
                    try:
                        import pandas as pd

                        df = pd.DataFrame(records)
                        st.dataframe(df, use_container_width=True)
                    except Exception:
                        st.json(records)
                else:
                    st.info("No records returned.")
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")
    else:
        if st.button("Run Analysis"):
            try:
                from neo4j import GraphDatabase

                driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
                with driver.session() as session:
                    result = session.run(analysis["query"])
                    records = result.data()
                driver.close()

                if records:
                    st.success(f"Analysis returned {len(records)} records")
                    try:
                        import pandas as pd

                        df = pd.DataFrame(records)
                        st.dataframe(df, use_container_width=True)
                    except Exception:
                        st.json(records)
                else:
                    st.info("No records returned.")
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")


elif selected_section == "Semantic Search":
    st.subheader("Semantic Search (OpenSearch + Neo4j Context)")
    st.write("Search for security findings and packages with semantic understanding.")

    search_query = st.text_input(
        "Search query",
        placeholder="e.g., 'SQL injection vulnerabilities' or 'cryptography dependencies'",
        key="semantic_search_query",
    )

    search_type = st.radio(
        "Search type", ["Security Findings", "Packages & Dependencies", "Both"], horizontal=True, key="search_type"
    )

    result_limit = st.slider("Result limit", min_value=5, max_value=50, value=10, key="search_limit")

    if st.button("Search", disabled=not search_query.strip()):
        with st.spinner("Searching..."):
            try:
                payload = {
                    "query": {
                        "multi_match": {
                            "query": search_query.strip(),
                            "fields": ["content", "meta.source", "meta.metadata_envelope.extra_meta"],
                        }
                    },
                    "size": result_limit,
                    "_source": ["content", "meta.source", "meta.metadata_envelope"],
                }

                os_endpoint = _normalize_local_endpoint(
                    os.getenv("OPENSEARCH_HOST", "http://localhost:9200"), "http://localhost:9200"
                )
                # Use workspace-specific index for semantic search
                workspace_id = st.session_state.get("workspace_id", "default")
                workspace_index = f"ask_certus_{workspace_id}"
                url = f"{os_endpoint.rstrip('/')}/{workspace_index}/_search"
                resp = requests.post(
                    url,
                    json=payload,
                    params={"allow_no_indices": "true", "ignore_unavailable": "true"},
                    timeout=10,
                )
                resp.raise_for_status()
                response_json = resp.json()
                hits = response_json.get("hits", {}).get("hits", [])

                if hits:
                    st.success(f"Found {len(hits)} results")
                    for i, hit in enumerate(hits, 1):
                        with st.expander(f"Result {i} - Score: {hit['_score']:.2f}"):
                            source = hit.get("_source", {})
                            content = source.get("content", "N/A")[:500]
                            meta = source.get("meta", {})

                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Source**: {meta.get('source', 'Unknown')}")
                            with col2:
                                st.write(f"**Score**: {hit['_score']:.2f}")

                            st.write(f"**Content**: {content}...")
                            st.json(meta)
                else:
                    st.info("No results found.")
            except Exception as exc:
                st.error(f"Search failed: {exc}")


elif selected_section == "Security Analyst Capstone":
    st.subheader("Security Analyst Capstone: Complete Workflow")
    st.write(
        "Learn how to analyze security findings and software inventory using Knowledge Graphs, Semantic Search, Keyword Search, and Hybrid Analysis."
    )

    # Initialize session state for capstone
    if "capstone_phase" not in st.session_state:
        st.session_state["capstone_phase"] = 1
    if "capstone_sample_data_ready" not in st.session_state:
        st.session_state["capstone_sample_data_ready"] = False

    # Phase navigation
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("← Previous Phase"):
            if st.session_state["capstone_phase"] > 1:
                st.session_state["capstone_phase"] -= 1
                st.rerun()

    with col2:
        phase_num = st.session_state["capstone_phase"]
        st.write(f"**Phase {phase_num} of 8**")

    with col3:
        if st.button("Next Phase →"):
            if st.session_state["capstone_phase"] < 8:
                st.session_state["capstone_phase"] += 1
                st.rerun()

    st.divider()

    phase = st.session_state["capstone_phase"]

    if phase == 1:
        st.subheader("Phase 1: Environment Setup & Data Preparation")
        st.write(
            "Initialize Neo4j and OpenSearch with sample security scanning data (SARIF) and software inventory (SBOM)."
        )

        col1, col2 = st.columns(2)
        with col1:
            st.write("**What You'll Learn:**")
            st.write("- Loading security findings into a knowledge graph")
            st.write("- Indexing package inventory for semantic search")
            st.write("- Preparing data for multi-modal analysis")

        with col2:
            st.write("**Key Concepts:**")
            st.write("- **SARIF**: Security Analysis Results Format (findings)")
            st.write("- **SPDX**: Software Package Data Exchange (inventory)")
            st.write("- **Neo4j**: Graph database for relationships")

        st.info(
            "📦 Sample data files are located in `samples/security-scans/` and referenced throughout this capstone."
        )

        if st.button("Run Setup", key="setup_button"):
            with st.spinner("Setting up capstone environment..."):
                try:
                    # Health check
                    health = fetch_health_checks(api_base)
                    all_healthy = all(ok for ok, _ in health.values())

                    if all_healthy:
                        st.success("✅ All services healthy (Neo4j, OpenSearch, FastAPI)")
                        st.info(
                            "Sample data files are ready at:\n- SARIF: `samples/security-scans/sarif/security-findings.sarif`\n- SBOM: `samples/security-scans/spdx/sbom-example.spdx.json`"
                        )
                        st.session_state["capstone_sample_data_ready"] = True
                    else:
                        st.warning("⚠️ Some services may not be fully ready. Check Monitoring tab for details.")
                except Exception as exc:
                    st.error(f"Setup check failed: {exc}")

        with st.expander("📚 Learn More: What is a Knowledge Graph?"):
            st.write("""
            A knowledge graph represents entities (findings, packages, files) as nodes and their relationships as edges.
            This allows you to ask questions like:
            - "What vulnerabilities are in file X?"
            - "What packages depend on library Y?"
            - "How many findings are high severity?"
            """)

    elif phase == 2:
        st.subheader("Phase 2: Knowledge Graph Exploration")
        st.write("Query Neo4j to understand relationships between security findings and software packages.")

        st.info(
            "The knowledge graph contains: Scans → Findings → Severity & Locations, and SBOMs → Packages → Dependencies & Licenses"
        )

        # Predefined graph queries
        graph_queries = {
            "Findings by Severity": "MATCH (f:Finding)-[:HAS_SEVERITY]->(sev:Severity) RETURN sev.level as severity, COUNT(f) as count ORDER BY count DESC",
            "Critical Findings": "MATCH (f:Finding)-[:HAS_SEVERITY]->(sev:Severity {level: 'CRITICAL'}) RETURN f.message as finding, COUNT(*) as count LIMIT 10",
            "Finding Locations": "MATCH (f:Finding)-[:LOCATED_AT]->(loc:Location) RETURN f.message as finding, loc.uri as file, loc.line as line LIMIT 10",
            "Package Inventory": "MATCH (sbom:SBOM)-[:CONTAINS]->(pkg:Package) RETURN pkg.name as package, pkg.version as version LIMIT 20",
            "Dependency Chains": "MATCH (p1:Package)-[:DEPENDS_ON]->(p2:Package) RETURN p1.name as package, p2.name as dependency LIMIT 15",
            "License Compliance": "MATCH (pkg:Package)-[:USES_LICENSE]->(lic:License) RETURN lic.name as license, COUNT(DISTINCT pkg) as package_count ORDER BY package_count DESC",
        }

        selected_query = st.selectbox("Select a graph query", list(graph_queries.keys()), key="capstone_graph_query")

        if st.button("Run Graph Query", key="run_graph_query"):
            with st.spinner("Executing Cypher query..."):
                try:
                    from neo4j import GraphDatabase

                    neo4j_uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
                    if "neo4j://neo4j:" in neo4j_uri:
                        neo4j_uri = neo4j_uri.replace("neo4j://neo4j:", "neo4j://localhost:")
                    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
                    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

                    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
                    with driver.session() as session:
                        result = session.run(graph_queries[selected_query])
                        records = result.data()
                    driver.close()

                    if records:
                        st.success(f"✅ Query returned {len(records)} records")
                        try:
                            import pandas as pd

                            df = pd.DataFrame(records)
                            st.dataframe(df, use_container_width=True)
                        except Exception:
                            st.json(records)
                    else:
                        st.info("No records returned.")
                except Exception as exc:
                    st.error(f"Query failed: {exc}")

        with st.expander("💡 Tips: Understanding Graph Relationships"):
            st.write("""
            - **Findings → Severity**: Each finding has a severity level (CRITICAL, HIGH, MEDIUM, LOW)
            - **Findings → Locations**: Findings occur at specific file paths and line numbers
            - **Packages → Dependencies**: Track transitive dependencies and supply chain risk
            - **Packages → Licenses**: Monitor license compliance across dependencies
            """)

    elif phase == 3:
        st.subheader("Phase 3: Semantic Search for Findings")
        st.write("Use OpenSearch semantic search to discover security findings by meaning, not just keywords.")

        semantic_examples = {
            "SQL Injection Risks": "SQL injection vulnerabilities",
            "Authentication Issues": "authentication and authorization problems",
            "Hardcoded Secrets": "hardcoded credentials and secrets",
            "Critical Vulnerabilities": "severe security issues",
            "Cryptography Problems": "cryptographic weaknesses",
            "Dangerous Functions": "unsafe and deprecated functions",
        }

        selected_semantic = st.selectbox(
            "Choose a search scenario", list(semantic_examples.keys()), key="semantic_scenario"
        )

        if st.button("Run Semantic Search", key="run_semantic_search"):
            with st.spinner("Searching with semantic understanding..."):
                try:
                    payload = {
                        "query": {
                            "multi_match": {"query": semantic_examples[selected_semantic], "fields": ["content"]}
                        },
                        "size": 10,
                        "_source": ["content", "meta.source"],
                    }

                    workspace_id = st.session_state.get("workspace_id", "default")
                    workspace_index = f"ask_certus_{workspace_id}"
                    url = f"{os_endpoint.rstrip('/')}/{workspace_index}/_search"
                    resp = requests.post(
                        url,
                        json=payload,
                        params={"allow_no_indices": "true", "ignore_unavailable": "true"},
                        timeout=10,
                    )
                    resp.raise_for_status()
                    hits = resp.json().get("hits", {}).get("hits", [])

                    if hits:
                        st.success(f"✅ Found {len(hits)} relevant results")
                        for i, hit in enumerate(hits, 1):
                            with st.expander(f"Result {i} - Relevance: {hit['_score']:.2f}"):
                                content = hit.get("_source", {}).get("content", "")[:500]
                                st.write(content + "...")
                    else:
                        st.info("No results found. Check if sample data has been ingested.")
                except Exception as exc:
                    st.error(f"Search failed: {exc}")

        with st.expander("🔍 Why Semantic Search?"):
            st.write("""
            Semantic search understands meaning beyond exact keyword matching:
            - "SQL injection" ≈ "SQL-based attacks"
            - "hardcoded secrets" ≈ "embedded credentials"
            - Especially useful when tool output uses different terminology
            """)

    elif phase == 4:
        st.subheader("Phase 4: Keyword Search for Precision & Compliance")
        st.write("Perform exact and Boolean searches for compliance audits and precise incident analysis.")

        keyword_examples = {
            "Exact Rule Match": "B602",
            "Multiple Rules": "B105 OR B602",
            "File-Specific Search": "filepath:*.py",
            "High Severity + Specific File": "severity:HIGH AND filepath:*.py",
            "License Audit": "license:GPL",
        }

        selected_keyword = st.selectbox(
            "Choose a compliance query", list(keyword_examples.keys()), key="keyword_scenario"
        )

        if st.button("Run Keyword Search", key="run_keyword_search"):
            with st.spinner("Executing precision keyword search..."):
                try:
                    # Simple keyword search - would need actual keyword parsing in production
                    search_term = keyword_examples[selected_keyword]

                    payload = {"query": {"query_string": {"query": search_term}}, "size": 20, "_source": ["content"]}

                    workspace_id = st.session_state.get("workspace_id", "default")
                    workspace_index = f"ask_certus_{workspace_id}"
                    url = f"{os_endpoint.rstrip('/')}/{workspace_index}/_search"
                    resp = requests.post(
                        url,
                        json=payload,
                        params={"allow_no_indices": "true", "ignore_unavailable": "true"},
                        timeout=10,
                    )
                    resp.raise_for_status()
                    hits = resp.json().get("hits", {}).get("hits", [])

                    if hits:
                        st.success(f"✅ Found {len(hits)} exact matches")
                        st.dataframe(
                            [
                                {
                                    "Result": i,
                                    "Content": hit.get("_source", {}).get("content", "")[:100] + "...",
                                }
                                for i, hit in enumerate(hits[:10], 1)
                            ],
                            use_container_width=True,
                        )
                    else:
                        st.info("No results found.")
                except Exception as exc:
                    st.error(f"Search failed: {exc}")

        with st.expander("✓ When to Use Keyword Search"):
            st.write("""
            **Compliance Audits**: Find all instances of specific rules or tools
            **Incident Response**: Locate exact findings by ID or file path
            **Boolean Logic**: Combine multiple criteria (AND, OR, NOT)
            **Precision**: Avoid false positives from semantic approximation
            """)

    elif phase == 5:
        st.subheader("Phase 5: Hybrid Analysis - Combining All Approaches")
        st.write("Integrate knowledge graph, semantic, and keyword search for comprehensive analysis.")

        hybrid_scenarios = {
            "SQL Injection Impact": "Semantic search for SQL injection + graph analysis of impacted files",
            "License Compliance": "Keyword search for GPL + dependency chain analysis",
            "Hotspot Analysis": "Find critical files (keyword) + severity distribution (graph)",
            "Dependency Risk": "Semantic search for vulnerable packages + dependency chains (graph)",
        }

        selected_hybrid = st.selectbox(
            "Choose an analysis scenario", list(hybrid_scenarios.keys()), key="hybrid_scenario"
        )
        st.info(f"🔗 {hybrid_scenarios[selected_hybrid]}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Run Semantic Phase", key="hybrid_semantic"):
                with st.spinner("Running semantic search..."):
                    st.write("✅ Semantic results would appear here")

        with col2:
            if st.button("Run Graph Phase", key="hybrid_graph"):
                with st.spinner("Querying knowledge graph..."):
                    st.write("✅ Graph results would appear here")

        st.divider()
        st.write("**Combined Analysis Result**")
        st.info(
            "In production, the results from both approaches are correlated to provide deeper insights than either method alone."
        )

        with st.expander("🎯 Hybrid Analysis Patterns"):
            st.write("""
            1. **Semantic Discovery**: Find relevant findings/packages by meaning
            2. **Graph Enrichment**: Add relationships and context from knowledge graph
            3. **Keyword Refinement**: Filter results with precise criteria
            4. **Correlation**: Cross-reference results across all three approaches
            5. **Reporting**: Generate comprehensive analysis documents
            """)

    elif phase == 6:
        st.subheader("Phase 6: Provenance & Attestation Tracking")
        st.write("Track where findings come from and verify supply chain integrity.")

        st.write("**Key Provenance Questions:**")
        st.write("- Which tool reported this finding?")
        st.write("- When was the scan executed?")
        st.write("- Who ran the analysis and approved it?")
        st.write("- Can we verify the scan results haven't been tampered with?")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Attestation Example**")
            attestation = {
                "scan_id": "scan-20250127-001",
                "timestamp": "2025-01-27T14:32:15Z",
                "tool": "bandit",
                "tool_version": "1.7.5",
                "user": "security-analyst",
                "status": "verified",
                "signature": "sha256:abc123...",
            }
            st.json(attestation)

        with col2:
            st.write("**Metadata Tracking**")
            st.write("- **Ingestion ID**: Unique identifier for each data import")
            st.write("- **Captured At**: Timestamp of when the scan ran")
            st.write("- **Source**: Tool that produced the findings")
            st.write("- **Verification**: Cryptographic proof of authenticity")

        st.info("🔐 OCI attestations ensure findings are trustworthy and haven't been modified after collection.")

    elif phase == 7:
        st.subheader("Phase 7: Generating Security Reports")
        st.write("Synthesize analysis into actionable reports for different audiences.")

        report_types = {
            "Executive Summary": "High-level risk assessment and metrics",
            "Technical Deep Dive": "Detailed findings with remediation guidance",
            "Compliance Report": "Evidence of security checks and controls",
            "Risk Register": "Prioritized findings with business impact",
        }

        selected_report = st.selectbox("Select report type", list(report_types.keys()), key="report_type")

        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**{selected_report}**")
            st.write(report_types[selected_report])

        with col2:
            if st.button("Generate Report", key="gen_report"):
                with st.spinner("Generating report..."):
                    st.success(f"✅ {selected_report} would be generated here")
                    st.info("In production, reports are created from analysis results and exported as PDF/HTML")

        st.divider()
        st.write("**Report Customization**")
        include_metrics = st.checkbox("Include metrics dashboard", value=True)
        include_remediation = st.checkbox("Include remediation steps", value=True)
        include_evidence = st.checkbox("Include evidence artifacts", value=True)

        if st.button("Download Report Sample", key="download_report"):
            sample_report = """
# Security Analysis Report
Generated: 2025-01-27

## Executive Summary
- Total Findings: 12
- Critical Severity: 2
- High Severity: 4
- Medium Severity: 6

## Recommendations
1. Address critical findings immediately
2. Plan remediation for high-severity issues
3. Monitor medium-severity findings
            """
            st.download_button(
                label="Download Report",
                data=sample_report.encode(),
                file_name="security_report.md",
                mime="text/markdown",
            )

    elif phase == 8:
        st.subheader("Phase 8: Capstone Wrap-Up & Best Practices")
        st.write("Consolidate learning and establish ongoing security analysis practices.")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**What You've Learned**")
            st.write("✅ Loading security data (SARIF, SPDX)")
            st.write("✅ Graph-based relationship analysis")
            st.write("✅ Semantic search for discovery")
            st.write("✅ Keyword search for precision")
            st.write("✅ Hybrid workflows for deep insights")
            st.write("✅ Tracking provenance and attestations")
            st.write("✅ Generating actionable reports")

        with col2:
            st.write("**Next Steps**")
            st.write("📖 Study the full capstone tutorial")
            st.write("🔧 Customize scripts for your data")
            st.write("📊 Build automated analysis pipelines")
            st.write("🤝 Integrate with your CI/CD")
            st.write("📈 Monitor trends over time")
            st.write("🎓 Train your team on workflows")

        st.divider()

        st.write("**Best Practices Summary**")
        practices = """
        1. **Automate Data Ingestion**: Load findings and inventory on every scan
        2. **Track Provenance**: Always verify scan authenticity and integrity
        3. **Use Multiple Search Approaches**: Combine semantic, keyword, and graph queries
        4. **Maintain Knowledge Graph**: Keep relationships up-to-date and accurate
        5. **Generate Regular Reports**: Establish cadence for stakeholder reporting
        6. **Monitor Trends**: Track metrics over time to measure improvement
        7. **Iterate on Analysis**: Refine queries and workflows based on learnings
        """
        st.write(practices)

        st.info("📚 For detailed instructions and examples, see: `docs/learn/security-analyst-capstone.md`")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("View Full Tutorial", key="view_tutorial"):
                st.write("Tutorial location: `docs/Learn/security-analyst-capstone.md`")

        with col2:
            if st.button("Review Sample Scripts", key="view_scripts"):
                st.write("Script location: `samples/capstone/`")

        with col3:
            if st.button("Start Over", key="restart_capstone"):
                st.session_state["capstone_phase"] = 1
                st.rerun()
