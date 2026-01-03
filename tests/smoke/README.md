# Smoke Tests

This package holds documentation-driven smoke tests that exercise the
published tutorials end-to-end against a running Certus TAP stack.

## Current Coverage

- `tests/smoke/basics/test_ingestion_pipelines.py` mirrors the steps from
  `docs/learn/basics/ingestion-pipelines.md`: single document upload,
  recursive folder ingestion, and search verification via OpenSearch.
- `tests/smoke/basics/test_sample_datalake_upload.py` follows
  `docs/reference/learn/basics/sample-datalake-upload.md`: uploads the
  datalake sample bundle to LocalStack (S3) and ingests it via `/index/s3`.
- `tests/smoke/basics/test_golden_bucket.py` replays
  `docs/learn/basics/golden-bucket.md`: stages the privacy pack in the raw
  bucket, promotes it to the golden bucket, ingests, and validates masking
  through the Ask API.
- `tests/smoke/security_workflows/test_hybrid_search.py` mirrors
  `docs/learn/security-workflows/hybrid-search.md`: ingests the mock SARIF +
  SPDX artifacts and verifies hybrid OpenSearch + Neo4j queries.
- `tests/smoke/security_workflows/test_semantic_search.py` follows
  `docs/learn/security-workflows/semantic-search.md`: ingests the security
  scans workspace and verifies embeddings plus a KNN query.
- `tests/smoke/security_workflows/test_keyword_search.py` executes the
  deterministic keyword queries from `docs/learn/security-workflows/keyword-search.md`.
- `tests/smoke/security_workflows/test_neo4j_local_ingestion.py` runs the
  Neo4j loader script and validates the resulting graph as described in
  `docs/learn/security-workflows/neo4j-local-ingestion-query.md`.

## Running Locally

1. Start the stack (`just up`) so `ask-certus-backend`, `opensearch`, etc. are
   available on the default Docker network.
2. Launch the smoke profile:

   ```bash
   docker compose --profile test up --abort-on-container-exit --exit-code-from smoke-tests smoke-tests
   ```

   or run it directly:

   ```bash
   docker compose --profile test run --rm smoke-tests
   ```

### Useful Environment Variables

| Variable                | Purpose                                             | Default                                                 |
| ----------------------- | --------------------------------------------------- | ------------------------------------------------------- |
| `API_BASE`              | Base URL for the Ask API                            | `http://ask-certus-backend:8000`                        |
| `OS_ENDPOINT`           | OpenSearch endpoint used for verification           | `http://opensearch:9200`                                |
| `SMOKE_WORKSPACE`       | Workspace used for tutorial runs                    | `smoke-ingestion-{timestamp}`                           |
| `SMOKE_TUTORIAL_FILE`   | Override path to `quick-start-guide.txt`            | `/app/samples/ingestion-examples/quick-start-guide.txt` |
| `SMOKE_TUTORIAL_DIR`    | Override path to the ingestion tutorial directory   | `/app/samples/ingestion-examples`                       |
| `SMOKE_REQUEST_TIMEOUT` | Request timeout when calling the API                | `60` seconds                                            |
| `SMOKE_DATALAKE_DIR`    | Path to the datalake sample bundle                  | `/app/samples/datalake-demo`                            |
| `SMOKE_RAW_BUCKET`      | Raw bucket name used for LocalStack uploads         | `raw`                                                   |
| `SMOKE_PRIVACY_RAW_DIR` | Path to the privacy-pack raw documents              | `/app/samples/privacy-pack/raw`                         |
| `SMOKE_GOLDEN_BUCKET`   | Golden bucket name for promotions                   | `golden`                                                |
| `SMOKE_BASE_INDEX`      | Override the base OpenSearch index for shared flows | `OPENSEARCH_INDEX` (`ask_certus`) by default            |

These settings can be provided via `docker compose run -e KEY=value` or by
editing `.env`. The compose profile installs dependencies with `uv` and runs
`pytest --confcutdir=tests/smoke`
so that the smoke suite stays isolated from the heavier `tests/` fixtures.
