# Privacy Monitoring Operations Guide

## Purpose
Outline day-to-day procedures for running the privacy logging system (PII detection, anonymization vs. quarantine decisions, incident review, and alerting).

## Audience & Prerequisites
- Privacy/compliance teams and platform operators.
- Requires access to the ingestion stack, OpenSearch Dashboards, and (optionally) alert destinations (email/Slack/SIEM).

## Overview
- Presidio/TruffleHog analyzers emit structured events via `certus_ask.services.privacy_logger`.
- Events include `privacy.pii_detected`, `privacy.entity_detected`, `privacy.high_confidence_pii_detected`, `document.privacy_anonymized`, and `document.privacy_quarantined`.
- Each event carries `document_id`, `document_name`, `entity_types`, `pii_entity_count`, `confidence`, `action`, and the request `trace_id`.
- Operators review Dashboards daily, tune strict mode/high-confidence thresholds, and respond to alerts when spikes occur.

## Key Concepts

### Workflow
1. **Upload** – ingestion logs `ingestion.document_upload_start`.
2. **Scan** – Presidio logs entities and aggregate counts.
3. **Decision** – `action` set to `ANONYMIZED`, `QUARANTINED`, or `REJECTED` depending on `strict_mode` and confidence thresholds.
4. **Index** – downstream ingestion completes (`ingestion.document_indexed_success`).

### Modes & Thresholds
```python
privacy_logger = PrivacyLogger(strict_mode=False)  # anonymize vs reject
PresidioAnonymizer(high_confidence_threshold=0.9)
```
- **Strict mode (True)** – any PII triggers quarantine/rejection.
- **Lenient mode (False)** – scrub/anonymize and continue indexing.

## Workflows / Operations

### Daily Review
1. Open Dashboards → Discover (`logs-*`).
2. Filter `logger:"certus_ask.services.privacy_logger"`.
3. Check:
   - Overnight incident count.
   - High-confidence events (`event: privacy.high_confidence_pii_detected`).
   - Quarantined documents (`action.keyword: QUARANTINED`).

### Incident Investigation
- **Spike in detections**
  ```json
  {
    "query": {
      "range": {"timestamp": {"gte": "now-2h"}},
      "term": {"event": "privacy.pii_detected"}
    },
    "aggs": {"by_document": {"terms": {"field": "document_name.keyword","size":100}}}
  }
  ```
  Review document samples, adjust analyzer patterns, or raise thresholds.

- **False positives**
  ```json
  {
    "query": {
      "bool": {
        "must": [
          {"term": {"event": "privacy.entity_detected"}},
          {"term": {"entity_type.keyword": "CREDIT_CARD"}},
          {"range": {"confidence": {"gte": 0.9}}}
        ]
      }
    }
  }
  ```
  Use results to add exclusions or custom recognizers.

### Alerting
- Create OpenSearch monitors:
  - High confidence PII: `event:privacy.high_confidence_pii_detected` with `doc_count > 0`.
  - Rate spike: compare current hour vs. daily average.
  - Quarantine events: `action.keyword:"QUARANTINED"`.
- Forward alerts to Slack/SIEM via `_plugins/_alerting` monitors or use Streamlit notifications.

## Configuration / Interfaces
- `.env` toggles `ENABLE_PRIVACY_LOGGING`, `STRICT_MODE`, and high-confidence thresholds via Presidio settings.
- Logs live in the same `logs-certus-tap-*` indices; follow [OpenSearch Logging Guide](opensearch.md) for retention policies. For longer retention, apply a dedicated ILM policy (e.g., 90-day retention) to copies of privacy events.

## Troubleshooting / Gotchas
- **No privacy events** – verify privacy middleware is enabled, Presidio dependencies are installed, and `SEND_LOGS_TO_OPENSEARCH=true`.
- **Excessive quarantines** – switch to lenient mode or raise the high-confidence threshold; review entity types causing noise.
- **Performance issues** – scan time visible in `privacy.scan_complete` events (`duration_ms`). Disable unnecessary entity types or offload scanning to separate workers.

## Related Documents
- [Privacy Investigation Queries](privacy-queries.md)
- [Logging Stack Component](../components/logging-stack.md)
- [OpenSearch Logging Guide](opensearch.md)
