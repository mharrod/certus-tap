# Service & Router Playbook

How we keep ingestion services, FastAPI routers, and supporting components well-tested without booting the entire stack.

## Quick Start

```bash
# Run all service-layer suites
uv run python -m pytest tests/test_services/ -v

# Focus on routers
uv run python -m pytest tests/test_routers_api.py -v

# Target a specific module
uv run python -m pytest tests/test_services/test_opensearch.py::TestOpenSearchClientInitialization

# Include coverage for the service packages
uv run python -m pytest tests/test_services/ --cov=certus_ask.services --cov-report=term
```

## Philosophy

- **Isolate business logic** – mocked OpenSearch/S3/Presidio ensure failures point at our code, not the network.
- **Use moto/fakes where helpful** – Moto provides realistic S3 behavior; `MagicMock`/`SimpleNamespace` cover lightweight seams.
- **Keep tests fast** – most suites should finish in under a second; reserve dockerized/system tests for `preflight`.

## Toolbox

| Tool | Purpose |
| --- | --- |
| `tests/conftest.py` fixtures | Set env vars, provide moto S3 clients, mock OpenSearch stores, create FastAPI app/TestClient. |
| `moto.mock_aws()` | In-memory S3 API for datalake helpers and router tests. |
| `MagicMock` / `SimpleNamespace` | Stub Presidio analyzer results, OpenSearch responses, evaluation services, etc. |
| `pytest-asyncio` | Enables `@pytest.mark.asyncio` for async routers. |
| FastAPI `TestClient` | Executes router flows end-to-end without launching uvicorn. |

## Coverage Snapshot

| Module | Focus | Typical Assertions |
|--------|-------|--------------------|
| `test_opensearch.py` | Document store caching, CRUD, workspace index sanitization | `mock.index.called`, sanitized index names |
| `test_s3.py` | Bucket/dir uploads, metadata, cached client | moto operations, ensuring `upload_file` called |
| `test_datalake_service_unit.py` | Bucket bootstrap, folder promotion, masking | moto head/put semantics, `.masked` artifacts |
| `test_presidio_example.py` | Analyzer/anonymizer samples, privacy logger | fixture-driven PII assertions |
| `test_routers_api.py` & friends | Health, datalake preprocess, query flows | HTTP status codes, metadata preview, error handling |

## Patterns by Layer

### Ingestion Services (S3 helpers)
File: `tests/test_services/test_datalake_service_unit.py`
- Simulate `head_bucket` raising `ClientError("404")` to assert `ensure_bucket` creates the bucket.
- Verify `ensure_folders` writes `Key="folder/"`.
- Patch `datalake.upload_file` to capture keys when testing `upload_directory`.
- Stub `scan_file_for_privacy_data` to return Presidio results and assert `.masked` files are produced.

### Pipeline Components
File: `tests/test_pipelines_preprocessing.py`
- Fake Presidio analyzer output and ensure strict mode quarantines docs.
- Stub anonymizer to return `SimpleNamespace(text="<MASK>")` and confirm metadata annotations.
- Patch document writer components to validate metadata previews.

### FastAPI Routers
Files: `tests/test_routers_api.py`, `tests/test_datalake.py`, `tests/test_routers/test_ingestion_router.py`
- `test_app` fixture clears cached settings, patches `get_document_store`/`get_s3_client`, and builds a FastAPI instance.
- `TestClient(test_app, raise_server_exceptions=False)` allows asserting 4xx/5xx responses directly.
- Async routers (e.g., datalake streaming) rely on moto clients plus `@pytest.mark.asyncio`.

### External API Clients
Example: `tests/test_services/test_trust_client.py`
- Patch only the boundary (`httpx.AsyncClient`) so the client logic (retries, headers) runs unmodified.
- Use lightweight dummy responses to assert `Authorization` headers, retry counts, and parsed payloads.

## Writing New Tests

1. **Decide scope** – unit (mock everything) vs. integration (moto/localstack).
2. **Patch the boundary** – import the target module and patch service entry points (`get_document_store`, `get_s3_client`, `requests.post`, etc.).
3. **Use fixtures** – extend `tests/conftest.py` only when setup repeats; keep fixture scope minimal to avoid slow startups.
4. **Assert behavior, not implementation** – focus on outputs, log entries, or interactions (e.g., `client.upload_file` called with the right key).

### Example Template

```python
from unittest.mock import MagicMock
from certus_ask.services import my_service

def test_my_service_handles_retries(monkeypatch):
    client = MagicMock()
    client.do_work.side_effect = [TimeoutError, "ok"]

    result = my_service.perform(client)

    assert result == "ok"
    assert client.do_work.call_count == 2
```

## Common Pitfalls

- **Forgetting to clear caches** – call `certus_ask.core.config.get_settings.cache_clear()` when tests mutate env vars.
- **Leaking network calls** – ensure every external dependency is patched; CI should never hit real APIs.
- **Non-deterministic async tests** – mark them with `@pytest.mark.asyncio` and avoid raw `sleep`.
- **Real file/dir writes** – use `tmp_path` and clean up via fixtures.

## Merge Checklist

- Does every new branch/feature have unit coverage?
- If an API surface changed, did you update the router tests (`tests/test_routers_api.py`, `tests/test_datalake.py`, etc.)?
- Did you run `uv run python -m pytest -m "not smoke"` locally?
- For cross-service features, did you finish with `./scripts/preflight.sh`?

Keeping these patterns consistent ensures the ingestion stack can evolve quickly without breaking the critical pipelines.
