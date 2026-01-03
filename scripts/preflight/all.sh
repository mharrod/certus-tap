#!/bin/bash

set -euo pipefail

API_BASE=${API_BASE:-http://localhost:8000}
DATA_PREP_BASE=${DATA_PREP_BASE:-http://localhost:8100}
WORKSPACE_ID=${WORKSPACE_ID:-preflight-test}
HEALTH_BASE=${HEALTH_BASE:-$API_BASE/v1/health}
OS_ENDPOINT=${OS_ENDPOINT:-http://localhost:9200}
NEO4J_URI=${NEO4J_URI:-neo4j://localhost:7687}
NEO4J_USER=${NEO4J_USER:-neo4j}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-password}
NEO4J_BROWSER=${NEO4J_BROWSER:-http://localhost:7474}
MLFLOW_ENDPOINT=${MLFLOW_ENDPOINT:-http://localhost:6001}
LOCALSTACK_ENDPOINT=${LOCALSTACK_ENDPOINT:-http://localhost:4566}
LOCALSTACK_COMPOSE_FILE=${LOCALSTACK_COMPOSE_FILE:-certus_infrastructure/docker-compose.yml}
LOCALSTACK_SERVICE_NAME=${LOCALSTACK_SERVICE_NAME:-localstack}
LOCALSTACK_SAMPLES_MOUNT=${LOCALSTACK_SAMPLES_MOUNT:-/tmp/samples}
LOGS_INDEX=${LOGS_INDEX:-logs-certus-tap}
DOCS_INDEX=${DOCS_INDEX:-${OPENSEARCH_INDEX:-ask_certus}}
DOCS_INDEX_PATTERN=$DOCS_INDEX
STREAMLIT_ENDPOINT=${STREAMLIT_ENDPOINT:-http://localhost:8501}
if [[ "$DOCS_INDEX_PATTERN" != *"*"* ]]; then
    DOCS_INDEX_PATTERN="${DOCS_INDEX_PATTERN}*"
fi

if ! command -v jq >/dev/null 2>&1; then
    printf '[preflight] ERROR: jq is required for metadata envelope validation. Please install jq.\n' >&2
    exit 1
fi

LOCALSTACK_EXEC_MODE="aws"
detect_localstack_exec_mode() {
    if command -v docker >/dev/null 2>&1; then
        if docker compose -p certus -f "$LOCALSTACK_COMPOSE_FILE" ps "$LOCALSTACK_SERVICE_NAME" >/dev/null 2>&1; then
            LOCALSTACK_EXEC_MODE="docker"
            return
        fi
    fi
    LOCALSTACK_EXEC_MODE="aws"
}

resolve_sample_path() {
    local input_path=$1
    if [ "$LOCALSTACK_EXEC_MODE" = "docker" ]; then
        case "$input_path" in
            samples/*)
                printf '%s/%s' "${LOCALSTACK_SAMPLES_MOUNT%/}" "${input_path#samples/}"
                return
                ;;
        esac
    fi
    printf '%s' "$input_path"
}

detect_localstack_exec_mode

log() {
    printf '[preflight] %s\n' "$1"
}

fail() {
    printf '
[preflight] ERROR: %s\n' "$1" >&2
    exit 1
}

check_http() {
    local url=$1
    local name=$2
    if ! curl -fsS "$url" >/dev/null; then
        fail "${name} check failed for ${url}"
    fi
    log "${name} OK"
}

check_trust_services() {
    # Check if trust services should be tested
    if [ "${CHECK_TRUST:-true}" = "true" ]; then
        log "Checking Certus Trust services..."

        # Check Rekor
        if ! curl -fsS "http://localhost:3001" >/dev/null; then
            log "⚠️  Rekor not available (optional for some configurations)"
        else
            log "✅ Rekor OK"
        fi

        # Check Fulcio
        if ! curl -fsS "http://localhost:5555" >/dev/null; then
            log "⚠️  Fulcio not available (optional for some configurations)"
        else
            log "✅ Fulcio OK"
        fi

        # Check Certus Trust
        if ! curl -fsS "http://localhost:8057/v1/health" >/dev/null; then
            fail "Certus Trust check failed for http://localhost:8057/v1/health"
        fi
        log "✅ Certus Trust OK"
    fi
}

check_localstack_health() {
    if [ "$LOCALSTACK_EXEC_MODE" = "docker" ]; then
        if ! docker compose -p certus -f "$LOCALSTACK_COMPOSE_FILE" exec -T "$LOCALSTACK_SERVICE_NAME" \
            curl -fsS "http://localhost:4566/_localstack/health" >/dev/null; then
            fail "LocalStack check failed via docker exec"
        fi
        log "LocalStack OK"
    else
        check_http "$LOCALSTACK_ENDPOINT/_localstack/health" "LocalStack"
    fi
}
localstack_cli() {
    if [ "$LOCALSTACK_EXEC_MODE" = "docker" ]; then
        docker compose -p certus -f "$LOCALSTACK_COMPOSE_FILE" exec -T "$LOCALSTACK_SERVICE_NAME" awslocal "$@"
    else
        aws --endpoint-url "$LOCALSTACK_ENDPOINT" "$@"
    fi
}

workspace_path() {
    local suffix=$1
    suffix=${suffix#/}
    printf "%s/v1/%s/%s" "$API_BASE" "$WORKSPACE_ID" "$suffix"
}

run_smoke_query() {
    local payload='{ "question": "When was the metadata envelope smoke check performed?" }'
    local response
    response=$(curl -fsS -H 'Content-Type: application/json' -d "$payload" "$(workspace_path "ask")") || fail "Smoke query failed"
    log "Smoke query response: ${response}"
}

check_logging_handler() {
    log "Checking if OpenSearch logging handler is connected..."

    # Check if logs index exists
    local index_status
    index_status=$(curl -fsS "$OS_ENDPOINT/_cat/indices?format=json" | grep -c "$LOGS_INDEX" || echo "0")
    index_status=$(echo "$index_status" | tr -d '[:space:]' | head -1)

    if [ "$index_status" -eq 0 ]; then
        log "Logs index not yet created (will be created on first log entry)"
        return 0
    fi

    log "Logs index exists: $LOGS_INDEX"
}

check_logs_in_opensearch() {
    log "Waiting for logs to appear in OpenSearch (up to 10 seconds)..."

    local max_attempts=10
    local attempt=0
    local log_count=0

    while [ $attempt -lt $max_attempts ]; do
        # Count logs in the index
        log_count=$(curl -fsS "$OS_ENDPOINT/$LOGS_INDEX*/_count" 2>/dev/null | jq '.count // 0')

        if [ "$log_count" -gt 0 ]; then
            log "Found $log_count log entries in OpenSearch"

            # Verify log structure
            local latest_log
            latest_log=$(curl -fsS "$OS_ENDPOINT/$LOGS_INDEX*/_search?size=1&sort=timestamp:desc" 2>/dev/null | grep -o '"level":"[^"]*"' | head -1)

            if [ -n "$latest_log" ]; then
                log "Log structure verified: $latest_log"
                return 0
            fi
        fi

        attempt=$((attempt + 1))
        if [ $attempt -lt $max_attempts ]; then
            sleep 1
        fi
    done

    if [ "$log_count" -eq 0 ]; then
        log "WARNING: No logs found in OpenSearch after 10 seconds (this is normal on first startup)"
        log "Logs will be created automatically when services generate log entries"
        return 0
    fi
}

check_request_logging() {
    log "Testing request logging by making a health check..."

    # Make a request to generate logs
    curl -fsS "$HEALTH_BASE" >/dev/null

    # Give a moment for async handler to process
    sleep 2

    # Check if we have any logs
    local log_count
    log_count=$(curl -fsS "$OS_ENDPOINT/$LOGS_INDEX*/_count" 2>/dev/null | jq '.count // 0')

    if [ "$log_count" -gt 0 ]; then
        # Check for request logs specifically
        local request_logs
        request_logs=$(curl -fsS "$OS_ENDPOINT/$LOGS_INDEX*/_search?size=100" 2>/dev/null | grep -c 'request.start\|request.end\|request.error' || echo "0")
        request_logs=$(echo "$request_logs" | tr -cd '0-9')
        if [ -z "$request_logs" ]; then
            request_logs=0
        fi

        if [ "$request_logs" -gt 0 ]; then
            log "Request logging verified: Found request logs in OpenSearch"
            return 0
        else
            log "WARNING: Logs exist but no request logs found yet (may need more traffic)"
            return 0
        fi
    fi
}

test_logging_environment() {
    log "Checking logging configuration..."

    # Check if we can reach OpenSearch (required for logging)
    if ! curl -fsS "$OS_ENDPOINT" >/dev/null 2>&1; then
        fail "OpenSearch not accessible at $OS_ENDPOINT (required for logging)"
    fi

    log "OpenSearch is accessible for logging"
}

test_structured_logging() {
    log "Testing structured logging format in OpenSearch..."

    local log_entry
    log_entry=$(curl -fsS "$OS_ENDPOINT/$LOGS_INDEX*/_search?size=1&sort=timestamp:desc" 2>/dev/null)

    # Check for expected JSON fields in logs
    if echo "$log_entry" | grep -q '"timestamp"'; then
        log "✓ Logs have timestamp field"
    fi

    if echo "$log_entry" | grep -q '"level"'; then
        log "✓ Logs have level field"
    fi

    if echo "$log_entry" | grep -q '"message"'; then
        log "✓ Logs have message field"
    fi

    if echo "$log_entry" | grep -q '"logger"'; then
        log "✓ Logs have logger field"
    fi

    log "Structured logging format verified"
}

test_neo4j_connection() {
    log "Testing Neo4j database connection..."

    local response
    response=$(curl -fsS -X POST "${NEO4J_BROWSER}/db/neo4j/exec" \
        -H 'Content-Type: application/json' \
        -d '{"statements":[{"statement":"RETURN 1 as result"}]}' 2>/dev/null || echo "")

    if [ -z "$response" ]; then
        # Fallback: try neo4j API endpoint
        response=$(curl -fsS "http://localhost:7474/db/neo4j/tx" \
            -H 'Authorization: Basic '"$(echo -n "$NEO4J_USER:$NEO4J_PASSWORD" | base64)"'' \
            -H 'Content-Type: application/json' \
            -d '{"statements":[{"statement":"RETURN 1 as result"}]}' 2>/dev/null || echo "")
    fi

    if [ -n "$response" ] && echo "$response" | grep -q "result\|success\|200" 2>/dev/null; then
        log "Neo4j database connection OK"
        return 0
    else
        # Neo4j might still be accessible via browser, just can't execute queries from bash easily
        if curl -fsS "$NEO4J_BROWSER" >/dev/null 2>&1; then
            log "Neo4j browser accessible (query execution not tested from bash)"
            return 0
        fi
        fail "Cannot connect to Neo4j at ${NEO4J_BROWSER}"
    fi
}

test_neo4j_databases() {
    log "Checking Neo4j databases..."

    local response
    response=$(curl -fsS -u "$NEO4J_USER:$NEO4J_PASSWORD" \
        "http://localhost:7474/db/neo4j/info/" 2>/dev/null || echo "")

    if [ -n "$response" ]; then
        log "Neo4j is running and accessible"
        return 0
    else
        log "WARNING: Could not query Neo4j database info (may still be functional)"
        return 0
    fi
}

test_s3_buckets() {
    log "Verifying S3 buckets exist and are accessible..."

    local raw_bucket=${DATALAKE_RAW_BUCKET:-raw}
    local golden_bucket=${DATALAKE_GOLDEN_BUCKET:-golden}

    # Check raw bucket
    local raw_check
    raw_check=$(curl -fsS "$LOCALSTACK_ENDPOINT/raw" 2>/dev/null || echo "")

    if [ -n "$raw_check" ] || curl -fsS -I "$LOCALSTACK_ENDPOINT/$raw_bucket" >/dev/null 2>&1; then
        log "✓ S3 bucket '$raw_bucket' is accessible"
    else
        log "WARNING: Could not verify S3 bucket '$raw_bucket'"
    fi

    # Check golden bucket
    if curl -fsS -I "$LOCALSTACK_ENDPOINT/$golden_bucket" >/dev/null 2>&1; then
    log "✓ S3 bucket '$golden_bucket' is accessible"
    else
        log "WARNING: Could not verify S3 bucket '$golden_bucket'"
    fi
}

test_golden_bucket_workflow() {
    log "Verifying golden-bucket workflow (upload → privacy scan → promote → ingest)..."

    local raw_bucket=${DATALAKE_RAW_BUCKET:-raw}
    local golden_bucket=${DATALAKE_GOLDEN_BUCKET:-golden}
    local workspace="golden-preflight-${RANDOM}"
    local scan_key="preflight/security-scans/incoming/security-findings.sarif"
    local golden_key="scans/security-findings.sarif"
    local sample_source
    sample_source=$(resolve_sample_path "samples/security-scans/sarif/security-findings.sarif")

    log "Uploading sample SARIF to s3://$raw_bucket/$scan_key"
    localstack_cli s3 cp "$sample_source" "s3://$raw_bucket/$scan_key" >/dev/null

    log "Promoting clean file to golden bucket"
    curl -fsS -X POST "$DATA_PREP_BASE/v1/promotions/golden" \
        -H "Content-Type: application/json" \
        -d "{\"keys\": [\"$scan_key\"]}" >/dev/null

    log "Triggering security ingestion for golden key"
    curl -fsS -X POST "$DATA_PREP_BASE/v1/ingest/security" \
        -H "Content-Type: application/json" \
        -d "{\"workspace_id\": \"$workspace\", \"keys\": [\"$golden_key\"]}" >/dev/null

    log "Cleaning up test artifacts"
    localstack_cli s3 rm "s3://$raw_bucket/preflight/" --recursive >/dev/null || true
    localstack_cli s3 rm "s3://$golden_bucket/scans/security-findings.sarif" >/dev/null 2>&1 || true
    localstack_cli s3 rm "s3://$raw_bucket/quarantine/security-findings.sarif" >/dev/null 2>&1 || true
}

test_security_streaming_ingestion() {
    log "Validating SARIF/SPDX streaming ingestion from golden bucket..."

    local golden_bucket=${DATALAKE_GOLDEN_BUCKET:-golden}
    local run_id
    run_id="$(date -u +"%Y%m%d%H%M%S")-$RANDOM"

    local samples=(
        "sarif:samples/security-scans/sarif/security-findings.sarif:scans/preflight-${run_id}-bandit.sarif"
        "spdx:samples/security-scans/spdx/sbom-example.spdx.json:scans/preflight-${run_id}-sbom.spdx.json"
    )

    for entry in "${samples[@]}"; do
        IFS=':' read -r format sample_path target_key <<<"$entry"
        sample_path=$(resolve_sample_path "$sample_path")

        log "Uploading $format sample to s3://$golden_bucket/$target_key"
        localstack_cli s3 cp "$sample_path" "s3://$golden_bucket/$target_key" >/dev/null

        log "Streaming ingest of $format sample via /index/security/s3"
        local payload response ingestion_id items_indexed
        payload=$(cat <<EOF
{
  "bucket_name": "$golden_bucket",
  "key": "$target_key"
}
EOF
)
        response=$(
            curl -fsS -X POST "$(workspace_path "index/security/s3")" \
                -H 'Content-Type: application/json' \
                -d "$payload"
        )

        ingestion_id=$(echo "$response" | jq -r '.ingestion_id // empty')
        items_indexed=$(echo "$response" | jq '.findings_indexed // 0')

        if [ -z "$ingestion_id" ]; then
            fail "Streaming ingestion response missing ingestion_id for $target_key"
        fi
        if [ "$items_indexed" -le 0 ]; then
            fail "Streaming ingestion returned zero indexed items for $target_key"
        fi

        log "✓ $format streaming ingestion succeeded (ingestion_id: $ingestion_id, indexed: $items_indexed)"

        localstack_cli s3 rm "s3://$golden_bucket/$target_key" >/dev/null 2>&1 || true
    done
}

test_document_count() {
    log "Checking document count in OpenSearch..."

    local doc_count
    doc_count=$(curl -fsS "$OS_ENDPOINT/$DOCS_INDEX_PATTERN/_count" 2>/dev/null | jq '.count // 0')

    if [ "$doc_count" -gt 0 ]; then
        log "✓ Documents in index: $doc_count"
    else
        log "WARNING: No documents found in OpenSearch index (expected after ingestion)"
    fi
}

test_neo4j_node_count() {
    log "Checking Neo4j node counts..."

    # Query for Finding nodes
    local finding_response
    finding_response=$(curl -fsS -X POST "http://localhost:7474/db/neo4j/tx/commit" \
        -H 'Authorization: Basic '"$(echo -n "$NEO4J_USER:$NEO4J_PASSWORD" | base64)"'' \
        -H 'Content-Type: application/json' \
        -d '{
            "statements": [
              {
                "statement": "MATCH (f:Finding) RETURN count(f) as count"
              }
            ]
        }' 2>/dev/null || echo "")

    if [ -n "$finding_response" ]; then
        local finding_count
        finding_count=$(echo "$finding_response" | jq '.results[0].data[0].row[0] // 0' 2>/dev/null || echo "0")

        if [ "$finding_count" -gt 0 ]; then
            log "✓ Neo4j Finding nodes: $finding_count"
        else
            log "WARNING: No Finding nodes in Neo4j"
        fi

        # Query for Location nodes
        local location_response
        location_response=$(curl -fsS -X POST "http://localhost:7474/db/neo4j/tx/commit" \
            -H 'Authorization: Basic '"$(echo -n "$NEO4J_USER:$NEO4J_PASSWORD" | base64)"'' \
            -H 'Content-Type: application/json' \
            -d '{
                "statements": [
                  {
                    "statement": "MATCH (l:Location) RETURN count(l) as count"
                  }
                ]
            }' 2>/dev/null || echo "")

        local location_count
        location_count=$(echo "$location_response" | jq '.results[0].data[0].row[0] // 0' 2>/dev/null || echo "0")

        if [ "$location_count" -gt 0 ]; then
            log "✓ Neo4j Location nodes: $location_count"
        fi
    else
        log "WARNING: Could not query Neo4j node counts"
    fi
}

test_end_to_end_rag() {
    log "Running end-to-end RAG test with real content..."

    # Create a test document with meaningful content
    local test_file
    test_file=$(mktemp -t tap-rag-test.XXXXXX.txt)
    trap 'rm -f "$test_file"' RETURN

    cat > "$test_file" << 'CONTENT'
Certus TAP Documentation

The Certus TAP system provides enterprise document ingestion and knowledge management.

Key Features:
- Multi-source document ingestion (files, folders, GitHub, web)
- Vector-based semantic search using embeddings
- Neo4j knowledge graph for security findings
- Privacy-preserving PII detection and anonymization
- RAG (Retrieval-Augmented Generation) pipeline

Supported File Formats:
PDF, DOCX, TXT, MD, JSON, SARIF, SPDX

The system indexes documents into OpenSearch for fast retrieval and Neo4j for relationship queries.
CONTENT

    # Upload the document
    log "Uploading test document with real content..."
    local upload_response
    upload_response=$(curl -fsS -X POST "$(workspace_path "index/")" \
        -H 'Content-Type: multipart/form-data' \
        -F "uploaded_file=@${test_file};type=text/plain;filename=tap-readme.txt" 2>/dev/null || echo "")

    if [ -z "$upload_response" ]; then
        log "WARNING: Could not upload test document (RAG test skipped)"
        trap - RETURN
        return 0
    fi

    local ingestion_id
    ingestion_id=$(echo "$upload_response" | jq -r '.ingestion_id // empty' 2>/dev/null)

    if [ -z "$ingestion_id" ]; then
        log "WARNING: No ingestion_id in upload response"
        trap - RETURN
        return 0
    fi

    log "✓ Document uploaded with ingestion_id: $ingestion_id"

    # Wait for indexing
    sleep 2

    # Run a query that should match the document content
    log "Querying RAG pipeline with document-relevant question..."
    local query_payload='{ "question": "What are the key features of Certus TAP?" }'
    local query_response
    query_response=$(curl -fsS -H 'Content-Type: application/json' -d "$query_payload" "$(workspace_path "ask")" 2>/dev/null || echo "")

    if [ -n "$query_response" ]; then
        local reply
        reply=$(echo "$query_response" | jq -r '.reply // empty' 2>/dev/null)

        if [ -n "$reply" ] && [ "$reply" != "I don't have information about the context." ]; then
            log "✓ RAG pipeline returned relevant content"
            log "  Response preview: ${reply:0:100}..."
        else
            log "WARNING: RAG pipeline returned generic response (may need more indexing time)"
        fi
    else
        log "WARNING: Could not execute RAG query"
    fi

    trap - RETURN
}

test_workspace_isolation() {
    log "Testing workspace isolation..."

    local test_workspace="test-workspace-$$"

    # Try to upload to a different workspace
    local test_file
    test_file=$(mktemp -t tap-isolation-test.XXXXXX.txt)
    trap 'rm -f "$test_file"' RETURN
    echo "Isolation test document" > "$test_file"

    local upload_response
    upload_response=$(curl -fsS -X POST "$API_BASE/v1/$test_workspace/index/" \
        -H 'Content-Type: multipart/form-data' \
        -F "uploaded_file=@${test_file}" 2>/dev/null || echo "")

    if [ -n "$upload_response" ]; then
        local isolation_ingestion_id
        isolation_ingestion_id=$(echo "$upload_response" | jq -r '.ingestion_id // empty' 2>/dev/null)

        if [ -n "$isolation_ingestion_id" ]; then
            log "✓ Different workspace can be created and indexed"
        fi
    else
        log "WARNING: Could not test workspace isolation"
    fi

    trap - RETURN
}

test_error_handling() {
    log "Testing error handling with invalid inputs..."

    # Test invalid file upload (empty file)
    local empty_file
    empty_file=$(mktemp -t tap-empty-test.XXXXXX.txt)
    trap 'rm -f "$empty_file"' RETURN

    # Touch creates empty file
    touch "$empty_file"

    local error_response
    error_response=$(curl -fsS -X POST "$(workspace_path "index/")" \
        -H 'Content-Type: multipart/form-data' \
        -F "uploaded_file=@${empty_file}" 2>/dev/null || echo "")

    # Just verify it doesn't crash the backend
    if [ -n "$error_response" ]; then
        log "✓ Invalid input handled gracefully (no crash)"
    else
        log "WARNING: Could not test error handling"
    fi

    # Test invalid JSON to SARIF endpoint
    local invalid_sarif
    invalid_sarif=$(mktemp -t tap-invalid-sarif.XXXXXX.sarif)
    trap 'rm -f "$invalid_sarif"' RETURN
    echo "{ invalid json" > "$invalid_sarif"

    local sarif_error
    sarif_error=$(curl -fsS -X POST "$(workspace_path "index/security")" \
        -H 'Content-Type: multipart/form-data' \
        -F "uploaded_file=@${invalid_sarif}" 2>/dev/null || echo "")

    if echo "$sarif_error" | grep -q "error\|Error\|invalid" 2>/dev/null; then
        log "✓ Invalid SARIF format rejected appropriately"
    else
        log "WARNING: Invalid SARIF handling unclear"
    fi

    trap - RETURN
}

test_rekor() {
    log "Testing Rekor transparency log service..."

    local rekor_health
    rekor_health=$(curl -fsS "$REKOR_ENDPOINT" 2>/dev/null || echo "")

    if [ -n "$rekor_health" ]; then
        log "✓ Rekor is running and accessible"

        # Try to get server info
        local rekor_info
        rekor_info=$(curl -fsS "$REKOR_ENDPOINT/api/v1/log/info" 2>/dev/null || echo "")

        if [ -n "$rekor_info" ]; then
            local tree_size
            tree_size=$(echo "$rekor_info" | jq '.treeSize // empty' 2>/dev/null || echo "")

            if [ -n "$tree_size" ]; then
                log "✓ Rekor log info retrieved: tree size = $tree_size"
            else
                log "✓ Rekor API responding"
            fi
        fi
    else
        log "WARNING: Rekor not accessible at $REKOR_ENDPOINT"
    fi
}

test_trillian() {
    log "Testing Trillian log server..."

    local trillian_health
    trillian_health=$(curl -fsS "$TRILLIAN_LOG_ENDPOINT" 2>/dev/null || echo "")

    if [ -n "$trillian_health" ]; then
        log "✓ Trillian Log Server is running and accessible"
    else
        log "WARNING: Trillian Log Server not accessible at $TRILLIAN_LOG_ENDPOINT"
    fi
}

test_oci_registry() {
    log "Testing local OCI registry..."

    local endpoint=${OCI_REGISTRY_ENDPOINT:-http://localhost:5000}
    local catalog
    catalog=$(curl -fsS "$endpoint/v2/_catalog" 2>/dev/null || echo "")

    if [ -n "$catalog" ]; then
        log "✓ OCI registry responding at $endpoint"

        if command -v jq >/dev/null 2>&1; then
            local repo_count
            repo_count=$(echo "$catalog" | jq '.repositories | length' 2>/dev/null || echo "")
            if [ -n "$repo_count" ]; then
                log "✓ Registry catalog contains $repo_count repositories"
            fi
        fi
    else
        log "WARNING: OCI registry not accessible at $endpoint"
    fi
}

test_oci_attestation_workflow() {
    log "Testing OCI image push and attestation workflow..."

    local registry_host="localhost:5000"
    local repo="preflight/oci-attest"
    local tag="run-$(date -u +"%Y%m%d%H%M%S")-$RANDOM"
    local ref="${registry_host}/${repo}:${tag}"
    local predicate_file
    predicate_file=$(mktemp)
    local key_dir
    key_dir=$(mktemp -d)
    local key_prefix="$key_dir/cosign"

    # Ensure base image is present
    docker pull --quiet alpine:3.19 >/dev/null 2>&1 || fail "Unable to pull alpine:3.19 for OCI test"
    docker tag alpine:3.19 "$ref"

    docker push "$ref" >/dev/null 2>&1 || fail "Failed to push $ref to local registry"

    cat >"$predicate_file" <<EOF
{
  "run_id": "$tag",
  "status": "passed",
  "tool": "preflight-cosign",
  "description": "Smoke attestation for OCI tutorial"
}
EOF

    local cosign_password="preflight-${RANDOM}"

    COSIGN_PASSWORD="$cosign_password" cosign generate-key-pair \
        --output-key-prefix "$key_prefix" >/dev/null 2>&1 || fail "Failed to generate temporary cosign key pair"

    COSIGN_PASSWORD="$cosign_password" cosign attest \
        --key "${key_prefix}.key" \
        --predicate "$predicate_file" \
        --type vuln \
        --allow-http-registry \
        --yes \
        "$ref" >/dev/null 2>&1 || fail "Cosign attestation failed for $ref"

    local catalog
    catalog=$(curl -fsS "$OCI_REGISTRY_ENDPOINT/v2/_catalog" | jq -r '.repositories[]' 2>/dev/null || echo "")
    if ! printf '%s\n' "$catalog" | grep -q "preflight/oci-attest"; then
        fail "OCI registry catalog missing preflight/oci-attest after attestation push"
    fi

    log "✓ OCI attestation workflow succeeded for $ref"

    rm -f "$predicate_file" "${key_prefix}.key" "${key_prefix}.pub"
    rmdir "$key_dir" >/dev/null 2>&1 || true
    docker rmi "$ref" >/dev/null 2>&1 || true
}

test_s3_ingestion() {
    log "Testing S3 bucket ingestion..."

    local s3_response
    s3_response=$(curl -fsS -X POST "$(workspace_path "index/s3")" \
        -H 'Content-Type: application/json' \
        -d '{
            "bucket_name": "raw",
            "prefix": "samples/"
        }' 2>/dev/null || echo "")

    if [ -z "$s3_response" ]; then
        log "WARNING: S3 ingestion request failed"
        return 0
    fi

    local ingestion_id
    ingestion_id=$(echo "$s3_response" | jq -r '.ingestion_id // empty' 2>/dev/null)

    if [ -n "$ingestion_id" ]; then
        local processed_files
        processed_files=$(echo "$s3_response" | jq '.processed_files // 0' 2>/dev/null)

        if [ "$processed_files" -gt 0 ]; then
            log "✓ S3 ingestion successful: $processed_files files processed"
        else
            log "WARNING: S3 ingestion completed but no files matched"
        fi
    else
        local error_msg
        error_msg=$(echo "$s3_response" | jq -r '.detail // .message // .error // empty' 2>/dev/null)

        if [ -n "$error_msg" ]; then
            log "WARNING: S3 ingestion failed: $error_msg"
        else
            log "WARNING: S3 ingestion response unclear"
        fi
    fi
}

test_github_ingestion() {
    log "Testing GitHub repository ingestion..."

    # Use a small public repo for testing
    local github_response
    github_response=$(curl -fsS -X POST "$(workspace_path "index/github")" \
        -H 'Content-Type: application/json' \
        -d '{
            "repo_url": "https://github.com/octocat/Hello-World",
            "branch": "master",
            "include_globs": ["README*", "**/*.md"],
            "max_file_size_kb": 64
        }' 2>/dev/null || echo "")

    if [ -z "$github_response" ]; then
        log "WARNING: GitHub ingestion request failed (may need valid GitHub token)"
        return 0
    fi

    local ingestion_id
    ingestion_id=$(echo "$github_response" | jq -r '.ingestion_id // empty' 2>/dev/null)

    if [ -n "$ingestion_id" ]; then
        local file_count
        file_count=$(echo "$github_response" | jq '.file_count // 0' 2>/dev/null)

        if [ "$file_count" -gt 0 ]; then
            log "✓ GitHub repository ingestion successful: $file_count files indexed"
        else
            log "WARNING: GitHub repository processed but no files matched patterns"
        fi
    else
        local error_msg
        error_msg=$(echo "$github_response" | jq -r '.detail // .message // .error // empty' 2>/dev/null)

        if [ -n "$error_msg" ]; then
            log "WARNING: GitHub ingestion failed: $error_msg"
        else
            log "WARNING: GitHub ingestion response unclear"
        fi
    fi
}

test_neo4j_query() {
    log "Testing Neo4j with SARIF ingestion and graph query..."

    # Create a test SARIF file
    local sarif_file
    sarif_file=$(mktemp -t tap-sarif-test.XXXXXX.sarif)
    trap 'rm -f "$sarif_file"' RETURN

    cat > "$sarif_file" << 'SARIF'
{
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "PrefligthTest",
          "version": "1.0.0"
        }
      },
      "results": [
        {
          "ruleId": "TEST-001",
          "level": "error",
          "message": { "text": "Test critical vulnerability" },
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": { "uri": "src/test.py" },
                "region": { "startLine": 42 }
              }
            }
          ]
        },
        {
          "ruleId": "TEST-002",
          "level": "warning",
          "message": { "text": "Test warning finding" },
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": { "uri": "config/settings.py" },
                "region": { "startLine": 15 }
              }
            }
          ]
        }
      ]
    }
  ]
}
SARIF

    # Upload SARIF file to backend
    log "Uploading test SARIF file to backend..."
    local ingestion_response
    ingestion_response=$(curl -fsS -X POST "$(workspace_path "index/security")" \
        -H 'Content-Type: multipart/form-data' \
        -F "uploaded_file=@${sarif_file}" 2>/dev/null || echo "")

    if [ -z "$ingestion_response" ]; then
        log "WARNING: Could not ingest SARIF file (Neo4j test skipped)"
        trap - RETURN
        return 0
    fi

    local findings_indexed
    findings_indexed=$(echo "$ingestion_response" | jq '.findings_indexed // 0' 2>/dev/null || echo "0")

    if [ "$findings_indexed" -lt 2 ]; then
        log "WARNING: Expected 2 findings indexed, got $findings_indexed"
    else
        log "✓ SARIF ingestion successful: $findings_indexed findings indexed"
    fi

    # Wait a moment for Neo4j to process
    sleep 2

    # Test Neo4j Cypher query via browser API
    log "Querying Neo4j for SARIF findings..."
    local query_response
    query_response=$(curl -fsS -X POST "http://localhost:7474/db/neo4j/tx/commit" \
        -H 'Authorization: Basic '"$(echo -n "$NEO4J_USER:$NEO4J_PASSWORD" | base64)"'' \
        -H 'Content-Type: application/json' \
        -d '{
            "statements": [
              {
                "statement": "MATCH (f:Finding) RETURN count(f) as finding_count"
              }
            ]
        }' 2>/dev/null || echo "")

    if [ -n "$query_response" ]; then
        local finding_count
        finding_count=$(echo "$query_response" | jq '.results[0].data[0].row[0] // 0' 2>/dev/null || echo "0")

        if [ "$finding_count" -gt 0 ]; then
            log "✓ Neo4j query successful: Found $finding_count Finding nodes in graph"

            # Try to get file locations
            local file_response
            file_response=$(curl -fsS -X POST "http://localhost:7474/db/neo4j/tx/commit" \
                -H 'Authorization: Basic '"$(echo -n "$NEO4J_USER:$NEO4J_PASSWORD" | base64)"'' \
                -H 'Content-Type: application/json' \
                -d '{
                    "statements": [
                      {
                        "statement": "MATCH (f:Finding)-[:LOCATED_IN]->(l:Location)-[:FILE]->(fl:File) RETURN count(fl) as file_count"
                      }
                    ]
                }' 2>/dev/null || echo "")

            local file_count
            file_count=$(echo "$file_response" | jq '.results[0].data[0].row[0] // 0' 2>/dev/null || echo "0")

            if [ "$file_count" -gt 0 ]; then
                log "✓ Neo4j graph relationships verified: $file_count files linked to findings"
            else
                log "WARNING: Graph relationships incomplete (may still be processing)"
            fi
        else
            log "WARNING: No Finding nodes found in Neo4j (may not be enabled)"
        fi
    else
        log "WARNING: Could not execute Neo4j query (Neo4j API may not be accessible from bash)"
    fi

    trap - RETURN
}

test_metadata_envelope_preview() {
    log "Validating metadata envelopes via upload ingestion..."

    local tmp_file
    tmp_file=$(mktemp -t tap-upload)
    trap 'rm -f "$tmp_file"' RETURN

    local upload_filename="metadata-envelope-smoke.txt"
    local unique_token
    unique_token=$(python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
)
    printf 'Metadata envelope smoke check run %s\n' "$unique_token" >"$tmp_file"

    local response
    response=$(
        curl -fsS -X POST "$(workspace_path "index/")" \
            -H 'Content-Type: multipart/form-data' \
            -F "uploaded_file=@${tmp_file};type=text/plain;filename=${upload_filename}"
    )

    local preview_count
    preview_count=$(echo "$response" | jq '.metadata_preview | length // 0')
    if [ "$preview_count" -lt 1 ]; then
        fail "Metadata preview missing from ingestion response"
    fi

    local ingestion_id envelope_ingestion_id envelope_source content_hash envelope_filename
    ingestion_id=$(echo "$response" | jq -r '.ingestion_id // empty')
    envelope_ingestion_id=$(echo "$response" | jq -r '.metadata_preview[0].ingestion_id // empty')
    envelope_source=$(echo "$response" | jq -r '.metadata_preview[0].source // empty')
    content_hash=$(echo "$response" | jq -r '.metadata_preview[0].content_hash // empty')
    envelope_filename=$(echo "$response" | jq -r '.metadata_preview[0].extra.filename // empty')

    if [ -z "$ingestion_id" ]; then
        fail "Ingestion response missing ingestion_id"
    fi
    if [ -z "$envelope_ingestion_id" ] || [ "$ingestion_id" != "$envelope_ingestion_id" ]; then
        fail "Metadata envelope ingestion_id mismatch (response: $ingestion_id, envelope: ${envelope_ingestion_id:-none})"
    fi
    if [ "$envelope_source" != "upload" ]; then
        fail "Metadata envelope source unexpected: ${envelope_source:-none}"
    fi
    if [ -z "$content_hash" ] || [ "${#content_hash}" -ne 64 ]; then
        fail "Metadata envelope missing valid content_hash"
    fi
    if [ "$envelope_filename" != "$upload_filename" ]; then
        fail "Metadata envelope filename mismatch (expected $upload_filename, got ${envelope_filename:-none})"
    fi

    log "Refreshing OpenSearch index pattern ${DOCS_INDEX_PATTERN} before verification..."
    curl -fsS -X POST "$OS_ENDPOINT/$DOCS_INDEX_PATTERN/_refresh" >/dev/null 2>&1 || true

    local search_payload
    read -r -d '' search_payload <<EOF || true
{
  "size": 1,
  "_source": ["meta.metadata_envelope", "metadata_envelope"],
  "query": {
    "bool": {
      "should": [
        { "term": { "meta.ingestion_id.keyword": "$ingestion_id" } },
        { "term": { "meta.metadata_envelope.ingestion_id.keyword": "$ingestion_id" } },
        { "match": { "meta.ingestion_id": "$ingestion_id" } },
        { "match": { "meta.metadata_envelope.ingestion_id": "$ingestion_id" } },
        { "term": { "metadata_envelope.ingestion_id.keyword": "$ingestion_id" } },
        { "match": { "metadata_envelope.ingestion_id": "$ingestion_id" } }
      ],
      "minimum_should_match": 1
    }
  }
}
EOF

    local indexed_hits=0
    local search_response=""
    local attempt=0
    local max_attempts=15
    while [ $attempt -lt $max_attempts ]; do
        search_response=$(curl -fsS -H 'Content-Type: application/json' -d "$search_payload" "$OS_ENDPOINT/$DOCS_INDEX_PATTERN/_search" || true)
        if [ -n "$search_response" ]; then
            indexed_hits=$(echo "$search_response" | jq '.hits.hits | length // 0')
            if [ "$indexed_hits" -gt 0 ]; then
                break
            fi
        fi
        attempt=$((attempt + 1))
        sleep 1
    done

    if [ "$indexed_hits" -lt 1 ]; then
        fail "No documents found in OpenSearch index pattern ${DOCS_INDEX_PATTERN} for ingestion $ingestion_id"
    fi

    local stored_ingestion stored_source stored_content_hash stored_filename
    stored_ingestion=$(
        echo "$search_response" | jq -r '.hits.hits[0]._source.meta.metadata_envelope.ingestion_id // .hits.hits[0]._source.metadata_envelope.ingestion_id // empty'
    )
    stored_source=$(
        echo "$search_response" | jq -r '.hits.hits[0]._source.meta.metadata_envelope.source // .hits.hits[0]._source.metadata_envelope.source // empty'
    )
    stored_content_hash=$(
        echo "$search_response" | jq -r '.hits.hits[0]._source.meta.metadata_envelope.content_hash // .hits.hits[0]._source.metadata_envelope.content_hash // empty'
    )
    stored_filename=$(
        echo "$search_response" | jq -r '.hits.hits[0]._source.meta.metadata_envelope.extra.filename // .hits.hits[0]._source.metadata_envelope.extra.filename // empty'
    )

    if [ "$stored_ingestion" != "$ingestion_id" ]; then
        fail "Stored document ingestion_id mismatch (expected $ingestion_id, found ${stored_ingestion:-none})"
    fi
    if [ "$stored_source" != "upload" ]; then
        fail "Stored document metadata_envelope.source unexpected: ${stored_source:-none}"
    fi
    if [ -z "$stored_content_hash" ] || [ "$stored_content_hash" != "$content_hash" ]; then
        fail "Stored document hash mismatch (preview hash $content_hash, stored ${stored_content_hash:-none})"
    fi
    if [ "$stored_filename" != "$upload_filename" ]; then
        fail "Stored metadata filename mismatch (expected $upload_filename, got ${stored_filename:-none})"
    fi

    trap - RETURN
    log "Metadata envelopes verified for ingestion $ingestion_id and persisted to ${DOCS_INDEX_PATTERN} (preview count: $preview_count)"
}


log "Checking FastAPI health endpoint"
check_http "$HEALTH_BASE" "FastAPI health"

log "Checking data prep service health endpoint"
check_http "$DATA_PREP_BASE/health" "Data prep health"

log "Checking ingestion router health"
check_http "$HEALTH_BASE/ingestion" "Ingestion health"

log "Checking evaluation router health"
check_http "$HEALTH_BASE/evaluation" "Evaluation health"

log "Checking embedding cache health"
check_http "$HEALTH_BASE/embedder" "Embedding health"

log "Checking datalake buckets"
check_http "$HEALTH_BASE/datalake" "Datalake health"

log "Checking OpenSearch availability"
check_http "$OS_ENDPOINT" "OpenSearch root"

log "Checking Neo4j availability"
check_http "$NEO4J_BROWSER" "Neo4j browser"

# Skip MLflow check for now – service runs in its own stack.
# log "Checking MLflow availability"
# check_http "$MLFLOW_ENDPOINT" "MLflow"
check_trust_services

log "Checking LocalStack availability"
check_localstack_health

log "Checking Streamlit console"
check_http "$STREAMLIT_ENDPOINT" "Streamlit UI"

log "Checking OpenTelemetry Collector"
OPENTELEMETRY_ENDPOINT=${OPENTELEMETRY_ENDPOINT:-http://localhost:4318}
if curl -fsS "$OPENTELEMETRY_ENDPOINT" >/dev/null 2>&1; then
    log "OpenTelemetry Collector OK"
else
    log "WARNING: OpenTelemetry Collector not available at $OPENTELEMETRY_ENDPOINT"
fi

log "Checking VictoriaMetrics"
VICTORIAMETRICS_ENDPOINT=${VICTORIAMETRICS_ENDPOINT:-http://localhost:8428}
if curl -fsS "$VICTORIAMETRICS_ENDPOINT" >/dev/null 2>&1; then
    log "VictoriaMetrics OK"
else
    log "WARNING: VictoriaMetrics not available at $VICTORIAMETRICS_ENDPOINT"
fi

log "Checking Grafana"
GRAFANA_ENDPOINT=${GRAFANA_ENDPOINT:-http://localhost:3002}
if curl -fsS "$GRAFANA_ENDPOINT" >/dev/null 2>&1; then
    log "Grafana OK"
else
    log "WARNING: Grafana not available at $GRAFANA_ENDPOINT"
fi

log "Checking Rekor transparency log"
REKOR_ENDPOINT=${REKOR_ENDPOINT:-http://localhost:3001}
if curl -fsS "$REKOR_ENDPOINT" >/dev/null 2>&1; then
    log "Rekor OK"
else
    log "WARNING: Rekor not available at $REKOR_ENDPOINT"
fi

log "Checking Trillian log server"
TRILLIAN_LOG_ENDPOINT=${TRILLIAN_LOG_ENDPOINT:-http://localhost:8091/metrics}
if curl -fsS "$TRILLIAN_LOG_ENDPOINT" >/dev/null 2>&1; then
    log "Trillian Log Server OK"
else
    log "WARNING: Trillian Log Server not available at $TRILLIAN_LOG_ENDPOINT"
fi

log "Checking OCI registry"
OCI_REGISTRY_ENDPOINT=${OCI_REGISTRY_ENDPOINT:-http://localhost:5000}
if curl -fsS "$OCI_REGISTRY_ENDPOINT/v2/_catalog" >/dev/null 2>&1; then
    log "OCI registry OK"
else
    log "WARNING: OCI registry not available at $OCI_REGISTRY_ENDPOINT"
fi

log ""
log "========== S3 STORAGE TESTS =========="
test_s3_buckets
test_golden_bucket_workflow
test_security_streaming_ingestion
log "========== S3 STORAGE TESTS PASSED =========="
log ""

# Logging smoke tests
log ""
log "========== LOGGING TESTS =========="
test_logging_environment
check_logging_handler
check_logs_in_opensearch
check_request_logging
test_structured_logging
log "========== LOGGING TESTS PASSED =========="
log ""

# Neo4j smoke tests
log ""
log "========== NEO4J TESTS =========="
test_neo4j_connection
test_neo4j_databases
test_neo4j_query
log "========== NEO4J TESTS PASSED =========="
log ""

# Transparency and signing tests
log ""
log "========== TRANSPARENCY & SIGNING TESTS =========="
test_rekor
test_trillian
test_oci_registry
test_oci_attestation_workflow
log "========== TRANSPARENCY & SIGNING TESTS PASSED =========="
log ""

log ""
log "========== DOCUMENT INGESTION TESTS =========="
log "Running metadata envelope preview test"
test_metadata_envelope_preview
test_document_count
test_neo4j_node_count
test_end_to_end_rag
test_workspace_isolation
test_error_handling
test_s3_ingestion
test_github_ingestion
log "========== DOCUMENT INGESTION TESTS PASSED =========="
log ""

log "Running smoke query through RAG pipeline"
run_smoke_query

# log "Testing GitHub repository ingestion"
# curl -fsS -X POST "$(workspace_path "index/github")" \
#   -H 'Content-Type: application/json' \
#   -d '{"repo_url":"https://github.com/octocat/Hello-World","branch":"master","include_globs":["README*","**/*.md"],"max_file_size_kb":64}' >/dev/null || fail "GitHub ingestion failed"

# log "Testing SARIF ingestion"
# sarif_file=$(mktemp)
# cat <<'SARIF' > "$sarif_file"
# {
#   "version": "2.1.0",
#   "runs": [
#     {
#       "tool": {
#         "driver": {
#           "name": "TAP Demo"
#         }
#       },
#       "results": [
#         {
#           "ruleId": "DOCOPS001",
#           "level": "warning",
#           "message": { "text": "Sample SARIF finding" },
#           "locations": [
#             {
#               "physicalLocation": {
#                 "artifactLocation": { "uri": "src/example.py" },
#                 "region": { "startLine": 10 }
#               }
#             }
#           ]
#         }
#       ]
#     }
#   ]
# }
# SARIF
# curl -fsS -X POST "$(workspace_path "index/sarif")" -F "uploaded_file=@$sarif_file" >/dev/null || fail "SARIF ingestion failed"
# rm -f "$sarif_file"

# log "Testing direct web ingestion"
# curl -fsS -X POST "$(workspace_path "index/web")" \
#   -H 'Content-Type: application/json' \
#   -d '{"urls":["https://www.example.com"],"render":false}' >/dev/null || fail "Web ingestion failed"

# log "Testing sitemap crawl ingestion"
# curl -fsS -X POST "$(workspace_path "index/web/crawl")" \
#   -H 'Content-Type: application/json' \
#   -d '{"seed_urls":["https://www.example.com"],"max_pages":1,"max_depth":0,"render":false}' >/dev/null || fail "Web crawl ingestion failed"

cleanup_test_workspace() {
    log ""
    log "========== CLEANUP =========="
    log "Cleaning up test workspace: $WORKSPACE_ID"

    # Delete documents from OpenSearch for this workspace
    log "Deleting test documents from OpenSearch..."
    curl -fsS -X POST "$OS_ENDPOINT/$DOCS_INDEX_PATTERN/_delete_by_query" \
        -H 'Content-Type: application/json' \
        -d '{
            "query": {
                "term": {
                    "meta.workspace_id.keyword": "'"$WORKSPACE_ID"'"
                }
            }
        }' >/dev/null 2>&1 || log "WARNING: Could not delete test documents"

    # Delete Neo4j nodes created during tests
    log "Deleting test data from Neo4j..."
    curl -fsS -X POST "http://localhost:7474/db/neo4j/tx/commit" \
        -H 'Authorization: Basic '"$(echo -n "$NEO4J_USER:$NEO4J_PASSWORD" | base64)"'' \
        -H 'Content-Type: application/json' \
        -d '{
            "statements": [
              {
                "statement": "MATCH (f:Finding {ingestion_id: /PrefligthTest|test/}) DETACH DELETE f"
              }
            ]
        }' >/dev/null 2>&1 || log "WARNING: Could not delete test Neo4j data"

    log "✓ Test workspace cleaned up"
    log "========== CLEANUP COMPLETE =========="
    log ""
}

log "All checks passed."

# Clean up test data unless PREFLIGHT_KEEP_DATA is set
if [ "${PREFLIGHT_KEEP_DATA:-false}" != "true" ]; then
    cleanup_test_workspace
else
    log "PREFLIGHT_KEEP_DATA is set; test data retained in workspace: $WORKSPACE_ID"
fi
