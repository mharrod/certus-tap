# API Error Codes

## Purpose
Provide a definitive catalog of every machine-readable error code emitted by the Certus TAP API, how those codes map to HTTP status responses, and the context clients need to remediate issues.

## Audience & Prerequisites
- API consumers who need to handle errors deterministically.
- Backend contributors adding new error codes to the platform.
- Familiarity with the [Standard Response Format](api-response.md) and FastAPI’s exception model.

## Overview
- Error codes follow the pattern `<category>_<specific_error>` and are tightly coupled to HTTP status codes.
- Every error payload includes `status`, `error.code`, `error.message`, and optional `error.context`.
- Categories align with underlying subsystems (authentication, privacy, storage, search, etc.) so callers can triage quickly.

## Key Concepts

### Naming Convention & Categories

| Category                      | Prefix                      | Typical HTTP Status | Meaning                                         |
| ----------------------------- | --------------------------- | ------------------- | ----------------------------------------------- |
| **Authentication**            | `auth_*`                    | 401                 | Missing or invalid credentials                  |
| **Authorization/Permissions** | `permission_*`, `privacy_*` | 403                 | Caller lacks required scope or action denied    |
| **Validation**                | `validation_*`              | 400 / 422           | Request or payload fails validation             |
| **File/Resource**             | `file_*`, `bucket_*`        | 400 / 404           | Source file, bucket, or index not found         |
| **Processing**                | `processing_*`              | 500 / 503           | Pipeline execution failures                     |
| **Search/Index**              | `index_*`, `search_*`       | 404 / 500           | OpenSearch errors                               |
| **Conflict**                  | `conflict_*`                | 409                 | Request conflicts with existing resource state  |
| **Privacy**                   | `privacy_*`                 | 400 / 403           | PII detection or privacy violations             |
| **Service**                   | `service_*`                 | 503 / 504           | External dependency unavailable or timed out    |
| **Rate Limiting**             | `rate_limit_*`              | 429                 | Request quota exceeded                          |
| **Storage**                   | `storage_*`                 | 500                 | S3 and storage failures                         |

### Standard Error Object

All error responses follow the structure defined in [api-response.md](api-response.md):

```json
{
  "status": "error",
  "data": null,
  "error": {
    "code": "validation_failed",
    "message": "File exceeds maximum size of 100MB",
    "context": {
      "max_size_mb": 100,
      "actual_size_mb": 256
    }
  },
  "timestamp": "2024-11-14T12:34:56.789Z",
  "trace_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

### HTTP Status Mapping
Each status has a fixed set of codes and example payloads.

#### 400 – Bad Request

| Error Code          | Meaning                        | When Raised                             |
| ------------------- | ------------------------------ | --------------------------------------- |
| `validation_failed` | Request fails validation       | Payload constraint violations           |
| `invalid_format`    | File/data format invalid       | Non-JSON file, wrong encoding           |
| `invalid_request`   | Request structure invalid      | Missing required fields                 |
| `file_too_large`    | File exceeds size limit        | Upload > 100MB                          |
| `no_matching_files` | Glob/prefix matched no files   | GitHub/S3 include patterns match none  |

```json
{
  "status": "error",
  "data": null,
  "error": {
    "code": "validation_failed",
    "message": "File exceeds maximum size of 100MB",
    "context": {
      "max_size_mb": 100,
      "actual_size_mb": 256
    }
  },
  "timestamp": "...",
  "trace_id": "..."
}
```

#### 401 – Unauthorized

| Error Code     | Meaning                         | When Raised                                |
| -------------- | ------------------------------- | ------------------------------------------ |
| `auth_missing` | Authorization header not found  | Protected endpoint without `Authorization` |
| `auth_invalid` | Token invalid/expired/revoked   | Bearer/API token cannot be validated       |

#### 403 – Forbidden

| Error Code          | Meaning                            | When Raised                                   |
| ------------------- | ---------------------------------- | --------------------------------------------- |
| `permission_denied` | Caller lacks required role/scope   | Workspace ingestion without maintainer role   |
| `privacy_violation` | Operation blocked for privacy      | Access to quarantined/PII documents           |

#### 404 – Not Found

| Error Code         | Meaning                    | When Raised                                   |
| ------------------ | -------------------------- | --------------------------------------------- |
| `file_not_found`   | File path or key missing   | Local path or S3 key absent                   |
| `bucket_not_found` | S3 bucket missing          | Bucket deleted or misspelled                  |
| `index_not_found`  | OpenSearch index missing   | Index not yet created or deleted              |
| `prefix_not_found` | No objects under prefix    | Batch ingest target empty                     |

#### 409 – Conflict

| Error Code              | Meaning                          | When Raised                                   |
| ----------------------- | -------------------------------- | --------------------------------------------- |
| `conflict_state`        | Resource already exists          | Duplicate workspace/index/ingestion creation  |
| `ingestion_in_progress` | Concurrent ingestion in progress | Another ingestion for same dataset            |

#### 422 – Unprocessable Entity

| Error Code                   | Meaning                       | When Raised                               |
| ---------------------------- | ----------------------------- | ----------------------------------------- |
| `validation_failed`          | Payload violates constraints  | Field-level errors                        |
| `semantic_validation_failed` | Cross-field validation failed | Include/exclude overlap, invalid combos   |

#### 429 – Too Many Requests

| Error Code            | Meaning                   | When Raised               |
| --------------------- | ------------------------- | ------------------------- |
| `rate_limit_exceeded` | Request quota exceeded    | Per-token or per-IP limit |

#### 500 – Internal Server Error

| Error Code          | Meaning                     | When Raised                      |
| ------------------- | --------------------------- | -------------------------------- |
| `processing_failed` | General pipeline error      | Unexpected preprocessing failure |
| `parse_failed`      | Document parsing failed     | Unsupported/corrupted formats    |
| `ingestion_failed`  | Indexing pipeline failed    | Chunking/indexing issue          |
| `storage_error`     | S3 operation failed         | Upload/download/list problems    |
| `index_error`       | OpenSearch operation failed | Index/search operations          |
| `mlflow_error`      | MLflow logging failed       | Experiment logging unsuccessful  |

#### 503 – Service Unavailable

| Error Code               | Meaning                      | When Raised                        |
| ------------------------ | ---------------------------- | ---------------------------------- |
| `service_unavailable`    | External dependency down     | Any critical service offline       |
| `opensearch_unavailable` | OpenSearch not responding    | Connection failure                 |
| `llm_unavailable`        | LLM provider unavailable     | RAG pipeline cannot reach LLM      |

#### 504 – Gateway Timeout

| Error Code | Meaning                       | When Raised            |
| ---------- | ----------------------------- | ---------------------- |
| `timeout`  | Operation exceeded time limit | Long-running queries   |

### Reference Library
Use the snippets below when you need quick context for categories.

- **Validation Errors:** `validation_failed`, `invalid_format`, `invalid_request`, `file_too_large`, `no_matching_files`.
- **Resource Errors:** `file_not_found`, `bucket_not_found`, `index_not_found`, `prefix_not_found`.
- **Processing Errors:** `processing_failed`, `parse_failed`, `ingestion_failed`, `storage_error`, `index_error`, `mlflow_error`.
- **Service Errors:** `service_unavailable`, `opensearch_unavailable`, `llm_unavailable`, `timeout`.
- **Auth Errors:** `auth_missing`, `auth_invalid`, `permission_denied`, `privacy_violation`.

## Workflows / Operations
1. **Introduce a new error** only when a distinct remediation path exists.
2. **Add the constant** in the relevant module (`certus_ask/schemas/errors.py` or specific router).
3. **Document** the code in this file under the appropriate HTTP status and category.
4. **Reference** the code from endpoint docstrings (see [API Documentation Standard](api-doc-standard.md)).
5. **Test** by exercising the error path locally and capturing the JSON payload for documentation.

## Configuration / Interfaces
- Error schemas live in `certus_ask/schemas/errors.py` and FastAPI response models.
- Standard response helpers in `certus_ask/core/response_utils.py` populate the `error` object.
- Structured logs include the error code plus `trace_id` for correlation.

## Troubleshooting / Gotchas
- **Duplicate codes:** Never reuse a code for different meanings; prefer new specific suffixes.
- **Missing docs:** Any new code must appear here before merging feature work.
- **HTTP mismatch:** Ensure the HTTP status set in `HTTPException` matches the table above.
- **Context overload:** Keep `error.context` lightweight (avoid dumping entire payloads).

## Related Documents
- [Standardized Response Format and Trace IDs](api-response.md)
- [API Documentation Standard](api-doc-standard.md)
- [Metadata Envelopes](metadata-envelopes.md)
- [Logging – Troubleshooting](../logging/troubleshooting.md)
