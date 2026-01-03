#!/usr/bin/env bash
# Deploy Certus-Trust with production Sigstore integration
#
# Usage:
#   ./scripts/deploy-trust-production.sh [start|stop|rebuild|status|logs]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    # Check Docker Compose
    if ! command -v docker compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi

    # Check if certus-network exists
    if ! docker network ls | grep -q certus-network; then
        log_info "Creating certus-network..."
        docker network create certus-network
        log_success "Created certus-network"
    fi

    log_success "Prerequisites check passed"
}

start_infrastructure() {
    log_info "Starting infrastructure services..."

    cd "${PROJECT_ROOT}"

    # Start core infrastructure
    log_info "Starting core infrastructure (OpenSearch, LocalStack, Neo4j, VictoriaMetrics)..."
    docker compose -f certus_infrastructure/docker-compose.yml up -d

    # Wait a bit for services to initialize
    sleep 5

    # Start Sigstore infrastructure
    log_info "Starting Sigstore infrastructure (Rekor, Trillian, Fulcio)..."
    docker compose -f certus_infrastructure/docker-compose.sigstore.yml up -d

    log_success "Infrastructure services started"
}

wait_for_service() {
    local service_name=$1
    local url=$2
    local max_attempts=30
    local attempt=0

    log_info "Waiting for ${service_name} to be ready..."

    while [ $attempt -lt $max_attempts ]; do
        if curl -sf "${url}" > /dev/null 2>&1; then
            log_success "${service_name} is ready"
            return 0
        fi

        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done

    log_error "${service_name} failed to start after ${max_attempts} attempts"
    return 1
}

start_trust_service() {
    log_info "Starting Certus-Trust service in production mode..."

    cd "${PROJECT_ROOT}"

    # Check if Sigstore services are running
    wait_for_service "Rekor" "http://localhost:3001/api/v1/log" || exit 1

    # Start Trust service
    log_info "Building and starting Certus-Trust..."
    docker compose -f certus_trust/deploy/docker-compose.prod.yml up -d --build

    # Wait for Trust service
    wait_for_service "Certus-Trust" "http://localhost:8057/v1/health" || exit 1

    log_success "Certus-Trust service started in production mode"
}

show_status() {
    log_info "Service Status:"
    echo ""

    # Check infrastructure
    echo "Infrastructure Services:"
    docker compose -f certus_infrastructure/docker-compose.yml ps
    echo ""

    # Check Sigstore
    echo "Sigstore Services:"
    docker compose -f certus_infrastructure/docker-compose.sigstore.yml ps
    echo ""

    # Check Trust
    echo "Certus-Trust Service:"
    docker compose -f certus_trust/deploy/docker-compose.prod.yml ps
    echo ""

    # Check endpoints
    echo "Endpoint Health:"
    if curl -sf http://localhost:3001/api/v1/log > /dev/null 2>&1; then
        echo -e "  Rekor:         ${GREEN}✓${NC} http://localhost:3001"
    else
        echo -e "  Rekor:         ${RED}✗${NC} http://localhost:3001"
    fi

    if curl -sf http://localhost:5555/healthz > /dev/null 2>&1; then
        echo -e "  Fulcio:        ${GREEN}✓${NC} http://localhost:5555"
    else
        echo -e "  Fulcio:        ${RED}✗${NC} http://localhost:5555"
    fi

    if curl -sf http://localhost:8057/v1/health > /dev/null 2>&1; then
        echo -e "  Certus-Trust:  ${GREEN}✓${NC} http://localhost:8057"
    else
        echo -e "  Certus-Trust:  ${RED}✗${NC} http://localhost:8057"
    fi
}

show_logs() {
    local service=${1:-}

    cd "${PROJECT_ROOT}"

    if [ -z "$service" ]; then
        log_info "Showing Certus-Trust logs (Ctrl+C to exit)..."
        docker compose -f certus_trust/deploy/docker-compose.prod.yml logs -f
    else
        log_info "Showing logs for ${service}..."
        case $service in
            rekor)
                docker compose -f certus_infrastructure/docker-compose.sigstore.yml logs -f rekor
                ;;
            fulcio)
                docker compose -f certus_infrastructure/docker-compose.sigstore.yml logs -f fulcio
                ;;
            trust|certus-trust)
                docker compose -f certus_trust/deploy/docker-compose.prod.yml logs -f
                ;;
            *)
                log_error "Unknown service: ${service}"
                echo "Available services: rekor, fulcio, trust"
                exit 1
                ;;
        esac
    fi
}

stop_services() {
    log_info "Stopping services..."

    cd "${PROJECT_ROOT}"

    # Stop Trust service
    docker compose -f certus_trust/deploy/docker-compose.prod.yml down || true

    # Stop Sigstore
    docker compose -f certus_infrastructure/docker-compose.sigstore.yml down || true

    # Stop infrastructure
    docker compose -f certus_infrastructure/docker-compose.yml down || true

    log_success "Services stopped"
}

rebuild_services() {
    log_info "Rebuilding and restarting services..."

    stop_services

    cd "${PROJECT_ROOT}"

    # Rebuild Trust service
    docker compose -f certus_trust/deploy/docker-compose.prod.yml build --no-cache

    # Start everything again
    start_infrastructure
    start_trust_service

    log_success "Services rebuilt and restarted"
}

test_production() {
    log_info "Testing production Sigstore integration..."

    # Test signing
    log_info "Testing artifact signing..."
    SIGN_RESPONSE=$(curl -sf -X POST http://localhost:8057/v1/sign \
        -H "Content-Type: application/json" \
        -d '{
            "artifact": "sha256:abc123def456789",
            "artifact_type": "sbom",
            "subject": "test:v1.0.0"
        }' || echo "")

    if [ -n "$SIGN_RESPONSE" ]; then
        log_success "Signing test passed"

        # Extract entry_id
        ENTRY_ID=$(echo "$SIGN_RESPONSE" | jq -r '.entry_id' 2>/dev/null || echo "")

        if [ -n "$ENTRY_ID" ] && [ "$ENTRY_ID" != "null" ]; then
            log_success "Got Rekor entry ID: ${ENTRY_ID}"

            # Verify in Rekor
            log_info "Verifying entry in Rekor..."
            if curl -sf "http://localhost:3001/api/v1/log/entries/${ENTRY_ID}" > /dev/null; then
                log_success "Entry found in Rekor transparency log"
            else
                log_warn "Entry not found in Rekor (may be using mock mode)"
            fi
        fi
    else
        log_error "Signing test failed"
    fi

    echo ""
    log_info "Production test complete"
}

# Main command handler
case "${1:-start}" in
    start)
        check_prerequisites
        start_infrastructure
        start_trust_service
        show_status
        echo ""
        log_success "Certus-Trust production deployment complete!"
        echo ""
        echo "Next steps:"
        echo "  1. View status:  ./scripts/deploy-trust-production.sh status"
        echo "  2. View logs:    ./scripts/deploy-trust-production.sh logs"
        echo "  3. Test signing: ./scripts/deploy-trust-production.sh test"
        echo "  4. API docs:     http://localhost:8057/docs"
        ;;

    stop)
        stop_services
        ;;

    rebuild)
        rebuild_services
        ;;

    status)
        show_status
        ;;

    logs)
        show_logs "${2:-}"
        ;;

    test)
        test_production
        ;;

    *)
        echo "Usage: $0 {start|stop|rebuild|status|logs [service]|test}"
        echo ""
        echo "Commands:"
        echo "  start    - Start all services (infrastructure + Sigstore + Trust)"
        echo "  stop     - Stop all services"
        echo "  rebuild  - Rebuild and restart all services"
        echo "  status   - Show service status and health"
        echo "  logs     - Show logs (optionally specify: rekor, fulcio, trust)"
        echo "  test     - Test production Sigstore integration"
        exit 1
        ;;
esac
