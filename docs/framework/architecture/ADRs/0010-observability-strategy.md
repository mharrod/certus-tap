# ADR 0010 – Unified Observability Strategy

## Status

Accepted – November 2025

## Context

Certus TAP spans multiple services (Ask, Evaluate, Assurance, Transform, Trust, Integrity). Early debugging required jumping between disparate logging formats, ad hoc metrics, and siloed tracing. We needed a unified observability approach that lets operators trace a single workflow (scan → transform → query → evaluation) across services and environments (hybrid, self-hosted, SaaS).

## Decision

Adopt the following observability standards:

1. **OpenTelemetry Everywhere:** All services emit traces/spans using OpenTelemetry SDKs. Requests propagate `traceparent` headers; fall back to `X-Request-ID` when necessary.
2. **OpenSearch / Dashboards:** Use the shared OpenTelemetry collector to ship traces/logs to OpenSearch (or a compatible backend). Provide saved dashboards for guardrail denials, evaluation pass rates, and scan status.
3. **Structured Logging Schema:** Every log line includes `service_name`, `workspace_id`, `test_id`, `evidence_id`, `manifest_digest`, and `request_id` (when applicable). JSON logging is enforced across services (ADR-0001).
4. **Metrics / Histograms:** Expose Prometheus/OpenTelemetry metrics for key workflows (scan durations, evaluation latency, guardrail denials per type, upload permission latency). Use consistent metric names and labels.
5. **MLflow for Experiments:** certus-evaluate logs metrics and evidence references to MLflow runs; Assurance can also log scan metadata as part of regression testing.
6. **Evidence Correlation:** All evidence IDs and upload permissions include trace IDs so operators can pivot from MLflow/OpenSearch back to signed artifacts.

## Consequences

- Operators can follow an issue end-to-end via shared trace IDs.
- Alerting rules (OpenSearch, Prometheus) can watch for guardrail spikes or failing evaluations in real time.
- MLflow runs become first-class audit artifacts because they are tied to evidence IDs.
- Services must keep their OpenTelemetry instrumentation up to date; new services must adopt the same schema.
