# Privacy Investigation Queries

## Purpose
Provide ready-to-use OpenSearch queries for investigating PII detections, quarantine events, and privacy anomalies captured by the `certus_ask.services.privacy_logger`.

## Audience & Prerequisites
- Privacy analysts and security engineers triaging incidents.
- Needs access to the `logs-certus-tap-*` indices in OpenSearch Dashboards or REST API.

## Overview
Privacy events share the `logger: "certus_ask.services.privacy_logger"` context and emit event names such as `privacy.pii_detected`, `privacy.entity_detected`, `privacy.high_confidence_pii_detected`, and `privacy.quarantined`. Use the snippets below in Dashboards (KQL) or `_search` requests to explore incidents.

## Key Concepts

### Core Queries
- **All privacy logs**
  ```json
  {
    "query": {
      "bool": {
        "filter": [
          {"term": {"logger": "certus_ask.services.privacy_logger"}}
        ]
      }
    }
  }
  ```
- **PII detections**
  ```json
  { "query": { "term": { "event": "privacy.pii_detected" } } }
  ```
- **High-confidence detections**
  ```json
  { "query": { "term": { "event": "privacy.high_confidence_pii_detected" } } }
  ```
- **Quarantined artifacts**
  ```json
  {
    "query": {
      "bool": {
        "must": [
          {"term": {"event": "privacy.pii_detected"}},
          {"term": {"action.keyword": "QUARANTINED"}}
        ]
      }
    }
  }
  ```

### Aggregations
- **PII type frequency**
  ```json
  {
    "size": 0,
    "query": {"term": {"event": "privacy.entity_detected"}},
    "aggs": {"entity_types": {"terms": {"field": "entity_type.keyword","size":50}}}
  }
  ```
- **Incidents over time**
  ```json
  {
    "size": 0,
    "query": {"term": {"event": "privacy.pii_detected"}},
    "aggs": {
      "by_hour": {
        "date_histogram": {"field": "timestamp","fixed_interval":"1h"},
        "aggs": {
          "total_entities": {"sum":{"field":"pii_entity_count"}},
          "unique_documents": {"cardinality":{"field":"document_id.keyword"}}
        }
      }
    }
  }
  ```
- **Action breakdown (anonymized vs quarantined)**
  ```json
  {
    "size": 0,
    "query": {"term": {"event": "privacy.pii_detected"}},
    "aggs": {"by_action": {"terms": {"field": "action.keyword"}}}
  }
  ```

## Workflows / Operations
1. **Identify high-risk documents**
   ```json
   {
     "query": {
       "bool": {
         "must": [
           {"term": {"event": "privacy.high_confidence_pii_detected"}},
           {"range": {"confidence": {"gte": 0.95}}}
         ]
       }
     },
     "_source": ["document_id","document_name","entity_types","confidence"]
   }
   ```
2. **Track repeat offenders (same document repeatedly contains PII)**
   ```json
   {
     "size": 0,
     "query": {"term": {"event": "privacy.pii_detected"}},
     "aggs": {
       "repeat_documents": {
         "terms": {"field": "document_name.keyword","min_doc_count":2,"size":100}
       }
     }
   }
   ```
3. **Trace a document’s privacy lifecycle**
   ```json
   {
     "query": {"term": {"document_id.keyword": "DOC-123"}},
     "sort": [{"timestamp": {"order": "asc"}}],
     "_source": ["timestamp","event","action","pii_entity_count","message"]
   }
   ```

## Configuration / Interfaces
- Use the `logs-*` data view in Dashboards; filter by `logger:"certus_ask.services.privacy_logger"`.
- Fields of interest:
  - `document_id`, `document_name`
  - `entity_types`, `pii_entity_count`, `confidence`
  - `action` (`ANONYMIZED`, `QUARANTINED`)
  - `workspace_id`, `ingestion_id`

## Troubleshooting / Gotchas
- **No privacy events present** – ensure the privacy logger is enabled (see `.env` `ENABLE_PRIVACY_LOGGING`) and Presidio/trufflehog pipelines are active.
- **Duplicate hits** – multiple entities per document intentionally emit separate `privacy.entity_detected` events; use aggregations to deduplicate per document.
- **False positives** – review high-confidence results manually and tune Presidio analyzers if needed.

## Related Documents
- [Privacy Operations Guide](privacy-operations.md)
- [Logging Stack Component](../components/logging-stack.md)
- [OpenSearch Logging Guide](opensearch.md)
