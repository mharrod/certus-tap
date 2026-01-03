# Security-Specialized Small Language Model (SLM) for Certus

**Status:** Draft v1.0
**Author:** System Architecture
**Date:** 2025-12-11
## Executive Summary

While large language models (GPT-4, Claude) excel at complex reasoning and planning, they are **expensive, slow, and overkill** for many routine security tasks. This proposal defines a **two-tier AI strategy** where Certus leverages both large LLMs (for complex tasks via AAIF) and a **security-specialized Small Language Model (SLM)** for high-frequency, domain-specific operations.

**The Problem:**

Current AI-assisted security workflows face a cost/performance tradeoff:
- **Large LLMs (GPT-4):** Powerful but expensive ($0.10+ per analysis) and slow (2-5 seconds)
- **Rule-based systems:** Fast and cheap but brittle and require constant maintenance
- **No middle ground:** Need domain-specialized AI that is fast, accurate, and cost-effective

**The Solution:**

A **security-specialized SLM (1-7B parameters)** that:
- Is **trained/fine-tuned on security-specific datasets** (CVEs, exploits, SARIF, vulnerability patterns)
- Handles **high-frequency tasks** (classification, triage, severity assessment, pattern detection)
- Runs **locally or on-premises** (sensitive security data never leaves infrastructure)
- Provides **10-100x cost reduction** vs. GPT-4 for routine tasks
- Achieves **sub-second inference** (<100ms) for real-time analysis

**Strategic Positioning:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Certus Two-Tier AI Architecture                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Tier 1: Large Language Models (Complex Reasoning)             │
│  ├─ Models: GPT-4, Claude, Llama 3 70B (via AAIF/MCP)         │
│  ├─ Use cases: Multi-step planning, remediation strategies,   │
│  │              incident response, compliance reporting         │
│  ├─ Cost: High ($0.10-$0.50 per run)                          │
│  └─ Latency: 2-5 seconds                                       │
│                                                                 │
│  Tier 2: Security-Specialized SLM (High-Frequency Tasks)       │
│  ├─ Model: Certus SecModel (1-7B params, fine-tuned)          │
│  ├─ Use cases: Vulnerability classification, triage, severity  │
│  │              assessment, pattern detection, false positive  │
│  │              filtering, exploit likelihood scoring           │
│  ├─ Cost: Very low ($0.001 per run or free if local)          │
│  └─ Latency: <100ms (real-time)                                │
│                                                                 │
│  Decision Flow:                                                 │
│  1. SLM performs fast triage/classification                    │
│  2. If complex reasoning needed → escalate to LLM (Tier 1)     │
│  3. If routine/pattern-based → SLM completes task              │
└─────────────────────────────────────────────────────────────────┘
```

**What This Enables:**

1. **Massive Cost Reduction** - 90%+ savings on routine security tasks (triage every scan vs. selective LLM use)
2. **Real-Time Analysis** - Sub-100ms inference enables real-time security checks in CI/CD, IDE, commit hooks
3. **Data Privacy** - Model runs entirely on-premises; sensitive security data never sent to cloud LLMs
4. **Domain Expertise** - Model understands security-specific concepts (CVEs, CWEs, CVSS, exploit patterns)
5. **Continuous Learning** - Fine-tune on Certus scan results to improve accuracy for your specific codebase/patterns
6. **Seamless Integration** - Exposed via MCP server, embedded in Certus services, callable from AAIF agents

**Business Impact:**

- **Cost:** 90%+ reduction in AI costs for security operations
- **Speed:** 10-50x faster vulnerability triage
- **Coverage:** Analyze every scan, every commit, every PR (not just selective analysis due to cost)
- **Accuracy:** >90% classification accuracy, >85% precision (low false positives)
- **Privacy:** No sensitive data leaves your infrastructure

This proposal complements the AAIF Agent Framework by providing a **fast, cost-effective, domain-specialized layer** beneath the general-purpose LLM orchestration.

## Motivation

### Current State

**AI in Certus Today:**
- **Certus-Ask:** Uses RAG + large LLMs for Q&A and knowledge retrieval
- **AAIF Agents:** Use large LLMs (GPT-4, Claude) for planning and orchestration
- **No specialized models:** All AI is general-purpose, not security-optimized

**Current Workflow for Vulnerability Analysis:**

```
Developer commits code
  ↓
Certus-Assurance runs scan (Dagger pipeline)
  ↓
SARIF results generated (could be 100s-1000s of findings)
  ↓
[Manual triage required]
  OR
[Expensive GPT-4 call to analyze all findings]
  ↓
Developer reviews and fixes
```

**Problems:**

1. **Manual triage is slow and error-prone**
   - Developers spend hours reviewing findings
   - Hard to prioritize (which are critical? which are false positives?)

2. **GPT-4 analysis is too expensive for every scan**
   - Cost: $0.10-$0.50 per scan analysis
   - At scale: 1000 scans/day = $100-$500/day = $36K-$182K/year
   - Can't afford to analyze every commit, every PR

3. **Delayed feedback**
   - Scans run, but analysis is batched or manual
   - Developers don't get immediate actionable feedback

4. **No domain specialization**
   - GPT-4 is general-purpose, may hallucinate security details
   - Not optimized for security-specific tasks
   - Doesn't learn from your organization's patterns

5. **Data privacy concerns**
   - Sending sensitive security data to OpenAI/Anthropic
   - Compliance issues (GDPR, SOC2, HIPAA)

### Why a Security-Specialized SLM?

#### Performance Comparison

| Capability                  | Manual | Rule-Based | GPT-4 | Security SLM |
|-----------------------------|--------|------------|-------|--------------|
| **Vulnerability Classification** | ✅ Accurate | ⚠️ Brittle | ✅ Accurate | ✅ Accurate |
| **Severity Assessment**     | ✅ Accurate | ⚠️ Rigid | ✅ Flexible | ✅ Accurate |
| **False Positive Detection**| ✅ Expert | ❌ Poor | ✅ Good | ✅ Very Good |
| **Pattern Detection**       | ⚠️ Slow | ✅ Fast | ⚠️ Slow | ✅ Very Fast |
| **Cost per Analysis**       | $5-10 (labor) | ~$0 | $0.10-$0.50 | $0.001-$0.01 |
| **Latency**                 | Minutes-Hours | <1ms | 2-5s | <100ms |
| **Scalability**             | ❌ Limited | ✅ High | ⚠️ Medium | ✅ Very High |
| **Domain Knowledge**        | ✅ Expert | ⚠️ Encoded | ⚠️ General | ✅ Specialized |
| **Continuous Learning**     | ✅ Yes | ❌ No | ⚠️ Limited | ✅ Yes |
| **Data Privacy**            | ✅ Private | ✅ Private | ❌ Cloud | ✅ Private |

**Key Insight:** Security SLM combines the accuracy of GPT-4 with the speed/cost of rule-based systems, while maintaining data privacy.

#### What Makes Security Different from General-Purpose LLMs?

**Domain-Specific Knowledge:**
- CVE database structure and semantics
- CWE taxonomy and relationships
- CVSS scoring methodology
- Exploit patterns and signatures
- Language-specific vulnerability patterns (Python vs. Java vs. JavaScript)
- Framework-specific security issues (Django, React, Spring Boot)
- SARIF/SBOM format understanding

**Security-Specific Tasks:**
- Vulnerability type classification (not general text classification)
- Exploit likelihood assessment (requires security expertise)
- Remediation prioritization (risk-based, not just severity)
- False positive detection (security context required)
- Code pattern matching for vulnerabilities

**Organizational Context:**
- Your codebase patterns and conventions
- Your historical vulnerability patterns
- Your false positive patterns
- Your security policies and risk tolerance
- Your tech stack and frameworks

A fine-tuned security SLM can **learn all of this** and provide better, faster, cheaper analysis than a general-purpose LLM.

### Problems Addressed

| Problem | Impact | SLM Solution |
|---------|--------|--------------|
| **High AI costs** | Can't analyze every scan ($36K-$182K/year) | 90%+ cost reduction, analyze everything |
| **Slow triage** | Developers wait hours for feedback | Real-time analysis (<100ms) |
| **False positives** | Noise overwhelms signal, low trust | Learned FP patterns, high precision |
| **No prioritization** | Developers don't know what to fix first | Risk-based scoring and ranking |
| **Data privacy** | Security data sent to cloud providers | Local/on-prem deployment |
| **Generic AI** | Hallucinations, no domain expertise | Security-trained, domain-specialized |
| **No learning** | Same mistakes repeated | Continuous fine-tuning on your data |

## Goals & Non-Goals

| Goals | Non-Goals |
|-------|-----------|
| Train/fine-tune a security-specialized SLM (1-7B params) | Replace large LLMs entirely (complementary, not replacement) |
| Achieve >90% accuracy on vulnerability classification | Build AGI for security (focused domain model) |
| Reduce AI costs by 90%+ for routine security tasks | Support all possible security tasks (focus on high-value) |
| Enable real-time security analysis (<100ms latency) | Perfect accuracy (acceptable to escalate to human/LLM) |
| Run entirely on-premises for data privacy | Train model from scratch (fine-tune existing model) |
| Integrate with AAIF architecture via MCP | Build a separate agent framework |
| Continuously learn from Certus scan results | Retrain on every single scan (batch retraining) |
| Provide explainable outputs (why this classification?) | Black-box model (interpretability required) |

## Proposed Solution

### Model Selection & Training Strategy

#### Phase 1: Fine-Tuning Approach (Recommended)

**Base Model Selection:**

We'll fine-tune an existing high-quality SLM rather than training from scratch. Candidates:

| Model | Parameters | Context Length | Strengths | License |
|-------|-----------|----------------|-----------|---------|
| **Llama 3.2 (1B/3B)** | 1B or 3B | 128K | Excellent performance, long context, latest architecture | Llama 3 (permissive) |
| **Phi-3.5-mini** | 3.8B | 128K | Strong reasoning, instruction-following, Microsoft-backed | MIT |
| **Mistral 7B** | 7B | 32K | High quality, widely used, good documentation | Apache 2.0 |
| **Qwen2.5 (3B/7B)** | 3B or 7B | 32K | Strong coding capabilities, multilingual | Apache 2.0 |

**Recommendation: Llama 3.2 (3B)**

Reasoning:
- ✅ **Excellent base performance** - Strong instruction-following and reasoning
- ✅ **Long context (128K)** - Can process entire SARIF files, long code snippets
- ✅ **Latest architecture** - Benefits from Meta's recent research
- ✅ **Permissive license** - Can deploy commercially
- ✅ **Efficient** - 3B is sweet spot for accuracy vs. speed
- ✅ **Strong community** - Good tooling, examples, support

**Fallback: Phi-3.5-mini (3.8B)** if we need stronger reasoning or Microsoft ecosystem integration.

#### Training Data Strategy

**Objective:** Fine-tune Llama 3.2 (3B) on security-specific tasks using curated datasets.

##### Dataset Sources

**1. Public Security Datasets (Foundation)**

```
NVD (National Vulnerability Database)
├─ 250K+ CVE records with descriptions
├─ CVSS scores and vectors
├─ CWE mappings
└─ References and exploit availability

CWE (Common Weakness Enumeration)
├─ 900+ weakness types with descriptions
├─ Code examples (vulnerable vs. secure)
├─ Relationships and taxonomy
└─ Detection methods

CAPEC (Common Attack Pattern Enumeration)
├─ 500+ attack patterns
├─ Prerequisites and indicators
└─ Mitigations

Exploit Databases
├─ Exploit-DB (50K+ exploits)
├─ Metasploit modules
├─ PoC repositories
└─ Security advisories (GitHub, vendors)

Security Code Datasets
├─ SARD (Software Assurance Reference Dataset)
├─ Juliet Test Suite (vulnerable code examples)
├─ OWASP Code Examples
├─ GitHub Security Advisories
└─ CVE patch commits (vulnerable → fixed)
```

**2. Certus-Specific Data (Specialization)**

```
Historical Scan Results
├─ SARIF files (10K+ scans, if available)
├─ SBOM data
├─ Scan metadata (duration, tools used)
└─ Artifact information

Human Annotations
├─ True positives vs. false positives (labeled)
├─ Severity assessments (human expert judgments)
├─ Prioritization decisions (what was fixed first)
├─ Remediation outcomes (what fixes worked)
└─ Code review feedback

Organizational Context
├─ Security policies (encoded as examples)
├─ Approved/prohibited patterns
├─ Technology stack patterns
├─ Framework-specific rules
└─ Historical vulnerability patterns by team/repo
```

**3. Synthetic Data (Augmentation)**

```
Code Generation
├─ Generate vulnerable code variants
├─ Generate secure alternatives
├─ Mutate existing examples
└─ Create edge cases

SARIF Generation
├─ Synthetic SARIF with known issues
├─ Varied severity distributions
├─ Different tool outputs
└─ Complex multi-file findings

Scenario Generation
├─ Triage scenarios with context
├─ Prioritization exercises
└─ Remediation planning examples
```

##### Training Tasks

Fine-tune the model on these specific tasks:

**Task 1: Vulnerability Classification**

```
Input: Code snippet + context
Output: Vulnerability type (SQL Injection, XSS, etc.) or "None"

Example:
Input: "cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')"
Output: "SQL Injection (CWE-89)"
```

**Task 2: Severity Assessment**

```
Input: Vulnerability description + code context + environment
Output: CVSS base score or severity level (Critical/High/Medium/Low)

Example:
Input: "SQL injection in admin panel, no authentication required, database contains PII"
Output: "CVSS 9.8 (Critical) - Remote code execution risk, sensitive data exposure"
```

**Task 3: False Positive Detection**

```
Input: SARIF finding + code context
Output: True Positive or False Positive + reasoning

Example:
Input: "Potential SQL injection in cursor.execute(query, params)"
Output: "False Positive - Parameterized query is used, no string interpolation"
```

**Task 4: Exploit Likelihood**

```
Input: Vulnerability details + code context + deployment info
Output: Exploit likelihood (High/Medium/Low) + reasoning

Example:
Input: "XSS in admin-only page, requires authentication, output encoding missing"
Output: "Medium - Requires authentication which limits attack surface, but admin accounts are high-value targets"
```

**Task 5: Triage and Prioritization**

```
Input: List of vulnerabilities with context
Output: Ranked list with priority reasoning

Example:
Input: [SQL Injection in public API, XSS in internal tool, outdated dependency]
Output:
1. SQL Injection (Critical - public exposure, data breach risk)
2. Outdated dependency (High - known CVE with exploit available)
3. XSS in internal tool (Medium - limited exposure, requires auth)
```

**Task 6: Pattern Detection**

```
Input: Code snippet
Output: List of security anti-patterns detected

Example:
Input: "password = request.GET['password']; hash = md5(password)"
Output:
- Password in GET parameter (should use POST)
- MD5 for password hashing (use bcrypt/argon2)
- No salt detected
```

**Task 7: Remediation Suggestion**

```
Input: Vulnerability description + vulnerable code
Output: Secure code alternative + explanation

Example:
Input: "SQL injection in: cursor.execute(f'DELETE FROM users WHERE id = {uid}')"
Output: "Use parameterized query: cursor.execute('DELETE FROM users WHERE id = %s', (uid,))"
```

##### Dataset Preparation Pipeline

```python
# certus_slm/data/pipeline.py
class SecurityDatasetPipeline:
    """
    Prepare training data for security SLM.
    """

    async def prepare_training_data(self) -> Dataset:
        """
        Combine all data sources into training dataset.
        """
        datasets = []

        # 1. Public security data
        nvd_data = await self._process_nvd()
        cwe_data = await self._process_cwe()
        exploit_data = await self._process_exploits()
        code_examples = await self._process_code_examples()

        datasets.extend([nvd_data, cwe_data, exploit_data, code_examples])

        # 2. Certus-specific data
        if certus_data_available():
            sarif_data = await self._process_sarif_files()
            annotations = await self._load_human_annotations()
            datasets.extend([sarif_data, annotations])

        # 3. Synthetic data
        synthetic = await self._generate_synthetic_data()
        datasets.append(synthetic)

        # Combine and shuffle
        combined = self._combine_datasets(datasets)

        # Split train/val/test
        train, val, test = self._split_dataset(combined, ratios=[0.8, 0.1, 0.1])

        return {
            "train": train,
            "validation": val,
            "test": test
        }

    async def _process_nvd(self) -> Dataset:
        """Process NVD CVE data into training examples."""
        examples = []

        # Download NVD feeds
        nvd_feeds = await download_nvd_feeds()

        for cve in nvd_feeds:
            # Classification task
            examples.append({
                "task": "classify",
                "input": f"CVE: {cve['description']}",
                "output": cve['cwe_id'],
                "metadata": {"cve_id": cve['id'], "cvss": cve['cvss']}
            })

            # Severity assessment task
            examples.append({
                "task": "assess_severity",
                "input": cve['description'],
                "output": f"CVSS {cve['cvss_score']} ({cve['severity']})",
                "metadata": {"cve_id": cve['id']}
            })

        return Dataset.from_list(examples)

    async def _process_cwe(self) -> Dataset:
        """Process CWE data for pattern detection."""
        examples = []

        cwe_data = await download_cwe_database()

        for cwe in cwe_data:
            if cwe.get('code_examples'):
                for example in cwe['code_examples']:
                    # Pattern detection task
                    examples.append({
                        "task": "detect_pattern",
                        "input": example['vulnerable_code'],
                        "output": f"Vulnerable pattern detected: {cwe['name']} (CWE-{cwe['id']})",
                        "metadata": {"cwe_id": cwe['id']}
                    })

                    # Remediation task
                    if example.get('secure_code'):
                        examples.append({
                            "task": "remediate",
                            "input": f"Fix this vulnerability:\n{example['vulnerable_code']}",
                            "output": example['secure_code'],
                            "metadata": {"cwe_id": cwe['id']}
                        })

        return Dataset.from_list(examples)

    async def _process_sarif_files(self) -> Dataset:
        """Process Certus SARIF files for triage training."""
        examples = []

        # Load historical SARIF files
        sarif_files = await load_certus_sarif_files()

        for sarif in sarif_files:
            for result in sarif['runs'][0]['results']:
                # Get human annotation if available
                annotation = await get_annotation(result['id'])

                if annotation:
                    # False positive detection
                    examples.append({
                        "task": "false_positive_detection",
                        "input": self._format_sarif_finding(result),
                        "output": "True Positive" if annotation['is_real'] else "False Positive",
                        "explanation": annotation['reasoning'],
                        "metadata": {"finding_id": result['id']}
                    })

                    # Severity assessment (if human adjusted)
                    if annotation.get('severity_override'):
                        examples.append({
                            "task": "assess_severity",
                            "input": self._format_sarif_finding(result),
                            "output": annotation['severity_override'],
                            "explanation": annotation['severity_reasoning'],
                            "metadata": {"finding_id": result['id']}
                        })

        return Dataset.from_list(examples)

    def _format_sarif_finding(self, result: dict) -> str:
        """Format SARIF result as training input."""
        return f"""
Finding: {result['message']['text']}
Rule: {result['ruleId']}
Severity: {result['level']}
Location: {result['locations'][0]['physicalLocation']['artifactLocation']['uri']}
Code Snippet: {self._get_code_snippet(result)}
"""

    async def _generate_synthetic_data(self) -> Dataset:
        """Generate synthetic training examples."""
        examples = []

        # Use GPT-4 to generate diverse vulnerable code examples
        generator = SyntheticDataGenerator()

        # Generate SQL injection variants
        sql_examples = await generator.generate_variants(
            vulnerability_type="SQL Injection",
            languages=["Python", "Java", "JavaScript", "PHP"],
            count=1000
        )
        examples.extend(sql_examples)

        # Generate XSS variants
        xss_examples = await generator.generate_variants(
            vulnerability_type="XSS",
            languages=["JavaScript", "TypeScript", "HTML"],
            count=1000
        )
        examples.extend(xss_examples)

        # ... generate for other vulnerability types

        return Dataset.from_list(examples)
```

#### Fine-Tuning Process

**Infrastructure:**

```
Hardware Requirements:
├─ Training: 1x A100 (80GB) or 4x A10G (24GB each)
├─ Training time: 24-48 hours (estimated)
├─ Inference: CPU (fast enough) or 1x T4 GPU (for production scale)
└─ Cost: ~$100-500 for training (one-time)
```

**Training Configuration:**

```python
# certus_slm/training/config.py
training_config = {
    # Base model
    "base_model": "meta-llama/Llama-3.2-3B-Instruct",

    # Training hyperparameters
    "learning_rate": 2e-5,
    "batch_size": 8,
    "gradient_accumulation_steps": 4,
    "num_epochs": 3,
    "warmup_steps": 100,
    "weight_decay": 0.01,

    # LoRA (efficient fine-tuning)
    "use_lora": True,
    "lora_r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.1,
    "lora_target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],

    # Training optimizations
    "fp16": True,
    "gradient_checkpointing": True,

    # Evaluation
    "eval_steps": 500,
    "save_steps": 1000,
    "logging_steps": 100,

    # Output
    "output_dir": "certus-secmodel-v1",
    "save_total_limit": 3
}
```

**Training Script:**

```python
# certus_slm/training/train.py
from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments
from peft import LoraConfig, get_peft_model
from datasets import load_dataset

def train_security_slm():
    """Train security-specialized SLM."""

    # 1. Load base model
    model_name = "meta-llama/Llama-3.2-3B-Instruct"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        device_map="auto"
    )

    # 2. Configure LoRA for efficient fine-tuning
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=0.1,
        bias="none",
        task_type="CAUSAL_LM"
    )
    model = get_peft_model(model, lora_config)

    # 3. Load prepared dataset
    dataset = load_dataset("certus/security-training-data")

    # 4. Configure training
    training_args = TrainingArguments(
        output_dir="certus-secmodel-v1",
        num_train_epochs=3,
        per_device_train_batch_size=8,
        gradient_accumulation_steps=4,
        learning_rate=2e-5,
        fp16=True,
        logging_steps=100,
        eval_steps=500,
        save_steps=1000,
        evaluation_strategy="steps",
        save_total_limit=3,
        load_best_model_at_end=True,
        report_to="wandb"
    )

    # 5. Train
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        tokenizer=tokenizer,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False)
    )

    trainer.train()

    # 6. Save final model
    model.save_pretrained("certus-secmodel-v1-final")
    tokenizer.save_pretrained("certus-secmodel-v1-final")

    # 7. Evaluate on test set
    test_results = trainer.evaluate(dataset["test"])
    print(f"Test results: {test_results}")

    return model, tokenizer
```

#### Evaluation Framework

**Benchmark Tasks:**

```python
# certus_slm/evaluation/benchmarks.py
class SecuritySLMBenchmark:
    """Comprehensive evaluation of security SLM."""

    def __init__(self, model, tokenizer):
        self.model = model
        self.tokenizer = tokenizer

    async def run_full_evaluation(self) -> dict:
        """Run all benchmark tasks."""
        results = {}

        # 1. Classification accuracy
        results['classification'] = await self._eval_classification()

        # 2. Severity assessment
        results['severity'] = await self._eval_severity()

        # 3. False positive detection
        results['false_positive'] = await self._eval_false_positives()

        # 4. Triage quality
        results['triage'] = await self._eval_triage()

        # 5. Inference latency
        results['latency'] = await self._eval_latency()

        # 6. Comparison with GPT-4
        results['vs_gpt4'] = await self._compare_with_gpt4()

        return results

    async def _eval_classification(self) -> dict:
        """Evaluate vulnerability classification accuracy."""
        test_set = load_classification_test_set()

        correct = 0
        total = len(test_set)

        for example in test_set:
            prediction = await self._classify(example['code'])
            if prediction == example['label']:
                correct += 1

        accuracy = correct / total

        return {
            "accuracy": accuracy,
            "total_examples": total,
            "target": 0.90  # 90% target
        }

    async def _eval_severity(self) -> dict:
        """Evaluate CVSS scoring accuracy."""
        test_set = load_severity_test_set()

        mae = 0  # Mean absolute error
        within_1_point = 0

        for example in test_set:
            predicted_cvss = await self._assess_severity(example['vulnerability'])
            true_cvss = example['cvss_score']

            error = abs(predicted_cvss - true_cvss)
            mae += error

            if error <= 1.0:
                within_1_point += 1

        mae /= len(test_set)
        accuracy_within_1 = within_1_point / len(test_set)

        return {
            "mean_absolute_error": mae,
            "accuracy_within_1_point": accuracy_within_1,
            "target_mae": 0.5
        }

    async def _eval_false_positives(self) -> dict:
        """Evaluate false positive detection."""
        test_set = load_fp_test_set()

        tp, fp, tn, fn = 0, 0, 0, 0

        for example in test_set:
            prediction = await self._detect_false_positive(example['finding'])
            true_label = example['is_true_positive']

            if prediction and true_label:
                tp += 1
            elif prediction and not true_label:
                fp += 1
            elif not prediction and not true_label:
                tn += 1
            else:
                fn += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        return {
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "target_precision": 0.85,
            "target_recall": 0.90
        }

    async def _eval_latency(self) -> dict:
        """Measure inference latency."""
        test_inputs = load_latency_test_set()

        latencies = []

        for input_text in test_inputs:
            start = time.time()
            _ = await self._infer(input_text)
            latency_ms = (time.time() - start) * 1000
            latencies.append(latency_ms)

        return {
            "p50_ms": np.percentile(latencies, 50),
            "p95_ms": np.percentile(latencies, 95),
            "p99_ms": np.percentile(latencies, 99),
            "mean_ms": np.mean(latencies),
            "target_p95_ms": 100
        }

    async def _compare_with_gpt4(self) -> dict:
        """Compare SLM performance vs GPT-4."""
        test_set = load_comparison_test_set()

        slm_correct = 0
        gpt4_correct = 0
        both_correct = 0

        for example in test_set:
            slm_pred = await self._classify(example['code'])
            gpt4_pred = await self._classify_with_gpt4(example['code'])

            slm_is_correct = (slm_pred == example['label'])
            gpt4_is_correct = (gpt4_pred == example['label'])

            if slm_is_correct:
                slm_correct += 1
            if gpt4_is_correct:
                gpt4_correct += 1
            if slm_is_correct and gpt4_is_correct:
                both_correct += 1

        return {
            "slm_accuracy": slm_correct / len(test_set),
            "gpt4_accuracy": gpt4_correct / len(test_set),
            "agreement_rate": both_correct / len(test_set),
            "slm_cost_per_100": 0.10,  # $0.001 * 100
            "gpt4_cost_per_100": 10.00  # $0.10 * 100
        }
```

**Success Criteria:**

| Metric | Target | Measurement |
|--------|--------|-------------|
| Classification Accuracy | >90% | % correct vulnerability type predictions |
| Severity MAE | <0.5 points | Mean absolute error on CVSS scoring |
| False Positive Precision | >85% | % of flagged FPs that are actually FPs |
| False Positive Recall | >90% | % of actual FPs that are detected |
| Inference Latency (p95) | <100ms | 95th percentile inference time |
| vs GPT-4 Accuracy | >85% of GPT-4 | Performance relative to GPT-4 baseline |
| Cost Reduction | >90% | Cost savings vs GPT-4 for same tasks |

### Deployment Architecture

#### Three Deployment Options

```
┌─────────────────────────────────────────────────────────────┐
│         Security SLM Deployment Architecture                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Option 1: Embedded in Services (Low Latency)              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Certus-Assurance Pod                              │    │
│  │  ├─ Assurance API                                  │    │
│  │  ├─ Dagger Pipeline                                │    │
│  │  └─ SLM Inference Engine (embedded)                │    │
│  │      └─ certus-secmodel-v1 (3B params)             │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  Pros: Ultra-low latency (<50ms), no network overhead      │
│  Cons: Higher memory per pod (6-8GB), harder to update     │
│  Use for: Real-time scan analysis during pipeline          │
│                                                             │
│  Option 2: Dedicated Inference Service (Scalable)          │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Certus SLM Inference Service                      │    │
│  │  ├─ vLLM Server (GPU-accelerated)                  │    │
│  │  ├─ Model: certus-secmodel-v1                      │    │
│  │  ├─ HTTP API (OpenAI-compatible)                   │    │
│  │  └─ Autoscaling (based on request volume)          │    │
│  └────────────────────────────────────────────────────┘    │
│                   ↑                                         │
│                   │ (HTTP calls)                            │
│         ┌─────────┴─────────┐                               │
│         ↓                   ↓                               │
│  ┌─────────────┐    ┌─────────────┐                        │
│  │ Assurance   │    │ Trust       │                        │
│  │ Service     │    │ Service     │    ...                 │
│  └─────────────┘    └─────────────┘                        │
│                                                             │
│  Pros: Shared resource, easy updates, cost-efficient       │
│  Cons: Network latency (~10-20ms), central bottleneck      │
│  Use for: Multi-service access, production deployment      │
│                                                             │
│  Option 3: MCP Server (AAIF Integration)                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │  certus-secmodel-mcp-server                        │    │
│  │  ├─ MCP Protocol Handler                           │    │
│  │  ├─ Model: certus-secmodel-v1                      │    │
│  │  └─ Tools:                                         │    │
│  │      ├─ classify_vulnerability                     │    │
│  │      ├─ assess_severity                            │    │
│  │      ├─ detect_false_positive                      │    │
│  │      ├─ triage_findings                            │    │
│  │      └─ suggest_remediation                        │    │
│  └────────────────────────────────────────────────────┘    │
│                   ↑                                         │
│                   │ (MCP protocol)                          │
│         ┌─────────┴─────────┐                               │
│         ↓                   ↓                               │
│  ┌─────────────┐    ┌─────────────┐                        │
│  │ Goose Agent │    │ Claude      │    Any MCP Client      │
│  └─────────────┘    │ Desktop     │                        │
│                     └─────────────┘                        │
│                                                             │
│  Pros: AAIF ecosystem integration, agent-accessible        │
│  Cons: Additional protocol overhead                        │
│  Use for: Agent workflows, IDE integrations                │
│                                                             │
│  Recommendation: Use ALL THREE (different use cases)       │
└─────────────────────────────────────────────────────────────┘
```

#### Recommended Hybrid Approach

**Deployment Strategy:**

1. **Option 2 (Dedicated Service)** as primary deployment
   - Shared inference service using vLLM
   - GPU-accelerated for performance
   - All Certus services call this

2. **Option 3 (MCP Server)** for AAIF integration
   - Wraps the dedicated service
   - Exposes via MCP protocol
   - Agents and IDEs can access

3. **Option 1 (Embedded)** for critical paths only (optional)
   - If latency requirements are extreme (<50ms)
   - Only for high-frequency operations

#### Implementation: Dedicated Inference Service

```python
# certus_slm/inference/server.py
from vllm import LLM, SamplingParams
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Certus Security SLM Inference Service")

# Load model
model = LLM(
    model="certus-secmodel-v1",
    tensor_parallel_size=1,  # Single GPU
    dtype="float16",
    max_model_len=4096,
    gpu_memory_utilization=0.9
)

sampling_params = SamplingParams(
    temperature=0.1,  # Low temperature for consistency
    top_p=0.95,
    max_tokens=512
)

class ClassificationRequest(BaseModel):
    code: str
    context: str = ""

class SeverityRequest(BaseModel):
    vulnerability: str
    code: str = ""
    environment: str = ""

class TriageRequest(BaseModel):
    findings: list[dict]
    context: str = ""

@app.post("/v1/classify")
async def classify_vulnerability(request: ClassificationRequest):
    """Classify vulnerability type."""

    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a security expert specialized in vulnerability classification.
Classify the vulnerability type in the provided code.<|eot_id|>

<|start_header_id|>user<|end_header_id|>
Code:
{request.code}

Context: {request.context}

Classify the vulnerability (e.g., SQL Injection, XSS, etc.) or respond "None" if no vulnerability.<|eot_id|>

<|start_header_id|>assistant<|end_header_id|>"""

    outputs = model.generate([prompt], sampling_params)
    result = outputs[0].outputs[0].text.strip()

    return {
        "vulnerability_type": result,
        "confidence": _extract_confidence(result),
        "model": "certus-secmodel-v1"
    }

@app.post("/v1/assess-severity")
async def assess_severity(request: SeverityRequest):
    """Assess vulnerability severity."""

    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a security expert specialized in CVSS scoring.
Assess the severity of the vulnerability.<|eot_id|>

<|start_header_id|>user<|end_header_id|>
Vulnerability: {request.vulnerability}
Code: {request.code}
Environment: {request.environment}

Provide CVSS base score (0-10) and severity level (Critical/High/Medium/Low) with reasoning.<|eot_id|>

<|start_header_id|>assistant<|end_header_id|>"""

    outputs = model.generate([prompt], sampling_params)
    result = outputs[0].outputs[0].text.strip()

    return {
        "assessment": result,
        "cvss_score": _extract_cvss(result),
        "severity": _extract_severity(result),
        "model": "certus-secmodel-v1"
    }

@app.post("/v1/triage")
async def triage_findings(request: TriageRequest):
    """Triage and prioritize findings."""

    findings_text = "\n".join([
        f"{i+1}. {f['rule_id']}: {f['message']} (Severity: {f['level']})"
        for i, f in enumerate(request.findings)
    ])

    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a security expert specializing in vulnerability triage.
Analyze the findings and provide a prioritized list with reasoning.<|eot_id|>

<|start_header_id|>user<|end_header_id|>
Findings:
{findings_text}

Context: {request.context}

Prioritize these findings and explain your reasoning.<|eot_id|>

<|start_header_id|>assistant<|end_header_id|>"""

    outputs = model.generate([prompt], sampling_params)
    result = outputs[0].outputs[0].text.strip()

    return {
        "triage": result,
        "prioritized_ids": _extract_prioritized_ids(result),
        "model": "certus-secmodel-v1"
    }

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "model": "certus-secmodel-v1"}

# Helper functions
def _extract_confidence(text: str) -> float:
    """Extract confidence score from output."""
    # Parse output for confidence indicators
    # Simple heuristic for now
    return 0.85

def _extract_cvss(text: str) -> float:
    """Extract CVSS score from output."""
    import re
    match = re.search(r'CVSS:?\s*(\d+\.\d+)', text)
    return float(match.group(1)) if match else 0.0

def _extract_severity(text: str) -> str:
    """Extract severity level from output."""
    text_lower = text.lower()
    if 'critical' in text_lower:
        return 'critical'
    elif 'high' in text_lower:
        return 'high'
    elif 'medium' in text_lower:
        return 'medium'
    else:
        return 'low'

def _extract_prioritized_ids(text: str) -> list[int]:
    """Extract prioritized finding IDs."""
    import re
    matches = re.findall(r'(\d+)\.', text)
    return [int(m) for m in matches]
```

**Deployment (Kubernetes):**

```yaml
# certus-slm-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: certus-slm-inference
  namespace: certus-tap
spec:
  replicas: 2  # Start with 2 for HA
  selector:
    matchLabels:
      app: certus-slm-inference
  template:
    metadata:
      labels:
        app: certus-slm-inference
    spec:
      containers:
      - name: inference-server
        image: certus/slm-inference:v1
        resources:
          requests:
            memory: "16Gi"
            cpu: "4"
            nvidia.com/gpu: "1"  # T4 or A10G
          limits:
            memory: "24Gi"
            cpu: "8"
            nvidia.com/gpu: "1"
        ports:
        - containerPort: 8000
        env:
        - name: MODEL_PATH
          value: "/models/certus-secmodel-v1"
        - name: GPU_MEMORY_UTILIZATION
          value: "0.9"
        volumeMounts:
        - name: model-storage
          mountPath: /models
      volumes:
      - name: model-storage
        persistentVolumeClaim:
          claimName: certus-slm-models
---
apiVersion: v1
kind: Service
metadata:
  name: certus-slm-inference
  namespace: certus-tap
spec:
  selector:
    app: certus-slm-inference
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: certus-slm-inference-hpa
  namespace: certus-tap
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: certus-slm-inference
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### Implementation: MCP Server

```python
# certus_slm/mcp/server.py
from mcp.server import Server
from mcp.types import Tool
import httpx

server = Server("certus-secmodel-mcp")

# HTTP client for inference service
client = httpx.AsyncClient(base_url="http://certus-slm-inference.certus-tap")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="classify_vulnerability",
            description="Classify vulnerability type in code",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "context": {"type": "string"}
                },
                "required": ["code"]
            }
        ),
        Tool(
            name="assess_severity",
            description="Assess vulnerability severity (CVSS scoring)",
            inputSchema={
                "type": "object",
                "properties": {
                    "vulnerability": {"type": "string"},
                    "code": {"type": "string"},
                    "environment": {"type": "string"}
                },
                "required": ["vulnerability"]
            }
        ),
        Tool(
            name="detect_false_positive",
            description="Detect if a finding is a false positive",
            inputSchema={
                "type": "object",
                "properties": {
                    "finding": {"type": "object"},
                    "code": {"type": "string"}
                },
                "required": ["finding"]
            }
        ),
        Tool(
            name="triage_findings",
            description="Triage and prioritize multiple findings",
            inputSchema={
                "type": "object",
                "properties": {
                    "findings": {"type": "array", "items": {"type": "object"}},
                    "context": {"type": "string"}
                },
                "required": ["findings"]
            }
        ),
        Tool(
            name="suggest_remediation",
            description="Suggest remediation for a vulnerability",
            inputSchema={
                "type": "object",
                "properties": {
                    "vulnerability": {"type": "string"},
                    "code": {"type": "string"}
                },
                "required": ["vulnerability", "code"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> str:
    """Call SLM inference service."""

    if name == "classify_vulnerability":
        response = await client.post("/v1/classify", json=arguments)
        return response.json()

    elif name == "assess_severity":
        response = await client.post("/v1/assess-severity", json=arguments)
        return response.json()

    elif name == "detect_false_positive":
        # Convert finding to prompt
        finding = arguments["finding"]
        code = arguments.get("code", "")

        prompt_data = {
            "finding": f"{finding['rule_id']}: {finding['message']}",
            "code": code
        }

        response = await client.post("/v1/detect-false-positive", json=prompt_data)
        return response.json()

    elif name == "triage_findings":
        response = await client.post("/v1/triage", json=arguments)
        return response.json()

    elif name == "suggest_remediation":
        response = await client.post("/v1/remediate", json=arguments)
        return response.json()

    else:
        raise ValueError(f"Unknown tool: {name}")
```

### Integration with Certus Services

#### Certus-Assurance Integration

```python
# certus_assurance/analysis/slm_analyzer.py
from certus_slm.client import SLMClient

class SLMSecurityAnalyzer:
    """
    Integrate SLM into Certus-Assurance pipeline.
    """

    def __init__(self):
        self.slm_client = SLMClient("http://certus-slm-inference.certus-tap")

    async def analyze_scan_results(self, sarif_results: dict) -> dict:
        """
        Analyze SARIF results using SLM.

        Provides:
        - Classification of vulnerabilities
        - Severity assessment
        - False positive detection
        - Prioritized list for remediation
        """
        findings = sarif_results['runs'][0]['results']

        # 1. Classify and assess each finding
        analyzed_findings = []
        for finding in findings:
            # Get code snippet
            code = await self._get_code_snippet(finding)

            # Classify vulnerability type (if not already classified)
            if not finding.get('classified'):
                classification = await self.slm_client.classify(code)
                finding['slm_classification'] = classification

            # Assess severity
            severity = await self.slm_client.assess_severity(
                vulnerability=finding['message']['text'],
                code=code
            )
            finding['slm_severity'] = severity

            # Detect false positives
            fp_check = await self.slm_client.detect_false_positive(
                finding=finding,
                code=code
            )
            finding['slm_false_positive'] = fp_check

            analyzed_findings.append(finding)

        # 2. Triage and prioritize
        triage = await self.slm_client.triage_findings(
            findings=analyzed_findings,
            context=self._build_context(sarif_results)
        )

        # 3. Generate summary
        summary = self._generate_summary(analyzed_findings, triage)

        return {
            "findings": analyzed_findings,
            "triage": triage,
            "summary": summary,
            "slm_analyzed": True,
            "slm_model": "certus-secmodel-v1"
        }

    async def real_time_check(self, code: str, language: str) -> dict:
        """
        Real-time security check during code editing.

        Fast (<100ms) analysis for IDE integration.
        """
        # Pattern detection
        patterns = await self.slm_client.detect_patterns(
            code=code,
            language=language
        )

        vulnerabilities = []
        for pattern in patterns:
            # Quick severity check
            severity = await self.slm_client.assess_severity(
                vulnerability=pattern['description'],
                code=code
            )

            vulnerabilities.append({
                "type": pattern['type'],
                "severity": severity,
                "line": pattern['line'],
                "message": pattern['message'],
                "suggestion": pattern.get('fix_suggestion')
            })

        return {
            "vulnerabilities": vulnerabilities,
            "analysis_time_ms": patterns['latency_ms']
        }

    def _build_context(self, sarif_results: dict) -> str:
        """Build context for triage."""
        metadata = sarif_results.get('metadata', {})
        return f"Repository: {metadata.get('repo')}, Language: {metadata.get('language')}"

    def _generate_summary(self, findings: list, triage: dict) -> dict:
        """Generate executive summary."""
        return {
            "total_findings": len(findings),
            "by_severity": self._count_by_severity(findings),
            "false_positives_detected": len([f for f in findings if f.get('slm_false_positive', {}).get('is_fp')]),
            "top_priority": triage['prioritized_ids'][:5],
            "recommended_actions": triage.get('recommendations', [])
        }
```

**Usage in Scan Pipeline:**

```python
# certus_assurance/pipeline/scan.py
async def run_security_scan(repo_url: str, profile: str):
    """Run security scan with SLM analysis."""

    # 1. Run scanners (existing pipeline)
    sarif_results = await run_scanners(repo_url, profile)

    # 2. Analyze with SLM
    slm_analyzer = SLMSecurityAnalyzer()
    analyzed_results = await slm_analyzer.analyze_scan_results(sarif_results)

    # 3. If critical issues found and complex reasoning needed, escalate to LLM
    critical_count = len([f for f in analyzed_results['findings'] if f['slm_severity']['severity'] == 'critical'])

    if critical_count > 5:
        # Too complex for SLM alone, escalate to Goose agent via MCP
        logger.info(f"Escalating {critical_count} critical findings to LLM agent")
        agent_analysis = await invoke_goose_agent(analyzed_results)
        analyzed_results['agent_analysis'] = agent_analysis

    # 4. Return enhanced results
    return analyzed_results
```

#### Integration with AAIF Agents

Goose agents can use the SLM for fast triage, then escalate to GPT-4 for complex tasks:

```yaml
# ~/.config/goose/profiles/certus-security.yaml (updated)
mcp_servers:
  - name: certus-secmodel
    command: certus-mcp-server
    args: [secmodel]
    enabled: true
    priority: high  # Use SLM first before expensive LLM calls
```

**Agent workflow:**

```python
# Goose agent decision flow
async def analyze_vulnerabilities(findings: list):
    """
    Two-tier analysis: SLM for triage, LLM for complex reasoning.
    """

    # 1. Fast triage with SLM
    triage = await mcp_call("certus-secmodel", "triage_findings", {"findings": findings})

    # 2. Filter to high-priority items
    high_priority = [f for f in findings if f['id'] in triage['prioritized_ids'][:10]]

    # 3. For complex cases, use LLM (GPT-4) for detailed analysis
    complex_analysis = []
    for finding in high_priority:
        if finding['severity'] == 'critical' and finding['exploit_available']:
            # Complex reasoning needed: use LLM
            analysis = await llm_analyze(finding)  # GPT-4 call
            complex_analysis.append(analysis)
        else:
            # Simple case: SLM suggestion is sufficient
            suggestion = await mcp_call("certus-secmodel", "suggest_remediation", {
                "vulnerability": finding['type'],
                "code": finding['code']
            })
            complex_analysis.append(suggestion)

    return complex_analysis
```

**Cost Comparison:**

```
Without SLM (All GPT-4):
- 100 findings × $0.10 = $10.00 per scan
- 1000 scans/day = $10,000/day = $3.65M/year

With SLM (Tiered):
- 100 findings × $0.001 (SLM triage) = $0.10
- 10 complex cases × $0.10 (GPT-4 deep analysis) = $1.00
- Total: $1.10 per scan
- 1000 scans/day = $1,100/day = $401K/year
- Savings: $3.25M/year (89% reduction)
```

### Continuous Learning Pipeline

**Objective:** Improve model over time by learning from Certus scan results.

```python
# certus_slm/learning/continuous.py
class ContinuousLearningPipeline:
    """
    Continuously improve SLM from production data.
    """

    async def collect_training_data(self):
        """Collect new training examples from production."""

        # 1. Collect human feedback
        feedback = await self._collect_human_feedback()
        # Examples: "This was a false positive", "Severity should be High not Medium"

        # 2. Collect corrections
        corrections = await self._collect_corrections()
        # Examples: SLM said "No vulnerability" but scanner found one

        # 3. Collect successful remediations
        remediations = await self._collect_remediations()
        # Examples: What fixes actually worked in production

        # 4. Combine into training dataset
        new_training_data = self._combine_feedback(feedback, corrections, remediations)

        return new_training_data

    async def retrain_model(self, new_data: Dataset):
        """Retrain model on new data."""

        # 1. Merge with existing training data
        full_dataset = self._merge_datasets(self.original_training_data, new_data)

        # 2. Fine-tune model
        new_model = await self._fine_tune(
            base_model=self.current_model,
            dataset=full_dataset,
            epochs=1  # Single epoch for incremental learning
        )

        # 3. Evaluate new model
        evaluation = await self._evaluate(new_model)

        # 4. If better, deploy new model
        if evaluation['accuracy'] > self.current_model_accuracy:
            await self._deploy_model(new_model)
            logger.info(f"Deployed new model version: {evaluation['accuracy']:.2%} accuracy")
        else:
            logger.warning("New model not better, keeping current model")

    async def _collect_human_feedback(self) -> list:
        """Collect human feedback on SLM predictions."""
        # Query database for human annotations
        feedback = await db.query("""
            SELECT
                finding_id,
                slm_prediction,
                human_correction,
                reasoning
            FROM human_feedback
            WHERE created_at > NOW() - INTERVAL '30 days'
        """)

        return feedback

    async def _collect_corrections(self) -> list:
        """Collect cases where SLM was wrong."""
        corrections = await db.query("""
            SELECT
                code,
                slm_classification,
                actual_classification,
                severity
            FROM scan_results
            WHERE slm_classification != actual_classification
                AND created_at > NOW() - INTERVAL '30 days'
        """)

        return corrections
```

**Retraining Schedule:**

```
Monthly retraining:
├─ Collect 30 days of production data
├─ Human feedback (500-1000 examples)
├─ Corrections (100-200 examples)
├─ Successful remediations (200-500 examples)
├─ Total new examples: ~1000/month
└─ Retrain model, evaluate, deploy if better

Quarterly major update:
├─ Incorporate new CVEs from NVD
├─ Update with new vulnerability patterns
├─ Expand to new languages/frameworks
└─ Full evaluation and benchmarking
```

## Use Cases & Examples

### Use Case 1: Real-Time IDE Security Checks

**Scenario:** Developer writes code in VS Code, gets immediate security feedback.

```python
# VS Code extension integration
async def on_code_change(code: str, language: str):
    """Called on every code change in editor."""

    # Call SLM for fast analysis
    result = await slm_client.real_time_check(code, language)

    # Display warnings inline (< 100ms latency)
    for vuln in result['vulnerabilities']:
        editor.add_diagnostic(
            line=vuln['line'],
            severity=vuln['severity'],
            message=vuln['message'],
            suggestion=vuln['suggestion']
        )
```

**Result:**
- Developer gets feedback in <100ms
- No need to wait for full scan
- Learns secure coding patterns in real-time

### Use Case 2: Commit Hook Pre-Flight Check

**Scenario:** Developer commits code, SLM checks for security issues before allowing commit.

```bash
# .git/hooks/pre-commit
#!/bin/bash

# Get staged files
FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(py|js|java)$')

# Check each file with SLM
for file in $FILES; do
    result=$(certus-slm check-file "$file")

    if echo "$result" | grep -q "CRITICAL"; then
        echo "🚫 Commit blocked: Critical security issue in $file"
        echo "$result"
        exit 1
    fi
done

echo "✅ Security pre-flight check passed"
```

**Result:**
- Prevent insecure code from being committed
- Immediate feedback (< 1 second for typical files)
- Educate developers at point of creation

### Use Case 3: PR Review Automation

**Scenario:** PR is opened, SLM provides security review comments.

```python
# GitHub App integration
@app.route('/webhook/pull_request', methods=['POST'])
async def handle_pr(request):
    """Handle PR opened/updated event."""

    pr = request.json['pull_request']

    # Get changed files
    changed_files = await github.get_pr_files(pr['number'])

    # Analyze with SLM
    security_review = []
    for file in changed_files:
        if file['status'] == 'added' or file['status'] == 'modified':
            analysis = await slm_client.analyze_code(
                code=file['patch'],
                filename=file['filename']
            )

            if analysis['vulnerabilities']:
                security_review.append({
                    "file": file['filename'],
                    "line": analysis['line'],
                    "severity": analysis['severity'],
                    "comment": analysis['message'],
                    "suggestion": analysis['suggestion']
                })

    # Post review comments
    if security_review:
        await github.create_review(
            pr_number=pr['number'],
            comments=security_review,
            event='REQUEST_CHANGES'
        )
    else:
        await github.create_review(
            pr_number=pr['number'],
            body="✅ No security issues detected by SLM",
            event='APPROVE'
        )
```

**Result:**
- Automated security review in <5 seconds
- Developers get actionable feedback
- Reduce security team review burden

### Use Case 4: Bulk Scan Triage

**Scenario:** Nightly scan finds 1000 issues, SLM triages to top 20.

```python
# Nightly scan job
async def nightly_security_scan():
    """Scan all repositories and triage findings."""

    repos = await get_all_repos()

    for repo in repos:
        # 1. Run full scan
        scan_results = await certus_assurance.scan(repo.url)

        # 2. SLM triage (cheap, fast)
        triage = await slm_client.triage_findings(
            findings=scan_results['findings'],
            context=f"Repo: {repo.name}, Owner: {repo.owner}"
        )

        # 3. Create tickets for top 20
        top_findings = triage['prioritized_ids'][:20]

        for finding_id in top_findings:
            finding = next(f for f in scan_results['findings'] if f['id'] == finding_id)

            # Get remediation suggestion
            remediation = await slm_client.suggest_remediation(
                vulnerability=finding['type'],
                code=finding['code']
            )

            # Create Jira ticket
            await jira.create_ticket(
                title=f"[Security] {finding['type']} in {repo.name}",
                description=f"{finding['message']}\n\nRemediation:\n{remediation}",
                priority=finding['severity']
            )
```

**Cost Analysis:**

```
Without SLM:
- 100 repos × 100 findings = 10,000 findings
- Manual triage: 5 min/finding × 10,000 = 50,000 min = 833 hours
- Cost: 833 hours × $100/hr = $83,300

With SLM:
- 10,000 findings × $0.001 = $10
- 2,000 findings escalated to human (20%) = 166 hours = $16,600
- Total cost: $16,610
- Savings: $66,690 (80% reduction)
```

### Use Case 5: Security Metrics Dashboard

**Scenario:** Security team wants visibility into vulnerability trends.

```python
# Dashboard data aggregation
async def generate_security_metrics():
    """Generate security metrics using SLM analysis."""

    # Get last 30 days of scans
    scans = await db.get_scans(days=30)

    metrics = {
        "total_scans": len(scans),
        "total_findings": 0,
        "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "by_type": {},
        "false_positive_rate": 0,
        "mean_triage_time": 0,
        "top_vulnerabilities": []
    }

    for scan in scans:
        # SLM analysis provides consistent classification
        analysis = scan['slm_analysis']

        metrics["total_findings"] += len(analysis['findings'])

        for finding in analysis['findings']:
            # Count by severity
            severity = finding['slm_severity']['severity']
            metrics["by_severity"][severity] += 1

            # Count by type
            vuln_type = finding['slm_classification']['type']
            metrics["by_type"][vuln_type] = metrics["by_type"].get(vuln_type, 0) + 1

            # Track false positives
            if finding.get('slm_false_positive', {}).get('is_fp'):
                metrics["false_positives"] += 1

    # Calculate rates
    metrics["false_positive_rate"] = metrics["false_positives"] / metrics["total_findings"]

    # Top vulnerabilities
    metrics["top_vulnerabilities"] = sorted(
        metrics["by_type"].items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    return metrics
```

**Value:**
- Consistent classification across all scans (SLM provides standardization)
- Trend analysis (severity distribution over time)
- Measure improvement (false positive rate declining)

## Phased Roadmap

### Phase 0: Research & Planning (Weeks 1-2)

**Goals:**
- Finalize model selection (Llama 3.2 3B vs alternatives)
- Design training data pipeline
- Set up infrastructure (GPU instance for training)
- Define success criteria and benchmarks

**Deliverables:**
- Model selection justification document
- Training data pipeline design
- Infrastructure provisioning plan
- Benchmark dataset prepared
- Phase 1 detailed plan

**Success Criteria:**
- Model selected and justified
- Training infrastructure provisioned
- 10K+ training examples collected
- Benchmark dataset with ground truth labels

### Phase 1: Model Training & Evaluation (Weeks 3-6)

**Goals:**
- Collect and prepare training datasets
- Fine-tune base model on security tasks
- Comprehensive evaluation and benchmarking
- Iteration based on results

**Deliverables:**
- Security training dataset (50K+ examples)
- Fine-tuned model: `certus-secmodel-v1`
- Evaluation report with metrics
- Comparison vs GPT-4 benchmark
- Model published to internal registry

**Success Criteria:**
- Classification accuracy >90%
- Severity assessment MAE <0.5
- False positive precision >85%
- Inference latency p95 <100ms
- Performance within 15% of GPT-4 on benchmarks

### Phase 2: Inference Service Deployment (Weeks 7-9)

**Goals:**
- Deploy inference service to Certus TAP
- Build REST API for model access
- Integrate with Certus-Assurance (pilot)
- Load testing and optimization

**Deliverables:**
- vLLM-based inference service (production-ready)
- REST API with OpenAPI spec
- Certus-Assurance integration (beta)
- Load testing results
- Deployment documentation

**Success Criteria:**
- Service achieves 99.9% uptime
- p95 latency <100ms under load
- Successfully processes 1000 requests/day
- Zero critical incidents

### Phase 3: MCP Integration & AAIF Ecosystem (Weeks 10-12)

**Goals:**
- Build MCP server for SLM
- Integrate with Goose agents
- Enable IDE access (Claude Desktop, VS Code)
- Two-tier AI workflow (SLM → LLM escalation)

**Deliverables:**
- `certus-secmodel-mcp-server` (production-ready)
- Goose profile updated with SLM tools
- IDE integration examples
- Documentation: "Using Security SLM via MCP"
- Two-tier workflow examples

**Success Criteria:**
- MCP server passes integration tests
- Goose agents can call SLM tools
- Claude Desktop users can access SLM
- Two-tier workflow reduces LLM costs by 80%+

### Phase 4: Continuous Learning Pipeline (Weeks 13-15)

**Goals:**
- Implement feedback collection
- Build retraining pipeline
- Deploy monthly retraining schedule
- Monitor model performance over time

**Deliverables:**
- Feedback collection system
- Automated retraining pipeline
- Model versioning and rollback system
- Performance monitoring dashboard
- Retraining runbook

**Success Criteria:**
- Feedback collected from >500 users
- Retraining pipeline executes successfully
- New model version shows improvement
- Performance tracking dashboard live

### Phase 5: Scale & Optimization (Weeks 16+)

**Goals:**
- Optimize inference performance
- Expand to more use cases
- Build specialized variants (language-specific models)
- Publish research/blog posts

**Deliverables:**
- Performance optimization (target: <50ms p95)
- Language-specific model variants (Python, JavaScript, Java)
- Real-time IDE integration (production)
- Blog post: "Building a Security-Specialized SLM"
- Academic paper (if novel contributions)

**Success Criteria:**
- 50%+ improvement in inference speed
- Support for 5+ programming languages
- 10K+ daily inference requests
- Published research/blog post

## Success Metrics

### Model Performance Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| **Classification Accuracy** | >90% | % correct vulnerability type predictions on test set |
| **Severity MAE** | <0.5 points | Mean absolute error in CVSS score predictions |
| **False Positive Precision** | >85% | % of predicted FPs that are actually FPs |
| **False Positive Recall** | >90% | % of actual FPs that are detected |
| **Inference Latency (p95)** | <100ms | 95th percentile inference time |
| **Inference Latency (p50)** | <50ms | Median inference time |
| **vs GPT-4 Accuracy** | >85% | Performance relative to GPT-4 on same benchmarks |

### Business Impact Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Cost Reduction** | >90% | Savings vs GPT-4 for equivalent workload |
| **Triage Speed** | 10x faster | Time to triage scan results |
| **Coverage** | 100% of scans | % of scans analyzed by AI (vs selective) |
| **Developer Satisfaction** | 4.2/5 | Post-interaction survey ratings |
| **False Positive Reduction** | 30% | Reduction in FP rate vs rule-based systems |
| **Time to Resolution** | 40% faster | Time from vulnerability detection to fix |

### Adoption Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Daily Inference Requests** | 10K+ by Week 16 | Request count from logs |
| **Certus Services Using SLM** | 3+ services | Assurance, Trust, Insight |
| **IDE Users** | 100+ users | Unique users accessing via IDE |
| **Agent Workflows Using SLM** | 80%+ | % of Goose workflows using SLM |

### Cost Metrics

| Metric | Current (GPT-4) | With SLM | Savings |
|--------|-----------------|----------|---------|
| **Per-scan analysis** | $0.10-$0.50 | $0.001-$0.01 | 90-99% |
| **Monthly (1K scans/day)** | $3K-$15K | $30-$300 | 90-99% |
| **Annual** | $36K-$182K | $10.8K-$109K | 70-94% |

**Additional costs:**
- Training: ~$500 (one-time)
- GPU inference: ~$500/month (T4 instance)
- Storage: ~$50/month (model weights)
- Total additional: ~$550/month
- **Net savings: $2.5K-$14.5K/month**

## Risks & Mitigations

### Risks

1. **Model Hallucination**
   - Risk: SLM generates incorrect classifications or severities
   - Impact: False sense of security, missed vulnerabilities
   - Mitigation: Confidence scoring (only act on high confidence)
   - Mitigation: Validation against CVE database
   - Mitigation: Human-in-the-loop for critical findings
   - Mitigation: Escalation to GPT-4 for low-confidence cases

2. **Training Data Quality**
   - Risk: Noisy or biased training data leads to poor model
   - Impact: Low accuracy, unreliable predictions
   - Mitigation: Curated, validated datasets (NVD, CWE)
   - Mitigation: Human annotation of Certus data
   - Mitigation: Synthetic data generation with verification
   - Mitigation: Regular evaluation and retraining

3. **Model Drift**
   - Risk: Model performance degrades as new vulnerabilities emerge
   - Impact: Missed new vulnerability types
   - Mitigation: Continuous learning pipeline (monthly retraining)
   - Mitigation: Monitor performance metrics over time
   - Mitigation: Alert if accuracy drops below threshold
   - Mitigation: Fallback to GPT-4 for unknown patterns

4. **Infrastructure Costs**
   - Risk: GPU costs higher than expected
   - Impact: ROI reduced
   - Mitigation: Start with CPU inference (sufficient for 3B model)
   - Mitigation: Use spot instances for training
   - Mitigation: Aggressive caching to reduce inference volume
   - Mitigation: Batch processing where real-time not required

5. **Accuracy Not Meeting Targets**
   - Risk: Model doesn't achieve >90% accuracy
   - Impact: Can't replace manual triage
   - Mitigation: Start with Llama 3.2 (proven strong base)
   - Mitigation: Iterative training with evaluation
   - Mitigation: Hybrid approach (SLM + human for edge cases)
   - Mitigation: Fallback to GPT-4 if SLM confidence low

6. **Adoption Resistance**
   - Risk: Users don't trust AI recommendations
   - Impact: Low usage, ROI not realized
   - Mitigation: Explainable outputs (show reasoning)
   - Mitigation: Gradual rollout with success stories
   - Mitigation: Human validation in early phase
   - Mitigation: Performance dashboard showing accuracy

### Non-Risks

- **Privacy concerns:** Model runs on-premises, no data sent to third parties
- **Vendor lock-in:** Open-source base model (Llama 3.2), can switch if needed
- **Replacing security experts:** SLM augments, doesn't replace (human-in-the-loop)
- **Model size too large:** 3B params is small enough for CPU inference

## Dependencies

### External Dependencies

**Training:**
- **Hugging Face Transformers** - Model training/fine-tuning
- **PyTorch** - Deep learning framework
- **PEFT (LoRA)** - Efficient fine-tuning
- **Datasets** - Data loading and processing
- **Weights & Biases** (optional) - Experiment tracking

**Inference:**
- **vLLM** - Fast inference server with continuous batching
- **FastAPI** - REST API framework
- **ONNX Runtime** (optional) - For CPU-optimized inference

**Data:**
- **NVD API** - CVE data
- **CWE Database** - Weakness enumeration
- **GitHub API** - Security advisories, patch commits

### Internal Dependencies

- **Certus-Assurance** - Primary integration point for scan analysis
- **Certus TAP** - Platform for deployment
- **Certus-Insight** - Telemetry and metrics
- **MCP Infrastructure** - For AAIF integration
- **AAIF Agent Framework** - For two-tier AI workflows

### Infrastructure

**Training:**
- 1x A100 (80GB) or 4x A10G (24GB) for 24-48 hours
- ~500GB storage for datasets
- S3/object storage for model artifacts

**Inference (Production):**
- 2-10 pods with 1x T4 GPU each (or CPU-only for lower load)
- 16-24GB RAM per pod
- Load balancer
- Model storage (10GB per model version)

## Cost Analysis

### One-Time Costs

| Item | Cost | Notes |
|------|------|-------|
| **Training Infrastructure** | $300-$500 | A100 instance for 48 hours |
| **Dataset Preparation** | $200 | Labor for annotation/curation |
| **Model Development** | $5K-$10K | Engineering time (2 weeks) |
| **Benchmarking** | $500 | Compute for comprehensive evaluation |
| **Total One-Time** | **$6K-$11K** | |

### Monthly Recurring Costs

| Item | Cost | Notes |
|------|------|-------|
| **Inference Infrastructure** | $500 | 2x T4 GPU instances |
| **Model Storage** | $50 | S3 storage for model versions |
| **Monitoring/Telemetry** | $100 | Logs, metrics, dashboards |
| **Retraining** | $100 | Monthly fine-tuning job |
| **Total Monthly** | **$750** | |

### Monthly Savings

| Item | Before (GPT-4) | After (SLM) | Savings |
|------|----------------|-------------|---------|
| **Scan Analysis (1K scans/day)** | $3K-$15K | $30-$300 | $2.97K-$14.7K |
| **IDE Checks (10K checks/day)** | N/A (too expensive) | $10 | Enable new capability |
| **PR Reviews (500/day)** | $500-$2.5K | $5-$50 | $495-$2.45K |
| **Total Monthly Savings** | | | **$3.5K-$17K** |

**Net Monthly Savings:** $2.75K-$16.25K (after infrastructure costs)

**Annual Net Savings:** $33K-$195K

**ROI Timeline:** 1-2 months (one-time costs recovered)

## Next Steps

### Immediate Actions (Week 1)

1. ✅ Review and approve this proposal
2. ✅ Assign engineering owner (1 ML engineer + 1 backend engineer)
3. ✅ Provision training infrastructure (A100 instance)
4. ✅ Set up development environment
   - Install Hugging Face, PyTorch, vLLM
   - Configure access to NVD API, CWE database
   - Set up experiment tracking (Weights & Biases)
5. ✅ Create project repositories:
   - `certus/certus-secmodel` (model training)
   - `certus/certus-slm-inference` (inference service)

### Phase 0 Kickoff (Weeks 1-2)

1. Finalize model selection (validate Llama 3.2 3B choice)
2. Design training data pipeline in detail
3. Collect initial 10K training examples
4. Prepare benchmark test set (1K examples with ground truth)
5. Set up training infrastructure and validate
6. Create detailed Phase 1 backlog

### Communication Plan

1. **Internal:**
   - Present proposal to engineering + ML teams
   - Weekly progress updates during training
   - Demo model capabilities (Week 6)
   - Monthly showcases after deployment

2. **External (post-Phase 3):**
   - Blog post: "Building a Security-Specialized SLM"
   - Webinar: "Two-Tier AI: SLM + LLM for Security"
   - Open-source training pipeline (optional)
   - Academic paper submission (if novel)

### Success Criteria for Approval

- [ ] Strategic alignment with AAIF proposal (complementary two-tier AI)
- [ ] Cost savings are realistic and measurable (>90% vs GPT-4)
- [ ] Model selection justified (Llama 3.2 3B)
- [ ] Training data strategy is sound (50K+ examples)
- [ ] Deployment architecture is feasible (vLLM + Kubernetes)
- [ ] Success metrics are clear and achievable
- [ ] Resource allocation approved (2 engineers, GPU infrastructure)
- [ ] Risk mitigation strategies are acceptable

---

## Appendix A: Model Selection Analysis

### Candidate Models

#### Llama 3.2 (1B/3B) ✅ RECOMMENDED

**Pros:**
- Latest architecture from Meta with strong performance
- 128K context window (handle long code/SARIF files)
- Excellent instruction-following
- Permissive license (Llama 3 Community License)
- Active community and good tooling support
- Strong performance/efficiency ratio

**Cons:**
- Relatively new (less battle-tested than Mistral)
- 1B may be too small, 3B is sweet spot

**Benchmark Results (on security tasks, estimated):**
- Classification: ~88-92%
- Severity: MAE ~0.4-0.6
- FP Detection: ~83-87%

**Recommendation:** Use 3B variant for best balance.

#### Phi-3.5-mini (3.8B)

**Pros:**
- Excellent reasoning capabilities
- Strong instruction-following
- 128K context window
- MIT license (very permissive)
- Microsoft backing

**Cons:**
- More research-oriented (less production use)
- Smaller community than Llama

**Benchmark Results:**
- Classification: ~86-90%
- Severity: MAE ~0.5-0.7
- FP Detection: ~80-85%

**Use Case:** Good alternative if need stronger reasoning.

#### Mistral 7B

**Pros:**
- Proven in production
- Large community
- Strong performance
- Apache 2.0 license

**Cons:**
- Larger (7B = slower inference)
- 32K context (vs 128K for Llama 3.2)
- Older architecture

**Benchmark Results:**
- Classification: ~90-93%
- Severity: MAE ~0.3-0.5
- FP Detection: ~85-88%

**Use Case:** If accuracy is critical and latency less important.

### Decision Matrix

| Model | Accuracy | Latency | License | Context | Community | Score |
|-------|----------|---------|---------|---------|-----------|-------|
| Llama 3.2 (3B) | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **22/25** |
| Phi-3.5-mini | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 20/25 |
| Mistral 7B | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 20/25 |

**Final Recommendation: Llama 3.2 (3B)**

---

## Appendix B: Training Data Sources

### Public Datasets

1. **NVD (National Vulnerability Database)**
   - URL: https://nvd.nist.gov/
   - Size: 250K+ CVE records
   - Format: JSON
   - License: Public domain (US government)

2. **CWE (Common Weakness Enumeration)**
   - URL: https://cwe.mitre.org/
   - Size: 900+ weakness types
   - Format: XML/CSV
   - License: Public domain

3. **CAPEC (Common Attack Pattern Enumeration)**
   - URL: https://capec.mitre.org/
   - Size: 500+ attack patterns
   - Format: XML
   - License: Public domain

4. **Exploit-DB**
   - URL: https://www.exploit-db.com/
   - Size: 50K+ exploits
   - Format: Text/Code
   - License: Check per-exploit

5. **SARD (Software Assurance Reference Dataset)**
   - URL: https://samate.nist.gov/SARD/
   - Size: 170K+ test cases
   - Format: Source code
   - License: Public domain

6. **Juliet Test Suite**
   - URL: https://samate.nist.gov/SRD/testsuite.php
   - Size: 64K test cases
   - Languages: C/C++, Java
   - License: Public domain

7. **GitHub Security Advisories**
   - URL: GitHub GraphQL API
   - Size: 10K+ advisories
   - Format: JSON
   - License: Public (via API)

### Data Collection Script

```python
# certus_slm/data/collectors/nvd.py
import requests
import json

async def download_nvd_cves():
    """Download all CVE records from NVD."""

    base_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    all_cves = []

    # NVD API pagination
    start_index = 0
    results_per_page = 2000

    while True:
        params = {
            "startIndex": start_index,
            "resultsPerPage": results_per_page
        }

        response = requests.get(base_url, params=params)
        data = response.json()

        cves = data.get("vulnerabilities", [])
        if not cves:
            break

        all_cves.extend(cves)
        start_index += results_per_page

        print(f"Downloaded {len(all_cves)} CVEs...")

        # Rate limiting
        await asyncio.sleep(6)  # NVD allows 10 req/min

    # Save to file
    with open("nvd_cves.json", "w") as f:
        json.dump(all_cves, f, indent=2)

    return all_cves
```

---

## Appendix C: Example Training Data

### Example 1: Vulnerability Classification

```json
{
  "task": "classify",
  "input": "cursor.execute(f'SELECT * FROM users WHERE username = {username}')",
  "output": "SQL Injection (CWE-89)",
  "explanation": "String interpolation in SQL query allows attacker to inject malicious SQL code. Should use parameterized queries.",
  "metadata": {
    "language": "Python",
    "severity": "Critical",
    "cvss": 9.8
  }
}
```

### Example 2: Severity Assessment

```json
{
  "task": "assess_severity",
  "input": "Remote code execution vulnerability in unauthenticated endpoint that processes user-uploaded files without validation.",
  "output": "CVSS 10.0 (Critical)",
  "explanation": "Network exploitable, no authentication required, complete system compromise possible. Maximum severity.",
  "metadata": {
    "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
  }
}
```

### Example 3: False Positive Detection

```json
{
  "task": "detect_false_positive",
  "input": {
    "finding": "Potential SQL injection in database query",
    "code": "cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))",
    "rule_id": "sql-injection-check"
  },
  "output": "False Positive",
  "explanation": "This is a parameterized query using placeholder (%s) and tuple parameter binding. No string interpolation or concatenation. Not vulnerable to SQL injection.",
  "confidence": 0.95
}
```

### Example 4: Remediation Suggestion

```json
{
  "task": "remediate",
  "input": {
    "vulnerability": "SQL Injection",
    "code": "query = 'DELETE FROM users WHERE id = ' + user_id\ncursor.execute(query)"
  },
  "output": "cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))",
  "explanation": "Replace string concatenation with parameterized query. Use placeholder (%s for PostgreSQL/MySQL, ? for SQLite) and pass parameters as tuple.",
  "alternative": "Use an ORM like SQLAlchemy: session.query(User).filter(User.id == user_id).delete()"
}
```

---

**End of Proposal**
