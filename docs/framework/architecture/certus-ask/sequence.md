# Sequence Diagrams

End-to-end flow references for common TAP interactions—use these to reason about touchpoints, guardrails, and hand-offs before updating pipelines or deployments.

## Store Documents in the S3-Compatible Layer

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant CLI as CLI / Script
    participant API as FastAPI /v1/datalake/upload
    participant S3 as S3-Compatible Layer

    Dev->>CLI: Run just datalake-upload …
    CLI->>API: POST /v1/datalake/upload (file metadata)
    API->>S3: Upload object to LocalStack
    API-->>CLI: 200 OK + key
```

| Participant         | Description                                               |
| ------------------- | --------------------------------------------------------- |
| Developer / CLI     | Invokes the helper endpoints locally.                     |
| FastAPI             | Validates payloads and streams bytes.                     |
| S3-Compatible Layer | LocalStack S3 endpoint storing raw and processed objects. |

## Bulk Index of Documents (single process)

```mermaid
sequenceDiagram
    participant User
    participant API as FastAPI /v1/{workspace}/index_folder
    participant Pipeline as Haystack Pipeline
    participant S3 as S3-Compatible Layer
    participant OS as OpenSearch

    User->>API: POST /v1/foo/index_folder
    API->>Pipeline: Start preprocessing workflow
    Pipeline->>S3: Optional uploads (privacy logs, quarantine)
    Pipeline->>OS: Write chunks and metadata
    API-->>User: Return ingestion counts
```

| Participant         | Description                                              |
| ------------------- | -------------------------------------------------------- |
| User                | Person or automation initiating ingestion.               |
| FastAPI             | certus*ask handling `/v1/{workspace}/index*\*` requests. |
| Haystack Pipeline   | Runs inside the same process; no background workers.     |
| S3-Compatible Layer | Optional persistence for raw/quarantined artifacts.      |
| OpenSearch          | Target store for embeddings + metadata.                  |

#### Simple Query

The Query function in the included application is very simple. More robust query capabilities will be built as a seperate service in the future.

```mermaid
sequenceDiagram
    participant US as User
    participant FA as FastAPI /v1/{workspace}/ask
    participant QP as Query Pipeline
    participant OS as OpenSearch
    participant LLM as LLM

    US->>FA: Send Request (e.g. /v1/ask)
    FA->>QP: Process Query
    QP->>OS: Query OpenSearch
    OS->>QP: Return Results
    QP->>LLM: Send Query and Results to LLM
    LLM->>QP: Return Answer
    QP->>US: Return Answer to User






```

| Participant    | Description                                        |
| -------------- | -------------------------------------------------- |
| User           | Issues a question via UI or API.                   |
| FastAPI        | Routes query to the retrieval pipeline.            |
| Query Pipeline | Embeds question, runs retrieval, orchestrates LLM. |
| OpenSearch     | Returns relevant context chunks.                   |
| LLM            | Generates final natural-language response.         |

## Web or Git Ingestion with Guardrails

Illustrates how `/v1/index/web` or Git ingestion respects robots.txt, rate limits, and sanitization before persisting data.

```mermaid
sequenceDiagram
    participant UA as User/Automation
    participant FA as FastAPI /v1/{workspace}/index/web
    participant Fetch as Fetcher/Scraper
    participant Sanitizer as Sanitizer/PII Filter
    participant Splitter as Splitter/Embedder
    participant Storage as Storage/OpenSearch

    UA->>FA: POST /v1/index/web (seed URLs)
    FA->>Fetch: Fetch/crawl URLs
    Fetch->>Sanitizer: Stream content
    Sanitizer->>Splitter: Clean + redact
    Splitter->>Storage: Store chunks & embeddings
    Storage-->>UA: Ingestion status
```

| Participant          | Description                                          |
| -------------------- | ---------------------------------------------------- |
| User/Automation      | Triggers ingestion (manual or scheduled).            |
| FastAPI              | Validates the request and builds the Haystack graph. |
| Fetcher/Scraper      | Downloads content, handles git clone or HTTP fetch.  |
| Sanitizer/PII Filter | Removes secrets, PII, or disallowed text.            |
| Splitter/Embedder    | Chunks content and produces embeddings.              |
| Storage/OpenSearch   | Persists processed content for retrieval.            |

## SARIF Upload to Ticketing

Edge collectors push SARIF files, which are normalized, indexed, and used to raise tickets or alerts.

```mermaid
sequenceDiagram
    participant Edge as CLI Upload
    participant FA as FastAPI /v1/{workspace}/index/security
    participant Pipe as Security Pipeline
    participant OS as OpenSearch
    participant ML as MLflow

    Edge->>FA: POST /v1/foo/index/security (payload + metadata)
    FA->>Pipe: Schema validation + parsing
    Pipe->>OS: Upsert findings in search index
    Pipe->>ML: Log ingestion metrics
    FA-->>Edge: Return counts + optional Neo4j ids
```

| Participant       | Description                                                |
| ----------------- | ---------------------------------------------------------- |
| CLI Upload        | Script or automation posting SARIF/SPDX payloads.          |
| FastAPI           | Validates request and routes to the SARIF/SPDX pipeline.   |
| Security Pipeline | Parses SARIF/SPDX, enriches metadata, handles Neo4j hooks. |
| OpenSearch        | Stores normalized findings for search/analytics.           |
| MLflow            | Captures ingestion metrics for observability.              |

## Guarded Query & LLM Selection

Extended query flow showing policy checks, guardrails, multi-LLM routing, and observability taps.

```mermaid
sequenceDiagram
    participant User as User
    participant FA as FastAPI
    participant Retriever as Retriever
    participant Reranker as Re-Ranker/Prompt Builder
    participant LLM as LLM Endpoint

    User->>FA: POST /v1/foo/ask
    FA->>Retriever: Embed + fetch context
    Retriever-->>FA: Candidate passages
    FA->>Reranker: Build prompt
    Reranker->>LLM: Submit prompt/context
    LLM-->>FA: Answer
    FA->>User: Return response
```

| Participant              | Description                                         |
| ------------------------ | --------------------------------------------------- |
| User                     | Initiates the question.                             |
| FastAPI                  | Coordinates the whole RAG call chain.               |
| Retriever                | Embeds question and fetches relevant context.       |
| Re-Ranker/Prompt Builder | Orders snippets, prepares final prompt.             |
| LLM Endpoint             | Executes completion/generation (Ollama by default). |

## Preflight & Health Automation

Shows how `./scripts/preflight.sh` orchestrates stack startup, sample ingestion, and verification before commits.

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Preflight as preflight.sh
    participant Stack as Docker Compose Stack
    participant Health as Health Checks
    participant Ingest as Sample Ingestion
    participant Tests as Integration Tests
    participant Report as Summary Output

    Dev->>Preflight: Run ./scripts/preflight.sh
    Preflight->>Stack: just up / docker compose up
    Stack-->>Preflight: Services ready
    Preflight->>Health: Call /v1/health/*
    Health-->>Preflight: Status OK
    Preflight->>Ingest: Trigger sample git/web/SARIF ingestion
    Ingest-->>Preflight: Ingestion results
    Preflight->>Tests: Execute smoke queries
    Tests-->>Preflight: Pass/fail status
    Preflight->>Report: Summarize outcomes
    Report-->>Dev: Display actionable report
```

| Participant          | Description                                             |
| -------------------- | ------------------------------------------------------- |
| Developer            | Engineer preparing a change or verifying the stack.     |
| preflight.sh         | Automation script orchestrating the workflow.           |
| Docker Compose Stack | Local services (backend, OpenSearch, LocalStack, etc.). |
| Health Checks        | `/v1/health/*` endpoints ensuring readiness.            |
| Sample Ingestion     | Representative ingestion tasks run during preflight.    |
| Integration Tests    | Smoke queries validating retriever/LLM path.            |
| Summary Output       | Final pass/fail report shown to the developer.          |
