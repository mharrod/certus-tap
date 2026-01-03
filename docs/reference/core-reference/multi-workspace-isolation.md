# Multi-Workspace Isolation

Certus TAP supports **multi-workspace isolation** for managing multiple independent ingestion and analysis workflows within a single system. Each workspace maintains completely separate data in dedicated OpenSearch indices, enabling secure multi-tenant use cases like product documentation, client analysis, or concurrent investigations.

## What is a Workspace?

A workspace is a logical grouping of documents and queries. Each workspace:

- Uses a dedicated OpenSearch index: `ask_certus_{workspace_id}`
- Stores all documents independently from other workspaces
- Has complete metadata isolation (every document includes `workspace_id` in its metadata)
- Can be created on-demand without any backend configuration

**Example workspaces:**
- `product-docs` - Product documentation
- `client-acme` - Analysis for ACME client
- `research-2024` - Research project
- `investigation-a` - Security investigation

## Creating a Workspace

### Via Streamlit UI

1. Open the Streamlit Console at `http://localhost:7501`
2. Look for the **"Workspace"** section at the bottom of the sidebar
3. Click the dropdown and select **"➕ Create new workspace..."**
4. Enter a workspace name (e.g., `product-a`)
5. Click **"Create Workspace"**

The workspace is created automatically on first document ingestion.

### Via API (curl)

Create a workspace by ingesting a document into it:

```bash
# Create workspace "product-a" with a document
curl -X POST "http://localhost:8000/v1/product-a/index/" \
  -F "uploaded_file=@document.pdf"
```

This creates the `ask_certus_product_a` index in OpenSearch if it doesn't already exist.

## Switching Workspaces

In the Streamlit UI, simply select a different workspace from the dropdown. All subsequent operations will use that workspace's isolated data.

**Current workspace indicator:** The sidebar shows "📍 Current: **workspace-name**"

## API Endpoints with Workspace ID

All ingestion and query endpoints use the `/{workspace_id}/` path pattern:

### Ingestion Endpoints

```bash
# Single file upload
curl -X POST "http://localhost:8000/v1/{workspace_id}/index/" \
  -F "uploaded_file=@document.pdf"

# Folder recursion
curl -X POST "http://localhost:8000/v1/{workspace_id}/index_folder/" \
  -H "Content-Type: application/json" \
  -d '{"local_directory": "docs"}'

# GitHub repository
curl -X POST "http://localhost:8000/v1/{workspace_id}/index/github" \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/user/repo", "branch": "main"}'

# SARIF vulnerability files
curl -X POST "http://localhost:8000/v1/{workspace_id}/index/sarif" \
  -F "uploaded_file=@scan-results.sarif"

# Web page scraping
curl -X POST "http://localhost:8000/v1/{workspace_id}/index/web" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "render": false}'

# Web domain crawling
curl -X POST "http://localhost:8000/v1/{workspace_id}/index/web/crawl" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "allowed_domains": ["example.com"]}'
```

### Query Endpoints

```bash
# Ask RAG question
curl -X POST "http://localhost:8000/v1/{workspace_id}/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the architecture?"}'
```

Replace `{workspace_id}` with your workspace name, e.g., `product-a`:

```bash
curl -X POST "http://localhost:8000/v1/product-a/index/" \
  -F "uploaded_file=@docs.pdf"

curl -X POST "http://localhost:8000/v1/product-a/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the API?"}'
```

## Metadata Isolation

Each document ingested includes `workspace_id` in its metadata envelope:

```json
{
  "version": "1.0",
  "workspace_id": "product-a",
  "ingestion_id": "96435e86-4f90-45a8-872e-63f7cf5b49c4",
  "document_id": "1de4f6a1f61b49a08868b11d24db517d",
  "source": "upload",
  "source_location": "uploads/index.md",
  "content_hash": "71ff7532f09f455b9fcd2d9b62f9f80b3ce8918ddd4782db0532ea777f2880c1",
  "captured_at": "2024-06-03T22:19:05.104163+00:00",
  "extra": {
    "filename": "index.md"
  }
}
```

This ensures complete traceability and prevents cross-workspace data leakage.

## Querying Across Workspaces

To query a specific workspace's documents via OpenSearch:

```bash
# Query workspace "product-a"
curl -s "http://localhost:9200/ask_certus_product_a/_search" \
  -H 'Content-Type: application/json' \
  -d '{"query": {"match_all": {}}, "size": 10}' | jq '.hits.hits'

# Query workspace "client-acme"
curl -s "http://localhost:9200/ask_certus_client_acme/_search" \
  -H 'Content-Type: application/json' \
  -d '{"query": {"match_all": {}}, "size": 10}' | jq '.hits.hits'
```

## Best Practices

### Naming Conventions

Use descriptive, URL-friendly workspace names:
- ✅ `product-docs`, `client-acme`, `research-2024`
- ❌ `Product Docs`, `Client@ACME`, `research 2024`

### Isolation Guarantees

- **Complete data separation** - No queries can cross workspaces
- **Metadata traceability** - Every document records its workspace_id
- **No configuration needed** - Workspaces are created on-demand
- **Scalable** - Add as many workspaces as needed

### Use Cases

1. **Multi-Product Documentation**
   - `product-mobile-app` for iOS/Android docs
   - `product-web-app` for web platform docs
   - `product-api` for API documentation

2. **Client-Specific Analysis**
   - `client-acme` for ACME Corp investigation
   - `client-globex` for Globex Corp investigation
   - Maintain strict data isolation per client

3. **Concurrent Research**
   - `research-2024-q1` for Q1 findings
   - `research-2024-q2` for Q2 findings
   - `research-archive` for historical data

4. **Development & Testing**
   - `dev-experiment-a` for prototyping
   - `staging-validation` for pre-production testing
   - `prod-live` for production data

## Troubleshooting

### Workspace not showing in dropdown?

The workspace dropdown fetches from OpenSearch with a 60-second cache. If your workspace doesn't appear:

1. Wait 60 seconds for the cache to refresh, or
2. Refresh the browser (F5)
3. Check that at least one document has been ingested into the workspace

### Accidentally mixing data?

If documents from different analysis are in the same workspace:

1. Create a new, correctly-named workspace
2. Re-ingest documents into the correct workspace
3. The old workspace data remains isolated (delete via OpenSearch if needed)

### Querying wrong workspace?

Always verify the `workspace_id` in your API calls. Compare:

```bash
# Correct: querying product-a
curl -X POST "http://localhost:8000/v1/product-a/ask" ...

# Wrong: this would query default workspace
curl -X POST "http://localhost:8000/v1/ask" ...
```

## Default Workspace

If no workspace is specified, the system uses `default`. This is useful for:
- Development and testing
- Single-use exploratory analysis
- Quick smoke tests

To explicitly use the default workspace:

```bash
curl -X POST "http://localhost:8000/v1/default/index/" \
  -F "uploaded_file=@document.pdf"
```
