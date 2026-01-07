# Certus TAP Justfile
# Development task automation for Certus Trust & Assurance Platform

default := "help"
set shell := ["bash", "-lc"]

# ============================================================================
# HELP & INFORMATION
# ============================================================================

## Show all available recipes
[group('help')]
help:
    @just --list --unsorted

## Show recipes organized by category
[group('help')]
help-categories:
    @echo "📚 Certus TAP Command Categories"
    @echo ""
    @echo "Setup:          setup-*           Initial installation and configuration"
    @echo "Development:    dev-*             Development environment (use shortcuts: up, down, logs)"
    @echo "Services:       service-*         Individual service management"
    @echo "Tutorials:      {name}-up/down    Tutorial-specific environments"
    @echo "Testing:        test-*            Run tests and quality checks"
    @echo "Security:       test-security-*   Security scanning profiles"
    @echo "Build:          build-*           Build artifacts and images"
    @echo "Documentation:  docs-*            Documentation server and build"
    @echo "Data Lake:      datalake-*        Data lake operations"
    @echo "Attestations:   *-attestations    Compliance and signing workflows"
    @echo "Deployment:     deploy-*          Production deployment"
    @echo "Utilities:      util-*            Cleanup and maintenance"
    @echo ""
    @echo "Run 'just --list' to see all commands"

# ============================================================================
# SETUP & INSTALLATION (setup-*)
# ============================================================================

## Install virtual environment and pre-commit hooks
[group('setup')]
setup-install:
    @echo "🚀 Creating virtual environment using uv"
    @uv sync
    @uv run pre-commit install

## Ensure the shared Docker network exists
[group('setup')]
setup-network:
    @docker network inspect certus-network >/dev/null 2>&1 || docker network create certus-network

## Login to GitHub Container Registry
[group('setup')]
setup-docker-login:
    @./scripts/docker-login.sh

## Complete first-time setup
[group('setup')]
setup-all: setup-install setup-network
    @echo "✅ Setup complete! Copy .env.example to .env and configure"

# Alias for backward compatibility
alias install := setup-install
alias ensure-network := setup-network
alias docker-login := setup-docker-login

# ============================================================================
# PRODUCTION STACK (up/down/rebuild)
# ============================================================================

## Start full production stack with real sigstore
[group('production')]
up services="" build="false": setup-docker-login setup-network
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

## Stop all compose stacks
[group('production')]
down:
    @echo "🛑 Stopping all services"
    @./scripts/shutdown-all.sh

## Rebuild and restart production stack
[group('production')]
rebuild services="": setup-docker-login
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
[group('production')]
cleanup:
    @./scripts/cleanup.sh

## Fully tear down the stack, including volumes
[group('production')]
destroy:
    @./scripts/destroy.sh

# Legacy aliases
alias shutdown := down

# ============================================================================
# INFRASTRUCTURE SERVICES (infrastructure-*)
# ============================================================================

## Start infrastructure services only
[group('infrastructure')]
infrastructure-up:
    @echo "🚀 Starting infrastructure services"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d

## Stop infrastructure services
[group('infrastructure')]
infrastructure-down:
    @echo "🛑 Stopping infrastructure services"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml down

# ============================================================================
# INDIVIDUAL SERVICES (service-*)
# ============================================================================

## Start specific service (ask, trust, assurance, transform)
[group('services')]
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
[group('services')]
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
[group('services')]
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
# TUTORIAL ENVIRONMENTS
# ============================================================================

## Start Ask tutorial environment (keyword, semantic, hybrid search)
[group('tutorials')]
ask-up: setup-network
    @echo "🚀 Starting Ask tutorial environment"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d opensearch neo4j localstack victoriametrics otel-collector
    @docker compose -f certus_ask/deploy/docker-compose.yml up -d
    @echo "✅ Ask environment ready - Tutorials: docs/learn/ask/"

## Stop Ask tutorial environment
[group('tutorials')]
ask-down:
    @docker compose -f certus_ask/deploy/docker-compose.yml down
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml down

## Start Assurance tutorial environment (basic tier)
[group('tutorials')]
assurance-up: setup-network
    @echo "🚀 Starting Assurance tutorial environment (basic tier)"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d localstack victoriametrics otel-collector
    @docker compose -f certus_assurance/deploy/docker-compose.yml up -d
    @echo "✅ Assurance environment ready - Tutorials: docs/learn/assurance/"

## Stop Assurance tutorial environment
[group('tutorials')]
assurance-down:
    @docker compose -f certus_assurance/deploy/docker-compose.yml down
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml down

## Start Assurance tutorial environment (verified tier)
[group('tutorials')]
assurance-verified-up: setup-network
    @echo "🚀 Starting Assurance tutorial environment (verified tier)"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d localstack victoriametrics otel-collector registry
    @docker compose -f certus_trust/deploy/docker-compose.yml up -d
    @docker compose -f certus_assurance/deploy/docker-compose.yml up -d
    @echo "✅ Assurance environment ready (verified) - Tutorials: docs/learn/assurance/"

## Stop verified Assurance tutorial environment
[group('tutorials')]
assurance-verified-down:
    @docker compose -f certus_assurance/deploy/docker-compose.yml down
    @docker compose -f certus_trust/deploy/docker-compose.yml down
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml down

## Start Trust tutorial environment (full verification stack)
[group('tutorials')]
trust-up: setup-network
    @echo "🚀 Starting Trust tutorial environment (full verification stack)"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d
    @docker compose -f certus_trust/deploy/docker-compose.yml up -d
    @docker compose -f certus_assurance/deploy/docker-compose.yml up -d
    @docker compose -f certus_transform/deploy/docker-compose.yml up -d
    @docker compose -f certus_ask/deploy/docker-compose.yml up -d
    @echo "✅ Trust environment ready - Tutorials: docs/learn/trust/"

## Stop Trust tutorial environment
[group('tutorials')]
trust-down:
    @docker compose -f certus_ask/deploy/docker-compose.yml down
    @docker compose -f certus_transform/deploy/docker-compose.yml down
    @docker compose -f certus_assurance/deploy/docker-compose.yml down
    @docker compose -f certus_trust/deploy/docker-compose.yml down
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml down

## Start Integrity tutorial environment (compliance, rate limits)
[group('tutorials')]
integrity-up: setup-network
    @echo "🚀 Starting Integrity tutorial environment"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d victoriametrics otel-collector opensearch
    @docker compose -f certus_ask/deploy/docker-compose.yml up -d
    @echo "✅ Integrity environment ready - Tutorials: docs/learn/integrity/"
    @echo "Note: Ensure INTEGRITY_* env vars are set in .env"

## Stop Integrity tutorial environment
[group('tutorials')]
integrity-down:
    @docker compose -f certus_ask/deploy/docker-compose.yml down
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml down

## Start Transform tutorial environment (ingestion, datalake)
[group('tutorials')]
transform-up: setup-network
    @echo "🚀 Starting Transform tutorial environment"
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml up -d opensearch localstack neo4j victoriametrics otel-collector
    @docker compose -f certus_ask/deploy/docker-compose.yml up -d
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml exec -T localstack /bin/bash /docker-entrypoint-initaws.d/init-buckets.sh >/dev/null 2>&1 || true
    @echo "✅ Transform environment ready - Tutorials: docs/learn/transform/"

## Stop Transform tutorial environment
[group('tutorials')]
transform-down:
    @docker compose -f certus_ask/deploy/docker-compose.yml down
    @docker compose -p certus -f certus_infrastructure/docker-compose.yml down

# ============================================================================
# CODE QUALITY & LINTING (check/test-lint)
# ============================================================================

## Run all code quality tools (linting, type checking, manifest validation)
[group('quality')]
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

## Format and validate assurance manifests
[group('quality')]
manifest-check:
    @echo "🧾 Formatting assurance manifests (cue fmt)"
    @cd dagger_modules/security/manifests && cue fmt ./...
    @echo "🛡️ Validating manifest examples (cue vet)"
    @cd dagger_modules/security/manifests && cue vet ./examples/python-light.cue
    @cd dagger_modules/security/manifests && cue vet ./examples/polyglot.cue
    @git diff --exit-code dagger_modules/security/manifests || (echo "❌ Cue formatting changes detected. Commit the updated manifests." >&2; exit 1)

# ============================================================================
# TESTING - GENERAL (test-*)
# ============================================================================

## Run all tests with coverage
[group('testing')]
test:
    @echo "🚀 Testing code: Running pytest with coverage"
    @uv run python -m pytest --cov --cov-config=.coveragerc --cov-report=xml

## Run fast tests (unit + integration, skip smoke)
[group('testing')]
test-fast:
    @echo "⚡ Running fast tests (unit + integration)"
    @uv run python -m pytest -m "not smoke"

## Run smoke tests (requires Docker stack)
[group('testing')]
test-smoke:
    @echo "💨 Running smoke suites"
    @uv run python -m pytest -m smoke

## Run integration tests only
[group('testing')]
test-integration:
    @echo "🧪 Running integration tests"
    @uv run python -m pytest -m integration

## Run privacy-focused tests
[group('testing')]
test-privacy:
    @echo "🛡️ Running privacy-marked tests"
    @uv run python -m pytest -m privacy

## Run service-layer tests only
[group('testing')]
test-services:
    @echo "🧩 Running service-layer tests"
    @uv run python -m pytest tests/test_services/ -v

## Run router/API tests only
[group('testing')]
test-routers:
    @echo "🌐 Running router/API tests"
    @uv run python -m pytest tests/test_routers/ -v

## Test all services
[group('testing')]
test-all:
    @echo "🧪 Testing all services"
    @uv run python -m pytest certus_ask/tests/
    @uv run python -m pytest certus_trust/tests/
    @uv run python -m pytest certus_assurance/tests/
    @uv run python -m pytest certus_transform/tests/

## Test real sigstore implementation
[group('testing')]
test-real:
    @echo "🧪 Testing real sigstore implementation"
    @uv run python -m pytest certus_trust/tests/ -v -m "sigstore"

# ============================================================================
# TESTING - ASSURANCE (test-assurance-*)
# ============================================================================

## Run all Certus Assurance tests
[group('testing-assurance')]
test-assurance:
    @echo "🧪 Running Certus Assurance tests (unit, integration, smoke, contract)"
    @uv run pytest certus_assurance/tests/ -v

## Run Certus Assurance unit tests
[group('testing-assurance')]
test-assurance-unit:
    @echo "⚡ Running Certus Assurance unit tests"
    @uv run pytest certus_assurance/tests/unit/ -v

## Run Certus Assurance smoke tests
[group('testing-assurance')]
test-assurance-smoke:
    @echo "💨 Running Certus Assurance smoke tests"
    @uv run pytest certus_assurance/tests/smoke/ -v

## Run Certus Assurance integration tests
[group('testing-assurance')]
test-assurance-integration:
    @echo "🔗 Running Certus Assurance integration tests"
    @uv run pytest certus_assurance/tests/integration/ -v

## Run Certus Assurance contract tests
[group('testing-assurance')]
test-assurance-contract:
    @echo "📋 Running Certus Assurance contract tests"
    @uv run pytest certus_assurance/tests/contract/ -v

## Run Dagger security module tests
[group('testing-assurance')]
test-dagger-security:
    @echo "🧪 Testing dagger_modules/security"
    @uv run python -m pytest dagger_modules/security/tests

# ============================================================================
# SECURITY SCANNING - PROFILES (test-security-*)
# ============================================================================

## Run security scans (default profile)
[group('security')]
test-security:
    @echo "🔐 Running security scans"
    @python tools/security/run_certus_assurance_security.py

## Smoke profile: Ruff only (~20 seconds)
[group('security')]
test-security-smoke:
    @echo "✨ Running smoke security profile (Ruff)"
    @cd dagger_modules/security && PYTHONPATH=. uv run python -m security_module.cli \
        --workspace ../.. \
        --export-dir ../../build/security-results \
        --profile smoke
    @echo "📁 Exported artifacts -> build/security-results/latest"

## Fast profile: Ruff/Bandit/detect-secrets (~2 minutes)
[group('security')]
test-security-fast:
    @echo "⚡ Running fast security profile (pre-commit recommended)"
    @cd dagger_modules/security && PYTHONPATH=. uv run python -m security_module.cli \
        --workspace ../.. \
        --export-dir ../../build/security-results \
        --profile fast
    @echo "📁 Exported artifacts -> build/security-results/latest"

## Medium profile: Fast + Opengrep (~4 minutes)
[group('security')]
test-security-medium:
    @echo "🔍 Running medium security profile (pre-push recommended)"
    @cd dagger_modules/security && PYTHONPATH=. uv run python -m security_module.cli \
        --workspace ../.. \
        --export-dir ../../build/security-results \
        --profile medium
    @echo "📁 Exported artifacts -> build/security-results/latest"

## Standard profile: Medium + Trivy (~8 minutes)
[group('security')]
test-security-standard:
    @echo "🛡️ Running standard security profile (CI recommended)"
    @cd dagger_modules/security && PYTHONPATH=. uv run python -m security_module.cli \
        --workspace ../.. \
        --export-dir ../../build/security-results \
        --profile standard
    @echo "📁 Exported artifacts -> build/security-results/latest"

## Full profile: All tools including privacy (~12 minutes)
[group('security')]
test-security-full:
    @echo "🔐 Running full security profile (release recommended)"
    @cd dagger_modules/security && PYTHONPATH=. uv run python -m security_module.cli \
        --workspace ../.. \
        --export-dir ../../build/security-results \
        --profile full
    @echo "📁 Exported artifacts -> build/security-results/latest"

## JavaScript profile: ESLint + retire.js + Trivy (~3 minutes)
[group('security')]
test-security-javascript:
    @echo "📜 Running JavaScript security profile"
    @cd dagger_modules/security && PYTHONPATH=. uv run python -m security_module.cli \
        --workspace ../.. \
        --export-dir ../../build/security-results \
        --profile javascript
    @echo "📁 Exported artifacts -> build/security-results/latest"

## Attestation profile: Ruff + SBOM + attestation (~30 seconds)
[group('security')]
test-security-attestation:
    @echo "📜 Running attestation test profile"
    @cd dagger_modules/security && PYTHONPATH=. uv run python -m security_module.cli \
        --workspace ../.. \
        --export-dir ../../build/security-results \
        --profile attestation-test
    @echo "📁 Exported artifacts -> build/security-results/latest"

## Legacy alias for 'full' profile
[group('security')]
test-security-light:
    @echo "🛡️ Running light security profile (legacy - use 'full' instead)"
    @just test-security-full

# ============================================================================
# SECURITY SCANNING - EXTERNAL WORKSPACES
# ============================================================================

## Scan OWASP Juice Shop with JavaScript profile
[group('security-external')]
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
[group('security-external')]
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
    @echo "📁 Results: $export_dir/latest"

## Run local SAST scanning (Trivy, OpenGrep, Bandit, Ruff)
[group('security-external')]
sast-scan tools="":
    @if [ -z "{{tools}}" ]; then \
        echo "🔍 Running SAST scans (all tools)"; \
        uv run python tools/sast/run_local_scan.py; \
    else \
        echo "🔍 Running SAST scans ({{tools}})"; \
        uv run python tools/sast/run_local_scan.py --tools {{tools}}; \
    fi

# ============================================================================
# BUILD & PACKAGING (build-*)
# ============================================================================

## Clean build artifacts
[group('build')]
clean-build:
    @echo "🚀 Removing build artifacts"
    @uv run python -c 'import shutil; import os; shutil.rmtree("dist") if os.path.exists("dist") else None'

## Build artifacts (wheel or docker image)
[group('build')]
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
[group('build')]
build-all:
    @echo "🐳 Building all services for production"
    @docker compose -f certus_ask/deploy/docker-compose.yml build
    @docker compose -f certus_trust/deploy/docker-compose.yml build
    @docker compose -f certus_assurance/deploy/docker-compose.yml build
    @docker compose -f certus_transform/deploy/docker-compose.yml build

# ============================================================================
# PREFLIGHT CHECKS (preflight-*)
# ============================================================================

## Run comprehensive preflight checks (all services)
[group('preflight')]
preflight:
    @./scripts/preflight/all.sh

## Run preflight checks on development environment
[group('preflight')]
preflight-dev:
    @echo "🚀 Running preflight checks on development environment"
    @./scripts/preflight/all.sh

## Run preflight checks for Ask tutorials
[group('preflight')]
preflight-ask:
    @./scripts/preflight/ask.sh

## Run preflight checks for Assurance tutorials (basic tier)
[group('preflight')]
preflight-assurance:
    @./scripts/preflight/assurance.sh

## Run preflight checks for Assurance tutorials (verified tier)
[group('preflight')]
preflight-assurance-verified:
    @./scripts/preflight/assurance-verified.sh

## Run preflight checks for Trust tutorials (full stack)
[group('preflight')]
preflight-trust:
    @./scripts/preflight/trust.sh

## Run preflight checks for Integrity tutorials
[group('preflight')]
preflight-integrity:
    @./scripts/preflight/integrity.sh

## Run preflight checks for Transform tutorials
[group('preflight')]
preflight-transform:
    @./scripts/preflight/transform.sh

## Verify trust tutorial compatibility
[group('preflight')]
tutorial-trust-verify:
    @echo "🔍 Verifying trust tutorial compatibility"
    @docker compose -f certus_infrastructure/docker-compose.sigstore.yml up -d
    @docker compose -f certus_trust/deploy/docker-compose.prod.yml up -d
    @./scripts/trust-smoke-test.sh || echo "Smoke tests not found"
    @echo "✅ Trust tutorials verified"

# ============================================================================
# DATA LAKE OPERATIONS (datalake-*)
# ============================================================================

## Upload sample bundle to raw bucket
[group('datalake')]
datalake-upload-samples:
    @TARGET_FOLDER="${DATALAKE_SAMPLE_FOLDER:-samples}" ./scripts/datalake-upload-sample.sh

## Remove uploaded sample bundle from raw bucket
[group('datalake')]
datalake-clean-samples:
    @source .env >/dev/null 2>&1 || true; \
    raw_bucket="${DATALAKE_RAW_BUCKET:-raw}"; \
    sample_folder="${DATALAKE_SAMPLE_FOLDER:-samples}"; \
    docker compose exec localstack awslocal s3 rm "s3://$$raw_bucket/$$sample_folder" --recursive || true

## Upload corpus to S3 and index it
[group('datalake')]
upload-index-corpus bucket="raw" prefix="corpus" workspace="default" endpoint="http://localhost:4566":
    @echo "📤 Uploading corpus to S3..."
    @uv run scripts/upload_corpus_to_s3.py --bucket {{bucket}} --prefix {{prefix}} --endpoint-url {{endpoint}} -v
    @echo ""
    @echo "📑 Indexing from S3..."
    @uv run scripts/index_s3_corpus.py --bucket {{bucket}} --prefix {{prefix}} --workspace {{workspace}} -v
    @echo ""
    @echo "✅ Done!"

# ============================================================================
# ATTESTATIONS & COMPLIANCE (attestations/compliance)
# ============================================================================

## Generate mock OCI attestations
[group('attestations')]
generate-attestations product="Acme Product" version="1.0.0":
    @python3 scripts/oci-attestations.py generate \
        --output samples/oci-attestations/artifacts \
        --product "{{product}}" \
        --version "{{version}}"

## Setup cosign keys for signing attestations
[group('attestations')]
setup-attestation-keys:
    @python3 scripts/oci-attestations.py setup-keys \
        --key-path samples/oci-attestations/keys/cosign.key

## Sign all generated attestations with cosign
[group('attestations')]
sign-attestations:
    @python3 scripts/oci-attestations.py sign \
        --artifacts-dir samples/oci-attestations/artifacts \
        --key-path samples/oci-attestations/keys/cosign.key

## Verify attestation signatures
[group('attestations')]
verify-attestations:
    @python3 scripts/oci-attestations.py verify \
        --artifacts-dir samples/oci-attestations/artifacts \
        --key-path samples/oci-attestations/keys/cosign.pub

## Push attestations to OCI registry
[group('attestations')]
push-to-registry registry="http://localhost:5000" username="" password="" repo="product-acquisition/attestations":
    @registry="{{registry}}" username="{{username}}" password="{{password}}" repo="{{repo}}" \
    python3 scripts/oci-attestations.py push \
        --artifacts-dir samples/oci-attestations/artifacts \
        --registry "$registry" \
        ${username:+--username "$username"} \
        ${password:+--password "$password"} \
        --repo "$repo"

## Complete attestations workflow (generate → sign → verify → push)
[group('attestations')]
attestations-workflow product="Acme Product" version="1.0.0":
    @./scripts/attestations-workflow.sh

## Generate signed compliance report
[group('attestations')]
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
[group('attestations')]
sign-compliance-report report key_path="samples/oci-attestations/keys/cosign.key":
    @python3 scripts/generate-compliance-report.py sign \
        --report "{{report}}" \
        --key-path "{{key_path}}"

## Upload signed compliance report to OCI registry
[group('attestations')]
upload-compliance-report report signature registry username password repo:
    @python3 scripts/generate-compliance-report.py upload \
        --report "{{report}}" \
        --signature "{{signature}}" \
        --registry "{{registry}}" \
        --username "{{username}}" \
        --password "{{password}}" \
        --repo "{{repo}}"

# Legacy alias
alias push-to-harbor := push-to-registry

# ============================================================================
# DEPLOYMENT (deploy-*)
# ============================================================================

## Deploy production environment with real sigstore
[group('deployment')]
deploy:
    @echo "🚀 Deploying production environment with real sigstore"
    @docker compose -f certus_infrastructure/docker-compose.sigstore.yml up -d
    @docker compose -f certus_trust/deploy/docker-compose.prod.yml up -d --build

## Rollback to mock implementation
[group('deployment')]
rollback-mock:
    @echo "🔙 Rolling back to mock implementation"
    @docker compose -f certus_trust/deploy/docker-compose.rollback.yml up -d

## Verify deployment health
[group('deployment')]
verify-deployment:
    @echo "🔍 Verifying deployment"
    @curl -f http://localhost:3001 || echo "Rekor not ready"
    @curl -f http://localhost:5555 || echo "Fulcio not ready"
    @curl -f http://localhost:8057/health || echo "Certus Trust not ready"
    @docker compose -f certus_trust/deploy/docker-compose.prod.yml logs --tail=50

# ============================================================================
# DOCUMENTATION (docs-*)
# ============================================================================

## Serve documentation locally
[group('documentation')]
docs-serve:
    @./scripts/mkdocs-serve.sh

## Test if documentation can be built without warnings
[group('documentation')]
docs-test:
    @uv run mkdocs build -s

## Build documentation
[group('documentation')]
docs-build:
    @uv run mkdocs build

# Alias
alias docs := docs-serve

# ============================================================================
# UTILITIES (util-*)
# ============================================================================

## Launch multi-agent zellij workspace
[group('utilities')]
agents:
    @./scripts/dev.zellij.sh

## Clean Python artifacts
[group('utilities')]
util-clean:
    @echo "🧹 Cleaning Python artifacts"
    @find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    @find . -type f -name "*.pyc" -delete 2>/dev/null || true
    @rm -rf .pytest_cache .ruff_cache .mypy_cache

## Show environment info
[group('utilities')]
util-env-info:
    @echo "Python: $(python --version 2>&1)"
    @echo "Docker: $(docker --version 2>&1)"
    @echo "UV: $(uv --version 2>&1)"
    @echo "Just: $(just --version 2>&1)"

## Update dependencies
[group('utilities')]
util-update-deps:
    @uv sync --upgrade

# ============================================================================
# DOCKER COMPOSE HELPERS (compose-*)
# ============================================================================

## Docker compose build helper
[group('compose')]
compose-build services="":
    @if [ -z "{{services}}" ]; then \
        echo "🐳 docker compose build (all services)"; \
        docker compose build; \
    else \
        echo "🐳 docker compose build {{services}}"; \
        docker compose build {{services}}; \
    fi

## Docker compose up helper
[group('compose')]
compose-up services="":
    @if [ -z "{{services}}" ]; then \
        echo "🐳 docker compose up -d"; \
        docker compose up -d; \
    else \
        echo "🐳 docker compose up -d {{services}}"; \
        docker compose up -d {{services}}; \
    fi

## Docker compose down helper
[group('compose')]
compose-down remove_volumes="false":
    @if [ "{{remove_volumes}}" = "true" ]; then \
        echo "🐳 docker compose down -v"; \
        docker compose down -v; \
    else \
        echo "🐳 docker compose down"; \
        docker compose down; \
    fi
