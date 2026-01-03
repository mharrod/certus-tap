"""Fixed IntegrityMiddleware with corrected rate limiting logic."""

import asyncio
import os
import time
import uuid
from collections import defaultdict, deque

from opentelemetry import metrics, trace
from opentelemetry.trace import SpanKind
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from certus_integrity.evidence import EvidenceGenerator
from certus_integrity.schemas import IntegrityDecision

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter("certus.integrity")

decision_counter = meter.create_counter(
    "integrity_decisions_total",
    description="Total number of integrity decisions made",
    unit="1",
)

check_duration = meter.create_histogram(
    "integrity_check_duration_seconds",
    description="Duration of integrity checks",
    unit="s",
)

rate_limit_violations = meter.create_counter(
    "integrity_rate_limit_violations_total",
    description="Total number of rate limit violations",
    unit="1",
)


class IntegrityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.rate_limit = int(os.getenv("INTEGRITY_RATE_LIMIT_PER_MIN", "100"))
        self.burst_limit = int(os.getenv("INTEGRITY_BURST_LIMIT", "20"))
        self.shadow_mode = os.getenv("INTEGRITY_SHADOW_MODE", "true").lower() == "true"
        self._request_history: dict[str, deque[float]] = defaultdict(deque)
        self._last_cleanup = time.time()

        # Whitelist for internal services
        whitelist_str = os.getenv("INTEGRITY_WHITELIST_IPS", "127.0.0.1,172.18.0.0/16")
        self.whitelist = set(whitelist_str.split(",")) if whitelist_str else set()

        # Initialize Evidence Generator
        self.evidence_generator = EvidenceGenerator(service_name="certus-ask")

    def _is_whitelisted(self, ip: str) -> bool:
        """Check if IP is whitelisted (no rate limiting)."""
        if ip in self.whitelist:
            return True

        # Check CIDR ranges
        try:
            import ipaddress

            ip_obj = ipaddress.ip_address(ip)
            for entry in self.whitelist:
                if "/" in entry:
                    network = ipaddress.ip_network(entry, strict=False)
                    if ip_obj in network:
                        return True
        except (ValueError, ImportError):
            pass

        return False

    def _cleanup_old_entries(self):
        """Periodically clean up empty IP entries to prevent memory leak."""
        now = time.time()
        # Only cleanup every 5 minutes
        if now - self._last_cleanup < 300:
            return

        self._last_cleanup = now

        # Remove IPs with no recent activity
        empty_ips = [ip for ip, history in self._request_history.items() if not history]
        for ip in empty_ips:
            del self._request_history[ip]

    def _is_rate_limited(self, ip: str) -> tuple[bool, int]:
        """
        Check if IP has exceeded rate limit.

        Returns:
            (is_limited, remaining_requests)
        """
        if self.rate_limit <= 0:
            return False, self.rate_limit

        now = time.time()
        history = self._request_history[ip]

        # Remove timestamps older than 60s (sliding window)
        while history and history[0] < now - 60:
            history.popleft()

        # Check burst protection (last 10 seconds)
        recent_count = sum(1 for ts in history if ts > now - 10)
        if recent_count >= self.burst_limit:
            return True, 0

        # Check overall rate limit
        if len(history) >= self.rate_limit:
            return True, 0

        # Not limited - calculate remaining
        remaining = self.rate_limit - len(history)

        return False, remaining

    def _record_request(self, ip: str):
        """Record a successful request timestamp for rate limiting."""
        now = time.time()
        self._request_history[ip].append(now)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.time()
        decision = "allowed"
        guardrail = "none"
        reason = "pass_through"
        trace_id = format(trace.get_current_span().get_span_context().trace_id, "032x")
        span_id = format(trace.get_current_span().get_span_context().span_id, "016x")

        # Periodic cleanup
        self._cleanup_old_entries()

        # 1. Start Span
        with tracer.start_as_current_span(
            "integrity.request",
            kind=SpanKind.SERVER,
        ) as span:
            # 2. Rate Limit Check
            # Check X-Forwarded-For header first (for proxied requests), then fall back to direct client IP
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                # X-Forwarded-For can contain multiple IPs, take the first one (original client)
                client_ip = forwarded_for.split(",")[0].strip()
            else:
                client_ip = request.client.host if request.client else "unknown"

            # Skip rate limit for whitelisted IPs
            is_limited = False
            remaining = self.rate_limit

            if not self._is_whitelisted(client_ip):
                is_limited, remaining = self._is_rate_limited(client_ip)

            if is_limited:
                guardrail = "rate_limit"
                reason = "rate_limit_exceeded"

                # Record violation metric
                rate_limit_violations.add(
                    1,
                    {
                        "client_ip": client_ip if client_ip != "unknown" else "unknown",
                        "shadow_mode": str(self.shadow_mode),
                    },
                )

                if self.shadow_mode:
                    decision = "allowed"
                    span.set_attribute("integrity.shadow_violation", True)
                else:
                    decision = "denied"

            # 3. Graph Budget Check (Placeholder)
            if decision == "allowed" and "/query" in request.url.path:
                span.set_attribute("integrity.graph_budget_check", "skipped_phase2")

            # 4. Record Telemetry
            duration = time.time() - start_time
            check_duration.record(duration, {"guardrail": "all"})

            decision_counter.add(
                1,
                {
                    "decision": decision,
                    "guardrail": guardrail,
                    "reason": reason,
                    "shadow_mode": str(self.shadow_mode),
                    "service": "certus-ask",
                },
            )

            span.set_attributes({
                "integrity.decision": decision,
                "integrity.guardrail": guardrail,
                "integrity.reason": reason,
                "integrity.shadow_mode": self.shadow_mode,
                "integrity.client_ip": client_ip if client_ip != "unknown" else "unknown",
            })

            # 5. Generate Evidence Bundle (Async / Fire-and-Forget)
            decision_obj = IntegrityDecision(
                decision_id=str(uuid.uuid4()),
                trace_id=trace_id,
                span_id=span_id,
                service="certus-ask",
                decision=decision,  # type: ignore
                reason=reason,
                guardrail=guardrail,
                metadata={"client_ip": client_ip, "shadow_mode": self.shadow_mode, "duration_ms": duration * 1000},
            )

            # Store reference to prevent garbage collection
            if not hasattr(self, "background_tasks"):
                self.background_tasks = set()

            task = asyncio.create_task(self.evidence_generator.process_decision(decision_obj))
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

            # 6. Enforce Decision
            if decision == "denied":
                now = int(time.time())
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": "Too many requests. Please try again later.",
                        "trace_id": trace_id,
                        "retry_after": 60,
                    },
                    headers={
                        "X-RateLimit-Limit": str(self.rate_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(now + 60),
                        "Retry-After": "60",
                    },
                )

            # Record the request timestamp for rate limiting (BEFORE calling next, so it counts immediately)
            if not is_limited and not self._is_whitelisted(client_ip):
                self._record_request(client_ip)

            # 7. Connect to Application
            response = await call_next(request)

            # Add rate limit headers to successful responses
            now = int(time.time())
            response.headers["X-RateLimit-Limit"] = str(self.rate_limit)
            response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
            response.headers["X-RateLimit-Reset"] = str(now + 60)

            return response
