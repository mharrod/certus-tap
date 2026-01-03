# Service Layer Migration

**Status:** In Progress (Phase 0 Complete)
**Author:** System Architecture
**Date:** 2025-12-07
**Last Updated:** 2025-12-13
## Executive Summary

Certus-Ask's FastAPI routers (especially `certus_ask/routers/ingestion.py`) contain thousands of lines of business logic, external service calls, and response handling. This router-centric architecture makes testing difficult, encourages tight coupling, and hinders reuse across CLI tools and background jobs.

We will migrate to a layered architecture: presentation (routers), service (business orchestration), and infrastructure (clients). This proposal offers **two migration strategies** with different risk/timeline tradeoffs:

- **Approach A (Full Migration):** Extract entire `_ingest_security_payload` (~600 lines) in one phase. Higher risk, faster timeline (5-7 days).
- **Approach B (Incremental Migration - RECOMMENDED):** Break extraction into 5 sub-phases. Lower risk, testable progress, longer timeline (10-12 days).

Both approaches achieve the same target architecture; they differ only in how we get there.

## Motivation

### Current Pain Points

- **God Routers:** Ingestion router handles HTTP parsing, SARIF/SPDX processing, Trust verification, S3 interactions, Neo4j operations, etc.
- **God Functions:** `_ingest_security_payload` is 600+ lines handling format detection, parsing, trust verification, Neo4j, embedding, and document writing.
- **Tight Coupling:** Routers instantiate dependencies directly (e.g., `boto3.client()`, `SarifToNeo4j()`), preventing dependency injection or mocking.
- **Poor Testability:** Business logic can only be tested via FastAPI test clients; unit tests require heavy patching.
- **Limited Reuse:** CLI scripts and background jobs can't reuse ingestion logic without importing routers.

### Desired Outcomes

- Routers focus on HTTP mechanics (request validation, response formatting).
- Service layer encapsulates business logic in reusable classes/components.
- Infrastructure clients abstract external dependencies (S3, Trust, Neo4j, etc.) with clear interfaces.
- Tests target services in isolation without HTTP overhead.

## Goals & Non-Goals

| Goals                                                                            | Non-Goals                                                    |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| Introduce presentation/service/infrastructure layers under `certus_ask/services` | Rewrite every router at once (migration will be incremental) |
| Move ingestion/security processing into reusable services                        | Change API contracts or the public schema of routers         |
| Improve test coverage via unit tests on service layer                            | Replace FastAPI or change how routers are registered         |
| Support future CLI/background jobs by reusing services                           | Address performance/scaling beyond refactoring scope         |

## Proposed Solution

### Target Architecture

```
Presentation Layer (Routers)
└── parse requests, call services, build responses

Service Layer (Business)
└── SecurityProcessor, FileProcessor, TrustVerificationService, Neo4jService, etc.

Infrastructure Layer
└── S3Client, TrustClient, Neo4jDriver, OpenSearchClient, etc.
```

- Router functions become thin controllers that validate input, call the appropriate service method, and translate service results into HTTP responses.
- Services live under `certus_ask/services/`, grouped by domain (ingestion/security, trust, storage). They accept dependencies via constructor or dependency injection.
- Infrastructure clients wrap boto3, Trust API, Neo4j driver, etc., centralizing configuration and mockability.

## Dependencies

- Existing `certus_ask/services/trust.py` and other utilities will be reused where possible.
- No external dependencies beyond current stack; requires internal reorganization only.
- Testing framework (pytest) remains the same; new unit tests added for service classes.

---

## Implementation Approaches

This proposal offers two migration strategies with different risk/timeline tradeoffs:

### Approach A: Full Migration (Higher Risk, Faster)

Extract entire `_ingest_security_payload` function (~600 lines) into `SecurityProcessor` in one phase. Achieves target architecture quickly but with higher debugging complexity.

**Pros:**

- ✅ Achieves clean architectural boundaries quickly (5-7 days)
- ✅ Clear separation of concerns from start
- ✅ Follows "do it right" philosophy
- ✅ Fewer intermediate states

**Cons:**

- ❌ Large change surface (~600 lines moved at once)
- ❌ Harder to debug when issues arise (multiple subsystems changed)
- ❌ Must mock 6+ dependencies simultaneously for testing
- ❌ Higher risk of breaking existing behavior
- ❌ Cannot merge incremental progress (all-or-nothing)
- ❌ Higher chance of "rewrite fatigue"

**Best For:**

- Teams with comprehensive test coverage
- Developers comfortable with large refactors
- Projects with time for extended debugging sessions
- Situations where clean architecture is critical upfront

**Timeline:** 5-7 days (all phases sequential)

---

### Approach B: Incremental Migration (Lower Risk, Recommended)

Break Phase 1 into 5 sub-phases (1a-1e). Extract logical subsystems incrementally while keeping orchestration in router initially. Gradually build toward full service layer.

**Pros:**

- ✅ Lower risk per change (~100 lines per sub-phase)
- ✅ Easier to isolate and debug issues (one subsystem at a time)
- ✅ Can merge and deploy progress weekly
- ✅ Each sub-phase delivers independently testable value
- ✅ Easier to pause/pivot if priorities change
- ✅ Steady forward momentum (less fatigue)
- ✅ Learn as you go (discover patterns early, adjust later phases)

**Cons:**

- ❌ Takes longer to reach full layering (10-12 days vs 5-7 days)
- ❌ Temporary "hybrid" state during migration
- ❌ More planning overhead

**Best For:**

- Research platforms (like Certus TAP)
- Teams prioritizing stability and learning
- Projects with shifting priorities
- First-time service layer migrations
- Situations where incremental delivery matters

**Timeline:** 10-12 days (but delivers value incrementally)

**Recommendation:** Based on Certus TAP's nature as a research/learning platform (per roadmap), **Approach B is recommended** for lower risk and steady progress.

---

## Phased Roadmap

### Phase 0 – Scaffolding (Day 1) ✅

**Status:** ✅ **COMPLETE** (2025-12-13)

- ✅ Created `certus_ask/services/ingestion/` directory structure
- ✅ Added placeholder service modules:
  - `security_processor.py` - SARIF/SPDX processing service
  - `file_processor.py` - General file ingestion service
  - `neo4j_service.py` - Neo4j graph operations service
  - `storage_service.py` - S3/file storage service
- ✅ Added `__init__.py` with clean exports
- ✅ Verified Python syntax valid, existing code unaffected

**Deliverable:** Foundation in place, ready for Phase 1

---

## Approach A Roadmap: Full Migration

### Phase 1 – Security Processing Extraction (Days 2-4)

- Move entire `_ingest_security_payload` logic (~600 lines) into `SecurityProcessor.process()`.
- Inject all dependencies via constructor:
  - `Neo4jService` for graph operations
  - `TrustClient` for verification (premium tier)
  - `DocumentStore` for OpenSearch
  - `DocumentEmbedder` for embeddings
  - `DocumentWriter` for persistence
- Update both router endpoints (`/index/security/upload`, `/index/security/s3`) to call `SecurityProcessor.process(...)`.
- Add comprehensive unit tests for `SecurityProcessor` covering:
  - SARIF parsing and document generation
  - SPDX parsing and document generation
  - JSONPath custom schema parsing
  - Pre-registered tools (Bandit, Trivy, etc.)
  - Trust verification (premium tier)
  - Neo4j integration (mocked)
  - Document embedding
  - Error handling for all formats

**Timeline:** 2-4 days
**Risk Level:** Medium-High (large change surface)
**Testing Effort:** High (must mock 6+ dependencies at once)
**Lines Moved:** ~600 lines

### Phase 2 – File/Document Processing (Days 5-6)

- Extract non-security ingestion paths (Markdown/text, general files) into `FileProcessor`.
- Replace router logic with service calls; ensure existing behavior (response schema, errors) remains unchanged.
- Add tests for `FileProcessor` focusing on splitting, metadata enrichment, and OpenSearch preparation.

### Phase 3 – Infrastructure Clients & Dependency Injection (Days 6-7)

- Introduce dedicated clients for S3, Neo4j, Trust, and other external services.
- Refactor services to use these clients; update dependency wiring (FastAPI dependency overrides).
- Add tests for clients (mocks/stubs) to ensure configuration and error handling are centralized.

### Phase 4 – Router Cleanup & Documentation (Days 7-8)

- Remove legacy helper functions from routers; ensure routers are thin.
- Update developer docs explaining the new architecture and how to add services.
- Expand test documentation to highlight unit tests vs. integration tests.
- Performance benchmarking (compare before/after)

**Total Timeline (Approach A):** 7-8 days (sequential, all-or-nothing)

---

## Approach B Roadmap: Incremental Migration (Recommended)

### Phase 1a – Neo4j Service Extraction (Days 2-3)

**Goal:** Extract Neo4j operations into testable service

**Tasks:**

- Implement `Neo4jService.load_sarif(sarif_data, scan_id, verification_proof, assessment_id)`
  - Wraps `SarifToNeo4j` instantiation and `load()` call
  - Returns graph result with node counts
- Implement `Neo4jService.load_spdx(spdx_data, sbom_id)`
  - Wraps `SpdxToNeo4j` instantiation and `load()` call
  - Returns graph result with package counts
- Implement `Neo4jService.generate_sarif_markdown(scan_id)`
  - Wraps `SarifToMarkdown` instantiation and `generate()` call
  - Returns markdown string
- Implement `Neo4jService.generate_spdx_markdown(sbom_id)`
  - Wraps `SpdxToMarkdown` instantiation and `generate()` call
  - Returns markdown string
- Accept Neo4j credentials (URI, user, password) via constructor
- Update `_ingest_security_payload` to call `Neo4jService` methods instead of inline Neo4j code
- Add unit tests with mocked Neo4j driver

**Lines Moved:** ~100 lines
**Risk Level:** Low
**Files Changed:**

- `certus_ask/services/ingestion/neo4j_service.py` (implement 4 methods)
- `certus_ask/routers/ingestion.py` (call service instead of inline code)
- `tests/services/ingestion/test_neo4j_service.py` (new file, 4 test cases)

**Deliverable:** Neo4j operations are testable in isolation, router still orchestrates

**Success Criteria:**

- ✅ All 4 Neo4jService methods have unit tests
- ✅ Existing integration tests pass
- ✅ No change to API behavior

---

### Phase 1b – Format Detection & Parsing (Days 3-5)

**Goal:** Extract format detection and parsing logic into testable methods

**Tasks:**

- Implement `SecurityProcessor.detect_format(filename, requested_format, tool_hint)` → `str`
  - Moves `_detect_security_format()` logic
  - Returns: "sarif", "spdx", "jsonpath", or raises `DocumentParseError`
- Implement `SecurityProcessor.parse_sarif(file_path)` → `(unified_scan, base_documents)`
  - Parses SARIF JSON using `parse_security_scan()`
  - Generates markdown summary + finding documents
  - Returns structured data for orchestration
- Implement `SecurityProcessor.parse_spdx(file_path)` → `(spdx_data, base_documents)`
  - Parses SPDX using `SpdxFileToDocuments`
  - Generates package documents
  - Returns structured data
- Implement `SecurityProcessor.parse_jsonpath(file_path, schema)` → `(unified_scan, base_documents)`
  - Parses custom JSONPath schemas
  - Handles validation via `SchemaLoader`
- Implement `SecurityProcessor.parse_preregistered_tool(file_path, tool_name)` → `(unified_scan, base_documents)`
  - Handles Bandit, Trivy, OpenGrep, etc.
  - Uses pre-registered schemas
- Add unit tests for each parser (mocked file I/O, focus on parse logic)

**Lines Moved:** ~250 lines
**Risk Level:** Low-Medium
**Files Changed:**

- `certus_ask/services/ingestion/security_processor.py` (add 5 parsing methods)
- `certus_ask/routers/ingestion.py` (call parsing methods)
- `tests/services/ingestion/test_security_processor.py` (5 test cases)

**Deliverable:** Parsing logic is testable, format-specific code is isolated

**Success Criteria:**

- ✅ Each format (SARIF, SPDX, JSONPath, pre-registered) has dedicated test
- ✅ Format detection logic handles edge cases (missing extensions, etc.)
- ✅ Existing integration tests pass

---

### Phase 1c – Trust Verification Extraction (Days 5-6)

**Goal:** Extract trust/premium tier verification into service layer

**Tasks:**

- Inject `TrustClient` into `SecurityProcessor` constructor (optional dependency)
- Implement `SecurityProcessor.verify_digest(file_bytes, artifact_locations, bucket, key)` → `str | None`
  - Moves `_enforce_verified_digest()` logic
  - Returns actual digest or raises `ValidationError`
  - Matches expected digest from artifact_locations
- Implement `SecurityProcessor.verify_trust_chain(signatures, artifact_locations)` → `verification_proof`
  - Calls `TrustClient.verify_chain()`
  - Validates chain_verified flag
  - Returns proof dict or raises `ValidationError`
- Add unit tests with mocked trust client
  - Test successful verification
  - Test failed verification (invalid signature)
  - Test missing digest
  - Test digest mismatch

**Lines Moved:** ~100 lines
**Risk Level:** Low
**Files Changed:**

- `certus_ask/services/ingestion/security_processor.py` (add 2 methods + trust_client field)
- `certus_ask/routers/ingestion.py` (call verification methods for premium tier)
- `tests/services/ingestion/test_security_processor.py` (4 test cases)

**Deliverable:** Trust verification is testable and isolated from parsing logic

**Success Criteria:**

- ✅ Premium tier verification works in isolation
- ✅ Free tier bypasses verification (no trust client needed)
- ✅ Digest mismatch raises ValidationError
- ✅ Existing integration tests pass

---

### Phase 1d – Document Generation & Embedding (Days 6-7)

**Goal:** Extract document creation and embedding logic into reusable methods

**Tasks:**

- Implement `SecurityProcessor.create_sarif_documents(unified_scan, metadata, neo4j_scan_id, verification_proof)` → `list[Document]`
  - Generates summary document with scan metadata
  - Generates individual finding documents
  - Attaches metadata (ingestion_id, workspace_id, tier, etc.)
  - Includes verification proof for premium tier
- Implement `SecurityProcessor.create_spdx_documents(spdx_data, metadata, neo4j_sbom_id)` → `list[Document]`
  - Generates SBOM summary document
  - Generates individual package documents
  - Attaches metadata
- Implement `SecurityProcessor.embed_documents(documents)` → `list[Document]`
  - Wraps `LoggingDocumentEmbedder` call
  - Uses configured embedding model
  - Returns documents with embeddings attached
- Add unit tests for document structure validation
  - Verify metadata fields present
  - Verify document content format
  - Verify embedding presence

**Lines Moved:** ~150 lines
**Risk Level:** Low
**Files Changed:**

- `certus_ask/services/ingestion/security_processor.py` (add 3 methods)
- `certus_ask/routers/ingestion.py` (call document methods)
- `tests/services/ingestion/test_security_processor.py` (3 test cases)

**Deliverable:** Document generation is testable, metadata structure is validated

**Success Criteria:**

- ✅ SARIF documents have correct metadata fields (source, record_type, etc.)
- ✅ SPDX documents have correct metadata fields
- ✅ Embedding is attached to documents
- ✅ Existing integration tests pass

---

### Phase 1e – Full Orchestration (Days 7-8)

**Goal:** Create master `SecurityProcessor.process()` method that orchestrates all helpers

**Tasks:**

- Implement `SecurityProcessor.process()` orchestration method:
  ```python
  async def process(
      self,
      workspace_id: str,
      file_bytes: bytes,
      source_name: str,
      requested_format: str,
      tool_hint: str | None = None,
      schema_dict: dict | str | None = None,
      ingestion_id: str,
      tier: str = "free",
      assessment_id: str | None = None,
      signatures: dict[str, Any] | None = None,
      artifact_locations: dict[str, Any] | None = None,
      s3_bucket: str | None = None,
      s3_key: str | None = None,
  ) -> SarifIngestionResponse:
      # 1. Detect format
      format = self.detect_format(filename, requested_format, tool_hint)

      # 2. Verify trust (if premium tier)
      verification_proof = None
      if tier == "premium":
          verification_proof = await self.verify_trust_chain(signatures, artifact_locations)
          self.verify_digest(file_bytes, artifact_locations, s3_bucket, s3_key)

      # 3. Parse based on format
      if format == "sarif":
          unified_scan, base_docs = self.parse_sarif(file_path)
          neo4j_scan_id = await self.neo4j_service.load_sarif(...)
          markdown = await self.neo4j_service.generate_sarif_markdown(neo4j_scan_id)
          documents = self.create_sarif_documents(unified_scan, metadata, neo4j_scan_id, verification_proof)
      elif format == "spdx":
          spdx_data, base_docs = self.parse_spdx(file_path)
          neo4j_sbom_id = await self.neo4j_service.load_spdx(spdx_data, workspace_id)
          markdown = await self.neo4j_service.generate_spdx_markdown(neo4j_sbom_id)
          documents = self.create_spdx_documents(spdx_data, metadata, neo4j_sbom_id)
      elif format == "jsonpath":
          unified_scan, base_docs = self.parse_jsonpath(file_path, schema_dict)
          documents = self.create_jsonpath_documents(unified_scan, metadata)

      # 4. Embed documents
      embedded = await self.embed_documents(documents)

      # 5. Write to document store
      self.writer.run(embedded)

      # 6. Return response
      return SarifIngestionResponse(
          request_id=get_request_id(),
          ingestion_id=ingestion_id,
          message=f"Indexed {findings_indexed} items from {source_name}",
          findings_indexed=findings_indexed,
          document_count=self.document_store.count_documents(),
          neo4j_scan_id=neo4j_scan_id,
          neo4j_sbom_id=neo4j_sbom_id,
      )
  ```
- Refactor `_ingest_security_payload` to thin wrapper:
  ```python
  async def _ingest_security_payload(...) -> SarifIngestionResponse:
      from certus_ask.core.config import Settings
      from certus_ask.services.ingestion import SecurityProcessor, Neo4jService
      from certus_ask.services.trust import get_trust_client

      settings = Settings()
      document_store = get_document_store_for_workspace(workspace_id)

      # Initialize services
      neo4j_service = Neo4jService(
          uri=settings.neo4j_uri,
          user=settings.neo4j_user,
          password=settings.neo4j_password,
      ) if settings.neo4j_enabled else None

      trust_client = get_trust_client() if tier == "premium" else None

      processor = SecurityProcessor(
          neo4j_service=neo4j_service,
          trust_client=trust_client,
          document_store=document_store,
      )

      return await processor.process(
          workspace_id=workspace_id,
          file_bytes=file_bytes,
          source_name=source_name,
          requested_format=requested_format,
          tool_hint=tool_hint,
          schema_dict=schema_dict,
          ingestion_id=ingestion_id,
          tier=tier,
          assessment_id=assessment_id,
          signatures=signatures,
          artifact_locations=artifact_locations,
          s3_bucket=s3_bucket,
          s3_key=s3_key,
      )
  ```
- Verify all integration tests pass (critical validation step)
- Update router endpoints to use thin wrapper

**Lines Moved:** ~50 lines (orchestration glue)
**Risk Level:** Low (all components already tested individually)
**Files Changed:**

- `certus_ask/services/ingestion/security_processor.py` (add `process()` orchestration method)
- `certus_ask/routers/ingestion.py` (refactor `_ingest_security_payload` to thin wrapper)

**Deliverable:** Router is thin (~500 lines), full service layer achieved for security ingestion

**Success Criteria:**

- ✅ `_ingest_security_payload` is < 30 lines (just service instantiation and delegation)
- ✅ All existing integration tests pass
- ✅ API behavior unchanged (same responses, errors, status codes)
- ✅ SecurityProcessor.process() has comprehensive unit test

---

### Phase 2 – File/Document Processing (Days 8-10)

**Goal:** Extract general file ingestion logic into `FileProcessor`

- Extract `index_document()` logic into `FileProcessor.process_file()`
- Extract `index_folder()` logic into `FileProcessor.process_folder()`
- Extract GitHub ingestion into `FileProcessor.process_github()`
- Move web scraping into `FileProcessor.process_web()`
- Add unit tests for each ingestion type

**Deliverable:** All ingestion types use service layer

---

### Phase 3 – Infrastructure Clients (Days 10-12)

**Goal:** Centralize external service clients for testability

- Create `StorageService.S3Client` wrapper (replace inline `boto3.client()` calls)
- Create `TrustClient` wrapper if not already abstracted (centralize trust service calls)
- Create `OpenSearchClient` wrapper (centralize document store operations)
- Ensure all clients use constructor injection for configuration (no globals)
- Add tests for each client (mocked external services)

**Deliverable:** All external dependencies are mockable, configuration centralized

---

### Phase 4 – Router Cleanup & Documentation (Days 12-13)

**Goal:** Final polish and documentation

- Remove all remaining helper functions from routers (`_metadata_preview_from_writer`, `_get_uploaded_file_size`, etc.)
- Ensure routers are pure HTTP handlers (validate request → call service → format response)
- Update architecture docs with C4 diagrams showing service layer
- Add developer guides:
  - "Adding a New Ingestion Service"
  - "Testing Service Layer Code"
  - "Dependency Injection Patterns"
- Performance benchmarking:
  - Compare ingestion latency before/after
  - Verify no regression in throughput
  - Document any performance impacts

**Deliverable:** Clean architecture, well-documented, production-ready

---

**Total Timeline (Approach B):** 12-13 days (delivers value incrementally each week)

---

## Deliverables

- ✅ New service modules under `certus_ask/services/ingestion/` with tests
- Updated routers that delegate to service layer classes
- Infrastructure clients wrapping S3, Trust, Neo4j, etc., with documentation
- Architecture documentation describing the layered approach
- Developer guides for working with service layer

## Success Metrics

1. **Router Size Reduction:** Ingestion router drops from ~2000 lines to ~500 lines focused on HTTP concerns
2. **Test Coverage:** Service layer gains unit tests covering core use cases without FastAPI test client
3. **Dependency Isolation:** All external dependencies accessed via dedicated clients (no `boto3.client` or direct imports in routers)
4. **Developer Onboarding:** Docs/guides explaining architecture; new contributors can add services without touching routers
5. **No Performance Regression:** Ingestion latency within 5% of baseline

## Risk Mitigation

### Approach A Risks

- **Large change surface:** Mitigate with comprehensive integration tests before/after
- **Debugging complexity:** Mitigate with extensive logging during migration
- **All-or-nothing:** Mitigate with feature flag to toggle old/new implementation

### Approach B Risks

- **Extended timeline:** Mitigate by allowing each sub-phase to be paused/resumed
- **Temporary hybrid state:** Mitigate with clear documentation of migration progress
- **Coordination overhead:** Mitigate with tracking issues per sub-phase

## Next Steps

1. ✅ **Phase 0 Complete** - Scaffolding in place
2. **Choose Approach:** Approve either Approach A or Approach B
3. **Create Tracking Issues:** One issue per phase/sub-phase
4. **Begin Implementation:** Start with chosen approach
5. **Weekly Check-ins:** Review progress, adjust timeline if needed

---

## Decision Log

| Date       | Decision                                | Rationale                                            |
| ---------- | --------------------------------------- | ---------------------------------------------------- |
| 2025-12-07 | Create service layer migration proposal | Address god router anti-pattern, improve testability |
| 2025-12-13 | Phase 0 scaffolding complete            | Foundation in place for either approach              |
| 2025-12-13 | Document Approach A and B options       | Allow informed choice between risk profiles          |
| TBD        | Select Approach A or B                  | Based on team preference and risk tolerance          |
