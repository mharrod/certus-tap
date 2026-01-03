"""OpenSearch index setup utilities for logs and documents."""

from opensearchpy import OpenSearch, exceptions

from certus_ask.core.logging import get_logger

logger = get_logger(__name__)


def create_logs_index(client: OpenSearch, index_name: str = "logs-certus-tap") -> None:
    """
    Create the logs index with appropriate mappings and settings.

    This creates a time-based index for application logs with fields optimized
    for searching and aggregating log data.

    Args:
        client: OpenSearch client instance
        index_name: Name of the logs index to create

    Raises:
        Exception: If index creation fails
    """
    logger.info("logs_index.creation_start", index_name=index_name)

    mapping = {
        "mappings": {
            "properties": {
                "timestamp": {
                    "type": "date",
                    "format": "strict_date_time",
                },
                "level": {
                    "type": "keyword",  # For filtering/aggregation
                },
                "logger": {
                    "type": "keyword",
                },
                "message": {
                    "type": "text",  # Full-text searchable
                },
                "request_id": {
                    "type": "keyword",  # For tracing
                },
                "doc_id": {
                    "type": "keyword",  # Correlate with documents
                },
                "duration_ms": {
                    "type": "float",  # For performance analysis
                },
                "error_type": {
                    "type": "keyword",
                },
                "module": {
                    "type": "keyword",
                },
                "function": {
                    "type": "keyword",
                },
                "line_number": {
                    "type": "integer",
                },
                "process_id": {
                    "type": "integer",
                },
                "thread_name": {
                    "type": "keyword",
                },
                "method": {
                    "type": "keyword",
                },
                "path": {
                    "type": "keyword",
                },
                "client_ip": {
                    "type": "ip",
                },
                "status_code": {
                    "type": "integer",
                },
                "exc_info": {
                    "type": "text",
                },
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,  # Adjust for production
            "index.lifecycle.name": "logs-policy",  # For auto-cleanup
        },
    }

    try:
        if not client.indices.exists(index=index_name):
            client.indices.create(index=index_name, body=mapping)
            logger.info("logs_index.created", index_name=index_name)
        else:
            logger.info("logs_index.already_exists", index_name=index_name)

    except exceptions.RequestError as e:
        if "already exists" in str(e):
            logger.info("logs_index.already_exists", index_name=index_name)
        else:
            logger.exception("logs_index.creation_failed", index_name=index_name, error=str(e))
            raise

    except Exception as e:
        logger.exception("logs_index.creation_failed", index_name=index_name, error=str(e))
        raise


def create_ilm_policy(client: OpenSearch) -> None:
    """
    Create Index Lifecycle Management (ILM) policy for automatic log cleanup.

    This policy rolls over logs daily and deletes logs older than 30 days.

    Args:
        client: OpenSearch client instance

    Raises:
        Exception: If policy creation fails
    """
    logger.info("ilm_policy.creation_start", policy_name="logs-policy")

    policy = {
        "policy": {
            "phases": {
                "hot": {
                    "min_age": "0d",
                    "actions": {
                        "rollover": {
                            "max_age": "1d",  # New index daily
                            "max_size": "10gb",
                        }
                    },
                },
                "delete": {
                    "min_age": "30d",
                    "actions": {"delete": {}},
                },
            }
        }
    }

    try:
        client.transport.perform_request(
            "PUT",
            "/_plugins/_ism/policies/logs-policy",
            body=policy,
        )
        logger.info("ilm_policy.created", policy_name="logs-policy")

    except Exception as e:
        logger.exception("ilm_policy.creation_failed", policy_name="logs-policy", error=str(e))
        # Don't raise - ILM policy is optional


def setup_logs_infrastructure(
    client: OpenSearch,
    index_name: str = "logs-certus-tap",
) -> None:
    """
    Set up complete logging infrastructure in OpenSearch.

    This creates:
    - Logs index with proper mappings
    - ILM policy for automatic log rotation and cleanup

    Args:
        client: OpenSearch client instance
        index_name: Name of the logs index to create

    Raises:
        Exception: If setup fails
    """
    logger.info("logs_infrastructure.setup_start", index_name=index_name)

    try:
        create_logs_index(client, index_name)
        create_ilm_policy(client)

        logger.info(
            "logs_infrastructure.setup_complete",
            index_name=index_name,
            policy_name="logs-policy",
        )

    except Exception as e:
        logger.exception("logs_infrastructure.setup_failed", error=str(e))
        raise


__all__ = [
    "create_ilm_policy",
    "create_logs_index",
    "setup_logs_infrastructure",
]
