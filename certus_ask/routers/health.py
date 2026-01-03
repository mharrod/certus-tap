from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from certus_ask.core.config import settings
from certus_ask.core.metrics import get_ingestion_metrics, get_query_metrics, get_service_uptime
from certus_ask.services import datalake as datalake_service
from certus_ask.services.opensearch import get_document_store
from certus_ask.services.s3 import get_s3_client

router = APIRouter(prefix="/v1/health", tags=["health"])
EMBEDDING_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"


@router.get("")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ingestion")
async def ingestion_health() -> dict[str, str]:
    try:
        document_store = get_document_store()
        document_store.count_documents()
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=503, detail=f"Ingestion pipeline unavailable: {exc}") from exc
    return {"status": "ok"}


@router.get("/evaluation")
async def evaluation_health() -> dict[str, str]:
    try:
        client = get_s3_client()
        client.list_buckets()
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=503, detail=f"Evaluation pipeline unavailable: {exc}") from exc
    return {"status": "ok"}


@router.get("/embedder")
async def embedder_health() -> dict[str, str]:
    try:
        SentenceTransformer(EMBEDDING_MODEL_ID)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=503, detail=f"Embedding model unavailable: {exc}") from exc
    return {"status": "ok"}


@router.get("/datalake")
async def datalake_health() -> dict[str, str]:
    client = get_s3_client()
    try:
        datalake_service.initialize_datalake_structure(client)
        for bucket in (settings.datalake_raw_bucket, settings.datalake_golden_bucket):
            client.head_bucket(Bucket=bucket)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=503, detail=f"Datalake unavailable: {exc}") from exc
    return {"status": "ok"}


# ============================================================================
# Service Statistics
# ============================================================================


class ServiceStats(BaseModel):
    """Statistics about Ask service activity."""

    opensearch: dict[str, Any] = Field(..., description="OpenSearch document counts")
    neo4j: dict[str, Any] = Field(..., description="Neo4j knowledge graph statistics")
    ingestion: dict[str, Any] = Field(..., description="Ingestion operation statistics")
    query: dict[str, Any] = Field(..., description="Query operation statistics")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")
    timestamp: datetime = Field(..., description="When stats were generated")


@router.get("/stats", response_model=ServiceStats)
async def get_stats() -> ServiceStats:
    """
    Get statistics about Ask service activity.

    Useful for monitoring data volumes, ingestion patterns, and query performance.
    """
    # OpenSearch statistics
    opensearch_stats = {"total_documents": 0, "indices": []}
    try:
        doc_store = get_document_store()
        opensearch_stats["total_documents"] = doc_store.count_documents()
        opensearch_stats["default_index"] = "ask_certus"
    except Exception as e:
        opensearch_stats["error"] = str(e)

    # Neo4j statistics
    neo4j_stats = {"enabled": settings.neo4j_enabled}
    if settings.neo4j_enabled:
        try:
            from certus_ask.services.ingestion.neo4j_service import Neo4jClient

            client = Neo4jClient()
            with client.driver.session() as session:
                # Count SecurityScan nodes
                scan_count = session.run("MATCH (s:SecurityScan) RETURN count(s) as count").single()
                neo4j_stats["total_scans"] = scan_count["count"] if scan_count else 0

                # Count Finding nodes
                finding_count = session.run("MATCH (f:Finding) RETURN count(f) as count").single()
                neo4j_stats["total_findings"] = finding_count["count"] if finding_count else 0

                # Count Component nodes
                component_count = session.run("MATCH (c:Component) RETURN count(c) as count").single()
                neo4j_stats["total_components"] = component_count["count"] if component_count else 0
        except Exception as e:
            neo4j_stats["error"] = str(e)

    # Ingestion metrics
    ingestion_metrics = get_ingestion_metrics()
    ingestion_stats = ingestion_metrics.to_dict()

    # Query metrics
    query_metrics = get_query_metrics()
    query_stats = query_metrics.to_dict()

    return ServiceStats(
        opensearch=opensearch_stats,
        neo4j=neo4j_stats,
        ingestion=ingestion_stats,
        query=query_stats,
        uptime_seconds=get_service_uptime(),
        timestamp=datetime.now(timezone.utc),
    )
