#!/usr/bin/env bash
set -euo pipefail

API_BASE=${API_BASE:-http://localhost:8000}
HEALTH_ENDPOINT="${API_BASE%/}/v1/health"
S3_ENDPOINT=${S3_ENDPOINT:-http://localhost:4566}
RAW_BUCKET=${DATALAKE_RAW_BUCKET:-raw}
GOLDEN_BUCKET=${DATALAKE_GOLDEN_BUCKET:-golden}
WORKSPACE_ID=${WORKSPACE_ID:-product-acquisition-review}
OPENSEARCH_ENDPOINT=${OPENSEARCH_ENDPOINT:-http://localhost:9200}
NEO4J_HTTP=${NEO4J_HTTP:-http://localhost:7474}
NEO4J_USER=${NEO4J_USER:-neo4j}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-password}
NEO4J_SERVICE=${NEO4J_SERVICE:-neo4j}
AWS_PROFILE_ARGS=()

if [[ -n "${AWS_PROFILE:-}" ]]; then
  AWS_PROFILE_ARGS+=(--profile "$AWS_PROFILE")
fi

AWS_CLI=(aws "${AWS_PROFILE_ARGS[@]}" --endpoint-url "$S3_ENDPOINT")
CAPSTONE_PREFIXES=(
  "product-acquisition/frameworks"
  "product-acquisition/policies"
  "product-acquisition/privacy"
  "product-acquisition/security"
)
SERVICES=(opensearch localstack neo4j ask-certus-backend)

log() {
  printf '[capstone-preflight] %s\n' "$1"
}

fail() {
  printf '[capstone-preflight] ERROR: %s\n' "$1" >&2
  exit 1
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Command '$1' is required. Install it or add it to your PATH."
  fi
}

check_service() {
  local service=$1
  if ! docker compose ps "$service" >/dev/null 2>&1; then
    fail "docker compose could not find service '$service'. Did you run the command from the repo root?"
  fi
  if ! docker compose ps "$service" | grep -q "Up"; then
    fail "Service '$service' is not running. Start it via 'just up' or 'docker compose up -d $service'."
  fi
  log "✓ docker compose reports '$service' is running"
}

check_curl() {
  local url=$1
  local note=$2
  if ! curl -fsS "$url" >/dev/null; then
    fail "HTTP check failed for ${note} (${url}). Ensure the service is reachable."
  fi
  log "✓ ${note} reachable"
}

check_s3_prefix() {
  local prefix=$1
  local target="s3://${GOLDEN_BUCKET}/${prefix}"
  local output
  if ! output=$("${AWS_CLI[@]}" s3 ls "$target" --recursive 2>/dev/null); then
    fail "Unable to list ${target}. Ensure LocalStack is running and buckets exist."
  fi
  local count
  count=$(printf '%s\n' "$output" | grep -E '^[0-9]{4}-' | wc -l | tr -d ' ')
  if [[ -z "$count" || "$count" -eq 0 ]]; then
    fail "No files detected under ${target}. Run ./scripts/promote_product_acquisition.sh before ingesting."
  fi
  log "✓ ${target} contains ${count} files"
}

check_scripts_exist() {
  [[ -x scripts/promote_product_acquisition.sh ]] || fail "scripts/promote_product_acquisition.sh is missing or not executable."
  [[ -x scripts/load_security_into_neo4j.py ]] || fail "scripts/load_security_into_neo4j.py is missing or not executable."
  log "✓ Required helper scripts are present"
}

check_neo4j_cypher() {
  if ! docker compose exec -T "$NEO4J_SERVICE" cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" 'RETURN 1;' >/dev/null; then
    fail "Failed to run a Cypher query via docker compose exec ${NEO4J_SERVICE}. Verify credentials/services."
  fi
  log "✓ Neo4j bolt endpoint responded to test query"
}

check_port() {
  local host_port=$1
  local description=$2
  python3 - <<PY >/dev/null || fail "$description ($host_port) is not reachable from the host."
import socket
host, port = "$host_port".split(":")
sock = socket.socket()
try:
    sock.settimeout(2)
    sock.connect((host, int(port)))
finally:
    sock.close()
PY
  log "✓ ${description} reachable on ${host_port}"
}

main() {
  require_cmd curl
  require_cmd jq
  require_cmd docker
  require_cmd python3
  require_cmd aws

  log "Checking docker compose services..."
  for svc in "${SERVICES[@]}"; do
    check_service "$svc"
  done

  log "Verifying HTTP endpoints..."
  check_curl "$HEALTH_ENDPOINT" "FastAPI health endpoint"
  check_curl "${OPENSEARCH_ENDPOINT%/}/_cluster/health" "OpenSearch cluster health"
  check_curl "$NEO4J_HTTP" "Neo4j HTTP interface"

  log "Checking bolt/neo4j connectivity..."
  check_port "localhost:7687" "Neo4j Bolt port"
  check_neo4j_cypher

  log "Checking S3 bucket contents at ${S3_ENDPOINT}..."
  for prefix in "${CAPSTONE_PREFIXES[@]}"; do
    check_s3_prefix "$prefix"
  done

  check_scripts_exist

  log "Security Capstone preflight completed successfully for workspace '${WORKSPACE_ID}'."
  log "Next steps: run ./scripts/promote_product_acquisition.sh if needed and follow docs/learn/security-analyst-capstone.md"
}

main "$@"
