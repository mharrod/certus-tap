# Streamlit Operations Console

## Purpose
Provide a browser-based interface for Certus TAP operators to ingest content, manage S3 buckets, monitor health, and trigger RAG queries without manual `curl` commands.

## Audience & Prerequisites
- Analysts or demo operators who prefer a GUI.
- Developers validating ingestion/guardrail workflows quickly.
- Requires the stack (`just up`) and Streamlit service (port `8501` by default) to be running.

## Overview
- `just up` launches the console automatically unless `START_STREAMLIT=false`.
- The sidebar lets you choose a workspace, configure connection settings, and navigate workflows.
- Workflows wrap existing REST endpoints (`/v1/index/*`, `/v1/datalake/*`, `/v1/ask`, `/v1/health/*`) and show raw JSON responses for auditing.

## Key Concepts

### Launch & Configuration
- Default port: `8501`. Override with `STREAMLIT_PORT=8600 just up`.
- Skip auto-start: `START_STREAMLIT=false just up`.
- Manual run: `uv run streamlit run src/certus_tap/streamlit_app.py`.
- Sidebar connection settings mirror `.env` (API base URL, AWS creds, S3 endpoint, OpenSearch host). Updates apply live.

### Workspace Selector
- Choose the target workspace for ingestion or RAG queries. New workspaces are created automatically at first ingestion.
- Ties into [Multi-Workspace Isolation](../general/multi-workspace-isolation.md); every workflow respects the selected workspace.

### Available Workflows (Highlights)

| Workflow | Description |
| -------- | ----------- |
| **Single / Batch Document Ingestion** | Upload files and call `POST /v1/{workspace}/index/`, surfacing `ingestion_id`, document counts, and metadata previews. |
| **Upload to Raw Bucket** | Push files or ZIP archives directly into the configured raw S3 bucket (LocalStack by default). |
| **Batch Load from S3** | Trigger `POST /v1/datalake/ingest/batch` to ingest an entire prefix. |
| **Promote Raw → Golden** | Call `/v1/datalake/preprocess` (single) or `/v1/datalake/preprocess/batch`. |
| **Browse S3** | List objects, download files, or delete them across raw/golden buckets. |
| **Monitoring / Health** | Invoke `/v1/health/*` endpoints and display recent log events. |
| **Metadata Lookup** | Paste an `ingestion_id` to run the OpenSearch metadata query described in the metadata envelope docs. |
| **Privacy Scan & Quarantine** | Run the privacy analyzer or review quarantined documents for release. |
| **OpenSearch Query** | Submit ad-hoc DSL queries to any index/pattern. |
| **Ask Certus** | Send prompts to `/v1/{workspace}/ask` to validate RAG plumbing end-to-end. |

All actions display structured results (JSON) so you can copy `ingestion_id` values or inspect error payloads.

## Workflows / Operations
1. **Bring up the stack:** `just up` (or `./scripts/start-up.sh`) ensures FastAPI, LocalStack, OpenSearch, Neo4j, and Streamlit are running.
2. **Configure workspace & endpoints:** In the sidebar, pick the workspace and verify API/S3 endpoints (defaults come from `.env`).
3. **Run ingestion or datalake workflows:** Use the relevant tabs to upload files, trigger S3 promotions, or run batch ingestions.
4. **Monitor health:** Periodically check the monitoring tab for `/v1/health/*` status and review logs from `logs-certus-tap`.
5. **Perform RAG validation:** After ingesting, switch to “Ask Certus” to confirm answers return as expected.

## Configuration / Interfaces
- Settings environment variables: `START_STREAMLIT`, `STREAMLIT_PORT`, `DOCOPS_API_BASE`, `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `OPENSEARCH_URL`.
- The app lives at `src/certus_tap/streamlit_app.py`.
- The UI interacts with:
  - REST API (`/v1/...`)
  - LocalStack S3 (via boto3)
  - OpenSearch (via REST)

## Troubleshooting / Gotchas
- **Console not reachable:** Ensure container is running (`docker compose ps streamlit`) and the port isn’t blocked.
- **Workspace mismatch:** Remember to switch workspaces before ingesting; otherwise documents land in the previously selected workspace.
- **S3 permission errors:** When targeting real AWS, update the sidebar credentials to an IAM user with the required bucket access.
- **Health tab failures:** If `/v1/health/*` fails, check backend logs (`docker compose logs ask-certus-backend`) before ingesting more data.

## Related Documents
- [Metadata Envelopes (API)](../api/metadata-envelopes.md) – Underpins the metadata lookup tab.
 - [OpenSearch Explorer](opensearch-explorer.md) – GUI and REST queries complement the Streamlit OpenSearch tab.
 - [Multi-Workspace Isolation](../general/multi-workspace-isolation.md)
 - [Privacy Operations (Logging)](../logging/privacy-operations.md)
