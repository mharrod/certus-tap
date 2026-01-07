# Additional Sections for Certus-Evaluate Implementation Guide

## INSERT AFTER "Architecture" SECTION (around line 203)

---

## Understanding LLM-as-Judge in RAGAS

### What is LLM-as-Judge?

**LLM-as-Judge** is an evaluation paradigm where a Large Language Model acts as the evaluator to assess the quality of another LLM's outputs. Instead of rule-based metrics or exact-match comparisons, an LLM examines the response and provides a judgment based on natural language understanding.

**Why RAGAS Uses LLM-as-Judge:**

RAGAS (Retrieval Augmented Generation Assessment) evaluates RAG systems by having an LLM analyze:
- **Semantic similarity** (not just keyword matching)
- **Logical consistency** (does the response contradict the context?)
- **Relevance** (does the answer address the query?)
- **Completeness** (is all necessary information included?)

This is fundamentally different from traditional metrics like BLEU or ROUGE, which rely on n-gram overlap.

### How RAGAS Metrics Work

#### 1. Faithfulness (LLM-based)

**Question**: Is the generated response grounded in the provided context?

**Method**:
1. LLM extracts "claims" from the generated response
2. For each claim, LLM checks if it's supported by the context
3. Score = (supported claims) / (total claims)

**Example**:
```
Query: "What is Certus?"
Context: ["Certus is a trust automation platform", "It provides security scanning"]
Response: "Certus is a trust automation platform that offers security scanning and blockchain verification"

LLM Analysis:
- Claim 1: "Certus is a trust automation platform" ✅ Supported by context
- Claim 2: "offers security scanning" ✅ Supported by context
- Claim 3: "blockchain verification" ❌ NOT in context

Faithfulness Score: 2/3 = 0.67
```

**Cost**: ~2-3 LLM calls per evaluation (claim extraction + verification)

#### 2. Answer Relevancy (LLM + Embeddings)

**Question**: Does the response actually answer the query?

**Method**:
1. LLM generates hypothetical questions that the response would answer
2. Compute embedding similarity between original query and generated questions
3. High similarity = response is relevant to the query

**Example**:
```
Query: "How do I configure MLflow?"
Response: "MLflow is a platform for managing ML workflows including tracking experiments and model registry."

LLM generates hypothetical questions this response would answer:
- "What is MLflow?"
- "What does MLflow do?"
- "What features does MLflow have?"

Embedding similarity with original query: 0.65 (medium - response doesn't answer "how to configure")

Answer Relevancy Score: 0.65
```

**Cost**: ~1 LLM call + embeddings for similarity

#### 3. Context Precision (LLM-based, requires reference)

**Question**: Are the retrieved context chunks ranked correctly? (Most relevant first)

**Method**:
1. For each context chunk, LLM determines if it's useful for answering the query
2. Compute precision@k (how many of the top-k chunks are relevant)
3. Penalizes irrelevant chunks appearing before relevant ones

**Requires**: Ground-truth answer to determine relevance

**Cost**: ~N LLM calls (where N = number of context chunks)

#### 4. Context Recall (LLM-based, requires reference)

**Question**: Did we retrieve all the necessary context?

**Method**:
1. LLM extracts "sentences" from the ground-truth answer
2. For each sentence, LLM checks if it can be attributed to the retrieved context
3. Score = (attributable sentences) / (total sentences)

**Requires**: Ground-truth answer

**Cost**: ~M LLM calls (where M = sentences in ground-truth)

### Cost Implications

**Typical Evaluation Cost Breakdown** (using GPT-4):

| Metric | LLM Calls | Avg Tokens | Cost per Eval |
|--------|-----------|------------|---------------|
| Faithfulness | 2-3 | 1000 input + 300 output | ~$0.05 |
| Answer Relevancy | 1 | 500 input + 200 output | ~$0.02 |
| Context Precision | N (3-5 chunks) | 400 input + 50 output per chunk | ~$0.06 |
| Context Recall | M (2-4 sentences) | 400 input + 50 output per sentence | ~$0.04 |
| **Total per Evaluation** | **7-13 calls** | **~4000 tokens** | **~$0.17** |

**Monthly Cost Projection** (1 workspace, 1000 queries/day):
- 100% evaluation: 30,000 evals/month × $0.17 = **$5,100/month**
- 10% sampling: 3,000 evals/month × $0.17 = **$510/month**
- With GPT-3.5-turbo (10× cheaper): **$51/month** (10% sampling)

### Why Reference Data is Critical

**Without Ground Truth** (Phase 1 limitation):
- ✅ Can compute: Faithfulness, Answer Relevancy
- ❌ Cannot compute: Context Precision, Context Recall
- ⚠️ Reduced confidence: No baseline to compare against

**With Reference Dataset** (Phase 2+):
- ✅ All 4 metrics computable
- ✅ Can detect regressions (scores drop vs. baseline)
- ✅ Can tune retrieval (optimize context precision/recall)
- ✅ Human-approved "ideal" responses provide objective standard

### LLM Provider Considerations

**Supported Providers** (via RAGAS):

| Provider | Models | Pros | Cons |
|----------|--------|------|------|
| OpenAI | GPT-4, GPT-3.5-turbo | Best accuracy, fast | Most expensive |
| Anthropic | Claude 3 (Opus, Sonnet) | Good reasoning, long context | Slower, expensive |
| Azure OpenAI | GPT-4, GPT-3.5-turbo | Enterprise SLA, compliance | Requires Azure setup |
| Local (Ollama) | Llama-3, Mistral | Free, private | Lower quality scores |

**Recommendation**: Start with GPT-4 for faithfulness/relevancy, GPT-3.5-turbo for precision/recall.

### Latency Considerations

**Typical Evaluation Latency**:
- **Faithfulness**: 3-5 seconds (sequential LLM calls)
- **Answer Relevancy**: 1-2 seconds (parallel: LLM + embeddings)
- **Context Precision**: 2-4 seconds (can parallelize per-chunk)
- **Context Recall**: 2-3 seconds (can parallelize per-sentence)

**Total p50 latency**: ~5-8 seconds (with parallelization)
**Total p99 latency**: ~12-15 seconds (rate limits, retries)

**Mitigation Strategies**:
1. **Async execution** (don't block Ask responses)
2. **Caching** (identical Q&A → free result)
3. **Sampling** (evaluate 10% instead of 100%)
4. **Batch processing** (offline nightly evaluations)

---

## INSERT AFTER "Data Models" SECTION (around line 388)

---

## Reference Dataset Lifecycle

### Overview

A **reference dataset** is a curated collection of query-response-context triplets that represent the "ground truth" for your RAG system. Each entry has been **human-reviewed and approved** to serve as the ideal benchmark for evaluation.

**Purpose**:
- Provide objective baseline for evaluation metrics
- Enable context precision/recall computation (requires ground truth)
- Detect regressions when RAG quality degrades
- Guide improvements (show where system fails vs. ideal)

**Ownership**: Each Certus-Ask workspace team owns their reference dataset quality and freshness.

### Dataset Structure

Each reference entry contains:

```python
{
  "query_signature": "what is certus trust automation platform",  # Normalized query
  "ideal_response": "Certus is a trust automation platform that provides...",
  "vetted_context": [
    "Certus TAP (Trust Automation Platform) enables...",
    "The platform includes security scanning, integrity verification..."
  ],
  "workspace_id": "acme",
  "approved_by": "alice@acme.com",
  "approved_at": "2025-12-28T10:30:00Z",
  "version": 1,
  "tags": ["core-product", "onboarding"],
  "notes": "Updated to reflect v2.0 capabilities"
}
```

**Key Fields**:
- `query_signature`: Normalized query for lookup (lowercase, whitespace collapsed)
- `ideal_response`: Human-written "perfect" answer
- `vetted_context`: Chunks that should have been retrieved
- `approved_by`: Who signed off (accountability)
- `version`: Increments when updated (audit trail)

### Creating Your First Dataset

#### Step 1: Sample Query Selection (Weeks 1-2)

**Goal**: Identify 50-100 representative queries

**Sampling Strategies**:

1. **Frequency-based sampling**:
   ```sql
   -- Get top 50 most common queries
   SELECT query, COUNT(*) as freq
   FROM ask_queries
   WHERE workspace_id = 'acme'
   GROUP BY query
   ORDER BY freq DESC
   LIMIT 50
   ```

2. **Diversity sampling**:
   - Cover all major product areas (5-10 categories)
   - Include edge cases (ambiguous, multi-hop, negation)
   - Vary query lengths (short/long), complexity (simple/complex)

3. **Failure case sampling**:
   ```sql
   -- Queries with low user satisfaction scores
   SELECT query
   FROM ask_queries
   WHERE workspace_id = 'acme'
     AND user_rating < 3
   ORDER BY RANDOM()
   LIMIT 20
   ```

**Quality Criteria**:
- ✅ Queries users actually ask (not synthetic)
- ✅ Diverse coverage (not all "What is X?" questions)
- ✅ Realistic difficulty (mix of easy, medium, hard)
- ❌ Avoid duplicates or near-duplicates
- ❌ Avoid queries with no good answer (out of scope)

#### Step 2: Ideal Response Annotation (Weeks 2-3)

**Who annotates**: Product experts, technical writers, domain SMEs

**Annotation Guidelines**:

1. **Completeness**: Answer should fully address the query
2. **Accuracy**: All statements must be factually correct
3. **Conciseness**: No unnecessary information (aim for 2-4 sentences)
4. **Tone**: Match your product voice (formal/casual)
5. **Grounding**: Every claim should be traceable to docs

**Example Annotation**:

```markdown
Query: "How do I enable DAST scanning in Certus?"

❌ BAD Response (too vague):
"You can enable DAST scanning in the configuration file."

✅ GOOD Response (complete, actionable):
"Enable DAST scanning by setting `dast.enabled=true` in your `certus-assurance`
manifest and specifying the target URL with `dast.target_url`. The ZAP scanner
will run during the assurance pipeline and output results to `zap-dast.sarif.json`."
```

**Tooling**:
- **Spreadsheet** (Google Sheets, Excel): Simple, collaborative, version control via comments
- **Label Studio**: Open-source annotation tool with QA workflows
- **Custom webapp**: Build internal tool with workspace auth, approval flows

**Effort Estimation**:
- 50 queries × 10 min/query = **~8 hours** (1 person)
- With review cycle: **~12-16 hours**

#### Step 3: Context Vetting (Week 3)

**Goal**: Identify which document chunks should have been retrieved

**Method**:

1. Run your RAG retrieval on each query
2. Human reviews retrieved chunks:
   - ✅ Keep chunks that help answer the query
   - ❌ Remove irrelevant/redundant chunks
   - 🔍 Add missing chunks (if retrieval failed)

3. Result: "Perfect retrieval" for each query

**Example**:

```
Query: "What scanners does Certus-Assurance support?"

Retrieved Chunks (before vetting):
1. "Certus-Assurance coordinates security scanning..." ✅ KEEP
2. "Supported scanners: Bandit, Semgrep, Checkov, Trivy, ZAP..." ✅ KEEP
3. "Certus-Trust handles signing and verification..." ❌ REMOVE (wrong service)
4. "Configure scanning in the manifest file..." ⚠️ BORDERLINE (keep if relevant to "how")

Vetted Context (after review):
- Chunk 1 (intro to Assurance)
- Chunk 2 (scanner list)
```

**Quality Criteria**:
- Minimum 1 relevant chunk per query
- Maximum 5-7 chunks (avoid overwhelming context)
- Chunks are complete sentences/paragraphs (not fragments)

#### Step 4: Approval & Versioning (Week 4)

**Approval Workflow**:

1. **Author** creates dataset entries
2. **Reviewer** (different person) validates:
   - Factual accuracy
   - Completeness
   - Context relevance
3. **Approver** (product owner, tech lead) signs off
4. Dataset versioned in MLflow with `approved_by` metadata

**Versioning Strategy**:

```python
# Initial dataset
version = 1
mlflow.log_artifact("reference_dataset_v1.jsonl", artifact_path="reference_dataset.jsonl")
mlflow.set_tag("dataset_version", "1")
mlflow.set_tag("approved_by", "alice@acme.com")
mlflow.set_tag("approved_at", "2025-12-28T10:30:00Z")

# After quarterly refresh
version = 2
mlflow.log_artifact("reference_dataset_v2.jsonl", artifact_path="reference_dataset.jsonl")
mlflow.set_tag("dataset_version", "2")
mlflow.set_tag("changelog", "Added 20 new queries, updated 5 responses for v2.0 release")
```

**Approval Gate**:
- ❌ Block evaluation if dataset not approved
- ✅ Log warning if dataset >90 days old

### Dataset Storage & Access

**Primary Storage**: MLflow Artifacts

```
MLflow Experiment: certus-evaluate-references-acme
├── Run: reference-dataset-v1
│   ├── Artifact: reference_dataset.jsonl (50 entries)
│   └── Tags: {version: 1, approved_by: alice@acme.com}
└── Run: reference-dataset-v2
    ├── Artifact: reference_dataset.jsonl (70 entries)
    └── Tags: {version: 2, approved_by: alice@acme.com, changelog: "..."}
```

**Access Pattern**:

```python
# Evaluator loads latest approved dataset
loader = MLflowReferenceLoader(tracking_uri="http://mlflow:5000")
reference = await loader.get_reference(
    workspace_id="acme",
    query_signature="how do i enable dast scanning"
)

if reference:
    # Use for context precision/recall
    ground_truth_answer = reference.ideal_response
    vetted_chunks = reference.vetted_context
else:
    # Skip precision/recall, log warning
    logger.warning("No reference data found, skipping context metrics")
```

**Backup**: Mirror summary in `certus-ask` config for reproducibility

```yaml
# certus-ask/config/workspaces/acme.yaml
evaluation:
  reference_dataset:
    mlflow_experiment: certus-evaluate-references-acme
    version: 2
    last_updated: "2025-12-28"
    entry_count: 70
```

### Governance & Maintenance

#### Quarterly Refresh Cycle

**Q1/Q2/Q3/Q4 Tasks**:

1. **Sample 5% of evaluations for human review**:
   ```sql
   SELECT query, response, evaluation_result
   FROM evaluation_logs
   WHERE workspace_id = 'acme'
     AND timestamp >= DATE_SUB(NOW(), INTERVAL 90 DAY)
   ORDER BY RANDOM()
   LIMIT 100  -- 5% of ~2000 evals
   ```

2. **Human reviewers assess**:
   - Does evaluation score match human judgment?
   - Are there new query patterns (product changes)?
   - Have ideal responses become outdated?

3. **Update dataset**:
   - Add 10-20 new queries (new features, FAQs)
   - Revise 5-10 responses (product updates)
   - Deprecate obsolete queries
   - Increment version number

4. **Recalibrate thresholds**:
   - If scores drift (e.g., avg faithfulness drops 0.85 → 0.75)
   - Investigate: Is retrieval degraded? Docs out of date?
   - Adjust manifest thresholds if quality improved

#### Quality Metrics for Datasets

**Track dataset health**:

| Metric | Threshold | Action if Failed |
|--------|-----------|------------------|
| **Coverage**: % of queries with reference entry | >80% | Add missing queries |
| **Freshness**: Days since last update | <90 days | Trigger refresh cycle |
| **Agreement**: Human vs. LLM score correlation | >0.7 | Review annotation quality |
| **Uniqueness**: Duplicate query signatures | <5% | Deduplicate dataset |

#### PII & Sensitive Data Controls

**Risk**: Reference datasets may contain customer data, internal architecture details

**Controls**:

1. **Sanitization**:
   ```python
   # Before storing reference entry
   query = sanitize_pii(query)  # Mask emails, IPs, API keys
   response = sanitize_pii(response)
   context = [sanitize_pii(chunk) for chunk in context]
   ```

2. **Access Control**:
   - Reference datasets stored per-workspace (isolated)
   - MLflow experiment access via RBAC
   - Audit log: Who accessed dataset, when?

3. **Plaintext opt-in**:
   ```yaml
   # Workspace config
   evaluation:
     log_full_content: false  # Default: hash-only
     log_full_content_approved_by: "alice@acme.com"  # Explicit approval
     log_full_content_expires: "2026-01-01"  # Time-bound approval
   ```

#### Tooling Requirements

**Phase 1** (Manual process):
- Google Sheets template for annotation
- Python script to convert → JSONL
- `mlflow` CLI to upload artifacts

**Phase 2** (Semi-automated):
- Web UI for annotation (FastAPI + React)
- Query sampling suggestions (frequency, failure rate)
- Approval workflow (PR-style reviews)

**Phase 3** (Fully integrated):
- Annotation tool embedded in Certus console
- Auto-detection of new query patterns
- A/B testing of reference dataset changes

### Example: Bootstrapping Acme Workspace Dataset

**Scenario**: Acme Corp uses Certus-Ask for internal documentation Q&A

**Week 1-2: Sampling**
- Analyzed 3 months of query logs (12,000 queries)
- Identified top 30 queries by frequency
- Added 20 diverse queries (one per doc category)
- Total: 50 queries selected

**Week 2-3: Annotation**
- Technical writer drafted ideal responses (6 hours)
- Product manager reviewed and revised (3 hours)
- Vetted context chunks from OpenSearch (4 hours)

**Week 3-4: Approval**
- CTO reviewed and approved dataset (1 hour)
- Uploaded to MLflow as `certus-evaluate-references-acme` v1
- Configured evaluator to fail-fast if reference missing

**Results**:
- Evaluation coverage: 85% (42/50 top queries have reference)
- Avg faithfulness: 0.82 (baseline established)
- Quarterly refresh cadence established

---

## INSERT INTO "Implementation Plan" PHASE 1 WEEK 2

Add to the existing **"Week 2: RAGAS Evaluator & Reference Loader"** section:

---

### Week 2: RAGAS Evaluator & Reference Loader (EXPANDED)

**Code Implementation**:
- [ ] Implement RAGAS evaluator with structured logging
- [ ] Implement reference dataset loader (reference_loader.py)
- [ ] Unit tests for evaluator and loader (mocked)

**Reference Dataset Bootstrapping** (NEW):

This week includes creating the initial reference dataset for at least 2 workspaces to validate the evaluation pipeline.

**Tasks**:

1. **Dataset Sampling** (Days 1-2):
   - [ ] Query Certus-Ask logs for top 30 queries per workspace
   - [ ] Select 20 diverse queries (coverage across doc categories)
   - [ ] Create `queries_selected.csv` with workspace_id, query, frequency, category

2. **Annotation Workflow Setup** (Day 2):
   - [ ] Create Google Sheets template with columns:
     - `query` (required)
     - `ideal_response` (required, multi-line text)
     - `vetted_context_1..5` (optional, chunk text)
     - `annotator` (who wrote it)
     - `reviewer` (who checked it)
     - `approved_by` (final signoff)
     - `tags` (e.g., "onboarding", "advanced")
     - `notes` (internal comments)
   - [ ] Share with workspace product teams for annotation

3. **Ideal Response Annotation** (Days 3-5):
   - [ ] Product experts write ideal responses (target: 10-15 min per query)
   - [ ] Guidelines:
     - 2-4 sentences, complete answer
     - Factually accurate (verify against docs)
     - Actionable (include steps if "how-to")
     - No PII or sensitive internal details
   - [ ] Goal: 50 annotated entries per workspace

4. **Context Vetting** (Days 6-7):
   - [ ] Run RAG retrieval for each query (use existing Ask pipeline)
   - [ ] Human review: Keep relevant chunks, remove irrelevant
   - [ ] Add missing chunks if retrieval failed (manual doc search)
   - [ ] Paste chunk text into `vetted_context_*` columns

5. **Review & Approval** (Days 8-9):
   - [ ] Peer review: Different person validates each entry
     - Accuracy check (is response correct?)
     - Completeness check (does it fully answer?)
     - Context check (are chunks relevant?)
   - [ ] Product owner final approval (sign `approved_by` column)

6. **MLflow Upload** (Day 10):
   - [ ] Export Google Sheet → `reference_dataset.jsonl`
   - [ ] Python script to upload:
     ```python
     import mlflow
     import json
     from datetime import datetime

     workspace_id = "acme"
     experiment_name = f"certus-evaluate-references-{workspace_id}"
     mlflow.set_experiment(experiment_name)

     with mlflow.start_run(run_name=f"dataset-v1-{datetime.now().strftime('%Y%m%d')}"):
         mlflow.log_artifact("reference_dataset.jsonl", artifact_path="reference_dataset.jsonl")
         mlflow.set_tags({
             "dataset_version": "1",
             "approved_by": "alice@acme.com",
             "approved_at": datetime.now().isoformat(),
             "entry_count": "50",
             "workspace_id": workspace_id
         })

     print(f"✅ Uploaded reference dataset v1 for {workspace_id}")
     ```
   - [ ] Repeat for second workspace (total: 100 reference entries)

7. **Validation** (Day 10):
   - [ ] Test reference loader:
     ```python
     loader = MLflowReferenceLoader(tracking_uri="http://localhost:5000")
     ref = await loader.get_reference("acme", "what is certus")
     assert ref is not None
     assert ref.approved_by == "alice@acme.com"
     ```
   - [ ] Verify evaluator fails gracefully when reference missing
   - [ ] Document reference dataset schema in `docs/reference-dataset-schema.md`

**Deliverables**:
- ✅ 2 workspaces × 50 reference entries = **100 total references**
- ✅ Reference datasets uploaded to MLflow
- ✅ Annotation template published for other teams
- ✅ Reference loader tested and working

**Time Budget**:
- Engineering: 3-4 days (loader implementation, MLflow integration)
- Product/SME: 5-6 days (annotation, review, approval)
- **Total**: 8-10 days (parallelizable)

**Success Criteria**:
- [ ] Can load reference entry by workspace_id + query
- [ ] Evaluator skips precision/recall when reference missing (logs warning)
- [ ] Evaluator uses reference for precision/recall when available
- [ ] All reference entries have `approved_by` metadata

---

## ADD NEW SECTION BEFORE "Success Metrics"

---

## Dataset Quality & Success Metrics

### Dataset Coverage Targets

**Phase 1 Targets** (End of Week 2):

| Workspace | Total Queries/Month | Reference Entries | Coverage |
|-----------|---------------------|-------------------|----------|
| Workspace 1 | 5,000 | 50 | Top 30 queries (~60%) |
| Workspace 2 | 3,000 | 50 | Top 30 queries (~70%) |
| **Total** | 8,000 | **100** | **~65%** |

**Phase 3 Targets** (Production):

| Workspace | Reference Entries | Coverage | Refresh Cadence |
|-----------|-------------------|----------|-----------------|
| All workspaces | 100-200 per workspace | >80% of queries | Quarterly |

### Dataset Quality Metrics

**Track and report weekly**:

```python
# Example metrics query
SELECT
    workspace_id,
    COUNT(*) as total_entries,
    COUNT(DISTINCT query_signature) as unique_queries,
    AVG(LENGTH(ideal_response)) as avg_response_length,
    MAX(approved_at) as last_updated,
    DATEDIFF(NOW(), MAX(approved_at)) as days_since_update
FROM reference_dataset
GROUP BY workspace_id
```

**Quality Thresholds**:

| Metric | Target | Red Flag |
|--------|--------|----------|
| **Unique queries** | 50-200 | <30 (insufficient coverage) |
| **Avg response length** | 200-500 chars | <100 (too brief), >1000 (too verbose) |
| **Days since update** | <90 days | >180 days (stale) |
| **Approval rate** | 100% | <95% (unapproved entries) |
| **Avg vetted chunks** | 2-5 per query | <1 (insufficient context), >10 (too much) |

### Evaluation Metrics with Reference Data

**Baseline Performance** (after Week 2 with reference data):

These metrics establish the "normal" performance of your RAG system:

| Metric | Expected Range | Interpretation |
|--------|----------------|----------------|
| **Faithfulness** | 0.75-0.90 | Response grounded in context |
| **Answer Relevancy** | 0.70-0.85 | Response addresses query |
| **Context Precision** | 0.60-0.80 | Relevant chunks ranked high |
| **Context Recall** | 0.65-0.85 | Retrieved necessary chunks |

**Regression Detection**:

```python
# Alert if score drops >10% from baseline
baseline_faithfulness = 0.85
current_faithfulness = 0.72  # 15% drop

if current_faithfulness < baseline_faithfulness * 0.9:
    alert("⚠️ Faithfulness regression detected!")
    # Investigate: Doc updates? Retrieval changes? LLM prompt changes?
```

### Human-LLM Agreement Metrics

**Quarterly Audit**: Compare human ratings vs. LLM scores

**Method**:
1. Sample 100 evaluated responses
2. Humans rate on 1-5 scale (faithfulness, relevancy)
3. Convert to 0-1 scale, compute correlation with LLM scores

**Target Correlation**: >0.7 (strong agreement)

```python
# Example validation
from scipy.stats import pearsonr

human_faithfulness_scores = [0.8, 0.9, 0.6, ...]  # 100 samples
llm_faithfulness_scores = [0.85, 0.88, 0.55, ...]  # 100 samples

correlation, p_value = pearsonr(human_faithfulness_scores, llm_faithfulness_scores)

if correlation > 0.7:
    print(f"✅ Strong agreement (r={correlation:.2f})")
else:
    print(f"⚠️ Weak agreement (r={correlation:.2f}) - review annotation guidelines")
```

**Low Agreement Causes**:
- Ambiguous annotation guidelines
- LLM prompt needs tuning
- Metric doesn't capture what humans value
- Dataset quality issues (noisy labels)

---

This completes the missing sections on:
1. ✅ **Understanding LLM-as-Judge** - Explains RAGAS mechanics, cost, latency
2. ✅ **Reference Dataset Lifecycle** - Complete workflow from sampling to maintenance
3. ✅ **Bootstrapping Guide** - Step-by-step for Week 2 implementation
4. ✅ **Dataset Quality Metrics** - Success criteria and validation

These sections should be inserted into the main proposal document at the locations indicated.
