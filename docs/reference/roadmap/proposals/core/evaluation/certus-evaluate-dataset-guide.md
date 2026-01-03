# Certus-Evaluate: Reference Dataset Creation Guide

> Complete implementation guide for creating, managing, and maintaining reference datasets for RAG evaluation with LLM-as-Judge

## Metadata

- **Type**: Implementation Guide (Dataset Creation)
- **Status**: Ready for Implementation
- **Author**: Certus TAP (AI agent for @harma)
- **Created**: 2025-12-28
- **Last Updated**: 2025-12-28
- **Related**: 
  - [certus-evaluate-service.md](./certus-evaluate-service.md) (main proposal)
  - [certus-evaluate-implementation-guide.md](./certus-evaluate-implementation-guide.md) (technical implementation)
- **Audience**: Product managers, technical writers, SMEs, workspace teams

## Executive Summary

This guide provides a complete workflow for creating and maintaining **reference datasets** - the human-curated ground truth that enables RAG evaluation with LLM-as-Judge metrics.

**What you'll learn**:
- ✅ How LLM-as-Judge evaluation works (RAGAS framework)
- ✅ Step-by-step dataset creation (sampling → annotation → approval)
- ✅ Tooling options (spreadsheets → Label Studio → custom webapp)
- ✅ Quality metrics and maintenance procedures
- ✅ Cost and effort estimation

**Key Facts**:
- **Minimum dataset size**: 50-100 query-response pairs per workspace
- **Initial effort**: 8-16 hours (annotation + review)
- **Ongoing maintenance**: Quarterly refresh (4-6 hours)
- **Evaluation cost**: ~$0.17 per eval with GPT-4, ~$0.02 with GPT-3.5-turbo

---

## Table of Contents

1. [Understanding LLM-as-Judge](#understanding-llm-as-judge)
2. [Reference Dataset Overview](#reference-dataset-overview)
3. [Dataset Creation Workflow](#dataset-creation-workflow)
4. [Tooling Recommendations](#tooling-recommendations)
5. [Storage and Access Patterns](#storage-and-access-patterns)
6. [Governance and Maintenance](#governance-and-maintenance)
7. [Quality Metrics](#quality-metrics)
8. [Cost Analysis](#cost-analysis)
9. [Example: Acme Workspace](#example-acme-workspace)
10. [Troubleshooting](#troubleshooting)

---

## Understanding LLM-as-Judge

### What is LLM-as-Judge?

**LLM-as-Judge** is an evaluation paradigm where a Large Language Model acts as the evaluator to assess the quality of another LLM's outputs. Instead of rule-based metrics or exact-match comparisons, an LLM examines the response and provides a judgment based on natural language understanding.

**Traditional Metrics** (BLEU, ROUGE):
```python
# N-gram overlap - misses semantic meaning
reference = "Certus is a trust automation platform"
response = "Certus is a platform for automating trust"
BLEU_score = 0.3  # Low score despite similar meaning
```

**LLM-as-Judge**:
```python
# LLM understands semantic equivalence
LLM analyzes: Both sentences convey the same core meaning
Semantic_similarity = 0.9  # High score - captures intent
```

### Why RAGAS Uses LLM-as-Judge

**RAGAS** (Retrieval Augmented Generation Assessment) evaluates RAG systems by having an LLM analyze:

1. **Semantic similarity** (not just keyword matching)
2. **Logical consistency** (does the response contradict the context?)
3. **Relevance** (does the answer address the query?)
4. **Completeness** (is all necessary information included?)

This is fundamentally different from traditional metrics because it evaluates **meaning** not **syntax**.

---

## RAGAS Metrics Explained

### 1. Faithfulness (LLM-based)

**Question**: Is the generated response grounded in the provided context?

**How it works**:
1. LLM extracts "claims" from the generated response
2. For each claim, LLM checks if it's supported by the context
3. Score = (supported claims) / (total claims)

**Example**:
```
Query: "What is Certus?"

Context: 
- "Certus is a trust automation platform"
- "It provides security scanning and integrity verification"

Response: 
"Certus is a trust automation platform that offers security scanning 
and blockchain verification"

LLM Analysis:
✅ Claim 1: "Certus is a trust automation platform" → Supported (context chunk 1)
✅ Claim 2: "offers security scanning" → Supported (context chunk 2)
❌ Claim 3: "blockchain verification" → NOT supported (hallucination)

Faithfulness Score: 2/3 = 0.67
```

**Why it matters**: Detects hallucinations where the LLM makes up information not in the source documents.

**Cost**: ~2-3 LLM calls per evaluation
- Call 1: Extract claims from response (~500 tokens)
- Call 2-N: Verify each claim against context (~400 tokens each)

**No reference data required**: Can run in shadow mode from day 1

---

### 2. Answer Relevancy (LLM + Embeddings)

**Question**: Does the response actually answer the query?

**How it works**:
1. LLM generates hypothetical questions that the response would answer
2. Compute embedding similarity between original query and generated questions
3. High similarity = response is relevant to the query

**Example**:
```
Query: "How do I configure MLflow in Certus?"

Response: 
"MLflow is a platform for managing ML workflows including tracking 
experiments and model registry."

LLM generates hypothetical questions this response answers:
- "What is MLflow?"
- "What does MLflow do?"
- "What features does MLflow have?"

Embedding similarity with original query: 0.65
(Medium similarity - response describes MLflow but doesn't answer "how to configure")

Answer Relevancy Score: 0.65
```

**Why it matters**: Catches responses that are factually correct but don't answer what the user asked.

**Cost**: ~1 LLM call + embedding computation
- LLM call: Generate questions (~500 tokens)
- Embeddings: Compute similarity (cheap, <$0.001)

**No reference data required**: Can run in shadow mode

---

### 3. Context Precision (LLM-based, REQUIRES reference)

**Question**: Are the retrieved context chunks ranked correctly? (Most relevant first)

**How it works**:
1. For each context chunk, LLM determines if it's useful for answering the query
2. Compute precision@k (how many of the top-k chunks are relevant)
3. Penalizes irrelevant chunks appearing before relevant ones

**Example**:
```
Query: "What scanners does Certus-Assurance support?"

Retrieved Context (in order):
1. "Certus-Assurance coordinates security scanning across tools" → Relevant ✅
2. "Supported scanners: Bandit, Semgrep, Checkov, Trivy, ZAP" → Relevant ✅
3. "Certus-Trust handles artifact signing and verification" → Irrelevant ❌
4. "Scanner results are output in SARIF format" → Relevant ✅

Ground Truth (ideal response):
"Certus-Assurance supports Bandit, Semgrep, Checkov, Trivy, and ZAP scanners"

LLM Analysis (using ground truth):
- Chunk 1: Useful for answering ✅
- Chunk 2: Directly answers query ✅
- Chunk 3: Not relevant to query ❌
- Chunk 4: Supportive detail ✅

Precision@2: 2/2 = 1.0 (perfect)
Precision@3: 2/3 = 0.67 (irrelevant chunk degraded)
Precision@4: 3/4 = 0.75

Context Precision Score: 0.81 (weighted average)
```

**Why it matters**: Helps tune retrieval ranking so the most relevant docs appear first.

**Cost**: ~N LLM calls (where N = number of context chunks, typically 3-5)

**REQUIRES reference data**: Needs ground-truth answer to determine relevance

---

### 4. Context Recall (LLM-based, REQUIRES reference)

**Question**: Did we retrieve all the necessary context?

**How it works**:
1. LLM extracts "sentences" from the ground-truth answer
2. For each sentence, LLM checks if it can be attributed to the retrieved context
3. Score = (attributable sentences) / (total sentences)

**Example**:
```
Query: "How do I enable DAST scanning?"

Ground Truth Answer:
"Enable DAST scanning by setting `dast.enabled=true` in your manifest. 
Specify the target URL with `dast.target_url`. The ZAP scanner will run 
and output results to `zap-dast.sarif.json`."

LLM extracts sentences:
1. "Enable DAST scanning by setting `dast.enabled=true`"
2. "Specify the target URL with `dast.target_url`"
3. "The ZAP scanner will run and output results"

Retrieved Context:
- Chunk A: "Configure DAST with dast.enabled=true..."
- Chunk B: "Set target URL using dast.target_url parameter..."
- (Missing chunk about output format)

LLM Analysis:
✅ Sentence 1: Can be attributed to Chunk A
✅ Sentence 2: Can be attributed to Chunk B
❌ Sentence 3: Cannot be attributed (missing context)

Context Recall Score: 2/3 = 0.67
```

**Why it matters**: Detects when retrieval misses important documents.

**Cost**: ~M LLM calls (where M = sentences in ground truth, typically 2-4)

**REQUIRES reference data**: Needs ground-truth answer to extract sentences

---

## Cost and Latency Analysis

### Per-Evaluation Cost Breakdown

**Using GPT-4** (December 2025 pricing):

| Metric | LLM Calls | Avg Input Tokens | Avg Output Tokens | Cost/Eval |
|--------|-----------|------------------|-------------------|-----------|
| Faithfulness | 3 | 1000 | 300 | ~$0.05 |
| Answer Relevancy | 1 | 500 | 200 | ~$0.02 |
| Context Precision | 4 (avg) | 400 | 50 | ~$0.06 |
| Context Recall | 3 (avg) | 400 | 50 | ~$0.04 |
| **Total** | **11 calls** | **~4000 tokens** | **~750 tokens** | **~$0.17** |

**Using GPT-3.5-turbo** (10× cheaper):
- **Total cost**: ~$0.017 per evaluation
- **Trade-off**: Lower accuracy on complex reasoning tasks

### Monthly Cost Projections

**Scenario: 1 workspace, 1000 queries/day**

| Evaluation % | Evals/Month | GPT-4 Cost | GPT-3.5 Cost |
|--------------|-------------|------------|--------------|
| 100% | 30,000 | $5,100 | $510 |
| 10% sampling | 3,000 | $510 | $51 |
| 1% sampling | 300 | $51 | $5 |

**Recommendation**: 
- Start with **10% sampling** + **GPT-4** = **$510/month/workspace**
- After baseline established, use GPT-3.5-turbo for ongoing monitoring = **$51/month**

### Latency Breakdown

**Per-evaluation latency** (sequential execution):

| Metric | Latency (p50) | Latency (p99) |
|--------|---------------|---------------|
| Faithfulness | 3-5 sec | 8-10 sec |
| Answer Relevancy | 1-2 sec | 4-5 sec |
| Context Precision | 2-4 sec | 6-8 sec |
| Context Recall | 2-3 sec | 5-7 sec |
| **Total** | **8-14 sec** | **23-30 sec** |

**With parallelization** (run metrics concurrently):
- **p50**: ~5-8 seconds
- **p99**: ~12-15 seconds

**Mitigation strategies**:
1. **Async execution**: Don't block Ask responses
2. **Caching**: Identical Q&A → instant result
3. **Sampling**: Evaluate 10% not 100%
4. **Batch processing**: Run evaluations nightly offline

---

## Reference Dataset Overview

### What is a Reference Dataset?

A **reference dataset** is a curated collection of query-response-context triplets that represent the "ground truth" for your RAG system. Each entry has been **human-reviewed and approved** to serve as the ideal benchmark.

**Purpose**:
- ✅ Provide objective baseline for evaluation metrics
- ✅ Enable context precision/recall computation (requires ground truth)
- ✅ Detect regressions when RAG quality degrades
- ✅ Guide improvements (show where system fails vs. ideal)

**Ownership**: Each Certus-Ask workspace team owns their reference dataset quality and freshness.

### Dataset Structure

**ReferenceEntry Model**:

```python
{
  "query_signature": "what is certus trust automation platform",  # Normalized
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

| Field | Type | Description |
|-------|------|-------------|
| `query_signature` | string | Normalized query for lookup (lowercase, whitespace collapsed) |
| `ideal_response` | string | Human-written "perfect" answer (2-4 sentences) |
| `vetted_context` | array | Context chunks that should have been retrieved (1-7 chunks) |
| `workspace_id` | string | Workspace identifier |
| `approved_by` | string | Email/ID of person who approved this entry |
| `approved_at` | datetime | Approval timestamp (for audit trail) |
| `version` | integer | Version number (increments on updates) |
| `tags` | array | Categories for organization (optional) |
| `notes` | string | Internal comments (optional) |

### Minimum Requirements

**Phase 1** (MVP):
- **50-100 queries per workspace**
- Cover top 30 most frequent queries (~60-70% coverage)
- At least 2 workspaces for validation

**Phase 3** (Production):
- **100-200 queries per workspace**
- >80% coverage of user queries
- Quarterly refresh cycle established

---

## Dataset Creation Workflow

### Overview

Creating a reference dataset involves **4 steps over 2-4 weeks**:

```
Step 1: Sample Queries (Days 1-2)
   ↓
Step 2: Annotate Ideal Responses (Days 3-7)
   ↓
Step 3: Vet Context Chunks (Days 8-10)
   ↓
Step 4: Review & Approve (Days 11-14)
```

**Total effort**: 
- **Engineering**: 2-3 days (tooling setup, MLflow integration)
- **Product/SME**: 8-12 days (annotation, review, approval)

---

### Step 1: Sample Query Selection

**Goal**: Identify 50-100 representative queries

**Duration**: 1-2 days

#### Strategy 1: Frequency-Based Sampling

Get the most common queries users actually ask:

```sql
-- Top 50 queries by frequency
SELECT 
    query,
    COUNT(*) as frequency,
    COUNT(DISTINCT user_id) as unique_users
FROM ask_queries
WHERE workspace_id = 'acme'
  AND timestamp >= DATE_SUB(NOW(), INTERVAL 90 DAY)
GROUP BY query
ORDER BY frequency DESC
LIMIT 50
```

**Pros**: Covers the most impactful queries
**Cons**: May miss edge cases and new features

#### Strategy 2: Diversity Sampling

Ensure coverage across all product areas:

```python
# Categorize queries by topic
categories = {
    "getting-started": ["what is", "how to start", "introduction"],
    "configuration": ["configure", "setup", "install"],
    "troubleshooting": ["error", "not working", "failed"],
    "advanced": ["integrate", "customize", "extend"],
    "security": ["permission", "auth", "access"],
}

# Select 10 queries per category
for category, keywords in categories.items():
    queries = filter_queries_by_keywords(all_queries, keywords)
    selected = random.sample(queries, min(10, len(queries)))
```

**Pros**: Comprehensive coverage
**Cons**: May include rare queries

#### Strategy 3: Failure Case Sampling

Focus on queries where the system performs poorly:

```sql
-- Queries with low user satisfaction
SELECT query, AVG(user_rating) as avg_rating
FROM ask_queries
WHERE workspace_id = 'acme'
  AND user_rating IS NOT NULL
GROUP BY query
HAVING avg_rating < 3.0
ORDER BY COUNT(*) DESC  -- Prioritize frequent low-rated queries
LIMIT 20
```

**Pros**: Targets improvement areas
**Cons**: Biased toward difficult queries

#### Recommended Approach: Hybrid

```
30 queries: Frequency-based (top queries)
20 queries: Diversity (one per category)
20 queries: Failure cases
────────────────────────────────
70 queries total
```

**Quality Criteria**:
- ✅ Queries users actually ask (not synthetic)
- ✅ Diverse coverage (not all "What is X?")
- ✅ Mix of difficulty (easy, medium, hard)
- ❌ Avoid near-duplicates ("what is certus" vs "what's certus")
- ❌ Avoid out-of-scope queries (no good answer exists)

**Output**: `queries_selected.csv`
```csv
query,frequency,category,priority
"What is Certus?",1250,getting-started,high
"How do I configure MLflow?",420,configuration,high
"Why is my scan failing?",89,troubleshooting,medium
...
```

---

### Step 2: Ideal Response Annotation

**Goal**: Write perfect answers for each query

**Duration**: 5-10 days (depending on team size)

**Who does this**: Product experts, technical writers, domain SMEs

#### Annotation Guidelines

**Completeness**: Answer should fully address the query
- ✅ Answers the "what" and "why"
- ✅ Includes "how" if applicable
- ✅ Provides context for understanding

**Accuracy**: All statements must be factually correct
- ✅ Verify against documentation
- ✅ Test commands/configurations
- ✅ Cross-check with SMEs

**Conciseness**: No unnecessary information
- ✅ Aim for 2-4 sentences (150-400 characters)
- ✅ One paragraph maximum
- ❌ Don't include tangential details

**Tone**: Match your product voice
- ✅ Formal for enterprise products
- ✅ Casual/friendly for developer tools
- ✅ Consistent across all entries

**Grounding**: Every claim traceable to docs
- ✅ Can cite source document/page
- ❌ No "I think" or assumptions
- ❌ No internal-only information

#### Good vs. Bad Examples

**Query**: "How do I enable DAST scanning in Certus?"

❌ **BAD Response** (too vague):
```
"You can enable DAST scanning in the configuration file."
```
**Problems**: Doesn't say which file, what to set, what happens next

✅ **GOOD Response** (complete, actionable):
```
"Enable DAST scanning by setting `dast.enabled=true` in your `certus-assurance` 
manifest and specifying the target URL with `dast.target_url`. The ZAP scanner 
will run during the assurance pipeline and output results to `zap-dast.sarif.json`."
```
**Why good**: Specific file, exact settings, outcome described

---

**Query**: "What is Certus?"

❌ **BAD Response** (too brief):
```
"Certus is a platform."
```
**Problems**: No useful information

❌ **BAD Response** (too verbose):
```
"Certus is a comprehensive trust automation platform that was designed to 
provide organizations with end-to-end visibility and control over their 
software supply chain security posture through integrated scanning, 
verification, and attestation capabilities, enabling teams to..."
```
**Problems**: Run-on sentence, jargon-heavy, overwhelming

✅ **GOOD Response** (balanced):
```
"Certus is a trust automation platform that provides security scanning, 
integrity verification, and supply chain attestation for software artifacts. 
It integrates with your CI/CD pipeline to automatically scan code, 
dependencies, and infrastructure for vulnerabilities."
```
**Why good**: Clear, concise, complete

#### Effort Estimation

**Time per query**: 10-15 minutes
- 5 min: Draft response
- 5 min: Verify accuracy (check docs)
- 3 min: Polish tone/grammar

**Total for 50 queries**: 
- Single annotator: **8-12 hours**
- Team of 3: **3-4 hours each** (parallelizable)

**With review cycle**: Add 50% time = **12-18 hours total**

---

### Step 3: Context Vetting

**Goal**: Identify which document chunks should have been retrieved

**Duration**: 2-3 days

**Who does this**: Same annotators OR separate reviewers

#### Vetting Process

1. **Run retrieval** for each query using your existing RAG system

```python
# For each query in dataset
for query in queries:
    # Use Certus-Ask's retrieval
    retrieved_chunks = opensearch.search(query, top_k=10)
    
    # Save for manual review
    save_for_review(query, retrieved_chunks)
```

2. **Manual review** of retrieved chunks:
   - ✅ **Keep** chunks that help answer the query
   - ❌ **Remove** irrelevant or redundant chunks
   - 🔍 **Add** missing chunks (manual doc search if retrieval failed)

3. **Result**: "Perfect retrieval" for each query (what should have been retrieved)

#### Review Example

**Query**: "What scanners does Certus-Assurance support?"

**Retrieved Chunks** (from OpenSearch):
```
1. "Certus-Assurance coordinates security scanning across multiple tools..." 
   → ✅ KEEP (context/intro)

2. "Supported scanners include Bandit (Python), Semgrep (multi-language), 
    Checkov (IaC), Trivy (containers), and ZAP (DAST)..." 
   → ✅ KEEP (directly answers query)

3. "Certus-Trust handles artifact signing and verification using Sigstore..." 
   → ❌ REMOVE (wrong service, not relevant)

4. "Scanner results are aggregated and converted to SARIF format..." 
   → ⚠️ BORDERLINE (supportive detail, keep if space allows)

5. "Configure scanners in the assurance manifest file..." 
   → ❌ REMOVE (about configuration, not list of scanners)
```

**Vetted Context** (final):
```
- Chunk 1: "Certus-Assurance coordinates..."
- Chunk 2: "Supported scanners include..."
- Chunk 4: "Scanner results are aggregated..." (optional)
```

#### Quality Criteria

**Coverage**:
- ✅ Minimum 1 relevant chunk per query
- ✅ Typical range: 2-5 chunks
- ❌ Maximum 7 chunks (avoid overwhelming context)

**Relevance**:
- ✅ Every chunk contributes to answering the query
- ❌ No tangential information
- ❌ No duplicate/redundant chunks

**Completeness**:
- ✅ Chunks contain all information in ideal response
- ✅ Can construct ideal response from chunks alone
- ❌ No gaps (missing critical info)

**Format**:
- ✅ Complete sentences/paragraphs (not fragments)
- ✅ Standalone (understandable without surrounding text)
- ✅ Properly extracted (no truncation mid-sentence)

#### Effort Estimation

**Time per query**: 5-10 minutes
- 2 min: Review retrieved chunks
- 3 min: Mark keep/remove
- 3 min: Search for missing chunks (if needed)

**Total for 50 queries**: 
- **4-8 hours** (can parallelize)

---

### Step 4: Approval & Versioning

**Goal**: Quality assurance and formal sign-off

**Duration**: 2-3 days

**Who does this**: 
- **Reviewer**: Peer (different from annotator)
- **Approver**: Product owner, tech lead, or SME

#### Approval Workflow

```
┌─────────────┐
│  Annotator  │ Draft responses + vet context
└──────┬──────┘
       ↓
┌─────────────┐
│  Reviewer   │ Validate accuracy, completeness, format
└──────┬──────┘
       ↓
    ┌──┴──────────┐
    │ Issues?      │
    └──┬─────┬────┘
       Yes   No
       ↓     ↓
   ┌────┐  ┌──────────┐
   │Fix │  │ Approver │ Final sign-off
   └─┬──┘  └────┬─────┘
     ↓          ↓
     └──────────┘
         ↓
   ┌────────────┐
   │  Upload to │
   │   MLflow   │
   └────────────┘
```

#### Review Checklist

**Factual Accuracy**:
- [ ] All statements are correct
- [ ] Commands/code snippets tested
- [ ] No outdated information

**Completeness**:
- [ ] Query fully answered
- [ ] No missing critical details
- [ ] Context sufficient to construct response

**Context Relevance**:
- [ ] All chunks help answer query
- [ ] No irrelevant chunks included
- [ ] No gaps in coverage

**Format & Style**:
- [ ] Tone matches product voice
- [ ] Grammar and spelling correct
- [ ] Consistent formatting

**Metadata Complete**:
- [ ] `approved_by` filled in
- [ ] `workspace_id` correct
- [ ] `tags` added (if applicable)

#### Versioning in MLflow

**Initial Upload**:

```python
import mlflow
from datetime import datetime

workspace_id = "acme"
experiment_name = f"certus-evaluate-references-{workspace_id}"

mlflow.set_experiment(experiment_name)

with mlflow.start_run(run_name=f"dataset-v1-{datetime.now().strftime('%Y%m%d')}"):
    # Upload dataset file
    mlflow.log_artifact(
        "reference_dataset_v1.jsonl", 
        artifact_path="reference_dataset.jsonl"
    )
    
    # Add metadata tags
    mlflow.set_tags({
        "dataset_version": "1",
        "approved_by": "alice@acme.com",
        "approved_at": datetime.now().isoformat(),
        "entry_count": "50",
        "workspace_id": workspace_id,
        "coverage": "top_30_queries",
        "changelog": "Initial dataset creation"
    })

print(f"✅ Uploaded reference dataset v1 for {workspace_id}")
```

**Subsequent Updates** (Quarterly refresh):

```python
# Version 2 after Q2 refresh
with mlflow.start_run(run_name=f"dataset-v2-{datetime.now().strftime('%Y%m%d')}"):
    mlflow.log_artifact("reference_dataset_v2.jsonl", ...)
    
    mlflow.set_tags({
        "dataset_version": "2",
        "approved_by": "alice@acme.com",
        "approved_at": datetime.now().isoformat(),
        "entry_count": "70",  # Added 20 queries
        "workspace_id": workspace_id,
        "changelog": "Added 20 new queries for v2.0 features, updated 5 responses"
    })
```

**Approval Gates**:

```python
# In evaluator code
reference = await loader.get_reference(workspace_id, query)

if not reference:
    logger.warning("no_reference_data", workspace_id=workspace_id)
    # Skip precision/recall metrics
    
if not reference.approved_by:
    logger.error("unapproved_reference_data", workspace_id=workspace_id)
    raise ValueError("Reference dataset must be approved")

# Check freshness
days_old = (datetime.now() - reference.approved_at).days
if days_old > 90:
    logger.warning("stale_reference_data", 
                   workspace_id=workspace_id, 
                   days_old=days_old)
```

---

## Tooling Recommendations

### Phase 1: Manual Process (Weeks 1-4)

**Recommended for**: Initial MVP, 1-2 workspaces, <100 queries

#### Option 1A: Google Sheets (RECOMMENDED for Phase 1)

**Pros**:
- ✅ Zero setup (everyone has access)
- ✅ Real-time collaboration
- ✅ Built-in comments/review workflow
- ✅ Version history (Track changes)
- ✅ Easy export to CSV/JSONL

**Cons**:
- ❌ No schema validation
- ❌ Manual formatting required
- ❌ Limited automation

**Template Structure**:

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `query` | text | ✅ | Original user query |
| `ideal_response` | text (multi-line) | ✅ | Perfect answer (2-4 sentences) |
| `vetted_context_1` | text (multi-line) | ✅ | First context chunk |
| `vetted_context_2` | text (multi-line) | ⚠️ | Second chunk (if needed) |
| `vetted_context_3` | text (multi-line) | ⚠️ | Third chunk (if needed) |
| `vetted_context_4` | text (multi-line) | ⚠️ | Fourth chunk (if needed) |
| `vetted_context_5` | text (multi-line) | ⚠️ | Fifth chunk (if needed) |
| `annotator` | email | ✅ | Who wrote it |
| `reviewer` | email | ✅ | Who reviewed it |
| `approved_by` | email | ✅ | Final approver |
| `tags` | text (comma-sep) | ⚠️ | Categories (e.g., "onboarding,config") |
| `notes` | text | ⚠️ | Internal comments |
| `status` | dropdown | ✅ | Draft / In Review / Approved |

**Conversion Script** (`sheets_to_jsonl.py`):

```python
#!/usr/bin/env python3
import csv
import json
from datetime import datetime

def normalize_query(query: str) -> str:
    """Normalize query for matching"""
    return " ".join(query.lower().strip().split())

def sheets_to_jsonl(csv_file: str, output_file: str, workspace_id: str):
    """Convert Google Sheets CSV to reference dataset JSONL"""
    
    entries = []
    
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # Skip if not approved
            if row['status'] != 'Approved':
                continue
            
            # Collect context chunks
            context = []
            for i in range(1, 6):
                chunk = row.get(f'vetted_context_{i}', '').strip()
                if chunk:
                    context.append(chunk)
            
            # Build entry
            entry = {
                "query_signature": normalize_query(row['query']),
                "ideal_response": row['ideal_response'].strip(),
                "vetted_context": context,
                "workspace_id": workspace_id,
                "approved_by": row['approved_by'],
                "approved_at": datetime.now().isoformat(),
                "version": 1,
                "tags": [t.strip() for t in row.get('tags', '').split(',') if t.strip()],
                "notes": row.get('notes', '').strip()
            }
            
            entries.append(entry)
    
    # Write JSONL
    with open(output_file, 'w') as f:
        for entry in entries:
            f.write(json.dumps(entry) + '\n')
    
    print(f"✅ Converted {len(entries)} approved entries to {output_file}")

if __name__ == "__main__":
    sheets_to_jsonl(
        csv_file="reference_dataset_acme.csv",
        output_file="reference_dataset_v1.jsonl",
        workspace_id="acme"
    )
```

**Usage**:
1. Share Google Sheet with team
2. Annotators fill in queries/responses/context
3. Reviewers add comments, change status to "Approved"
4. Export as CSV: File → Download → CSV
5. Run conversion script
6. Upload to MLflow

**Download template**: [Google Sheets Template](https://docs.google.com/spreadsheets/d/your-template-id) *(create and share)*

---

#### Option 1B: Excel (Alternative)

**Same as Google Sheets but**:
- ✅ Works offline
- ❌ Harder to collaborate (file-sharing issues)
- ❌ No real-time edits

Use if: Your organization restricts Google Workspace

---

### Phase 2: Semi-Automated (Months 2-6)

**Recommended for**: 3-10 workspaces, 100-500 queries, ongoing maintenance

#### Option 2A: Label Studio (RECOMMENDED for Phase 2)

**Label Studio** is an open-source data labeling tool with built-in QA workflows.

**Pros**:
- ✅ Purpose-built for annotation
- ✅ Built-in review workflow (assign, review, approve)
- ✅ User management and permissions
- ✅ Keyboard shortcuts (fast annotation)
- ✅ Metrics dashboard (annotator productivity)
- ✅ Export to JSON/CSV
- ✅ API for automation

**Cons**:
- ⚠️ Requires self-hosting or cloud subscription
- ⚠️ Learning curve (2-3 days)
- ⚠️ Overkill for <50 queries

**Setup** (Docker):

```yaml
# docker-compose-labelstudio.yml
version: '3.8'
services:
  label-studio:
    image: heartexlabs/label-studio:latest
    ports:
      - "8080:8080"
    environment:
      - LABEL_STUDIO_HOST=http://localhost:8080
    volumes:
      - label-studio-data:/label-studio/data

volumes:
  label-studio-data:
```

```bash
docker-compose -f docker-compose-labelstudio.yml up -d
# Access at http://localhost:8080
```

**Label Studio Configuration**:

```xml
<View>
  <Header value="Reference Dataset Annotation"/>
  
  <!-- Query (read-only) -->
  <Text name="query" value="$query" label="Query"/>
  
  <!-- Ideal Response (annotate) -->
  <TextArea name="ideal_response" 
            toName="query"
            placeholder="Write the perfect answer (2-4 sentences)"
            maxSubmissions="1"/>
  
  <!-- Context Chunks (annotate) -->
  <Text name="context_label" value="Vetted Context Chunks:"/>
  <TextArea name="context_1" placeholder="Chunk 1"/>
  <TextArea name="context_2" placeholder="Chunk 2 (optional)"/>
  <TextArea name="context_3" placeholder="Chunk 3 (optional)"/>
  <TextArea name="context_4" placeholder="Chunk 4 (optional)"/>
  <TextArea name="context_5" placeholder="Chunk 5 (optional)"/>
  
  <!-- Metadata -->
  <Choices name="category" toName="query" choice="single">
    <Choice value="getting-started"/>
    <Choice value="configuration"/>
    <Choice value="troubleshooting"/>
    <Choice value="advanced"/>
  </Choices>
  
  <TextArea name="notes" placeholder="Internal notes (optional)"/>
</View>
```

**Import Queries**:

```python
import requests

# Label Studio API
API_URL = "http://localhost:8080/api/projects/1/tasks"
API_KEY = "your-api-key"

# Load queries
queries = ["What is Certus?", "How do I configure MLflow?", ...]

for query in queries:
    task = {
        "data": {
            "query": query
        }
    }
    
    response = requests.post(
        API_URL,
        headers={"Authorization": f"Token {API_KEY}"},
        json=task
    )
```

**Export and Convert**:

```python
# Export from Label Studio
exported_data = requests.get(
    "http://localhost:8080/api/projects/1/export?exportType=JSON",
    headers={"Authorization": f"Token {API_KEY}"}
).json()

# Convert to reference dataset
entries = []
for item in exported_data:
    annotations = item['annotations'][0]['result']
    
    # Extract fields
    ideal_response = next(a['value']['text'][0] for a in annotations if a['from_name'] == 'ideal_response')
    context = [
        a['value']['text'][0]
        for a in annotations
        if a['from_name'].startswith('context_') and a['value']['text']
    ]
    
    entry = {
        "query_signature": normalize_query(item['data']['query']),
        "ideal_response": ideal_response,
        "vetted_context": context,
        "workspace_id": "acme",
        "approved_by": item['annotations'][0]['completed_by']['email'],
        "approved_at": item['annotations'][0]['created_at'],
        "version": 1
    }
    entries.append(entry)
```

**Workflow**:
1. Import queries to Label Studio
2. Assign tasks to annotators
3. Annotators fill in responses/context
4. Reviewers approve/reject
5. Export approved tasks
6. Convert to JSONL
7. Upload to MLflow

**Cost**: Free (self-hosted) or $39/user/month (cloud)

---

#### Option 2B: Custom Webapp (Build if needed)

**Build a custom tool if**:
- ✅ Need tight integration with Certus-Ask
- ✅ Want workspace-specific access control
- ✅ Label Studio doesn't fit your workflow

**Tech Stack**:
- Frontend: React or Streamlit (simpler)
- Backend: FastAPI
- Database: PostgreSQL (store annotations)
- Auth: Keycloak or Auth0 (workspace SSO)

**Features**:
- Query assignment (round-robin to annotators)
- Inline retrieval preview (show what Ask retrieved)
- Diff view (compare annotation versions)
- Approval workflow (draft → review → approved)
- Export to MLflow (one-click)

**Effort Estimation**:
- **Simple MVP** (Streamlit): 2-3 weeks (1 engineer)
- **Full webapp** (React + FastAPI): 6-8 weeks (1 engineer)

**Example Streamlit UI**:

```python
import streamlit as st
import mlflow

st.title("Reference Dataset Annotation")

# Load query
query = st.selectbox("Select Query", queries)

# Annotation form
ideal_response = st.text_area("Ideal Response", height=100)

context_chunks = []
for i in range(5):
    chunk = st.text_area(f"Context Chunk {i+1} (optional)", height=80)
    if chunk:
        context_chunks.append(chunk)

tags = st.multiselect("Tags", ["getting-started", "config", "troubleshooting"])
notes = st.text_area("Notes", height=60)

# Submit
if st.button("Submit for Review"):
    entry = {
        "query_signature": normalize_query(query),
        "ideal_response": ideal_response,
        "vetted_context": context_chunks,
        "workspace_id": st.session_state['workspace_id'],
        "approved_by": st.session_state['user_email'],
        "tags": tags,
        "notes": notes
    }
    
    save_to_database(entry)  # Save draft
    st.success("Submitted for review!")
```

---

### Phase 3: Fully Integrated (Month 6+)

**Recommended for**: Production, all workspaces, continuous improvement

#### Option 3: Certus Console Integration

**Embed annotation tool in Certus UI**:

- ✅ Workspace teams annotate within product
- ✅ Auto-suggest queries (frequency, low ratings)
- ✅ One-click upload to MLflow
- ✅ A/B testing (compare dataset versions)
- ✅ Auto-detect drift (alert when scores drop)

**Implementation**:
- Add `/reference-datasets` page to Certus console
- Use existing workspace auth/permissions
- Integrate with Certus-Ask query logs
- Connect to MLflow for storage

**Effort**: 8-12 weeks (full feature)

---

## Tooling Comparison Matrix

| Tool | Phase | Setup Time | Cost | Collaboration | Automation | Best For |
|------|-------|------------|------|---------------|------------|----------|
| **Google Sheets** | 1 | <1 hour | Free | ✅ Excellent | ❌ None | MVP, <100 queries |
| **Excel** | 1 | <1 hour | Free* | ⚠️ Fair | ❌ None | Offline/restricted orgs |
| **Label Studio** | 2 | 1-2 days | Free / $39/mo | ✅ Good | ✅ Good | 100-1000 queries |
| **Custom Webapp** | 2-3 | 2-8 weeks | Dev cost | ✅ Excellent | ✅ Excellent | Custom workflows |
| **Certus Console** | 3 | 8-12 weeks | Dev cost | ✅ Excellent | ✅ Excellent | Production scale |

**Recommendation**:
1. **Start with Google Sheets** (Phase 1, Weeks 1-4)
2. **Migrate to Label Studio** (Phase 2, Month 2+)
3. **Build into Certus Console** (Phase 3, Month 6+)

---

## Storage and Access Patterns

### MLflow Artifacts Storage

**Why MLflow**:
- ✅ Versioning built-in (multiple runs = multiple versions)
- ✅ Metadata tagging (approved_by, changelog, etc.)
- ✅ Artifact storage (JSONL files)
- ✅ Already integrated with Certus-Evaluate
- ✅ Query/search capabilities

**Storage Structure**:

```
MLflow Tracking Server
└── Experiments
    ├── certus-evaluate-references-acme
    │   ├── Run: dataset-v1-20251228
    │   │   ├── Artifact: reference_dataset.jsonl (50 entries)
    │   │   └── Tags: {version: 1, approved_by: alice@acme.com, entry_count: 50}
    │   └── Run: dataset-v2-20260328
    │       ├── Artifact: reference_dataset.jsonl (70 entries)
    │       └── Tags: {version: 2, approved_by: alice@acme.com, entry_count: 70}
    │
    └── certus-evaluate-references-globex
        └── Run: dataset-v1-20260115
            ├── Artifact: reference_dataset.jsonl (60 entries)
            └── Tags: {version: 1, approved_by: bob@globex.com}
```

**Upload Script**:

```python
import mlflow
from datetime import datetime

def upload_reference_dataset(
    jsonl_file: str,
    workspace_id: str,
    approved_by: str,
    version: int = 1,
    changelog: str = ""
):
    """Upload reference dataset to MLflow"""
    
    experiment_name = f"certus-evaluate-references-{workspace_id}"
    mlflow.set_experiment(experiment_name)
    
    # Count entries
    with open(jsonl_file) as f:
        entry_count = sum(1 for line in f)
    
    # Create run
    run_name = f"dataset-v{version}-{datetime.now().strftime('%Y%m%d')}"
    
    with mlflow.start_run(run_name=run_name):
        # Upload file
        mlflow.log_artifact(jsonl_file, artifact_path="reference_dataset.jsonl")
        
        # Add tags
        mlflow.set_tags({
            "dataset_version": str(version),
            "approved_by": approved_by,
            "approved_at": datetime.now().isoformat(),
            "entry_count": str(entry_count),
            "workspace_id": workspace_id,
            "changelog": changelog or f"Version {version} created"
        })
        
        run_id = mlflow.active_run().info.run_id
        print(f"✅ Uploaded dataset v{version} for {workspace_id}")
        print(f"   Run ID: {run_id}")
        print(f"   Entries: {entry_count}")
        
        return run_id

# Usage
upload_reference_dataset(
    jsonl_file="reference_dataset_acme_v1.jsonl",
    workspace_id="acme",
    approved_by="alice@acme.com",
    version=1,
    changelog="Initial dataset with top 50 queries"
)
```

### Access Pattern (in Evaluator)

```python
# src/certus_evaluate/core/reference_loader.py

class MLflowReferenceLoader:
    def __init__(self, tracking_uri: str):
        self.tracking_uri = tracking_uri
        mlflow.set_tracking_uri(tracking_uri)
    
    async def get_reference(
        self,
        workspace_id: str,
        query_signature: str
    ) -> Optional[ReferenceEntry]:
        """Load reference entry from latest approved dataset"""
        
        experiment_name = f"certus-evaluate-references-{workspace_id}"
        
        try:
            experiment = mlflow.get_experiment_by_name(experiment_name)
            if not experiment:
                logger.warning(f"No reference experiment for {workspace_id}")
                return None
            
            # Get latest run
            runs = mlflow.search_runs(
                experiment_ids=[experiment.experiment_id],
                order_by=["start_time DESC"],
                max_results=1
            )
            
            if runs.empty:
                logger.warning(f"No reference runs for {workspace_id}")
                return None
            
            run_id = runs.iloc[0].run_id
            
            # Download artifact
            artifact_path = mlflow.artifacts.download_artifacts(
                run_id=run_id,
                artifact_path="reference_dataset.jsonl"
            )
            
            # Search for matching query
            normalized_query = self._normalize_query(query_signature)
            
            with open(artifact_path) as f:
                for line in f:
                    entry_dict = json.loads(line)
                    entry = ReferenceEntry(**entry_dict)
                    
                    if self._normalize_query(entry.query_signature) == normalized_query:
                        return entry
            
            return None
            
        except Exception as e:
            logger.error(f"Error loading reference: {e}")
            return None
```

### Backup Strategy

**Mirror summary in Certus-Ask config** for reproducibility:

```yaml
# certus-ask/config/workspaces/acme.yaml
workspace:
  id: acme
  name: "Acme Corporation"
  
evaluation:
  enabled: true
  sampling_rate: 0.1  # Evaluate 10% of queries
  
  reference_dataset:
    mlflow_experiment: "certus-evaluate-references-acme"
    mlflow_run_id: "a1b2c3d4e5f6..."  # Pin to specific version
    version: 2
    last_updated: "2025-12-28"
    entry_count: 70
    approved_by: "alice@acme.com"
    
    # Baseline metrics (for regression detection)
    baseline:
      faithfulness: 0.85
      answer_relevancy: 0.78
      context_precision: 0.72
      context_recall: 0.80
```

**Benefits**:
- ✅ Reproducible (know which dataset version was used)
- ✅ Rollback (if new dataset causes issues)
- ✅ Audit trail (track dataset changes over time)

---

## Governance and Maintenance

### Quarterly Refresh Cycle

**Goal**: Keep dataset current with product changes

**Cadence**: Every 3 months (Q1, Q2, Q3, Q4)

**Process**:

#### Q-4 weeks: Preparation

1. **Sample recent evaluations for review**:
   ```sql
   SELECT 
       query,
       response,
       faithfulness_score,
       answer_relevancy_score
   FROM evaluation_logs
   WHERE workspace_id = 'acme'
     AND timestamp >= DATE_SUB(NOW(), INTERVAL 90 DAY)
   ORDER BY RANDOM()
   LIMIT 100  -- 5% sample
   ```

2. **Human reviewers assess**:
   - Does LLM score match your judgment?
   - Are there new query patterns (new features)?
   - Have ideal responses become outdated?

3. **Identify updates needed**:
   - New queries to add (10-20)
   - Responses to revise (5-10)
   - Queries to deprecate (obsolete features)

#### Q-2 weeks: Annotation

4. **Annotate new queries** (same process as initial creation)
5. **Revise existing responses** (verify against latest docs)
6. **Update context** (if retrieval changed)

#### Q-1 week: Review & Upload

7. **Peer review** (different person)
8. **Approver sign-off** (product owner)
9. **Upload v2 to MLflow** (increment version)
10. **Update workspace config** (new baseline metrics)

#### Q+1 week: Validation

11. **Run evaluations on v2 dataset**
12. **Compare scores vs. v1** (detect drift)
13. **Recalibrate thresholds** if needed

**Effort per Quarter**: 4-6 hours (incremental updates)

---

### Quality Metrics for Datasets

Track dataset health over time:

| Metric | How to Measure | Threshold | Action if Failed |
|--------|----------------|-----------|------------------|
| **Coverage** | % of queries with reference entry | >80% | Add missing queries |
| **Freshness** | Days since last update | <90 days | Trigger refresh cycle |
| **Agreement** | Human vs. LLM score correlation | >0.7 | Review annotation quality |
| **Uniqueness** | Duplicate query signatures | <5% | Deduplicate dataset |
| **Completeness** | Entries missing required fields | 0% | Fix incomplete entries |
| **Approval Rate** | % of entries approved | 100% | Remove unapproved entries |

**Monitoring Query** (run monthly):

```sql
SELECT 
    workspace_id,
    COUNT(*) as total_entries,
    COUNT(DISTINCT query_signature) as unique_queries,
    AVG(LENGTH(ideal_response)) as avg_response_length,
    AVG(ARRAY_LENGTH(vetted_context, 1)) as avg_context_chunks,
    MAX(approved_at) as last_updated,
    DATEDIFF(NOW(), MAX(approved_at)) as days_since_update,
    SUM(CASE WHEN approved_by IS NULL THEN 1 ELSE 0 END) as unapproved_count
FROM reference_dataset
GROUP BY workspace_id
```

**Dashboard** (track trends):

```python
import matplotlib.pyplot as plt

# Plot dataset growth over time
versions = [1, 2, 3, 4]
entry_counts = [50, 70, 85, 92]

plt.plot(versions, entry_counts, marker='o')
plt.xlabel('Dataset Version')
plt.ylabel('Entry Count')
plt.title('Reference Dataset Growth - Acme Workspace')
plt.show()
```

---

### PII and Sensitive Data Controls

**Risk**: Reference datasets may contain:
- Customer data (company names, emails)
- Internal architecture details
- API keys or secrets (in example queries)

**Controls**:

#### 1. Sanitization Before Storage

```python
import re

def sanitize_pii(text: str) -> str:
    """Mask PII in text"""
    
    # Mask emails
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 
                  '[EMAIL]', text)
    
    # Mask IP addresses
    text = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', 
                  '[IP_ADDRESS]', text)
    
    # Mask API keys (common patterns)
    text = re.sub(r'sk-[a-zA-Z0-9]{32,}', '[API_KEY]', text)
    text = re.sub(r'ghp_[a-zA-Z0-9]{36}', '[GITHUB_TOKEN]', text)
    
    # Mask URLs
    text = re.sub(r'https?://[^\s]+', '[URL]', text)
    
    return text

# Apply before storing
entry['ideal_response'] = sanitize_pii(entry['ideal_response'])
entry['vetted_context'] = [sanitize_pii(chunk) for chunk in entry['vetted_context']]
```

#### 2. Access Control

**MLflow Experiment Permissions**:
- Workspace teams: Read/write their own experiment
- Other teams: No access
- Admin/DevOps: Read-only across all

**Implementation** (MLflow auth plugin):

```python
# mlflow_auth_plugin.py

def can_read_experiment(user: str, experiment_name: str) -> bool:
    # Extract workspace_id from experiment name
    # e.g., "certus-evaluate-references-acme" → "acme"
    workspace_id = experiment_name.split('-')[-1]
    
    # Check user's workspace membership
    return user_has_workspace_access(user, workspace_id)
```

#### 3. Audit Logging

Track who accessed reference datasets:

```python
# Log access events
logger.info(
    "reference_dataset.accessed",
    workspace_id=workspace_id,
    user=user_email,
    action="download",
    dataset_version=version,
    timestamp=datetime.now().isoformat()
)
```

**Query audit logs**:

```sql
SELECT 
    user,
    workspace_id,
    action,
    COUNT(*) as access_count
FROM audit_logs
WHERE event_type = 'reference_dataset.accessed'
  AND timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY user, workspace_id, action
ORDER BY access_count DESC
```

#### 4. Opt-in for Plaintext Logging

**Default**: Only log content hashes
**Opt-in**: Explicit approval to log full query/response

```yaml
# Workspace config
evaluation:
  log_full_content: false  # Default
  
  # If enabled, require approval
  log_full_content_approved_by: "alice@acme.com"
  log_full_content_approved_at: "2025-12-28"
  log_full_content_expires: "2026-01-01"  # Time-bound
  log_full_content_reason: "Debugging evaluation accuracy issues"
```

**Enforce in code**:

```python
# In MLflowLogger
def log_evaluation(self, result, query=None, response=None, ...):
    # Always log hashes
    mlflow.log_text(result.query_hash, "query_hash.txt")
    
    # Opt-in for full content
    if settings.MLFLOW_LOG_FULL_CONTENT:
        # Check approval
        if not self._is_approved(workspace_id):
            logger.warning("Full content logging not approved")
            return
        
        # Check expiry
        if self._is_expired(workspace_id):
            logger.warning("Full content logging approval expired")
            return
        
        # Log with warning
        logger.warning("Logging full content (contains PII)")
        mlflow.log_text(query, "query.txt")
        mlflow.log_text(response, "response.txt")
```

---

## Quality Metrics

### Dataset Coverage Targets

**Phase 1** (End of Week 2):

| Workspace | Total Queries/Month | Reference Entries | Coverage |
|-----------|---------------------|-------------------|----------|
| Workspace 1 | 5,000 | 50 | ~60% (top 30 queries) |
| Workspace 2 | 3,000 | 50 | ~70% (top 30 queries) |
| **Total** | 8,000 | **100** | **~65%** |

**Phase 3** (Production):

| Workspace | Reference Entries | Coverage | Refresh Cadence |
|-----------|-------------------|----------|-----------------|
| All workspaces | 100-200 per workspace | >80% of queries | Quarterly |

### Evaluation Baseline Metrics

**After dataset creation**, establish baseline performance:

| Metric | Expected Range | Interpretation |
|--------|----------------|----------------|
| **Faithfulness** | 0.75-0.90 | Response grounded in context |
| **Answer Relevancy** | 0.70-0.85 | Response addresses query |
| **Context Precision** | 0.60-0.80 | Relevant chunks ranked high |
| **Context Recall** | 0.65-0.85 | Retrieved necessary chunks |

**Regression Detection**:

```python
# Alert if score drops >10% from baseline
baseline = {
    "faithfulness": 0.85,
    "answer_relevancy": 0.78,
    "context_precision": 0.72,
    "context_recall": 0.80
}

current = {
    "faithfulness": 0.72,  # 15% drop!
    "answer_relevancy": 0.75,
    ...
}

for metric, baseline_score in baseline.items():
    current_score = current[metric]
    drop_pct = (baseline_score - current_score) / baseline_score
    
    if drop_pct > 0.10:  # >10% drop
        alert(f"⚠️ {metric} regression: {baseline_score:.2f} → {current_score:.2f}")
        # Investigate: Doc updates? Retrieval changes? LLM prompt changes?
```

### Human-LLM Agreement

**Quarterly audit**: Validate that LLM scores match human judgment

**Process**:

1. **Sample 100 evaluated responses**
2. **Humans rate on 1-5 scale**:
   - Faithfulness: Is response grounded?
   - Relevancy: Does it answer the query?

3. **Convert to 0-1 scale**: `(rating - 1) / 4`
4. **Compute correlation** with LLM scores

**Target**: Pearson correlation **>0.7** (strong agreement)

```python
from scipy.stats import pearsonr

human_scores = [0.8, 0.9, 0.6, 0.7, ...]  # 100 samples
llm_scores = [0.85, 0.88, 0.55, 0.72, ...]  # 100 samples

correlation, p_value = pearsonr(human_scores, llm_scores)

if correlation > 0.7:
    print(f"✅ Strong agreement (r={correlation:.2f}, p={p_value:.4f})")
else:
    print(f"⚠️ Weak agreement (r={correlation:.2f})")
    print("Action: Review annotation guidelines or LLM prompts")
```

**Low agreement causes**:
- Ambiguous annotation guidelines
- LLM prompt needs tuning
- Metric doesn't capture what humans value
- Dataset quality issues (noisy labels)

---

## Cost Analysis

### Evaluation Cost Breakdown

**Assumptions**:
- 1 workspace, 1000 queries/day
- Evaluate 10% (100 queries/day = 3000/month)
- Using GPT-4 for all metrics

**Monthly Cost**:

```
3000 evaluations/month × $0.17/eval = $510/month
```

**Annual Cost**: $6,120/year

**Cost Optimization Strategies**:

1. **Use GPT-3.5-turbo for some metrics** (10× cheaper):
   - Context Precision/Recall → GPT-3.5-turbo
   - Faithfulness/Relevancy → GPT-4
   - **Savings**: ~50% → **$255/month**

2. **Aggressive caching**:
   - Cache evaluations by content hash
   - Typical hit rate: 20-30%
   - **Savings**: ~25% → **$383/month**

3. **Sample only 1%** instead of 10%:
   - **Savings**: 90% → **$51/month**
   - **Trade-off**: Less statistical confidence

4. **Batch offline** (evaluate nightly):
   - Batch API pricing (50% discount)
   - **Savings**: 50% → **$255/month**

**Recommended**: 10% sampling + GPT-4 + caching = **~$380/month**

### Dataset Creation Cost

**One-time costs**:

| Activity | Hours | Hourly Rate | Cost |
|----------|-------|-------------|------|
| Query sampling | 2 | $100 | $200 |
| Annotation (50 queries) | 10 | $75 | $750 |
| Context vetting | 6 | $75 | $450 |
| Review & approval | 4 | $100 | $400 |
| MLflow setup | 3 | $150 | $450 |
| **Total** | **25 hours** | - | **$2,250** |

**Quarterly maintenance**: 6 hours × $75 = **$450/quarter**

**Annual cost**: $2,250 + ($450 × 4) = **$4,050/year**

**Total Year 1 Cost** (1 workspace):
- Dataset creation: $2,250
- Dataset maintenance: $1,800
- Evaluation (LLM API): $4,560 (10% sampling + optimizations)
- **Total**: **$8,610/year** or **$718/month**

---

## Example: Acme Workspace

**Scenario**: Acme Corp uses Certus-Ask for internal documentation Q&A (engineering team of 200)

### Week 1-2: Sampling

**Query Analysis**:
- 3 months of logs: 12,000 queries
- Unique queries: 450
- Top 30 queries: 60% of traffic

**Sample Selection**:
- 30 queries: Frequency-based (top queries)
- 15 queries: Diversity (one per doc category)
- 5 queries: Failure cases (low ratings)
- **Total**: 50 queries

**Output**: `acme_queries_selected.csv`

### Week 2-3: Annotation

**Team**:
- Technical writer (lead annotator)
- Product manager (reviewer)
- Engineering lead (approver)

**Process**:
- Technical writer: 6 hours (draft all 50 responses)
- Product manager: 3 hours (review, suggest changes)
- Revisions: 2 hours
- Context vetting: 4 hours (run retrieval, manually review)

**Total**: 15 hours over 2 weeks

### Week 3-4: Approval & Upload

**Final review**:
- Engineering lead: 1 hour (spot-check 10 entries, approve all)

**MLflow upload**:
- Export from Google Sheets → CSV
- Run conversion script → JSONL
- Upload to MLflow: `certus-evaluate-references-acme` v1

**Validation**:
- Test reference loader (loads 5 sample queries)
- Verify evaluator uses reference for precision/recall
- Document baseline metrics

### Results

**Dataset**:
- 50 reference entries
- Coverage: 85% (top 30 queries)
- Version 1 approved by engineering lead

**Baseline Metrics** (first week of evaluation):
- Faithfulness: 0.82
- Answer Relevancy: 0.76
- Context Precision: 0.70
- Context Recall: 0.78

**Quarterly Refresh** (Q2):
- Added 20 new queries (v2.0 features)
- Updated 5 responses (doc changes)
- New baseline: faithfulness improved to 0.85

**Impact**:
- Detected 3 regressions (scores dropped >10%)
- Identified 2 retrieval issues (low context recall)
- Improved documentation based on low scores

---

## Troubleshooting

### Issue: Low Coverage (<50%)

**Symptom**: Many queries have no reference entry

**Causes**:
- Dataset too small
- Queries are very diverse (long tail)
- New features/docs added recently

**Solutions**:
1. Increase dataset size (aim for 100-200 entries)
2. Add queries from recent logs (past 30 days)
3. Use query clustering to identify patterns

### Issue: Low Agreement (<0.5)

**Symptom**: Human ratings don't match LLM scores

**Causes**:
- Annotation guidelines unclear
- LLM prompt needs tuning
- Metric doesn't capture human judgment

**Solutions**:
1. Clarify annotation guidelines (examples of good/bad)
2. Review LLM prompt in RAGAS configuration
3. Add human-rated examples to dataset
4. Consider custom metric (fine-tune LLM for your domain)

### Issue: Stale Dataset (>180 days)

**Symptom**: Dataset hasn't been updated in 6+ months

**Causes**:
- No ownership/accountability
- Quarterly refresh not scheduled
- Product changes outpaced dataset

**Solutions**:
1. Assign dataset owner (product manager)
2. Set calendar reminders for quarterly refresh
3. Automate staleness alerts (email when >90 days)
4. Trigger refresh on major product releases

### Issue: High Annotation Time (>20 min/query)

**Symptom**: Annotators spending too long per query

**Causes**:
- Queries are complex
- Documentation is unclear/incomplete
- Annotators lack domain expertise

**Solutions**:
1. Simplify queries (focus on common patterns)
2. Improve documentation first (update docs → easier annotation)
3. Pair annotators with SMEs (1:1 sessions)
4. Use draft responses from Ask as starting point

---

## Summary

**What you've learned**:

1. ✅ **LLM-as-Judge mechanics**: How RAGAS uses LLMs to evaluate RAG systems
2. ✅ **Dataset structure**: ReferenceEntry model with query/response/context
3. ✅ **Creation workflow**: Sample → Annotate → Vet → Approve
4. ✅ **Tooling options**: Google Sheets → Label Studio → Custom webapp
5. ✅ **Storage pattern**: MLflow artifacts with versioning
6. ✅ **Governance**: Quarterly refresh, quality metrics, PII controls
7. ✅ **Cost analysis**: ~$380/month/workspace for evaluation

**Next steps**:

1. **Week 1-2**: Select 50-100 queries for your workspace
2. **Week 2-3**: Annotate ideal responses and vet context
3. **Week 3-4**: Review, approve, upload to MLflow
4. **Week 4**: Validate reference loader and establish baseline metrics
5. **Quarterly**: Refresh dataset (add/update/deprecate queries)

**Key takeaways**:

- Reference datasets enable full RAGAS metrics (precision/recall)
- LLM-as-Judge provides semantic evaluation (not just keyword matching)
- Cost: ~$0.17 per evaluation with GPT-4 (optimize to $0.02)
- Effort: 15 hours initial creation, 6 hours quarterly maintenance
- Quality: Track coverage, freshness, agreement, and uniqueness

**Questions?** See [certus-evaluate-implementation-guide.md](./certus-evaluate-implementation-guide.md) for technical implementation details.
