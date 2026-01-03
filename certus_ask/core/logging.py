"""Structured logging configuration for Ask Certus Backend."""

import logging
import logging.handlers
from typing import Optional

import structlog


def configure_logging(
    level: str = "INFO",
    json_output: bool = True,
    opensearch_handler: Optional[logging.Handler] = None,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Whether to output JSON formatted logs
        opensearch_handler: Optional handler for OpenSearch logging
    """
    # Configure standard logging
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    if json_output:
        try:
            from pythonjsonlogger import jsonlogger

            formatter = jsonlogger.JsonFormatter()
        except ImportError:
            # Fallback if python-json-logger not installed
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    else:
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # OpenSearch handler (optional)
    if opensearch_handler:
        opensearch_handler.setLevel(level)
        root_logger.addHandler(opensearch_handler)

    # Configure structlog with stdlib integration
    # This sends logs through the standard logging system which captures our OpenSearch handler
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if json_output else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Bound structlog logger
    """
    return structlog.get_logger(name)
