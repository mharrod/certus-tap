"""Async OpenSearch logging handler with graceful degradation."""

import json
import logging
import queue
import threading
import time
from contextlib import suppress
from datetime import datetime
from typing import Optional

from opensearchpy import OpenSearch, exceptions

logger = logging.getLogger(__name__)


class AsyncOpenSearchHandler(logging.Handler):
    """
    Non-blocking OpenSearch handler with background worker thread.

    This handler sends logs to OpenSearch asynchronously without blocking
    the main application thread. If OpenSearch is unavailable, the handler
    gracefully degrades and the application continues normally.

    Features:
    - Non-blocking async sending via background thread
    - Queue-based buffering for efficiency
    - Automatic reconnection with exponential backoff
    - Circuit breaker pattern for failed connections
    - Graceful handling when OpenSearch is down
    """

    def __init__(
        self,
        hosts: list[dict],
        index_name: str = "logs-certus-tap",
        batch_size: int = 100,
        queue_size: int = 1000,
        timeout: int = 5,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Initialize the async OpenSearch handler.

        Args:
            hosts: List of OpenSearch host dicts (e.g., [{"host": "localhost", "port": 9200}])
            index_name: Name of the index to write logs to
            batch_size: Number of logs to batch before sending
            queue_size: Maximum size of the log queue
            timeout: Connection timeout in seconds
            username: OpenSearch username (if auth required)
            password: OpenSearch password (if auth required)
        """
        super().__init__()
        self.index_name = index_name
        self.batch_size = batch_size
        self.queue: queue.Queue = queue.Queue(maxsize=queue_size)
        self.hosts = hosts
        self.timeout = timeout
        self.username = username
        self.password = password

        # State tracking
        self.client: Optional[OpenSearch] = None
        self.is_running = True
        self.connection_attempts = 0
        self.max_connection_retries = 3
        self.last_connection_error_time = 0
        self.reconnect_delay = 5  # Start with 5 second delay
        self._is_available = False

        # Initialize client
        self._init_client()

        # Start background worker thread
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="OpenSearchLogWorker",
        )
        self.worker_thread.start()

    def _init_client(self) -> bool:
        """
        Initialize OpenSearch client with error handling.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            kwargs = {
                "hosts": self.hosts,
                "timeout": self.timeout,
                "verify_certs": False,  # For dev; set True in production
                "ssl_show_warn": False,
            }

            if self.username and self.password:
                kwargs["http_auth"] = (self.username, self.password)

            self.client = OpenSearch(**kwargs)

            # Test connection
            self.client.info()
            self._is_available = True
        except Exception as e:
            self.connection_attempts += 1
            self.last_connection_error_time = time.time()
            self.client = None
            self._is_available = False
            import sys

            print(
                f"✗ OpenSearch connection failed (attempt {self.connection_attempts}): {e}", file=sys.stderr, flush=True
            )
            return False
        else:
            import sys

            print(f"✓ OpenSearch logging handler connected to {self.hosts[0]}", file=sys.stderr, flush=True)
            self.connection_attempts = 0
            self.last_connection_error_time = 0
            return True

    def emit(self, record: logging.LogRecord) -> None:
        """
        Queue a log record for sending to OpenSearch.

        This method is non-blocking. If OpenSearch is down, the log is either
        queued (if space available) or silently dropped.

        Args:
            record: The log record to emit
        """
        try:
            log_entry = self._format_record(record)
            if log_entry:  # Only queue if we got a valid entry
                self.queue.put_nowait(log_entry)
        except queue.Full:
            # Queue is full, silently drop (app continues)
            # In production, could increment a metric here
            logger.debug("OpenSearch log queue full; dropping log record")
        except Exception as exc:
            # Never let logging failures crash the app
            logger.exception("Failed to emit log to OpenSearch", exc_info=exc)

    def _worker_loop(self) -> None:
        """Background thread that sends logs to OpenSearch."""
        batch = []
        idle_count = 0

        while self.is_running:
            try:
                # Try to get a log with timeout
                try:
                    log_entry = self.queue.get(timeout=2)
                    batch.append(log_entry)
                    idle_count = 0
                except queue.Empty:
                    idle_count += 1
                    # Send partial batch if we've been idle
                    if batch and idle_count >= 2:
                        self._send_batch(batch)
                        batch = []

                # Send batch when full
                if len(batch) >= self.batch_size:
                    self._send_batch(batch)
                    batch = []

            except Exception as exc:
                # Prevent worker thread from dying
                logger.exception("OpenSearch log worker encountered an error", exc_info=exc)

    def _send_batch(self, batch: list) -> None:
        """
        Send a batch of logs to OpenSearch.

        Args:
            batch: List of log entry dicts to send
        """
        if not batch:
            return

        # Try to reconnect if client is None
        if self.client is None:
            if self._should_attempt_reconnect():
                self._init_client()
            else:
                # Still in backoff period
                return

        if not self.client:
            return

        try:
            for log_entry in batch:
                self.client.index(
                    index=self.index_name,
                    body=log_entry,
                )
        except exceptions.ConnectionError as e:
            print(f"ERROR: OpenSearch connection error: {e}")
            self.client = None
            self._is_available = False
        except Exception as e:
            print(f"ERROR: Failed to send logs to OpenSearch: {e}")
            self.client = None
            self._is_available = False

    def _should_attempt_reconnect(self) -> bool:
        """Check if enough time has passed to attempt reconnection."""
        if self.connection_attempts >= self.max_connection_retries:
            # Use exponential backoff
            delay = min(self.reconnect_delay * (2 ** (self.connection_attempts - 1)), 300)
            elapsed = time.time() - self.last_connection_error_time
            return elapsed >= delay

        return True

    @property
    def is_available(self) -> bool:
        """Return whether the handler currently has an OpenSearch connection."""
        return self._is_available

    def _format_record(self, record: logging.LogRecord) -> dict:
        """
        Convert a Python log record to a dict for OpenSearch.

        Attempts to parse structlog JSON messages and extract all fields.

        Args:
            record: The log record to format

        Returns:
            Dict representation of the log for OpenSearch
        """
        # Get message (may include exception info)
        message = record.getMessage()

        # Base log entry
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line_number": record.lineno,
            "process_id": record.process,
            "thread_name": record.threadName,
        }

        # Try to parse message as JSON (from structlog)
        try:
            parsed = json.loads(message)
            if isinstance(parsed, dict):
                # Merge all parsed fields into log_entry
                log_entry.update(parsed)
                # Ensure we have a message field
                if "message" not in log_entry and "msg" in parsed:
                    log_entry["message"] = parsed["msg"]
            else:
                log_entry["message"] = message
        except (json.JSONDecodeError, ValueError):
            # If not JSON, just use as message
            log_entry["message"] = message

        # Always ensure we have a message field for readability
        if "message" not in log_entry:
            log_entry["message"] = str(message)[:500]  # Truncate very long messages

        # Add exception info if present
        if record.exc_info:
            exc_info = self.format(record)
            log_entry["exc_info"] = exc_info

        # Include extra attributes from the LogRecord (e.g., structlog context)
        standard_attrs = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
        }
        for attr, value in record.__dict__.items():
            if attr not in standard_attrs and not attr.startswith("_"):
                log_entry.setdefault(attr, value)

        return log_entry

    def flush(self) -> None:
        """Flush any remaining buffered logs (called on shutdown)."""
        with suppress(Exception):
            # Give worker thread a moment to finish
            self.worker_thread.join(timeout=5)

    def close(self) -> None:
        """Close the handler and stop the background thread."""
        self.is_running = False
        with suppress(Exception):
            self.worker_thread.join(timeout=5)
        super().close()
