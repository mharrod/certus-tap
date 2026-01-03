# Verifying Set-up

Run these checks after `just up` (or `./scripts/start-up.sh`) so you know every dependency is healthy before ingesting data. The quickest way to verify the setup is to run the preflight check. It will run through and test all the basic services

```bash
just preflight
```

## Manual checks

If you prefer, you can also do this manually.

### 1. LocalStack

Confirm the S3 emulator is reachable with dummy credentials:

```bash
aws s3 ls --endpoint-url=http://localhost:4566
```

The command should return at least the default buckets created by preflight runs (e.g., `tap-ingest`). If you receive `could not connect`, ensure Docker is running and revisit the AWS CLI configuration in `docs/installation/application.md`.

### 2. OpenSearch API

Visit [http://localhost:9200](http://localhost:9200) or use curl:

```bash
curl -s http://localhost:9200 | jq .
```

Expected snippet:

```json
{
  "name": "opensearch-node1",
  "cluster_name": "opensearch-cluster",
  "version": {
    "number": "2.17.1"
  },
  "tagline": "The OpenSearch Project: https://opensearch.org/"
}
```

If authentication is enabled in your environment, include `-u admin:admin`.

### 3. OpenSearch Dashboards

Navigate to [http://localhost:5601](http://localhost:5601) or query the status API:

```bash
curl -s http://localhost:5601/api/status | jq '.status.overall'
```

The status should be `"available"` (green). Errors here usually mean OpenSearch is still starting or the `opensearch-net` network is missing (`just up` recreates it automatically).

### 4. FastAPI backend

Check the root and health endpoints:

```bash
curl -s http://localhost:8000/ | jq .
curl -s http://localhost:8000/v1/health/rag | jq .
```

You can also open [http://localhost:8000/docs](http://localhost:8000/docs) for Swagger UI. If the service is down, inspect logs via `docker compose logs -f ask-certus-backend`.

### 5. MLflow UI

Open [http://localhost:5001](http://localhost:5001). You should see the MLflow tracking UI. If it fails to load, restart the stack (`just down && just up`) to ensure volumes were mounted correctly.
