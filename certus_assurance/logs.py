from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any


def _timestamp() -> float:
    return time.time()


@dataclass(slots=True)
class LogEvent:
    """Normalized payload emitted to WebSocket clients."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=_timestamp)

    def to_json(self) -> str:
        payload = {"type": self.type, "timestamp": self.timestamp, **self.data}
        return json.dumps(payload, ensure_ascii=False)


class LogStream:
    """In-memory queue for streaming scan events to WebSocket clients."""

    def __init__(self, job_id: str, loop: asyncio.AbstractEventLoop):
        self.job_id = job_id
        self._loop = loop
        self._queue: asyncio.Queue[LogEvent] = asyncio.Queue()
        self._history: list[LogEvent] = []
        self._closed = False
        self._lock = threading.Lock()

    @property
    def history(self) -> list[LogEvent]:
        return list(self._history)

    @property
    def queue(self) -> asyncio.Queue[LogEvent]:
        return self._queue

    def emit(self, event_type: str, **data: Any) -> None:
        event = LogEvent(type=event_type, data=data)
        with self._lock:
            if self._closed:
                return
            self._history.append(event)
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, event)
        except RuntimeError:
            # Event loop may be closed in test environments; keep history-only fallback.
            return

    def close(self, status: str, **data: Any) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        terminal = LogEvent(type="scan_complete", data={"status": status, **data})
        self._history.append(terminal)
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, terminal)
        except RuntimeError:
            return


class LogStreamManager:
    """Registry of log streams keyed by scan id."""

    def __init__(self) -> None:
        self._streams: dict[str, LogStream] = {}
        self._lock = threading.Lock()

    def register(self, job_id: str, loop: asyncio.AbstractEventLoop) -> LogStream:
        stream = LogStream(job_id, loop)
        with self._lock:
            self._streams[job_id] = stream
        return stream

    def get(self, job_id: str) -> LogStream | None:
        with self._lock:
            return self._streams.get(job_id)

    def pop(self, job_id: str) -> LogStream | None:
        with self._lock:
            return self._streams.pop(job_id, None)


log_stream_manager = LogStreamManager()
