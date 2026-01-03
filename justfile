# Certus TAP Justfile
# Development task automation for Certus Trust & Assurance Platform

default := "help"
set shell := ["bash", "-lc"]

# ============================================================================
# HELP & INFORMATION
# ============================================================================

## Show available recipes and their descriptions
help:
    @just --list

# ============================================================================
# SETUP & INSTALLATION
# ============================================================================

## Install virtual environment and pre-commit hooks
install:
    @echo "🚀 Creating virtual environment using uv"
    @uv sync
    @uv run pre-commit install

## Ensure the shared Docker network exists
ensure-network:
    @docker network inspect certus-network >/dev/null 2>&1 || docker network create certus-network

## Login to GitHub Container Registry using token from .env
docker-login:
    @./scripts/docker-login.sh

# ============================================================================
# CODE QUALITY & LINTING
# ============================================================================

## Run all code quality tools (linting, type checking, manifest validation)
check:
    @echo "🚀 Checking lock file consistency with 'pyproject.toml'"
    @uv lock --locked
    @echo "🚀 Linting code: Running pre-commit"
    @uv run pre-commit run -a
    @echo "🚀 Static type checking: Running mypy"
    @uv run mypy
    @echo "🚀 Checking for obsolete dependencies: Running deptry"
    # @uv run deptry src
    @just manifest-check

## Format and validate assurance manifests (runs during `just check`)
manifest-check:
    @echo "🧾 Formatting assurance manifests (cue fmt)"
    @cd dagger_modules/security/manifests && cue fmt ./...
    @echo "🛡️ Validating manifest examples (cue vet)"
    @cd dagger_modules/security/manifests && cue vet ./examples/python-light.cue
    @cd dagger_modules/security/manifests && cue vet ./examples/polyglot.cue
    @git diff --exit-code dagger_modules/security/manifests || (echo "❌ Cue formatting changes detected. Commit the updated manifests." >&2; exit 1)


# TESTING - GENERAL

## Run all tests with coverage
[group('test')]
test:
    @echo "🚀 Testing code: Running pytest with coverage"
    @uv run python -m pytest --cov --cov-config=.coveragerc --cov-report=xml

## Run fast tests (unit + integration, skip smoke)
[group('test')]
test-fast:
    @echo "⚡ Running fast tests (unit + integration)"
    @uv run python -m pytest -m "not smoke"

## Run smoke tests (requires Docker stack)
[group('test')]
test-smoke:
    @echo "💨 Running smoke suites"
    @uv run python -m pytest -m smoke

## Run integration tests only
[group('test')]
test-integration:
    @echo "🧪 Running integration tests"
    @uv run python -m pytest -m integration

## Run privacy-focused tests
[group('test')]
test-privacy:
    @echo "🛡️ Running privacy-marked tests"
    @uv run python -m pytest -m privacy

# ============================================================================
# TESTING - BY COMPONENT
# ============================================================================

## Run service-layer tests only
[group('test')]
test-services:
    @echo "🧩 Running service-layer tests"
    @uv run python -m pytest tests/test_services/ -v

## Run router/API tests only
[group('test')]
test-routers:
    @echo "🌐 Running router/API tests"
    @uv run python -m pytest tests/test_routers/ -v

## Run Certus Assurance tests (all test types)
[group('test')]
test-assurance:
    @echo "🧪 Running Certus Assurance tests (unit, integration, smoke, contract)"
    @uv run pytest certus_assurance/tests/ -v

## Run Certus Assurance unit tests only
[group('test')]
test-assurance-unit:
    @echo "⚡ Running Certus Assurance unit tests"
    @uv run pytest certus_assurance/tests/unit/ -v

## Run Certus Assurance smoke tests only
[group('test')]
test-assurance-smoke:
    @echo "💨 Running Certus Assurance smoke tests"
    @uv run pytest certus_assurance/tests/smoke/ -v

## Run Certus Assurance integration tests only
[group('test')]
test-assurance-integration:
    @echo "🔗 Running Certus Assurance integration tests"
    @uv run pytest certus_assurance/tests/integration/ -v

## Run Certus Assurance contract tests only
[group('test')]
test-assurance-contract:
    @echo "📋 Running Certus Assurance contract tests"
    @uv run pytest certus_assurance/tests/contract/ -v

## Run Dagger security module tests
[group('test')]
test-dagger-security:
    @echo "🧪 Testing dagger_modules/security"
    @uv run python -m pytest dagger_modules/security/tests

## Test all services
[group('test')]
test-all:
    @echo "🧪 Testing all services"
    @uv run python -m pytest certus_ask/tests/
    @uv run python -m pytest certus_trust/tests/
    @uv run python -m pytest certus_assurance/tests/
    @uv run python -m pytest certus_transform/tests/

## Test real sigstore implementation
[group('test')]
test-real:
    @echo "🧪 Testing real sigstore implementation"
    @uv run python -m pytest certus_trust/tests/ -v -m "sigstore"

# ============================================================================
# SECURITY SCANNING - PROFILES
# ============================================================================

## Run security scans (default profile)
[group('test')]
test-security:
    @echo "🔐 Running security scans"
    @python tools/security/run_certus_assurance_security.py

## Smoke profile: Ruff only (~20 seconds)
[group('test')]
test-security-smoke:
    @echo "✨ Running smoke security profile (Ruff)"
    @cd dagger_modules/security && PYTHONPATH=. uv run python -m security_module.cli \
        --workspace ../.. \
        --export-dir ../../build/security-results \
        --profile smoke
    @echo "📁 Exported artifacts -> build/security-results/latest"

## Fast profile: Ruff/Bandit/detect-secrets (~2 minutes, pre-commit recommended)
[group('test')]
test-security-fast:
    @echo "⚡ Running fast security profile (pre-commit recommended)"
    @cd dagger_modules/security && PYTHONPATH=. uv run python -m security_module.cli \
        --workspace ../.. \
        --export-dir ../../build/security-results \
        --profile fast
    @echo "📁 Exported artifacts -> build/security-results/latest"

## Medium profile: Fast + Opengrep (~4 minutes, pre-push recommended)
[group('test')]
test-security-medium:
    @echo "🔍 Running medium security profile (pre-push recommended)"
    @cd dagger_modules/security && PYTHONPATH=. uv run python -m security_module.cli \
        --workspace ../.. \
        --export-dir ../../build/security-results \
        --profile medium
    @echo "📁 Exported artifacts -> build/security-results/latest"

## Standard profile: Medium + Trivy (~8 minutes, CI recommended)
test-security-standard:
    @echo "🛡️ Running standard security profile (CI recommended)"
    @cd dagger_modules/security && PYTHONPATH=. uv run python -m security_module.cli \
        --workspace ../.. \
        --export-dir ../../build/security-results \
        --profile standard
    @echo "📁 Exported artifacts -> build/security-results/latest"

## Full profile: All tools including privacy (~12 minutes, release recommended)
test-security-full:
    @echo "🔐 Running full security profile (release recommended)"
    @cd dagger_modules/security && PYTHONPATH=. uv run python -m security_module.cli \
        --workspace ../.. \
        --export-dir ../../build/security-results \
        --profile full
    @echo "📁 Exported artifacts -> build/security-results/latest"

## JavaScript profile: ESLint + retire.js + Trivy + SBOM (~3 minutes)
test-security-javascript:
    @echo "📜 Running JavaScript security profile (Node.js/JavaScript projects)"
    @cd dagger_modules/security && PYTHONPATH=. uv run python -m security_module.cli \
        --workspace ../.. \
        --export-dir ../../build/security-results \
        --profile javascript
    @echo "📁 Exported artifacts -> build/security-results/latest"

## Attestation profile: Ruff + SBOM + attestation (~30 seconds)
test-security-attestation:
    @echo "📜 Running attestation test profile (SBOM + attestation validation)"
    @cd dagger_modules/security && PYTHONPATH=. uv run python -m security_module.cli \
        --workspace ../.. \
        --export-dir ../../build/security-results \
        --profile attestation-test
    @echo "📁 Exported artifacts -> build/security-results/latest"

## Legacy alias for 'full' profile (deprecated)
test-security-light:
    @echo "🛡️ Running light security profile (legacy - use 'full' instead)"
    @just test-security-full

# ============================================================================
# SECURITY SCANNING - EXTERNAL WORKSPACES
# ============================================================================

## Scan OWASP Juice Shop with JavaScript profile
test-security-juiceshop JUICESHOP_PATH="~/projects/juice-shop" EXPORT_DIR="":
    #!/usr/bin/env bash
    set -euo pipefail
    workspace_abs=$(cd "{{JUICESHOP_PATH}}" && pwd)
    export_dir="${{EXPORT_DIR}}"
    if [ -z "$export_dir" ]; then
        export_dir="$workspace_abs/security-results"
    fi
    echo "🧃 Scanning OWASP Juice Shop at $workspace_abs"
    cd dagger_modules/security
    PYTHONPATH=. uv run python -m security_module.cli \
        --workspace "$workspace_abs" \
        --export-dir "$export_dir" \
        --profile javascript
    echo "📁 Results: $export_dir/latest"

## Scan external workspace with configurable profile
test-security-external WORKSPACE_PATH PROFILE="javascript" EXPORT_DIR="":
    #!/usr/bin/env bash
    set -euo pipefail
    workspace_abs=$(cd "{{WORKSPACE_PATH}}" && pwd)
    export_dir="${{EXPORT_DIR}}"
    if [ -z "$export_dir" ]; then
        export_dir="$workspace_abs/security-results"
    fi
    echo "🔍 Scanning $workspace_abs with {{PROFILE}} profile"
    cd dagger_modules/security
    PYTHONPATH=. uv run python -m security_module.cli \
        --workspace "$workspace_abs" \
        --export-dir "$export_dir" \
        --profile "{{PROFILE}}"
    echo "📁 Results: $export_dir/latest"

## Run local SAST scanning (Trivy, OpenGrep, Bandit, Ruff via Dagger)
sast-scan tools="":
    @if [ -z "{{tools}}" ]; then \
        echo "🔍 Running SAST scans (all tools)"; \
        uv run python tools/sast/run_local_scan.py; \
    else \
        echo "🔍 Running SAST scans ({{tools}})"; \
        uv run python tools/sast/run_local_scan.py --tools {{tools}}; \
    fi

# ============================================================================
# BUILD & PACKAGING
# ============================================================================

## Clean build artifacts
clean-build:
    @echo "🚀 Removing build artifacts"
    @uv run python -c 'import shutil; import os; shutil.rmtree("dist") if os.path.exists("dist") else None'

## Build artifacts (wheel or docker image)
build target="wheel":
    @case "{{target}}" in \
        wheel) \
            echo "🚀 Creating wheel file"; \
            just clean-build >/dev/null; \
            uvx --from build pyproject-build --installer uv; \
            ;; \
        backend|docker|compose) \
            echo "🐳 Rebuilding docker image: ask-certus-backend"; \
            docker compose build --no-cache ask-certus-backend; \
            ;; \
        *) \
            echo "Unknown build target '{{target}}'. Use 'wheel' or 'backend'." >&2; \
            exit 1; \
            ;; \
    esac

## Build all services for production
build-all:
    @echo "🐳 Building all services for production"
    @docker compose -f certus_ask/deploy/docker-compose.yml build
    @docker compose -f certus_trust/deploy/docker-compose.yml build
    @docker compose -f certus_assurance/deploy/docker-compose.yml build
    @docker compose -f certus_transform/deploy/docker-compose.yml build

# ============================================================================
# DOCKER COMPOSE - INFRASTRUCTURE
# ============================================================================

## Start infrastructure services only
infrastructure-up:
    @echo "🚀 Starting infrastructure services"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d

## Stop infrastructure services
infrastructure-down:
    @echo "🛑 Stopping infrastructure services"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml down

# ============================================================================
# DOCKER COMPOSE - DEVELOPMENT ENVIRONMENT
# ============================================================================

## Start complete development environment (mock sigstore)
dev-up:
    @echo "🚀 Starting complete development environment with mock sigstore"
    @docker compose -f docker-compose.full-dev.yml up -d
    @./scripts/bootstrap-datalake.sh docker-compose.full-dev.yml

## Stop development environment
dev-down:
    @echo "🛑 Stopping development environment"
    @docker compose -f docker-compose.full-dev.yml down

## Build development environment
dev-build:
    @echo "🐳 Building development environment with mock sigstore"
    @docker compose -f docker-compose.full-dev.yml build

# ============================================================================
# DOCKER COMPOSE - PRODUCTION STACK
# ============================================================================

## Start full stack with real sigstore (build=true to rebuild first)
up services="" build="false": docker-login ensure-network
    @if [ "{{build}}" = "true" ]; then \
        if [ -z "{{services}}" ]; then \
            echo "🐳 Rebuilding images (all)..."; \
            docker compose -f certus_infrastructure/docker-compose.sigstore.yml up -d; \
            docker compose -f certus_trust/deploy/docker-compose.prod.yml build; \
        else \
            echo "🐳 Rebuilding images: {{services}}"; \
            docker compose -f certus_trust/deploy/docker-compose.prod.yml build {{services}}; \
        fi; \
    fi
    @if [ -z "{{services}}" ]; then \
        echo "🚀 Starting full stack with real sigstore"; \
        docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d; \
        ./scripts/bootstrap-datalake.sh certus_infrastructure/docker-compose.yml; \
        docker compose -p certus -f certus_infrastructure/docker-compose.sigstore.yml up -d; \
        sleep 5; \
        ./scripts/init-trillian.sh; \
        docker compose -f certus_ask/deploy/docker-compose.yml up -d; \
        docker compose -f certus_trust/deploy/docker-compose.prod.yml up -d; \
        docker compose -f certus_assurance/deploy/docker-compose.yml up -d; \
        docker compose -f certus_transform/deploy/docker-compose.yml up -d; \
    else \
        echo "🚀 Starting services: {{services}}"; \
        docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d; \
        ./scripts/bootstrap-datalake.sh certus_infrastructure/docker-compose.yml; \
        docker compose -p certus -f certus_infrastructure/docker-compose.sigstore.yml up -d; \
        sleep 5; \
        ./scripts/init-trillian.sh; \
        docker compose -f certus_ask/deploy/docker-compose.yml up -d; \
        docker compose -f certus_trust/deploy/docker-compose.prod.yml up -d; \
        docker compose -f certus_assurance/deploy/docker-compose.yml up -d; \
        docker compose -f certus_transform/deploy/docker-compose.yml up -d; \
    fi

## Stop all compose stacks (apps + infrastructure)
down:
    @echo "🛑 Stopping all services"
    @./scripts/shutdown-all.sh

## Alias for 'down'
shutdown:
    @just down

## Rebuild and restart the stack (down → build → up)
rebuild services="": docker-login
    @echo "🔄 Stopping containers..."
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml down || true
    @docker compose -p certus -f certus_infrastructure/docker-compose.sigstore.yml down || true
    @docker compose -f certus_ask/deploy/docker-compose.yml down || true
    @docker compose -f certus_trust/deploy/docker-compose.prod.yml down || true
    @docker compose -f certus_assurance/deploy/docker-compose.yml down || true
    @docker compose -f certus_transform/deploy/docker-compose.yml down || true
    @if [ -z "{{services}}" ]; then \
        echo "🐳 Rebuilding images (all)..."; \
        docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d; \
        docker compose -p certus -f certus_infrastructure/docker-compose.sigstore.yml up -d; \
        docker compose -f certus_ask/deploy/docker-compose.yml build; \
        docker compose -f certus_trust/deploy/docker-compose.prod.yml build; \
        docker compose -f certus_assurance/deploy/docker-compose.yml build; \
        docker compose -f certus_transform/deploy/docker-compose.yml build; \
    else \
        echo "🐳 Rebuilding images: {{services}}"; \
        docker compose -f certus_ask/deploy/docker-compose.yml build {{services}}; \
        docker compose -f certus_trust/deploy/docker-compose.prod.yml build {{services}}; \
        docker compose -f certus_assurance/deploy/docker-compose.yml build {{services}}; \
        docker compose -f certus_transform/deploy/docker-compose.yml build {{services}}; \
    fi
    @echo "🚀 Starting stack..."
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d
    @docker compose -p certus -f certus_infrastructure/docker-compose.sigstore.yml up -d
    @sleep 5
    @./scripts/init-trillian.sh
    @docker compose -f certus_ask/deploy/docker-compose.yml up -d
    @docker compose -f certus_trust/deploy/docker-compose.prod.yml up -d
    @docker compose -f certus_assurance/deploy/docker-compose.yml up -d
    @docker compose -f certus_transform/deploy/docker-compose.yml up -d

## Stop containers and remove compose project (volumes retained)
cleanup:
    @./scripts/cleanup.sh

## Fully tear down the stack, including volumes
destroy:
    @./scripts/destroy.sh

# ============================================================================
# DOCKER COMPOSE - INDIVIDUAL SERVICES
# ============================================================================

## Start specific service with dependencies (ask, trust, assurance, or transform)
service-up service="ask":
    @case "{{service}}" in \
        ask|certus-ask) \
            echo "🚀 Starting Certus Ask service"; \
            docker compose -p certus -f certus_infrastructure/docker-compose.yml -f certus_ask/deploy/docker-compose.yml up -d; \
            ;; \
        trust|certus-trust) \
            echo "🚀 Starting Certus Trust service"; \
            docker compose -p certus -f certus_infrastructure/docker-compose.yml -f certus_trust/deploy/docker-compose.yml up -d; \
            ;; \
        assurance|certus-assurance) \
            echo "🚀 Starting Certus Assurance service"; \
            docker compose -p certus -f certus_infrastructure/docker-compose.yml -f certus_assurance/deploy/docker-compose.yml up -d; \
            ;; \
        transform|certus-transform) \
            echo "🚀 Starting Certus Transform service"; \
            docker compose -p certus -f certus_infrastructure/docker-compose.yml -f certus_transform/deploy/docker-compose.yml up -d; \
            ;; \
        *) \
            echo "Unknown service '{{service}}'. Use: ask, trust, assurance, or transform." >&2; \
            exit 1; \
            ;; \
    esac

## Stop specific service
service-down service="ask":
    @case "{{service}}" in \
        ask|certus-ask) \
            echo "🛑 Stopping Certus Ask service"; \
            docker compose -f certus_ask/deploy/docker-compose.yml down; \
            ;; \
        trust|certus-trust) \
            echo "🛑 Stopping Certus Trust service"; \
            docker compose -f certus_trust/deploy/docker-compose.yml down; \
            ;; \
        assurance|certus-assurance) \
            echo "🛑 Stopping Certus Assurance service"; \
            docker compose -f certus_assurance/deploy/docker-compose.yml down; \
            ;; \
        transform|certus-transform) \
            echo "🛑 Stopping Certus Transform service"; \
            docker compose -f certus_transform/deploy/docker-compose.yml down; \
            ;; \
        *) \
            echo "Unknown service '{{service}}'. Use: ask, trust, assurance, or transform." >&2; \
            exit 1; \
            ;; \
    esac

## Build specific service
service-build service="ask":
    @case "{{service}}" in \
        ask|certus-ask) \
            echo "🐳 Building Certus Ask service"; \
            docker compose -f certus_ask/deploy/docker-compose.yml build; \
            ;; \
        trust|certus-trust) \
            echo "🐳 Building Certus Trust service"; \
            docker compose -f certus_trust/deploy/docker-compose.yml build; \
            ;; \
        assurance|certus-assurance) \
            echo "🐳 Building Certus Assurance service"; \
            docker compose -f certus_assurance/deploy/docker-compose.yml build; \
            ;; \
        transform|certus-transform) \
            echo "🐳 Building Certus Transform service"; \
            docker compose -f certus_transform/deploy/docker-compose.yml build; \
            ;; \
        *) \
            echo "Unknown service '{{service}}'. Use: ask, trust, assurance, or transform." >&2; \
            exit 1; \
            ;; \
    esac

# ============================================================================
# TUTORIAL-SPECIFIC ENVIRONMENTS
# ============================================================================

## Start minimal stack for Transform tutorials (ingestion, datalake, golden bucket)
transform-up: ensure-network
    @echo "🚀 Starting Transform tutorial environment"
    @echo "   Services: opensearch, localstack, neo4j, victoriametrics, otel-collector, ask-certus-backend"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d opensearch localstack neo4j victoriametrics otel-collector
    @docker compose -f certus_ask/deploy/docker-compose.yml up -d
    @echo "   Ensuring LocalStack buckets exist..."
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml exec -T localstack /bin/bash /docker-entrypoint-initaws.d/init-buckets.sh >/dev/null 2>&1 || true
    @echo "✅ Transform environment ready"
    @echo "   Tutorials: docs/learn/transform/"

## Stop Transform tutorial environment
transform-down:
    @echo "🛑 Stopping Transform tutorial environment"
    @docker compose -f certus_ask/deploy/docker-compose.yml down
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml down

## Start minimal stack for Ask tutorials (keyword, semantic, hybrid search, neo4j)
ask-up: ensure-network
    @echo "🚀 Starting Ask tutorial environment"
    @echo "   Services: opensearch, neo4j, localstack, victoriametrics, otel-collector, ask-certus-backend"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d opensearch neo4j localstack victoriametrics otel-collector
    @docker compose -f certus_ask/deploy/docker-compose.yml up -d
    @echo "✅ Ask environment ready"
    @echo "   Tutorials: docs/learn/ask/"

## Stop Ask tutorial environment
ask-down:
    @echo "🛑 Stopping Ask tutorial environment"
    @docker compose -f certus_ask/deploy/docker-compose.yml down
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml down

## Start full stack for Trust tutorials (security scans, verification, attestations)
trust-up: ensure-network
    @echo "🚀 Starting Trust tutorial environment (full verification stack)"
    @echo "   Services: all infrastructure + trust + assurance + transform + ask"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d
    @docker compose -f certus_trust/deploy/docker-compose.yml up -d
    @docker compose -f certus_assurance/deploy/docker-compose.yml up -d
    @docker compose -f certus_transform/deploy/docker-compose.yml up -d
    @docker compose -f certus_ask/deploy/docker-compose.yml up -d
    @echo "✅ Trust environment ready"
    @echo "   Tutorials: docs/learn/trust/"

## Stop Trust tutorial environment
trust-down:
    @echo "🛑 Stopping Trust tutorial environment"
    @docker compose -f certus_ask/deploy/docker-compose.yml down
    @docker compose -f certus_transform/deploy/docker-compose.yml down
    @docker compose -f certus_assurance/deploy/docker-compose.yml down
    @docker compose -f certus_trust/deploy/docker-compose.yml down
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml down

## Start minimal stack for Integrity tutorials (compliance, incidents, rate limits)
integrity-up: ensure-network
    @echo "🚀 Starting Integrity tutorial environment"
    @echo "   Services: victoriametrics, otel-collector, opensearch, ask-certus-backend (with integrity enabled)"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d victoriametrics otel-collector opensearch
    @docker compose -f certus_ask/deploy/docker-compose.yml up -d
    @echo "✅ Integrity environment ready"
    @echo "   Tutorials: docs/learn/integrity/"
    @echo "   Note: Ensure INTEGRITY_* env vars are set in .env"

## Stop Integrity tutorial environment
integrity-down:
    @echo "🛑 Stopping Integrity tutorial environment"
    @docker compose -f certus_ask/deploy/docker-compose.yml down
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml down

## Start basic stack for Assurance tutorials (scanning only, no verification)
assurance-up: ensure-network
    @echo "🚀 Starting Assurance tutorial environment (basic tier)"
    @echo "   Services: localstack, victoriametrics, otel-collector, certus-assurance"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d localstack victoriametrics otel-collector
    @docker compose -f certus_assurance/deploy/docker-compose.yml up -d
    @echo "✅ Assurance environment ready (basic tier)"
    @echo "   Tutorials: docs/learn/assurance/"

## Stop Assurance tutorial environment
assurance-down:
    @echo "🛑 Stopping Assurance tutorial environment"
    @docker compose -f certus_assurance/deploy/docker-compose.yml down
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml down

## Start verified stack for Assurance tutorials (with trust verification)
assurance-verified-up: ensure-network
    @echo "🚀 Starting Assurance tutorial environment (verified tier)"
    @echo "   Services: localstack, victoriametrics, otel-collector, registry, certus-trust, certus-assurance"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d localstack victoriametrics otel-collector registry
    @docker compose -f certus_trust/deploy/docker-compose.yml up -d
    @docker compose -f certus_assurance/deploy/docker-compose.yml up -d
    @echo "✅ Assurance environment ready (verified tier)"
    @echo "   Tutorials: docs/learn/assurance/ (with verification)"

## Stop verified Assurance tutorial environment
assurance-verified-down:
    @echo "🛑 Stopping Assurance tutorial environment (verified tier)"
    @docker compose -f certus_assurance/deploy/docker-compose.yml down
    @docker compose -f certus_trust/deploy/docker-compose.yml down
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml down

# ============================================================================
# DOCKER COMPOSE - HELPERS
# ============================================================================

## Docker compose build helper (optionally pass service names)
compose-build services="":
    @if [ -z "{{services}}" ]; then \
        echo "🐳 docker compose build (all services)"; \
        docker compose build; \
    else \
        echo "🐳 docker compose build {{services}}"; \
        docker compose build {{services}}; \
    fi

## Docker compose up helper (defaults to detached all services)
compose-up services="":
    @if [ -z "{{services}}" ]; then \
        echo "🐳 docker compose up -d"; \
        docker compose up -d; \
    else \
        echo "🐳 docker compose up -d {{services}}"; \
        docker compose up -d {{services}}; \
    fi

## Docker compose down helper (pass remove_volumes=true to drop volumes)
compose-down remove_volumes="false":
    @if [ "{{remove_volumes}}" = "true" ]; then \
        echo "🐳 docker compose down -v"; \
        docker compose down -v; \
    else \
        echo "🐳 docker compose down"; \
        docker compose down; \
    fi

# ============================================================================
# DEPLOYMENT & OPERATIONS
# ============================================================================

## Deploy production environment with real sigstore
deploy:
    @echo "🚀 Deploying production environment with real sigstore"
    @docker compose -f certus_infrastructure/docker-compose.sigstore.yml up -d
    @docker compose -f certus_trust/deploy/docker-compose.prod.yml up -d --build

## Rollback to mock implementation
rollback-mock:
    @echo "🔙 Rolling back to mock implementation"
    @docker compose -f certus_trust/deploy/docker-compose.rollback.yml up -d

## Verify deployment health
verify-deployment:
    @echo "🔍 Verifying deployment"
    @curl -f http://localhost:3001 || echo "Rekor not ready"
    @curl -f http://localhost:5555 || echo "Fulcio not ready"
    @curl -f http://localhost:8057/health || echo "Certus Trust not ready"
    @docker compose -f certus_trust/deploy/docker-compose.prod.yml logs --tail=50

# ============================================================================
# PREFLIGHT & HEALTH CHECKS
# ============================================================================

## Run health + smoke-test checks against the running stack
## Run comprehensive preflight checks (all services)
preflight:
    @./scripts/preflight/all.sh

## Run preflight checks on development environment
preflight-dev:
    @echo "🚀 Running preflight checks on development environment"
    @./scripts/preflight/all.sh

## Run preflight checks for Transform tutorials
preflight-transform:
    @./scripts/preflight/transform.sh

## Run preflight checks for Ask tutorials
preflight-ask:
    @./scripts/preflight/ask.sh

## Run preflight checks for Trust tutorials (full stack)
preflight-trust:
    @./scripts/preflight/trust.sh

## Run preflight checks for Integrity tutorials
preflight-integrity:
    @./scripts/preflight/integrity.sh

## Run preflight checks for Assurance tutorials (basic tier)
preflight-assurance:
    @./scripts/preflight/assurance.sh

## Run preflight checks for Assurance tutorials (verified tier)
preflight-assurance-verified:
    @./scripts/preflight/assurance-verified.sh

## Verify trust tutorial compatibility
tutorial-trust-verify:
    @echo "🔍 Verifying trust tutorial compatibility"
    @docker compose -f certus_infrastructure/docker-compose.sigstore.yml up -d
    @docker compose -f certus_trust/deploy/docker-compose.prod.yml up -d
    @./scripts/trust-smoke-test.sh || echo "Smoke tests not found"
    @echo "✅ Trust tutorials verified"

# ============================================================================
# DATA LAKE OPERATIONS
# ============================================================================

## Remove uploaded sample bundle from LocalStack raw bucket
datalake-clean-samples:
    @source .env >/dev/null 2>&1 || true; \
    raw_bucket="${DATALAKE_RAW_BUCKET:-raw}"; \
    sample_folder="${DATALAKE_SAMPLE_FOLDER:-samples}"; \
    docker compose exec localstack awslocal s3 rm "s3://$$raw_bucket/$$sample_folder" --recursive || true

## Upload sample bundle to raw bucket
datalake-upload-samples:
    @TARGET_FOLDER="${DATALAKE_SAMPLE_FOLDER:-samples}" ./scripts/datalake-upload-sample.sh

## Upload corpus to S3 and index it
upload-index-corpus bucket="raw" prefix="corpus" workspace="default" endpoint="http://localhost:4566":
    @echo "📤 Uploading corpus to S3..."
    @uv run scripts/upload_corpus_to_s3.py --bucket {{bucket}} --prefix {{prefix}} --endpoint-url {{endpoint}} -v
    @echo ""
    @echo "📑 Indexing from S3..."
    @uv run scripts/index_s3_corpus.py --bucket {{bucket}} --prefix {{prefix}} --workspace {{workspace}} -v
    @echo ""
    @echo "✅ Done!"

# ============================================================================
# ATTESTATIONS & COMPLIANCE
# ============================================================================

## Generate mock OCI attestations (SBOM, attestation, SARIF)
generate-attestations product="Acme Product" version="1.0.0":
    @python3 scripts/oci-attestations.py generate \
        --output samples/oci-attestations/artifacts \
        --product "{{product}}" \
        --version "{{version}}"

## Setup cosign keys for signing attestations
setup-attestation-keys:
    @python3 scripts/oci-attestations.py setup-keys \
        --key-path samples/oci-attestations/keys/cosign.key

## Sign all generated attestations with cosign
sign-attestations:
    @python3 scripts/oci-attestations.py sign \
        --artifacts-dir samples/oci-attestations/artifacts \
        --key-path samples/oci-attestations/keys/cosign.key

## Verify attestation signatures
verify-attestations:
    @python3 scripts/oci-attestations.py verify \
        --artifacts-dir samples/oci-attestations/artifacts \
        --key-path samples/oci-attestations/keys/cosign.pub

## Push attestations to OCI registry
push-to-registry registry="http://localhost:5000" username="" password="" repo="product-acquisition/attestations":
    @registry="{{registry}}" username="{{username}}" password="{{password}}" repo="{{repo}}" \
    python3 scripts/oci-attestations.py push \
        --artifacts-dir samples/oci-attestations/artifacts \
        --registry "$registry" \
        ${username:+--username "$username"} \
        ${password:+--password "$password"} \
        --repo "$repo"

## Alias for push-to-registry (legacy compatibility)
push-to-harbor registry="http://localhost:5000" username="" password="" repo="product-acquisition/attestations":
    @just push-to-registry registry={{registry}} username={{username}} password={{password}} repo={{repo}}

## Complete attestations workflow (generate → sign → verify → push)
attestations-workflow product="Acme Product" version="1.0.0":
    @./scripts/attestations-workflow.sh

## Generate signed compliance report from findings JSON
generate-compliance-report product vendor reviewer org findings_file output="samples/oci-attestations/reports":
    @python3 scripts/generate-compliance-report.py generate \
        --product "{{product}}" \
        --version "1.0.0" \
        --vendor "{{vendor}}" \
        --reviewer "{{reviewer}}" \
        --org "{{org}}" \
        --findings-file "{{findings_file}}" \
        --output "{{output}}"

## Sign compliance report with cosign
sign-compliance-report report key_path="samples/oci-attestations/keys/cosign.key":
    @python3 scripts/generate-compliance-report.py sign \
        --report "{{report}}" \
        --key-path "{{key_path}}"

## Upload signed compliance report to OCI registry
upload-compliance-report report signature registry username password repo:
    @python3 scripts/generate-compliance-report.py upload \
        --report "{{report}}" \
        --signature "{{signature}}" \
        --registry "{{registry}}" \
        --username "{{username}}" \
        --password "{{password}}" \
        --repo "{{repo}}"

# ============================================================================
# DOCUMENTATION
# ============================================================================

## Test if documentation can be built without warnings or errors
docs-test:
    @uv run mkdocs build -s

## Serve documentation locally (defaults to 127.0.0.1:8001)
docs-serve:
    @./scripts/mkdocs-serve.sh

## Alias for docs-serve
alias docs := docs-serve
## Launch multi-agent zellij workspace
agents:
    @./scripts/dev.zellij.sh
