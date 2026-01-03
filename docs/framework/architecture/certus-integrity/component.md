# Component View

```mermaid
graph TB
    subgraph certus_integrity
        Middleware["middleware.IntegrityMiddleware"]
        Evidence["evidence.EvidenceGenerator"]
        TelemetryCfg["telemetry.configure_observability"]
        PresidioSvc["services.presidio (get_analyzer/get_anonymizer)"]
    end

    Middleware --> Evidence
    Middleware --> TelemetryCfg
    Middleware --> HostRequest["FastAPI Request Context"]
    HostRequest --> PresidioSvc
```

| Component                  | Responsibilities                                                                  |
| -------------------------- | ---------------------------------------------------------------------------------- |
| IntegrityMiddleware        | Rate limiting, shadow mode, evidence generation, rate-limit headers, logging.     |
| EvidenceGenerator          | Background task that writes JSON bundles describing guardrail decisions.          |
| Telemetry helpers          | Instruments FastAPI with OpenTelemetry spans/metrics (used by host services).     |
| Presidio services          | Provide analyzer/anonymizer objects (Presidio when available, regex fallback).    |
