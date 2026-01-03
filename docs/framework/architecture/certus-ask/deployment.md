# Deployment

High-level deployment context tying users, pipelines, and observability targets before diving into concrete environments. We will aim to support the deployment of the TAP platforms with these deployment approaches.

## TAP Platform

```mermaid
graph TB
    subgraph Users
        Analysts["Analysts & Engineers"]
        Automations["CI/CD & Automation Jobs"]
    end

    subgraph ExternalSources["External Systems"]
        GitHub["Git Repos"]
        OSS["Public Docs & Websites"]
        SARIF["SARIF Producers"]
        Buckets["S3 Compatible Buckets"]
    end

    subgraph Platform["Certus TAP Platform"]
        API["FastAPI Gateway"]
        Pipelines["Ingestion Pipelines (Haystack)"]
        Search["OpenSearch Index"]
        Storage["Object Storage / Vector Store"]
        LLM["LLM / Guardrails"]
    end

    subgraph ExternalServices["External Services"]
        LLMProvider["Hosted LLM Providers (SageMaker, Ollama, Azure OpenAI)"]
        Observability["Monitoring / MLflow"]
    end

    Analysts --> API
    Automations --> API
    GitHub --> Pipelines
    OSS --> Pipelines
    SARIF --> Pipelines
    Buckets --> Pipelines
    Pipelines --> Storage
    Pipelines --> Search
    API --> Search
    API --> LLM
    LLM --> LLMProvider
    Pipelines --> Observability
    API --> Observability

    classDef primary stroke:#000000,stroke-width:2px;
    class API,Pipelines primary;
```

| Name                          | Description                                                   |
| ----------------------------- | ------------------------------------------------------------- |
| Analysts & Engineers          | Primary users of TAP APIs and UI surfaces.                 |
| CI/CD & Automation Jobs       | Scheduled workflows triggering ingestion or evaluation tasks. |
| GitHub / GitLab Repos         | Code and docs repositories feeding the pipelines.             |
| Public Docs & Websites        | Open web sources used for crawling.                           |
| SARIF Producers               | Security tool outputs being ingested.                         |
| S3 Compatible Buckets         | External storage delivering documents or receiving exports.   |
| FastAPI Gateway               | certus_ask entry point.                                       |
| Ingestion Pipelines           | Haystack-based document processing stages.                    |
| OpenSearch Index              | Primary vector/metadata store.                                |
| Object Storage / Vector Store | Long-lived storage for raw/processed data.                    |
| LLM / Guardrails              | Prompt orchestration plus safety layers.                      |
| Hosted LLM Providers          | External LLM endpoints (SageMaker/Ollama/Azure).              |
| Monitoring / MLflow           | Observability sinks for pipelines and models.                 |

## Local / Self-Contained Deployment

Developer-focused Docker Compose stack running entirely on a workstation for offline testing.

```mermaid
graph TB
    subgraph Host["Developer Laptop / Workstation"]
        subgraph Tooling["Host Tooling"]
            JUST["just / uv CLI"]
            Docs["MkDocs Preview"]
        end

        subgraph Stack["Docker Compose Stack"]
            Backend["certus_ask (FastAPI + pipelines)"]
            OS["OpenSearch"]
            LS["LocalStack (S3, STS, queues)"]
            ML["MLflow Tracking UI"]
            Vols["Bind-mounted data + .env"]
        end
    end

    User[(Engineer)]

    User --> JUST
    JUST --> Backend
    Docs -. optional .-> User
    Backend --> OS
    Backend --> LS
    Backend --> ML
    Backend --> Vols
    OS --> Backend
    LS --> Backend
    ML --> Backend

    classDef primary stroke:#000000,stroke-width:2px;
    classDef service stroke:#000000,stroke-width:1px;
    class Backend primary;
    class OS,LS,ML,Vols,JUST,Docs service;
```

| Name               | Description                                     |
| ------------------ | ----------------------------------------------- |
| just / uv CLI      | Local tooling to orchestrate syncs and scripts. |
| MkDocs Preview     | Docs live-reload service for writers.           |
| certus_ask         | FastAPI + pipelines container.                  |
| OpenSearch         | Local search engine container.                  |
| LocalStack         | AWS emulator providing S3/STS/queues.           |
| MLflow Tracking UI | Local experiment tracking service.              |
| Bind-mounted data  | Shared volumes for .env and artifacts.          |

## Self-Managed / Single VPC Deployment (no managed services)

All services run inside a single VPC (e.g., EC2 instances or a small Kubernetes cluster) with the customer responsible for every component.

```mermaid
graph TB
    subgraph VPC["Customer VPC / Data Center"]
        subgraph Frontend["UI & API Tier"]
            UI["Web / UI"]
            API["FastAPI / Gateway"]
            UI <--> API
        end

        subgraph Pipelines["Ingestion & Guardrails"]
            Workers["Pipelines & Background Jobs"]
        end

        subgraph StorageLayer["Data Layer"]
            RawStore["Object Storage (raw/quarantine/golden)"]
            Search["Self-Managed Search / Vector Store"]
            Tracking["MLflow / Observability"]
        end

        subgraph LLMStack["LLM / Safety"]
            LocalLLM["LLM Runtime"]
            Guardrails["Presidio / Safety Components"]
        end
    end

    GitRepo["Git Repository"] --> API
    Users[(Users / Scripts)] --> UI
    API --> Workers
    Workers --> RawStore
    Workers --> Search
    Workers --> Tracking
    Workers --> Guardrails --> LocalLLM
    LocalLLM --> Guardrails
```

| Name                        | Description                                               |
| --------------------------- | --------------------------------------------------------- |
| Web / UI                    | Customer-managed UI surface inside the VPC.               |
| FastAPI / Gateway           | certus_ask serving ingestion/query APIs.                  |
| Pipelines & Background Jobs | Haystack pipelines plus scheduled ingestion tasks.        |
| Object Storage              | Raw/quarantine/golden layers on customer-managed storage. |
| Self-Managed Search         | Customer-managed OpenSearch / vector database.            |
| MLflow / Observability      | Local telemetry and experiment tracking stack.            |
| LLM Runtime / Guardrails    | Customer-managed LLM plus Presidio-based safety layer.    |

## Cloud Deployment (with managed services)

Reference deployment for AWS accounts, using native services for storage, search, and model endpoints.

```mermaid


graph TB
    GitHubRepo["GitHub Repository"]
    ContainerRegistry["Container Registry (ECR)"]
    CICD["CI/CD Pipeline"]

    %% Cloud Provider
    subgraph Cloud
        subgraph Cloud_Services
            subgraph DL["Datalake"]
                S3R[Raw Data]
                AG[Transformations]
                S3P[Golden Data]
                S3R --> AG
                AG --> S3P
            end

            LLM[External LLM]
            OS[OpenSearch]
            ML[MLflow Tracking]
        end

        subgraph VPC
            subgraph UX["User Interface"]
                UAPI[API]
                UWEB[WEB]
                UAPI<-->UWEB
            end

            subgraph AAB["certus_ask (Container/EC2)"]
                API["FastAPI Service"]
                Workers["Pipelines & Background Jobs"]
                API<-->Workers
            end
        end
    end

    UX --> AAB
    GitHubRepo --> CICD
    CICD --> ContainerRegistry --> AAB
    AAB --> DL
    AAB --> OS
    AAB --> ML
    AAB --> LLM
    OS --> AAB
    ML --> AAB
    LLM --> AAB

    classDef primary stroke:#000000,stroke-width:2px;
    classDef service stroke:#000000,stroke-width:1px;
    class AAB primary;
    class UX,API,Workers service;
    class OS,S3R,S3P,AG,LLM,ML service;
```

| Name                              | Description                                    |
| --------------------------------- | ---------------------------------------------- |
| User Interface                    | Web/UI tier inside VPC accessing backend APIs. |
| certus_ask                        | EC2/Container running FastAPI and pipelines.   |
| Datalake on S3 Compatible Service | Raw/processed buckets plus Glue transforms.    |
| OpenSearch                        | Managed search cluster for embeddings.         |
| MLflow Tracking                   | Experiment tracking service (EC2/ECS).         |
| Managed/External LLM              | Managed LLM/embedding endpoints.               |

## Serverless Container Deployment

Generic view of a TAP deployment on a serverless container platform (Cloud Run, Azure Container Apps, AWS App Runner, etc.).

```mermaid
graph LR
    GitHub["GitHub / Git Provider"] --> CICD["CI/CD Pipeline"] --> Registry["Container Registry"]

    subgraph Cloud["Cloud Platform"]
        subgraph Host["Serverless Container Host"]
            App["certus_ask"]
        end

        subgraph Services["Managed Services"]
            Storage["Object Storage (raw/quarantine/golden)"]
            Search["Managed Search / Vector Store"]
            Mlflow["Managed MLflow / Observability"]
            LLM["Managed LLM Endpoint"]
        end
    end

    Users[(Users / Automations)] --> App
    Registry --> App

    App --> Storage
    App --> Search
    App --> Mlflow
    App --> LLM
    Storage --> App
    Search --> App
```

| Name                           | Description                                          |
| ------------------------------ | ---------------------------------------------------- |
| GitHub / Git Provider          | Source control feeding the CI/CD pipeline.           |
| CI/CD Pipeline                 | Builds and deploys container images.                 |
| Container Registry             | Stores built images (e.g., Artifact Registry/ECR).   |
| Serverless Container Host      | Executes the backend/pipelines as a managed service. |
| Object Storage                 | Raw/quarantine/golden data and artifacts.            |
| Managed Search / Vector Store  | Stores embeddings and metadata.                      |
| Managed MLflow / Observability | Captures experiment metrics and service telemetry.   |
| Managed LLM Endpoint           | External LLM used for inference/guardrails.          |

## Kubernetes Deployment

Generic Kubernetes topology (self-managed or cloud) detailing Deployments, StatefulSets, and supporting resources.

```mermaid
graph TB
    %% C4 Deployment-style view for Kubernetes
    subgraph Cluster["Kubernetes Cluster"]
        subgraph Namespace["certus-tap namespace"]
            subgraph Deploy["Deployments"]
                API["certus_ask Deployment\n(FastAPI Pods)"]
                Workers["Pipeline Worker Deployment\n(Celery/RQ Pods)"]
                Docs["MkDocs Preview Deployment (optional)"]
            end

            subgraph Stateful["StatefulSets"]
                OS["OpenSearch StatefulSet\n(PVC-backed)"]
                ML["MLflow Tracking StatefulSet\n(PVC-backed)"]
            end

            subgraph Jobs["CronJobs / Jobs"]
                Ingest["Ingestion CronJobs\n(web, git, SARIF)"]
            end

            subgraph Config["Config & Secrets"]
                ConfigMap["ConfigMaps (.env, pipelines)"]
                Secret["Secrets (API keys, DB creds)"]
            end

            subgraph Networking["Ingress / Services"]
                Ingress["Ingress Controller\n(Nginx/Traefik)"]
                SVC_API["Service: certus_ask"]
                SVC_OS["Service: OpenSearch"]
                SVC_ML["Service: MLflow"]
            end
        end
    end

    User[(Engineer / Client)]
    ExternalLLM["External LLM Endpoint\n(SageMaker / Ollama / Azure OpenAI)"]
    ObjectStore["Object Storage\n(S3 / Spaces)"]

    User --> Ingress
    Ingress --> SVC_API
    SVC_API --> API
    API --> Workers
    API --> OS
    API --> ML
    API --> ExternalLLM
    Workers --> OS
    Workers --> ObjectStore
    Ingest --> Workers
    ConfigMap --> API
    ConfigMap --> Workers
    Secret --> API
    Secret --> Workers
    Secret --> Ingest

    classDef primary stroke:#000000,stroke-width:2px;
    classDef service stroke:#000000,stroke-width:1px;
    class API,Workers primary;
    class OS,ML,SVC_API,SVC_OS,SVC_ML,Ingress,ConfigMap,Secret,Ingest,ObjectStore,ExternalLLM service;
```

| Name                             | Description                                   |
| -------------------------------- | --------------------------------------------- |
| certus_ask Deployment            | Stateless FastAPI pods serving APIs.          |
| Pipeline Worker Deployment       | Workers handling ingestion/ETL tasks.         |
| StatefulSets (OpenSearch/MLflow) | Persistent workloads backed by PVCs.          |
| CronJobs                         | Scheduled ingestion runs (web/git/SARIF).     |
| ConfigMaps / Secrets             | Runtime configuration and credentials.        |
| Ingress Controller               | Exposes services to external clients.         |
| Services                         | Stable endpoints for API, OpenSearch, MLflow. |
| External LLM Endpoint            | Off-cluster LLM provider.                     |
| Object Storage                   | S3/Spaces buckets accessed by workers.        |

## Hybrid Ingestion (Edge + Cloud)

Edge collectors inside customer environments sanitize data before tunneling it into the central Certus cloud stack.

```mermaid
graph TB
    %% Edge collectors + central cloud
    subgraph CustomerVPC["Customer VPC / On-Prem"]
        subgraph EdgeCollectors["Edge Collectors"]
            GHRunner["GitHub Actions Runner"]
            SARIFUploader["SARIF Uploader"]
            FileAgent["Docs / Repo Agent"]
        end

        Sanitizer["Sanitization Proxy\n(redaction, filtering)"]
        CustomerStore["Customer Storage (S3, SMB)"]
    end

    subgraph SecureChannel["Secure Channel"]
        VPN["Site-to-Site VPN / TLS Tunnel"]
    end

    subgraph CertusCloud["Certus Cloud Stack"]
        API["certus_ask"]
        Pipelines["Ingestion Pipelines"]
        OS["OpenSearch / Vector DB"]
        Storage["Central Object Storage"]
        ML["MLflow / Observability"]
    end

    subgraph ExternalServices["External Services"]
        LLM["Hosted LLM"]
        Tickets["Ticketing / Alerting"]
    end

    CustomerStore --> EdgeCollectors
    EdgeCollectors --> Sanitizer
    Sanitizer --> VPN
    VPN --> API
    API --> Pipelines
    Pipelines --> OS
    Pipelines --> Storage
    Pipelines --> ML
    API --> LLM
    Pipelines --> Tickets

    classDef primary stroke:#000000,stroke-width:2px;
    classDef service stroke:#000000,stroke-width:1px;
    class EdgeCollectors,API,Pipelines primary;
    class OS,Storage,ML,LLM,Tickets,Sanitizer,VPN,CustomerStore service;
```

| Name                          | Description                                                 |
| ----------------------------- | ----------------------------------------------------------- |
| Edge Collectors               | Customer-hosted runners pulling data from internal systems. |
| Sanitization Proxy            | Redaction/filtering layer before data leaves VPC.           |
| Site-to-Site VPN / TLS Tunnel | Secure channel between customer and Certus cloud.           |
| certus_ask                    | Central ingest API receiving sanitized payloads.            |
| Ingestion Pipelines           | Normalize and load artifacts into storage/search.           |
| OpenSearch / Vector DB        | Core retrieval store in the Certus cloud.                   |
| Central Object Storage        | Holds raw and processed documents.                          |
| MLflow / Observability        | Monitors ingestion and model health.                        |
| Hosted LLM                    | Downstream generation endpoint.                             |
| Ticketing / Alerting          | Systems receiving findings or alerts.                       |
