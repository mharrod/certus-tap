# Security Notes

Certus-Integrity doesn’t run as a standalone network service, but it enforces guardrails inside host applications.

## Rate Limiting & Shadow Mode

- Environment variables control limits (`INTEGRITY_RATE_LIMIT_PER_MIN`, `INTEGRITY_BURST_LIMIT`).
- Shadow mode (`INTEGRITY_SHADOW_MODE=true`) logs violations but does not block; useful during rollout.
- Whitelist (`INTEGRITY_WHITELIST_IPS`) bypasses throttling for trusted networks.

## Evidence Generation

- Every decision (allow/deny) is serialized via `EvidenceGenerator` with trace/span IDs, enabling forensic review.
- Evidence processing runs asynchronously; ensure the background task queue/storage is resilient in production.

## Presidio Integration

- If Presidio is unavailable, the module falls back to regex-based detection to avoid outages.
- When running with full Presidio, make sure models (spaCy) are bundled with the host service image.

## Telemetry

- `configure_observability` instruments FastAPI with OpenTelemetry. Exporters inherit credentials/targets from host settings.
- Adopt consistent sampling policies; middleware telemetry surfaces guardrail status (`integrity.decision`, etc.).

## Residual Risks

- Misconfigured rate limits can deny valid traffic; monitor `/health/stats` counters in the host app.
- Evidence bundles contain metadata (IP addresses, reasons). Handle storage/transmission securely.
- Presidio fallback (regex) is less accurate; alert when `_PRESIDIO_AVAILABLE` is false to ensure teams install the full dependency chain.
