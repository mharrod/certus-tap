# Datalake Orchestration (LocalStack S3)

## Purpose
Document how Certus TAP stages content through the raw and golden S3 buckets (LocalStack by default), including promotion workflows, helper scripts, and how ingestion endpoints interact with each tier.

## Audience & Prerequisites
- Operators managing ingestion pipelines.
- Developers wiring new automation around raw/golden buckets or quarantine flows.
- Familiarity with LocalStack (`http://localhost:4566`), `.env` bucket settings, and the `datalake` routers in `certus_ask/routers/datalake.py`.

## Overview
- **Raw bucket** (`DATALAKE_RAW_BUCKET`, default `raw`) receives uploads from Streamlit, CLI helpers, and external integrations.
- **Golden bucket** (`DATALAKE_GOLDEN_BUCKET`, default `golden`) stores vetted content promoted via `/v1/datalake/preprocess*` endpoints or helper scripts.
- Ingestion endpoints (`/v1/{workspace}/index/s3`, `/v1/{workspace}/index/security/s3`) read from golden so only approved artifacts reach OpenSearch/Neo4j.
- Quarantine prefixes capture privacy violations until a human approves them.

## Key Concepts

### Bucket Layout

```
raw/
 ├─ active/            # Fresh uploads awaiting review/promotion
 ├─ quarantine/        # Files flagged by privacy scanner (PII)
 └─ approved/          # Optional holding area post-review

golden/
 ├─ scans/             # SARIF/SPDX artifacts (security workflows)
 ├─ frameworks/        # Security frameworks (capstone sample)
 ├─ policies/          # Policy documents
 └─ privacy/           # Privacy docs, templates, etc.
```

Prefix names are conventions used by helper scripts; customize as needed if you update automation.

### Settings & Environment Variables

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `DATALAKE_RAW_BUCKET` | `raw` | Raw ingest bucket |
| `DATALAKE_GOLDEN_BUCKET` | `golden` | Golden / trusted bucket |
| `S3_ENDPOINT_URL` | `http://localhost:4566` | LocalStack endpoint |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | `test` | Local credentials consumed by CLI helpers |

### Helper Scripts
- `./scripts/setup-security-search.sh` – Bootstraps buckets, uploads sample SARIF/SPDX, optionally promotes to golden and triggers ingestion.
- `samples/capstone/setup-capstone.sh` – Loads SARIF/SBOM into Neo4j and ensures OpenSearch indexes exist for the security analyst capstone.
- Streamlit workflows (Upload to Raw, Promote Raw → Golden, Batch Ingest) wrap `/v1/datalake/*` APIs.

## Workflows / Operations

1. **Upload to Raw**
   ```bash
   aws --endpoint-url=http://localhost:4566 s3 cp docs/plan.md s3://raw/active/plan.md
   ```

2. **Privacy Scan / Quarantine**
   - `/v1/{workspace}/index/` automatically quarantines files with PII.
   - Quarantined files land under `s3://raw/quarantine/…`.
   - Analysts review via Streamlit or CLI, then move to `approved/` or delete.

3. **Promote to Golden**
   ```bash
   curl -X POST http://localhost:8000/v1/datalake/preprocess \
     -H "Content-Type: application/json" \
     -d '{"bucket_name":"raw","key":"active/plan.md","target_bucket":"golden","target_prefix":"policies/"}'
   ```
   - Batch promotions use `/v1/datalake/preprocess/batch`.

4. **Ingest from Golden**
   ```bash
   curl -X POST "http://localhost:8000/v1/default/index/s3" \
     -H "Content-Type: application/json" \
     -d '{"bucket_name":"golden","prefix":"policies/"}'
   ```
   - Security scans use `/v1/{workspace}/index/security/s3` with `key":"scans/bandit.sarif"`.

5. **Cleanup**
   - `aws --endpoint-url=http://localhost:4566 s3 rm s3://raw --recursive`
   - `just cleanup` or `just destroy` to tear down containers and volumes.

## Configuration / Interfaces
- REST endpoints in `certus_ask/routers/datalake.py` implement upload, list, preprocess (promote), and ingest batch operations.
- Streamlit console uses boto3 + REST to interact with these buckets.
- LocalStack service defined in `docker-compose.yml` exposes S3-compatible endpoints; swap to real AWS by updating `.env` credentials and endpoint.

## Troubleshooting / Gotchas
- **Missing prefixes:** Promotion/insertion commands fail with `NoSuchKey` if the target prefix hasn’t been synced. Use `aws s3 ls` to confirm paths.
- **Quarantine stuck:** Files stay in `raw/quarantine` until moved manually—make sure privacy reviewers have a documented process.
- **Permission errors:** When targeting actual AWS, ensure IAM policies allow `s3:PutObject`, `s3:ListBucket`, `s3:CopyObject`.
- **Large batch ingest:** Batch endpoints stream one object at a time; monitor backend logs for any 500s and re-run only failed keys.

## Related Documents
- [Metadata Envelopes (API)](../api/metadata-envelopes.md)
- [Streamlit Operations Console](streamlit-console.md)
- [Security Analyst Capstone](../../learn/security-workflows/security-analyst-capstone.md)
- [Privacy Operations (Logging)](../logging/privacy-operations.md)
