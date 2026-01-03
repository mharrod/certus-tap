"""
Real service dependencies extracted from certus_ask config

This module defines the actual services and dependencies used in the
TAP project, extracted from:
- docker-compose.yml
- certus_ask/core/config.py
- Environment variable configuration

These services and dependencies are used in the Neo4j spike to validate
the knowledge graph model against real project architecture.
"""

# Real services discovered from docker-compose.yml and config.py
REAL_SERVICES = [
    {
        "service_id": "ask-certus-backend",
        "name": "Ask Certus Backend",
        "description": "Main backend API for document analysis, ingestion, and querying",
        "criticality": "critical",
        "owner": "platform-team",
        "status": "active",
    },
    {
        "service_id": "opensearch",
        "name": "OpenSearch",
        "description": "Document and log storage/search. Handles both document indexing and application logging.",
        "criticality": "critical",
        "owner": "platform-team",
        "status": "active",
    },
    {
        "service_id": "opensearch-dashboards",
        "name": "OpenSearch Dashboards",
        "description": "UI for viewing documents and logs in OpenSearch",
        "criticality": "high",
        "owner": "platform-team",
        "status": "active",
    },
    {
        "service_id": "mlflow",
        "name": "MLflow",
        "description": "Experiment tracking and model management. Logs evaluation metrics and model performance.",
        "criticality": "high",
        "owner": "ml-team",
        "status": "active",
    },
    {
        "service_id": "localstack-s3",
        "name": "LocalStack S3",
        "description": "Data lake storage (S3-compatible). Stores raw and golden bucket data.",
        "criticality": "high",
        "owner": "data-team",
        "status": "active",
    },
    {
        "service_id": "llm-service",
        "name": "LLM Service",
        "description": "Large language model inference (Ollama or similar). Used for document analysis and Q&A.",
        "criticality": "critical",
        "owner": "ml-team",
        "status": "active",
    },
]

# Service dependencies as defined in docker-compose.yml and config.py
# Format: from_service depends_on to_service
REAL_SERVICE_DEPENDENCIES = [
    {
        "from": "ask-certus-backend",
        "to": "opensearch",
        "criticality": "critical",
        "description": "Stores documents, logs, and search results. Config: OPENSEARCH_HOST, OPENSEARCH_LOG_HOST",
    },
    {
        "from": "ask-certus-backend",
        "to": "mlflow",
        "criticality": "high",
        "description": "Logs experiment results and model metrics. Config: MLFLOW_TRACKING_URI",
    },
    {
        "from": "ask-certus-backend",
        "to": "localstack-s3",
        "criticality": "high",
        "description": "Accesses datalake for raw/golden data. Config: S3_ENDPOINT_URL (LocalStack)",
    },
    {
        "from": "ask-certus-backend",
        "to": "llm-service",
        "criticality": "critical",
        "description": "Calls LLM for document analysis and Q&A. Config: LLM_URL",
    },
    {
        "from": "opensearch-dashboards",
        "to": "opensearch",
        "criticality": "critical",
        "description": "Reads from OpenSearch for visualization. Config: OPENSEARCH_HOSTS",
    },
]

# Configuration endpoints extracted from config.py
SERVICE_ENDPOINTS = {
    "opensearch": {
        "host": "opensearch",
        "port": 9200,
        "protocol": "http",
        "env_vars": ["OPENSEARCH_HOST", "OPENSEARCH_LOG_HOST"],
    },
    "opensearch-dashboards": {
        "host": "opensearch-dashboards",
        "port": 5601,
        "protocol": "http",
        "env_vars": [],
    },
    "mlflow": {
        "host": "mlflow",
        "port": 5001,
        "protocol": "http",
        "env_vars": ["MLFLOW_TRACKING_URI"],
    },
    "localstack-s3": {
        "host": "localstack",
        "port": 4566,
        "protocol": "http",
        "env_vars": ["S3_ENDPOINT_URL"],
    },
    "llm-service": {
        "host": "ollama or custom",  # Not in docker-compose, external
        "port": 11434,
        "protocol": "http",
        "env_vars": ["LLM_URL"],
    },
}


def get_service_by_id(service_id: str) -> dict | None:
    """Look up a service by ID"""
    for svc in REAL_SERVICES:
        if svc["service_id"] == service_id:
            return svc
    return None


def get_dependencies_for_service(service_id: str) -> list[dict]:
    """Get all services that a given service depends on"""
    return [dep for dep in REAL_SERVICE_DEPENDENCIES if dep["from"] == service_id]


def get_dependents_of_service(service_id: str) -> list[dict]:
    """Get all services that depend on a given service (reverse dependency)"""
    return [dep for dep in REAL_SERVICE_DEPENDENCIES if dep["to"] == service_id]


if __name__ == "__main__":
    # Example usage
    print("=" * 70)
    print("Real Service Dependencies for Ask Certus Backend")
    print("=" * 70)
    print()

    print("Services:")
    for svc in REAL_SERVICES:
        print(f"  - {svc['service_id']:<20} ({svc['criticality']:<10}) {svc['name']}")
    print()

    print("Dependencies:")
    for dep in REAL_SERVICE_DEPENDENCIES:
        print(f"  {dep['from']:<25} → {dep['to']:<25} ({dep['criticality']})")
    print()

    print("Backend Service Dependencies:")
    deps = get_dependencies_for_service("ask-certus-backend")
    for dep in deps:
        print(f"  → {dep['to']:<25} ({dep['criticality']}) - {dep['description']}")
    print()

    print("Services depending on OpenSearch:")
    dependents = get_dependents_of_service("opensearch")
    for dep in dependents:
        print(f"  {dep['from']:<25} depends on OpenSearch")
