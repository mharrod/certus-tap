# Architecture

![Platform Diagram](/../../assets/images/assurance.png){ .static-diagram }

### Reading the Diagram

The architecture diagram illustrates the complete Certus Trust & Assurance Platform (TAP), showing how components work together across the entire assurance lifecycle. The diagram is organized into several key areas:

- **Left Side** – Inputs and testing orchestration (Assurance Manifest, Systems Under Test, Certus Assurance with its testing categories)
- **Center** – Core processing services (Certus Transform, Certus Ask with RAG and AI Reasoning capabilities)
- **Top** – Certus Trust for signing, verification, provenance, and transparency
- **Right Side** – Outputs and downstream consumers (Certus Insight for reporting, dashboards, and integrations)
- **Bottom** – Cross-cutting platform services (Human-in-the-Loop, Certus Protect, Certus Integrity, Certus Evaluate)

The platform operates across four deployment models shown at the bottom: Edge Compute, Core/Cloud Compute, Trust & Provenance, and Inputs/Outputs.

The remainder of this doc walks through each major component and how they integrate.

---

### 1. Assurance Inputs

**Assurance Manifest** acts as the declarative contract for a run. It scopes systems, models, datasets, policies, thresholds, and metadata (owners, environments, risk tier) and is signed before distribution. Pipeline orchestrators (Dagger, GitHub Actions, Tekton, GitLab CI, etc.) use the manifest to plan execution, fan out jobs, and stream signed status back to Certus Trust.

**Systems Under Test** include application repos, container images, infrastructure definitions, AI models (`.onnx`, `.pt`, `.safetensors`), datasets/ETL jobs, and runtime workloads. The manifest maps each target to required scanners and policy gates so the pipeline can trace accountability per asset.

---

### 2. Certus Assurance - Testing & Evidence Collection

The **Certus Assurance** component orchestrates comprehensive testing across four key categories, shown on the left side of the diagram:

#### Security Testing

- **SAST** (Static Application Security Testing) - Code analysis for vulnerabilities
- **DAST** (Dynamic Application Security Testing) - Runtime security testing
- **Fuzz** - Fuzzing and input validation testing
- **SCA** (Software Composition Analysis) - Dependency vulnerability scanning
- **Other** - Additional security tooling
- **Parse & Normalize** - Converts findings to standardized format

#### Integrity Testing

- **Signing** - Artifact signing validation
- **Privacy** - Privacy compliance checks
- **Posture** - Security posture assessment
- **PROVN** (Provenance) - Supply chain verification
- **Other** - Additional integrity checks
- **Parse & Normalize** - Standardizes integrity evidence

#### AI Evaluation

- **Adversarial** - Adversarial robustness testing
- **Toxicity** - Content toxicity detection
- **Safety** - AI safety assessments
- **Fairness** - Bias and fairness testing
- **Other** - Additional AI evaluations
- **Parse & Normalize** - Standardizes AI evaluation results

#### Light Coverage & Testing

- **Unit** - Unit test execution
- **Baseline** - Baseline testing
- **API** - API testing
- **Other** - Additional test types
- **Parse & Normalize** - Test result normalization

Each testing category collects evidence, normalizes findings into SARIF or JSON format, and forwards structured artifacts to Certus Transform for processing.

---

### 3. Certus Transform - Evidence Processing Pipeline

**Certus Transform** sits in the center-left of the diagram and handles the core data processing pipeline. It receives evidence from Certus Assurance and prepares it for downstream consumption:

- **Privacy** - Applies privacy controls and PII detection/masking
- **Enrichment** - Adds contextual metadata (owners, service, environment, threat intel)
- **Transformation** - Converts and normalizes data formats
- **Other** - Additional transformation capabilities

Transform outputs flow to both **Certus Ask** (for RAG and AI reasoning) and external systems for further processing. All transformations maintain evidence lineage and are eligible for signing by Certus Trust.

---

### 4. Certus Ask - RAG and AI Reasoning Engine

**Certus Ask** provides intelligent query and reasoning capabilities across the platform, shown in the center of the diagram with two main components:

#### RAG (Retrieval-Augmented Generation) Pipeline

A sequential processing chain for evidence-based responses:

1. **Ingest** - Receives processed evidence from Certus Transform
2. **Normalize & Dedupe** - Standardizes and deduplicates information
3. **Enrich** - Adds contextual metadata and relationships
4. **Assess** - Evaluates findings and generates insights
5. **Policy Gate** - Enforces policy compliance before output

#### AI Reasoning Rail

Advanced AI capabilities for complex analysis and automation:

- **Retrievers** - Query vector stores, knowledge graphs, and historical data
- **LLM Chain** - Orchestrates multi-step reasoning and generation workflows
- **Agent Orchestrator** - Coordinates specialist AI agents for complex tasks
- **Schema & Safety Gates** - Validates outputs for structure, safety, and bias
- **Fusion Logic** - Synthesizes insights from multiple sources

All AI operations are subject to guardrails and produce verifiable, traceable outputs that reference immutable evidence.

---

### 5. Certus Trust - Signing, Verification & Provenance

**Certus Trust** sits at the top of the diagram and provides the cryptographic foundation for the entire platform:

- **Sign / Verify** - Cryptographic signing and verification of artifacts using Cosign/Sigstore
- **WORM Compliant OCI** - Write-Once-Read-Many storage for immutable evidence
- **Transparency** - Public transparency logs via Rekor for auditability
- **Provenance** - SLSA provenance generation and verification
- **Audit Ledger** - Immutable audit trail of all operations
- **Timestamp** - RFC 3161 trusted timestamping

**Key and Identity Management** provides centralized control over:

- IRMS (Identity & Rights Management System)
- OIDC (OpenID Connect) integration
- Vault secrets management
- Threshold signatures for critical operations
- Policy-based key distribution

All artifacts flowing through the platform can be signed by Certus Trust, creating an unbroken chain of custody from evidence collection through to downstream consumption.

---

### 6. Cross-Cutting Platform Services

Four critical services provide horizontal capabilities across the entire platform:

#### Human-in-the-Loop

When policy gates detect exceptions or require manual review, the pipeline pauses and routes decisions to human reviewers. Approvals and rejections are recorded as signed artifacts and feed back into the policy evaluation process.

#### Certus Protect

Platform-wide guardrails that enforce security controls:

- Prompt isolation and validation for AI components
- Output filtering and sanitization
- Data exfiltration prevention
- Deterministic verification of automated actions

#### Certus Integrity

Runtime protection and monitoring:

- Rate limiting and abuse prevention
- Request validation and anomaly detection
- Workload integrity monitoring
- Behavioral analysis and threat detection

#### Certus Evaluate

Continuous evaluation and quality assurance:

- Model performance monitoring
- AI output quality assessment
- Policy effectiveness measurement
- Compliance validation

---

### 7. Certus Insight - Outputs & Downstream Integrations

**Certus Insight** provides visibility and integration capabilities on the right side of the diagram, organized into four key areas:

#### Security/Privacy

- **SIEM** (e.g., Splunk) - Security event aggregation and correlation
- **RAW Feed** (e.g., S3/Parquet) - Raw data exports for analytics
- **Compliance** (OSCAL) - Standards-based compliance reporting

#### Software Management

- **Issue/Case Mgmt** (e.g., Jira) - Automated ticket creation and tracking
- **ChatOps** (e.g., Slack) - Real-time notifications and collaboration
- **Coverage** (e.g., SonarQube) - Code coverage and quality metrics
- **Ticketing** (e.g., Jira) - Workflow automation
- **Email** (e.g., Outlook) - Stakeholder notifications
- **Other** - Additional integrations

#### Governance

- **GRC Face Dashboard** - Governance, Risk, and Compliance visualization
- **Continuous Evidence** - Real-time compliance evidence streams
- **SBOM** (e.g., Veratr) - Software Bill of Materials distribution
- **AI Assurance** - AI-specific compliance and safety reporting
- **MTTR & SLA** - Mean Time to Resolve and Service Level Agreement tracking

#### TAP

- **Release Notes** - Automated release documentation
- **PIAs** - Privacy Impact Assessments
- **Chatbot** - Interactive query interface
- **Product Docs** - Customer-facing documentation
- **API Ref** - API reference documentation
- **Other** - Additional documentation outputs

All outputs reference immutable evidence URIs signed by Certus Trust, enabling independent verification of claims without rerunning pipelines.

---

### 8. Deployment Models

The platform supports four deployment patterns shown at the bottom of the diagram:

- **Edge Compute** - Lightweight scanning and evidence collection at the edge
- **Core/Cloud Compute** - Primary processing, RAG, and AI reasoning in cloud/datacenter
- **Trust & Provenance** - Centralized signing, verification, and audit services
- **Inputs/Outputs** - External system integrations and data exchange

---

### 9. Evidence & Traceability Principles

The platform enforces end-to-end verifiability across all components:

- **Immutable Evidence** - Every artifact is cryptographically signed and stored in write-once storage
- **Chain of Custody** - Complete lineage from evidence collection through policy decisions to downstream distribution
- **Policy-as-Code** - Deterministic, versioned policy evaluation with reproducible results
- **Human Oversight** - Critical decisions require human approval with full audit trails
- **Verifiable Outputs** - All dashboards, reports, and integrations reference signed evidence URIs
- **Continuous Assurance** - Real-time visibility across security, integrity, privacy, and AI safety dimensions

This architecture delivers measurable trust through cryptographic verification, transparent processes, and traceable evidence chains.
