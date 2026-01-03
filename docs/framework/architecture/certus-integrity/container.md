# Container View

Since certus-integrity is embedded, the “container” view focuses on how it plugs into a host service.

```mermaid
graph LR
    Client["Client Request"] --> IntegrityMW["IntegrityMiddleware"]
    IntegrityMW --> HostApp["FastAPI Application"]

    IntegrityMW --> Evidence["Evidence Generator (evidence.py)"]
    IntegrityMW --> Telemetry["Telemetry (telemetry.py + OTel exporters)"]
    HostApp --> Presidio["Presidio Services (services.presidio)"]

    FastAPIMetrics["OTel Collector / Metrics Backend"]:::ext <-- Telemetry

    classDef ext fill:#2c2e3e,stroke:#c6a76b,color:#f5f5f2;
```

| Component                | Notes                                                                                   |
| ------------------------ | --------------------------------------------------------------------------------------- |
| IntegrityMiddleware      | Wraps incoming requests, applies rate limits, emits evidence, adds headers.           |
| Evidence Generator       | Async writer that persists decision metadata (transport agnostic).                    |
| Telemetry Helpers        | `configure_observability` instruments FastAPI + logs/metrics/traces.                 |
| Presidio Services        | Provides analyzer/anonymizer instances via `get_analyzer` and `get_anonymizer`.      |
| Host FastAPI App         | Loads the middleware + services to protect its own routes.                            |
