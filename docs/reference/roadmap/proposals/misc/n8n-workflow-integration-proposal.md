# N8n Workflow Automation Integration

**Status:** Draft
**Author:** System Architecture
**Date:** 2025-12-10
## Executive Summary

N8n is an open-source workflow automation platform that enables visual workflow creation and integration between diverse systems. By integrating N8n into the Certus platform, we will provide customers with low-code/no-code automation capabilities for security, compliance, and DevOps workflows. N8n will serve as the orchestration layer between Certus services (Assurance, Trust, Insight, Transform, Ask) and external systems (Jira, Slack, GitHub, PagerDuty, ServiceNow), enabling teams to build custom workflows without writing code.

**Key Use Cases:**

1. **Security Event Response** - Automatically create Jira tickets, notify teams, and trigger remediation workflows when security scans exceed thresholds
2. **Compliance Automation** - Generate and distribute compliance reports on schedules, collecting evidence and updating audit systems
3. **CI/CD Integration** - Orchestrate security scanning, artifact verification, and deployment gates across different pipeline tools
4. **Incident Management** - Coordinate responses across multiple systems when critical vulnerabilities are detected
5. **Custom Integrations** - Enable customers to connect Certus to their unique toolchains without custom development

## Motivation

### Current State

- Certus services expose REST APIs, WebSocket streams, and CLI interfaces
- Integration between Certus and external systems requires custom scripts or manual processes
- Notifications are limited to basic webhooks and Slack messages
- Complex multi-step workflows (e.g., "scan → verify → report → notify → ticket") require orchestration code
- Each customer's toolchain is different, requiring bespoke integration work

### Problems Addressed

1. **Integration Complexity** - Connecting Certus to external systems requires development effort and maintenance
2. **Workflow Rigidity** - Built-in workflows are opinionated and may not match customer processes
3. **Limited Automation** - Customers must manually coordinate actions across Certus services and external tools
4. **Scaling Custom Integrations** - Each unique customer requirement needs custom code
5. **Visibility Gap** - No centralized view of automation workflows and their execution status
6. **Developer Bottleneck** - Simple integrations require engineering time instead of being self-service

## Goals & Non-Goals

| Goals                                                                           | Non-Goals                                                                   |
| ------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Provide visual workflow builder for Certus operations and external integrations | Replace Certus service APIs (N8n wraps them, doesn't replace them)          |
| Enable self-service automation for security, compliance, and DevOps teams       | Force all customers to use N8n (it's an option, not a requirement)          |
| Pre-build common workflow templates (scan-to-ticket, scheduled reports, etc.)   | Re-implement Certus business logic in N8n workflows                         |
| Integrate N8n with all Certus services via custom nodes                        | Support every possible external integration (start with top 10-15 tools)    |
| Provide workflow observability and debugging capabilities                      | Build a general-purpose workflow engine (leverage N8n's existing strengths) |
| Support both cloud-hosted and self-hosted N8n deployments                      | Mandate N8n usage for basic Certus functionality                            |

## Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Certus N8n Integration                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │              N8n Workflow Engine                           │   │
│  │  • Visual workflow builder (web UI)                        │   │
│  │  • Workflow execution engine                               │   │
│  │  • Scheduling & triggers                                   │   │
│  │  • Webhook endpoints                                       │   │
│  │  • Credential management                                   │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              ↕                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │         Custom Certus N8n Nodes (Node Package)             │   │
│  │                                                            │   │
│  │  Security Operations:                                      │   │
│  │    • Certus-Assurance Node (trigger/manage scans)         │   │
│  │    • Certus-Trust Node (verify artifacts, attestations)   │   │
│  │    • Security Gate Node (enforce policies)                │   │
│  │                                                            │   │
│  │  Data & Analytics:                                         │   │
│  │    • Certus-Ask Node (ingest/query knowledge)             │   │
│  │    • Certus-Insight Node (reports, analytics)             │   │
│  │    • Certus-Transform Node (upload/promote artifacts)     │   │
│  │                                                            │   │
│  │  Supporting Nodes:                                         │   │
│  │    • Neo4j Query Node (graph traversal)                   │   │
│  │    • OpenSearch Query Node (findings search)              │   │
│  │    • SARIF Parser Node (extract findings)                 │   │
│  │    • SBOM Analyzer Node (dependency/license checks)       │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              ↕                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │              Certus Services (REST APIs)                   │   │
│  │  • Assurance • Trust • Insight • Ask • Transform           │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                               ↕
┌─────────────────────────────────────────────────────────────────────┐
│                    External Integrations                            │
│  (via native N8n nodes)                                             │
│                                                                     │
│  Ticketing:  Jira, ServiceNow, Linear, GitHub Issues               │
│  Messaging:  Slack, Microsoft Teams, Discord, Email                │
│  CI/CD:      GitHub Actions, GitLab CI, Jenkins, CircleCI          │
│  Monitoring: PagerDuty, Datadog, Prometheus, Grafana               │
│  Storage:    AWS S3, Google Cloud Storage, Azure Blob              │
│  Others:     HubSpot, Airtable, Notion, Google Sheets, etc.        │
└─────────────────────────────────────────────────────────────────────┘
```

### Integration Approach

#### 1. N8n Deployment Options

**Option A: Bundled Deployment (Recommended for TAP)**

```yaml
# docker-compose.yml (added to Certus TAP)
services:
  n8n:
    image: n8nio/n8n:latest
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
      - N8N_HOST=${N8N_HOST:-localhost}
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - WEBHOOK_URL=${N8N_WEBHOOK_URL:-http://localhost:5678/}
      - GENERIC_TIMEZONE=UTC
      - NODE_FUNCTION_ALLOW_EXTERNAL=@certus/n8n-nodes-certus
    volumes:
      - n8n-data:/home/node/.n8n
      - ./n8n/custom-nodes:/home/node/.n8n/custom
    networks:
      - certus-network
    depends_on:
      - postgres
    labels:
      - "com.certus.component=workflow-automation"
      - "com.certus.service=n8n"

  n8n-db:
    image: postgres:16
    environment:
      POSTGRES_DB: n8n
      POSTGRES_USER: n8n
      POSTGRES_PASSWORD: ${N8N_DB_PASSWORD}
    volumes:
      - n8n-postgres-data:/var/lib/postgresql/data
    networks:
      - certus-network

volumes:
  n8n-data:
  n8n-postgres-data:
```

**Option B: External N8n Instance**

For customers who already run N8n or prefer separate infrastructure:

- Provide N8n node package via npm: `@certus/n8n-nodes-certus`
- Document credential configuration for Certus API endpoints
- Publish workflow templates to N8n community library

#### 2. Custom Certus N8n Nodes

**Node Package Structure:**

```
packages/n8n-nodes-certus/
├── package.json
├── nodes/
│   ├── Assurance/
│   │   ├── Assurance.node.ts          # Main node
│   │   ├── AssuranceTrigger.node.ts   # Webhook trigger
│   │   ├── assurance.svg              # Icon
│   │   └── descriptions/
│   │       ├── ScanOperations.ts
│   │       ├── JobOperations.ts
│   │       └── ArtifactOperations.ts
│   │
│   ├── Trust/
│   │   ├── Trust.node.ts
│   │   ├── trust.svg
│   │   └── descriptions/
│   │       ├── VerifyOperations.ts
│   │       ├── AttestationOperations.ts
│   │       └── GraphOperations.ts
│   │
│   ├── Insight/
│   │   ├── Insight.node.ts
│   │   ├── insight.svg
│   │   └── descriptions/
│   │       ├── ReportOperations.ts
│   │       ├── AnalyticsOperations.ts
│   │       └── MetricsOperations.ts
│   │
│   ├── Ask/
│   │   ├── Ask.node.ts
│   │   ├── ask.svg
│   │   └── descriptions/
│   │
│   ├── Transform/
│   │   ├── Transform.node.ts
│   │   └── transform.svg
│   │
│   └── Utils/
│       ├── SarifParser.node.ts
│       ├── SbomAnalyzer.node.ts
│       ├── Neo4jQuery.node.ts
│       └── OpenSearchQuery.node.ts
│
├── credentials/
│   ├── CertusApi.credentials.ts       # API token auth
│   ├── CertusOAuth.credentials.ts     # OAuth flow
│   └── CertusLocal.credentials.ts     # Local TAP auth
│
└── workflows/
    └── templates/                      # Pre-built workflows
        ├── scan-to-jira.json
        ├── scheduled-compliance-report.json
        ├── vulnerability-response.json
        └── artifact-verification.json
```

**Example Node Implementation:**

```typescript
// nodes/Assurance/Assurance.node.ts
import {
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
} from 'n8n-workflow';

export class CertusAssurance implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'Certus Assurance',
    name: 'certusAssurance',
    icon: 'file:assurance.svg',
    group: ['transform'],
    version: 1,
    description: 'Interact with Certus-Assurance security scanning service',
    defaults: {
      name: 'Certus Assurance',
    },
    inputs: ['main'],
    outputs: ['main'],
    credentials: [
      {
        name: 'certusApi',
        required: true,
      },
    ],
    properties: [
      {
        displayName: 'Operation',
        name: 'operation',
        type: 'options',
        options: [
          {
            name: 'Create Scan',
            value: 'createScan',
            description: 'Trigger a new security scan',
            action: 'Create a new security scan',
          },
          {
            name: 'Get Scan Status',
            value: 'getScanStatus',
            description: 'Get the status of a running scan',
            action: 'Get scan status',
          },
          {
            name: 'Download Artifacts',
            value: 'getArtifacts',
            description: 'Download scan artifacts (SARIF, SBOM, etc.)',
            action: 'Download scan artifacts',
          },
          {
            name: 'Stream Logs',
            value: 'streamLogs',
            description: 'Stream real-time scan logs',
            action: 'Stream scan logs',
          },
        ],
        default: 'createScan',
      },
      {
        displayName: 'Repository URL',
        name: 'repoUrl',
        type: 'string',
        displayOptions: {
          show: {
            operation: ['createScan'],
          },
        },
        default: '',
        required: true,
        description: 'Git repository URL to scan',
      },
      {
        displayName: 'Scan Profile',
        name: 'profile',
        type: 'options',
        displayOptions: {
          show: {
            operation: ['createScan'],
          },
        },
        options: [
          {
            name: 'Light',
            value: 'light',
            description: 'Fast SAST scan (10-15 min)',
          },
          {
            name: 'Heavy',
            value: 'heavy',
            description: 'Comprehensive scan with DAST (30-45 min)',
          },
        ],
        default: 'light',
      },
      {
        displayName: 'Manifest',
        name: 'manifest',
        type: 'json',
        displayOptions: {
          show: {
            operation: ['createScan'],
          },
        },
        default: '{}',
        description: 'Optional: Custom manifest configuration',
      },
      {
        displayName: 'Job ID',
        name: 'jobId',
        type: 'string',
        displayOptions: {
          show: {
            operation: ['getScanStatus', 'getArtifacts', 'streamLogs'],
          },
        },
        default: '',
        required: true,
        description: 'Scan job ID to query',
      },
      {
        displayName: 'Wait for Completion',
        name: 'waitForCompletion',
        type: 'boolean',
        displayOptions: {
          show: {
            operation: ['createScan'],
          },
        },
        default: false,
        description: 'Whether to wait for scan to complete before continuing',
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const returnData: INodeExecutionData[] = [];
    const operation = this.getNodeParameter('operation', 0) as string;

    // Get credentials
    const credentials = await this.getCredentials('certusApi');
    const baseUrl = credentials.baseUrl as string;
    const apiToken = credentials.apiToken as string;

    for (let i = 0; i < items.length; i++) {
      try {
        if (operation === 'createScan') {
          const repoUrl = this.getNodeParameter('repoUrl', i) as string;
          const profile = this.getNodeParameter('profile', i) as string;
          const manifestInput = this.getNodeParameter('manifest', i) as string;
          const waitForCompletion = this.getNodeParameter('waitForCompletion', i) as boolean;

          let manifest = {};
          if (manifestInput) {
            manifest = JSON.parse(manifestInput);
          }

          // Call Certus-Assurance API
          const response = await this.helpers.request({
            method: 'POST',
            url: `${baseUrl}/v1/security-scans`,
            headers: {
              'Authorization': `Bearer ${apiToken}`,
              'Content-Type': 'application/json',
            },
            body: {
              manifest,
              profile,
              repo_url: repoUrl,
              branch: 'main',
            },
            json: true,
          });

          let finalResponse = response;

          // If waiting, poll for completion
          if (waitForCompletion) {
            const jobId = response.job_id;
            let status = 'queued';

            while (status === 'queued' || status === 'running') {
              await new Promise(resolve => setTimeout(resolve, 10000)); // Wait 10s

              const statusResponse = await this.helpers.request({
                method: 'GET',
                url: `${baseUrl}/v1/security-scans/${jobId}`,
                headers: {
                  'Authorization': `Bearer ${apiToken}`,
                },
                json: true,
              });

              status = statusResponse.status;
              finalResponse = statusResponse;
            }
          }

          returnData.push({
            json: finalResponse,
            pairedItem: { item: i },
          });

        } else if (operation === 'getScanStatus') {
          const jobId = this.getNodeParameter('jobId', i) as string;

          const response = await this.helpers.request({
            method: 'GET',
            url: `${baseUrl}/v1/security-scans/${jobId}`,
            headers: {
              'Authorization': `Bearer ${apiToken}`,
            },
            json: true,
          });

          returnData.push({
            json: response,
            pairedItem: { item: i },
          });

        } else if (operation === 'getArtifacts') {
          const jobId = this.getNodeParameter('jobId', i) as string;

          // First get scan status to get artifacts URL
          const scanStatus = await this.helpers.request({
            method: 'GET',
            url: `${baseUrl}/v1/security-scans/${jobId}`,
            headers: {
              'Authorization': `Bearer ${apiToken}`,
            },
            json: true,
          });

          if (scanStatus.artifacts_url) {
            // Download artifacts from S3 (or presigned URL)
            const artifacts = await this.helpers.request({
              method: 'GET',
              url: scanStatus.artifacts_url,
              headers: {
                'Authorization': `Bearer ${apiToken}`,
              },
              json: true,
            });

            returnData.push({
              json: {
                job_id: jobId,
                artifacts_url: scanStatus.artifacts_url,
                artifacts,
              },
              pairedItem: { item: i },
            });
          } else {
            throw new Error('No artifacts available for this scan');
          }
        }

      } catch (error) {
        if (this.continueOnFail()) {
          returnData.push({
            json: {
              error: error.message,
            },
            pairedItem: { item: i },
          });
          continue;
        }
        throw error;
      }
    }

    return [returnData];
  }
}
```

### 3. Pre-Built Workflow Templates

#### Template 1: Scan-to-Jira Workflow

**Trigger:** Scheduled (nightly) or webhook
**Steps:**

1. **Certus Assurance** - Create scan (light profile)
2. **Wait** - Poll for completion
3. **Certus Assurance** - Get artifacts
4. **SARIF Parser** - Extract findings by severity
5. **Filter** - Only critical/high findings
6. **Jira** - Create tickets for each finding
7. **Slack** - Notify security channel with summary
8. **Certus Insight** - Log workflow execution

**Workflow JSON:**

```json
{
  "name": "Nightly Security Scan → Jira Tickets",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "cronExpression",
              "expression": "0 2 * * *"
            }
          ]
        }
      },
      "name": "Schedule (2am daily)",
      "type": "n8n-nodes-base.scheduleTrigger",
      "position": [250, 300]
    },
    {
      "parameters": {
        "operation": "createScan",
        "repoUrl": "https://github.com/myorg/myapp",
        "profile": "light",
        "waitForCompletion": true
      },
      "name": "Run Security Scan",
      "type": "@certus/n8n-nodes-certus.certusAssurance",
      "credentials": {
        "certusApi": "Certus Production"
      },
      "position": [450, 300]
    },
    {
      "parameters": {
        "operation": "getArtifacts",
        "jobId": "={{$json.job_id}}"
      },
      "name": "Download Artifacts",
      "type": "@certus/n8n-nodes-certus.certusAssurance",
      "position": [650, 300]
    },
    {
      "parameters": {
        "sarifFile": "={{$json.artifacts.sarif}}"
      },
      "name": "Parse SARIF Findings",
      "type": "@certus/n8n-nodes-certus.sarifParser",
      "position": [850, 300]
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{$json.level}}",
              "operation": "equals",
              "value2": "error"
            },
            {
              "value1": "={{$json.level}}",
              "operation": "equals",
              "value2": "warning"
            }
          ]
        },
        "combineOperation": "any"
      },
      "name": "Filter Critical/High",
      "type": "n8n-nodes-base.if",
      "position": [1050, 300]
    },
    {
      "parameters": {
        "operation": "create",
        "project": "SEC",
        "issueType": "Bug",
        "summary": "={{$json.message.text}}",
        "description": "={{$json.message.markdown}}",
        "labels": ["security", "automated"],
        "priority": "High"
      },
      "name": "Create Jira Ticket",
      "type": "n8n-nodes-base.jira",
      "position": [1250, 300]
    },
    {
      "parameters": {
        "channel": "#security-alerts",
        "text": "Security scan complete. Created {{$json.tickets_created}} Jira tickets for critical/high findings."
      },
      "name": "Notify Slack",
      "type": "n8n-nodes-base.slack",
      "position": [1450, 300]
    }
  ],
  "connections": {
    "Schedule (2am daily)": {
      "main": [[{"node": "Run Security Scan"}]]
    },
    "Run Security Scan": {
      "main": [[{"node": "Download Artifacts"}]]
    },
    "Download Artifacts": {
      "main": [[{"node": "Parse SARIF Findings"}]]
    },
    "Parse SARIF Findings": {
      "main": [[{"node": "Filter Critical/High"}]]
    },
    "Filter Critical/High": {
      "main": [
        [{"node": "Create Jira Ticket"}],
        []
      ]
    },
    "Create Jira Ticket": {
      "main": [[{"node": "Notify Slack"}]]
    }
  }
}
```

#### Template 2: Compliance Report Generation & Distribution

**Trigger:** Monthly schedule
**Steps:**

1. **Certus Insight** - Generate compliance report (HIPAA/SOC2)
2. **Certus Trust** - Sign report with cosign
3. **Certus Transform** - Upload to golden bucket
4. **Email** - Send to compliance team
5. **Google Drive** - Archive in audit folder
6. **ServiceNow** - Update compliance records

#### Template 3: Pull Request Security Gate

**Trigger:** Webhook from GitHub PR
**Steps:**

1. **Webhook Trigger** - Receive GitHub PR webhook
2. **Certus Assurance** - Run light scan on PR branch
3. **Security Gate** - Check policy thresholds
4. **IF** - Violations found?
   - **YES** → GitHub API - Block PR merge, add comment
   - **NO** → GitHub API - Approve PR, add checkmark
5. **Slack** - Notify PR author with results

#### Template 4: Vulnerability Response Orchestration

**Trigger:** Webhook from Certus Insight (critical vulnerability detected)
**Steps:**

1. **Certus Insight** - Parse vulnerability details
2. **OpenSearch** - Find affected services/deployments
3. **PagerDuty** - Create incident
4. **Slack** - Notify on-call engineer
5. **Jira** - Create remediation ticket
6. **Certus Ask** - Query knowledge base for fix recommendations
7. **Email** - Send summary to security leadership

#### Template 5: Artifact Verification Pipeline

**Trigger:** Manual or CI/CD webhook
**Steps:**

1. **Certus Trust** - Verify OCI artifact signature
2. **Certus Trust** - Check SLSA provenance
3. **SBOM Analyzer** - Scan for license/CVE issues
4. **Neo4j Query** - Check supply chain graph
5. **IF** - All checks pass?
   - **YES** → Certus Transform - Promote to golden bucket
   - **NO** → Slack - Alert security team, quarantine artifact

### 4. Certus Service Integration Points

#### Certus-Assurance

**Operations:**

- `createScan(repoUrl, profile, manifest)` → returns job_id
- `getScanStatus(jobId)` → returns status, artifacts_url
- `getArtifacts(jobId)` → downloads SARIF, SBOM, provenance
- `streamLogs(jobId)` → WebSocket stream of logs
- `cancelScan(jobId)` → terminates running scan

**Webhook Trigger:**

- N8n receives webhooks when scans complete
- Payload includes job_id, status, summary, artifacts_url

#### Certus-Trust

**Operations:**

- `verifyArtifact(artifactUrl, signature)` → returns verified, rekor_entry
- `verifyAttestation(imageRef)` → returns attestations, provenance
- `getSupplyChainGraph(artifactId)` → returns dependency graph
- `signArtifact(artifactUrl, keyRef)` → returns signature, rekor_url

#### Certus-Insight

**Operations:**

- `generateReport(type, timeRange, filters)` → returns report_url
- `getMetrics(workspace, timeRange)` → returns analytics JSON
- `queryFindings(filters)` → returns SARIF findings
- `getComplianceScore(framework)` → returns score, gaps

**Webhook Trigger:**

- Threshold violations (e.g., >5 critical CVEs detected)
- Report generation complete
- Policy gate failures

#### Certus-Ask

**Operations:**

- `ingestDocument(url, metadata)` → returns ingestion_id
- `query(question, filters)` → returns answer, sources
- `healthCheck()` → returns status

#### Certus-Transform

**Operations:**

- `uploadToRaw(file, prefix, metadata)` → returns s3_key
- `promoteToGolden(sourcePrefix, checks)` → returns golden_url
- `verifyDigest(s3Key, expectedDigest)` → returns matched

### 5. Authentication & Security

#### Credential Types

**1. API Token Authentication (certusApi)**

```typescript
// credentials/CertusApi.credentials.ts
export class CertusApi implements ICredentialType {
  name = 'certusApi';
  displayName = 'Certus API';
  properties = [
    {
      displayName: 'Base URL',
      name: 'baseUrl',
      type: 'string' as NodePropertyTypes,
      default: 'https://assurance.certus.dev',
      description: 'Certus API base URL',
    },
    {
      displayName: 'API Token',
      name: 'apiToken',
      type: 'string' as NodePropertyTypes,
      typeOptions: {
        password: true,
      },
      default: '',
      description: 'API token from Certus console',
    },
  ];
}
```

**2. OAuth 2.0 (certusOAuth)**

For production deployments with SSO integration.

**3. Local TAP Authentication (certusLocal)**

For TAP users, auto-configure with local service endpoints:

- Assurance: `http://certus-assurance:8200`
- Trust: `http://certus-trust:8300`
- Insight: `http://certus-insight:8400`
- Ask: `http://certus-ask:8000`
- Transform: `http://certus-transform:8100`

#### Security Considerations

1. **Credential Storage** - N8n encrypts credentials at rest
2. **API Token Rotation** - Support token expiration and refresh
3. **Audit Logging** - All workflow executions logged to OpenSearch
4. **Rate Limiting** - Respect Certus API rate limits
5. **Network Isolation** - N8n runs in Certus network, can access internal services
6. **Webhook Security** - Validate webhook signatures from Certus services

### 6. Workflow Observability

#### Telemetry Integration

Every workflow execution emits telemetry to Certus Insight:

```typescript
// Automatic telemetry from all Certus nodes
{
  "event": "workflow_execution",
  "workflow_id": "scan-to-jira",
  "execution_id": "exec-123",
  "node": "certusAssurance",
  "operation": "createScan",
  "status": "success",
  "duration_ms": 45000,
  "timestamp": "2025-12-10T12:00:00Z",
  "user": "user@example.com",
  "metadata": {
    "job_id": "scan-456",
    "profile": "light"
  }
}
```

#### Workflow Dashboard

Add to Certus Insight:

- **Active Workflows** - List of enabled N8n workflows
- **Execution History** - Recent runs with status/duration
- **Error Tracking** - Failed executions with stack traces
- **Performance Metrics** - Average duration per workflow type
- **Audit Trail** - Who created/modified workflows

### 7. Deployment Architecture

#### TAP Integration

```
Certus TAP Stack
├── certus-assurance (port 8200)
├── certus-trust (port 8300)
├── certus-insight (port 8400)
├── certus-ask (port 8000)
├── certus-transform (port 8100)
├── neo4j (port 7474, 7687)
├── opensearch (port 9200)
├── postgres (port 5432)
└── n8n (port 5678)  ← NEW
    ├── n8n-db (postgres)
    └── Custom Certus nodes pre-installed
```

**Access:**

- UI: `http://localhost:5678` (local) or `https://n8n.certus.dev` (cloud)
- Webhook endpoints: `http://n8n:5678/webhook/*`

**Volumes:**

- Workflows: `/home/node/.n8n/workflows/`
- Credentials: `/home/node/.n8n/credentials/` (encrypted)
- Custom nodes: `/home/node/.n8n/custom/`

#### Scaling Considerations

For production deployments:

1. **Queue Mode** - Use Redis for job queue (scale workers independently)
2. **Worker Separation** - Run N8n editor and execution workers separately
3. **High Availability** - Multiple N8n instances behind load balancer
4. **Database** - Use managed PostgreSQL for workflow storage
5. **Observability** - Export metrics to Prometheus/Grafana

## Dependencies

### External

- **N8n** (v1.0+) - Open-source workflow automation platform
- **PostgreSQL** (v14+) - N8n workflow/execution storage
- **Redis** (optional) - Queue mode for scaled deployments

### Internal Certus Services

- **Certus-Assurance** - REST API for scan operations (Phase 1+)
- **Certus-Trust** - REST API for verification operations (Phase 2+)
- **Certus-Insight** - REST API for reporting/analytics (Phase 2+)
- **Certus-Ask** - REST API for ingestion/query (Phase 3+)
- **Certus-Transform** - REST API for S3 operations (Phase 3+)
- **OpenSearch** - Telemetry and workflow execution logs
- **Neo4j** (optional) - Graph queries from workflows

### Development Dependencies

- **Node.js** (v18+) - For custom node development
- **TypeScript** - Custom node implementation language
- **n8n node development SDK** - For building custom nodes

## Risks & Mitigations

### Risks

1. **Complexity Overhead** - Adding another service increases operational burden
   - **Mitigation:** Bundle with TAP, provide managed option, document well
2. **Security Surface** - Workflow automation has access to credentials/APIs
   - **Mitigation:** Encrypted credentials, audit logging, RBAC
3. **Performance Impact** - Workflows could create unexpected load
   - **Mitigation:** Rate limiting, quotas, queue mode for isolation
4. **Learning Curve** - Users need to learn N8n + Certus concepts
   - **Mitigation:** Pre-built templates, documentation, video tutorials
5. **Maintenance Burden** - Custom nodes require ongoing maintenance
   - **Mitigation:** Automated tests, version compatibility matrix

### Non-Risks

- **Vendor Lock-in** - N8n is open-source, workflows are exportable JSON
- **Data Privacy** - N8n runs in customer environment, data stays local
- **Cost** - Open-source self-hosted is free; cloud version is optional

## Phased Roadmap

### Phase 0: Discovery & Planning (Weeks 1-2)

**Goals:**

- Evaluate N8n deployment options (bundled vs. external)
- Design custom node architecture and API contracts
- Define initial workflow templates (scan-to-Jira, compliance report)
- Document authentication/security approach

**Deliverables:**

- This proposal document
- N8n + Certus architecture diagram
- Node interface specifications
- Authentication strategy doc

### Phase 1: Core Integration (Weeks 3-6)

**Goals:**

- Add N8n to docker-compose (TAP bundle)
- Develop Certus-Assurance node (scan operations)
- Implement credential types (API token, local TAP)
- Build 2-3 basic workflow templates
- Document node usage and workflow creation

**Deliverables:**

- N8n running in TAP stack (`docker-compose up`)
- `@certus/n8n-nodes-certus` package (Assurance node only)
- Workflow template: "Scan to Jira"
- Documentation: "Getting Started with N8n + Certus"

**Success Criteria:**

- Users can trigger Certus-Assurance scans from N8n
- Scan results flow to Jira/Slack automatically
- <30 minutes setup time for TAP users

### Phase 2: Expand Service Coverage (Weeks 7-10)

**Goals:**

- Add Certus-Trust node (verification, attestations)
- Add Certus-Insight node (reports, analytics)
- Add utility nodes (SARIF parser, SBOM analyzer)
- Build 3-5 additional workflow templates
- Implement webhook triggers from Certus services

**Deliverables:**

- Trust + Insight nodes in package
- Utility nodes (SARIF, SBOM)
- Workflow templates:
  - Pull Request Security Gate
  - Compliance Report Generation
  - Vulnerability Response Orchestration
- Webhook integration guide

**Success Criteria:**

- Complete end-to-end workflows (scan → verify → report → notify)
- Webhook triggers working from Assurance/Insight
- 10+ workflow templates published

### Phase 3: Data & Query Nodes (Weeks 11-13)

**Goals:**

- Add Certus-Ask node (ingestion, query)
- Add Certus-Transform node (S3 operations)
- Add Neo4j query node (graph traversal)
- Add OpenSearch query node (findings search)
- Implement advanced workflow templates

**Deliverables:**

- Ask + Transform nodes
- Neo4j + OpenSearch query nodes
- Workflow templates:
  - Artifact Verification Pipeline
  - Scheduled Compliance Automation
  - Documentation Ingestion Workflow
- Integration testing suite

**Success Criteria:**

- Workflows can query/manipulate all Certus data sources
- Complex multi-service orchestration working
- Performance benchmarks met (<10% overhead)

### Phase 4: Observability & Hardening (Weeks 14-16)

**Goals:**

- Implement telemetry emission to Certus Insight
- Build workflow execution dashboard in Insight
- Add OAuth 2.0 credential type
- Implement workflow testing framework
- Add error handling and retry logic
- Document troubleshooting and best practices

**Deliverables:**

- Workflow observability dashboard in Insight
- OAuth authentication support
- Testing framework with examples
- Production deployment guide
- Troubleshooting documentation

**Success Criteria:**

- All workflow executions visible in Insight
- OAuth working with customer SSO
- 90%+ test coverage on custom nodes
- Zero-downtime deployment documented

### Phase 5: Community & Ecosystem (Weeks 17+)

**Goals:**

- Publish nodes to npm registry
- Submit workflows to N8n community library
- Create video tutorials and webinars
- Build marketplace for custom workflow templates
- Gather customer feedback and iterate
- Explore managed N8n hosting option

**Deliverables:**

- Public npm package: `@certus/n8n-nodes-certus`
- N8n community library presence
- Video tutorials (5-10 workflows)
- Customer case studies
- Managed N8n offering (optional)

**Success Criteria:**

- 100+ active workflow deployments
- 10+ community-contributed templates
- 90%+ customer satisfaction
- Managed offering beta (optional)

## Success Metrics

### Adoption Metrics

1. **Workflow Deployment Rate**
   - Target: 50+ workflows deployed within 3 months of Phase 4
   - Measure: N8n workflow count per tenant
2. **Template Usage**
   - Target: 80% of customers use at least one pre-built template
   - Measure: Template deployment tracking
3. **Service Coverage**
   - Target: 100% of Certus services have N8n nodes
   - Measure: Node availability matrix

### Performance Metrics

1. **Workflow Execution Time**
   - Target: <10% overhead vs. direct API calls
   - Measure: Average duration per operation type
2. **Reliability**
   - Target: 99%+ workflow execution success rate
   - Measure: Failed executions / total executions
3. **Throughput**
   - Target: Handle 1000+ workflow executions/day per TAP instance
   - Measure: Execution rate metrics

### Business Impact Metrics

1. **Time Savings**
   - Target: Reduce security workflow automation effort by 70%
   - Measure: Customer surveys, time-to-automate tracking
2. **Integration Expansion**
   - Target: 50% increase in Certus-to-external-tool integrations
   - Measure: Unique external services connected per tenant
3. **Self-Service Adoption**
   - Target: 60% of workflow creation by non-engineers
   - Measure: User role analysis of workflow creators

### Quality Metrics

1. **Customer Satisfaction**
   - Target: 4.5/5 average rating for N8n integration
   - Measure: Quarterly NPS surveys
2. **Documentation Quality**
   - Target: 90% of support tickets resolved via docs
   - Measure: Support ticket categorization
3. **Error Rate**
   - Target: <5% of workflow executions fail due to bugs
   - Measure: Error tracking and categorization

## Alternative Approaches Considered

### 1. Build Custom Workflow Engine

**Pros:** Full control, optimized for Certus
**Cons:** Significant development effort, reinventing the wheel
**Decision:** Rejected - N8n provides 95% of needed functionality

### 2. Use Apache Airflow

**Pros:** Mature, Python-based, good for data pipelines
**Cons:** Code-first (not low-code), heavy infrastructure, data engineering focus
**Decision:** Rejected - Too complex for target users (DevOps/security teams)

### 3. Use Temporal

**Pros:** Robust workflow orchestration, code-first with SDKs
**Cons:** Requires programming, no visual builder, complex setup
**Decision:** Rejected - Doesn't meet low-code/no-code goal

### 4. Use Zapier/Make.com

**Pros:** Mature, large connector ecosystem
**Cons:** SaaS-only, expensive, limited self-hosting
**Decision:** Rejected - Customers need self-hosted option

### 5. Use GitHub Actions Only

**Pros:** Already integrated with repos, CI/CD native
**Cons:** Limited to Git events, no visual builder, YAML complexity
**Decision:** Partial - GitHub Actions remain supported for CI/CD, N8n for broader automation

### Decision: N8n

**Why N8n Won:**

- ✅ Open-source with self-hosting option
- ✅ Visual workflow builder (low-code)
- ✅ Extensive connector library (300+ integrations)
- ✅ Active community and ecosystem
- ✅ REST API for programmatic access
- ✅ Webhook triggers and actions
- ✅ Custom node development support
- ✅ Cloud and self-hosted deployment options
- ✅ Fair-code license (source-available)

## Documentation Requirements

### User Documentation

1. **Getting Started Guide**
   - Installing N8n in TAP
   - Configuring Certus credentials
   - Creating your first workflow
2. **Node Reference**
   - Complete documentation for each Certus node
   - Parameter descriptions and examples
   - Common use cases
3. **Workflow Templates Gallery**
   - Template descriptions and use cases
   - Step-by-step customization guides
   - Video walkthroughs
4. **Troubleshooting Guide**
   - Common errors and solutions
   - Debugging workflow executions
   - Performance optimization tips

### Developer Documentation

1. **Custom Node Development**
   - Node development setup
   - API integration patterns
   - Testing guidelines
2. **Architecture Reference**
   - N8n + Certus architecture
   - Authentication flows
   - Telemetry implementation
3. **Contributing Guide**
   - How to contribute workflow templates
   - Node enhancement process
   - Community guidelines

### Operations Documentation

1. **Deployment Guide**
   - TAP bundled deployment
   - External N8n deployment
   - High-availability setup
2. **Security Hardening**
   - Credential management
   - Network isolation
   - Audit logging configuration
3. **Monitoring & Observability**
   - Metrics collection
   - Log aggregation
   - Dashboard setup

## Next Steps

### Immediate Actions (Week 1)

1. ✅ Review and approve this proposal
2. ✅ Assign engineering owner and team
3. ✅ Set up N8n development environment
4. ✅ Create project repository: `certus/n8n-nodes-certus`
5. ✅ Schedule kickoff meeting with stakeholders

### Phase 0 Kickoff (Week 2)

1. Spike: Deploy N8n locally with TAP
2. Spike: Build proof-of-concept Assurance node
3. Spike: Test end-to-end workflow (scan → Slack)
4. Document findings and update roadmap
5. Create Phase 1 backlog with detailed tasks

### Communication Plan

1. **Internal:**
   - Present proposal to engineering team
   - Demo POC to product/leadership
   - Weekly progress updates during development
2. **External (post-Phase 1):**
   - Blog post: "Introducing N8n Integration"
   - Webinar: "Automate Security with Certus + N8n"
   - Community templates showcase

### Success Criteria for Approval

- [ ] Architecture aligns with Certus service patterns
- [ ] Deployment model works for TAP and cloud customers
- [ ] Security/auth approach is sound
- [ ] Roadmap is realistic and phased appropriately
- [ ] Documentation requirements are clear
- [ ] Resource allocation is approved

---

## Appendix A: Example Workflow Configurations

### A.1: Nightly Security Scan with Conditional Notifications

```json
{
  "name": "Nightly Scan - Conditional Alerts",
  "nodes": [
    {
      "name": "Cron Trigger",
      "type": "n8n-nodes-base.cron",
      "parameters": {"cronExpression": "0 2 * * *"}
    },
    {
      "name": "Scan Production",
      "type": "@certus/n8n-nodes-certus.certusAssurance",
      "parameters": {
        "operation": "createScan",
        "repoUrl": "https://github.com/myorg/prod-app",
        "profile": "heavy",
        "waitForCompletion": true
      }
    },
    {
      "name": "Parse Results",
      "type": "@certus/n8n-nodes-certus.sarifParser"
    },
    {
      "name": "Check Threshold",
      "type": "n8n-nodes-base.if",
      "parameters": {
        "conditions": {
          "number": [
            {"value1": "={{$json.critical_count}}", "operation": "larger", "value2": 0}
          ]
        }
      }
    },
    {
      "name": "Critical Alert",
      "type": "n8n-nodes-base.slack",
      "parameters": {
        "channel": "#security-critical",
        "text": "🚨 Critical vulnerabilities found: {{$json.critical_count}}"
      }
    },
    {
      "name": "Standard Report",
      "type": "n8n-nodes-base.emailSend",
      "parameters": {
        "toEmail": "security-team@company.com",
        "subject": "Daily Security Scan Results"
      }
    }
  ]
}
```

### A.2: Multi-Environment Scanning Pipeline

```json
{
  "name": "Multi-Environment Security Pipeline",
  "nodes": [
    {
      "name": "Manual Trigger",
      "type": "n8n-nodes-base.manualTrigger"
    },
    {
      "name": "Environments",
      "type": "n8n-nodes-base.set",
      "parameters": {
        "values": {
          "string": [
            {"name": "environments", "value": "dev,staging,production"}
          ]
        }
      }
    },
    {
      "name": "Split Environments",
      "type": "n8n-nodes-base.splitInBatches"
    },
    {
      "name": "Scan Environment",
      "type": "@certus/n8n-nodes-certus.certusAssurance",
      "parameters": {
        "operation": "createScan",
        "repoUrl": "https://github.com/myorg/app",
        "profile": "light",
        "manifest": "={{JSON.stringify({product: 'myapp-' + $json.environment})}}",
        "waitForCompletion": true
      }
    },
    {
      "name": "Compare Results",
      "type": "n8n-nodes-base.aggregate"
    },
    {
      "name": "Generate Report",
      "type": "@certus/n8n-nodes-certus.certusInsight",
      "parameters": {
        "operation": "generateReport",
        "type": "comparison"
      }
    }
  ]
}
```

## Appendix B: Custom Node API Reference

### B.1: Certus Assurance Node

**Resource:** `CertusAssurance`

**Operations:**

- `createScan` - Trigger new security scan
- `getScanStatus` - Query scan job status
- `getArtifacts` - Download scan artifacts
- `streamLogs` - Stream real-time logs
- `cancelScan` - Stop running scan
- `listScans` - List historical scans

**Parameters:**

| Parameter            | Type    | Required | Operations        | Description                      |
| -------------------- | ------- | -------- | ----------------- | -------------------------------- |
| `operation`          | options | Yes      | All               | Operation to perform             |
| `repoUrl`            | string  | Yes      | createScan        | Git repository URL               |
| `profile`            | options | Yes      | createScan        | Scan profile (light/heavy)       |
| `manifest`           | json    | No       | createScan        | Custom manifest JSON             |
| `branch`             | string  | No       | createScan        | Branch to scan (default: main)   |
| `waitForCompletion`  | boolean | No       | createScan        | Poll until complete              |
| `jobId`              | string  | Yes      | get*/cancel       | Scan job ID                      |
| `limit`              | number  | No       | listScans         | Max results (default: 50)        |
| `timeRange`          | options | No       | listScans         | Time filter (day/week/month/all) |

### B.2: Certus Trust Node

**Resource:** `CertusTrust`

**Operations:**

- `verifyArtifact` - Verify artifact signature
- `verifyAttestation` - Verify OCI attestation
- `getProvenance` - Retrieve SLSA provenance
- `signArtifact` - Sign artifact with cosign
- `queryGraph` - Query supply chain graph

### B.3: Certus Insight Node

**Resource:** `CertusInsight`

**Operations:**

- `generateReport` - Create compliance report
- `getMetrics` - Retrieve analytics metrics
- `queryFindings` - Search security findings
- `getComplianceScore` - Calculate compliance score

## Appendix C: Telemetry Schema

### C.1: Workflow Execution Event

```json
{
  "event_type": "workflow_execution",
  "timestamp": "2025-12-10T12:00:00Z",
  "workflow": {
    "id": "workflow-123",
    "name": "Nightly Security Scan",
    "version": "1.0"
  },
  "execution": {
    "id": "exec-456",
    "status": "success",
    "duration_ms": 45000,
    "node_count": 7,
    "nodes_executed": 7,
    "errors": []
  },
  "user": {
    "id": "user-789",
    "email": "user@example.com",
    "workspace": "acme-corp"
  },
  "operations": [
    {
      "node": "certusAssurance",
      "operation": "createScan",
      "status": "success",
      "duration_ms": 30000,
      "metadata": {
        "job_id": "scan-123",
        "profile": "light"
      }
    }
  ],
  "metadata": {
    "n8n_version": "1.0.0",
    "certus_nodes_version": "1.0.0"
  }
}
```

---

**End of Proposal**
