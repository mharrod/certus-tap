# Configuration Reference

Complete reference for all environment variables and configuration options.

## Critical Configuration

These variables **must** be set for the application to start.

### OpenSearch Configuration

#### OPENSEARCH_HOST

**Type**: URL
**Required**: Yes
**Description**: URL to OpenSearch cluster for storing ingested documents

**Examples**:
- Local: `http://localhost:9200`
- Docker: `http://opensearch:9200`
- AWS: `https://vpc-xxxxx.us-east-1.es.amazonaws.com`

**Validation**: Must start with `http://` or `https://`

#### OPENSEARCH_INDEX

**Type**: String
**Required**: Yes
**Description**: Index name where documents are stored

**Examples**:
- `ask_certus`
- `certus_documents`
- `tap_index`

**Constraints**: Must be valid OpenSearch index name (lowercase, no special chars except `-` and `_`)

### AWS Configuration

#### AWS_ACCESS_KEY_ID

**Type**: String
**Required**: Yes
**Description**: AWS access key for S3 authentication

**Examples**:
- LocalStack: `test` (default)
- AWS: `AKIA2Z4F5XY7Z9Q2M8P4` (format: AKIA...)

**Security**: Never commit to version control. Use secrets management in production.

#### AWS_SECRET_ACCESS_KEY

**Type**: String
**Required**: Yes
**Description**: AWS secret key for S3 authentication

**Examples**:
- LocalStack: `test` (default)
- AWS: Long random string (40+ characters)

**Security**: Use AWS Secrets Manager or equivalent in production.

#### S3_ENDPOINT_URL

**Type**: URL
**Required**: Yes
**Description**: S3 endpoint URL

**Examples**:
- LocalStack: `http://localstack:4566`
- AWS: `https://s3.amazonaws.com`
- S3-compatible: `https://s3.example.com`

**Validation**: Must start with `http://` or `https://`

#### AWS_REGION

**Type**: String (AWS region code)
**Required**: Yes
**Description**: AWS region for operations

**Examples**:
- `us-east-1` (N. Virginia)
- `us-west-2` (Oregon)
- `eu-west-1` (Ireland)
- `ap-southeast-1` (Singapore)

**Valid Regions**: Any valid AWS region code

### LLM Configuration

#### LLM_MODEL

**Type**: String
**Required**: Yes
**Description**: Name of the language model to use

**Examples**:
- Llama: `llama3.1:8b`
- Mistral: `mistral:latest`
- Neural Chat: `neural-chat:latest`
- Local custom: `my-custom-model:latest`

**Availability**: Model must be available in the LLM service

#### LLM_URL

**Type**: URL
**Required**: Yes
**Description**: URL to LLM service

**Examples**:
- Ollama local: `http://localhost:11434`
- Ollama Docker: `http://ollama:11434`
- Ollama Mac/Windows Docker: `http://host.docker.internal:11434`
- Custom service: `http://llm-service:8000`

**Validation**: Must start with `http://` or `https://`

### MLflow Configuration

#### MLFLOW_TRACKING_URI

**Type**: URL
**Required**: Yes
**Description**: URL to MLflow tracking server

**Examples**:
- Local: `http://localhost:5001`
- Docker: `http://mlflow:5001`
- Production: `https://mlflow.example.com`

**Validation**: Must start with `http://` or `https://`

---

## Optional Configuration

These variables have sensible defaults and are optional.

### OpenSearch Authentication

#### OPENSEARCH_HTTP_AUTH_USER

**Type**: String
**Required**: No
**Default**: Empty (no authentication)
**Description**: Username for OpenSearch authentication

**Examples**:
- `admin`
- `opensearch-user`

**Notes**: Required if OpenSearch cluster has security enabled

#### OPENSEARCH_HTTP_AUTH_PASSWORD

**Type**: String
**Required**: No
**Default**: Empty (no authentication)
**Description**: Password for OpenSearch authentication

**Examples**:
- `admin123`
- Complex password string

**Notes**: Required if OpenSearch cluster has security enabled

### Logging Configuration

#### LOG_LEVEL

**Type**: Enum
**Required**: No
**Default**: `INFO`
**Description**: Application logging level

**Valid Values**:
- `DEBUG` - Most verbose, includes all debug information
- `INFO` - Default, normal operation logging
- `WARNING` - Only warnings and errors
- `ERROR` - Only error messages
- `CRITICAL` - Only critical errors

**Examples**:
```bash
LOG_LEVEL=INFO      # Normal operation
LOG_LEVEL=DEBUG     # Development/troubleshooting
LOG_LEVEL=ERROR     # Production minimal logging
```

#### LOG_JSON_OUTPUT

**Type**: Boolean
**Required**: No
**Default**: `true`
**Description**: Output logs in JSON format for parsing

**Values**:
- `true` - JSON format (recommended for production)
- `false` - Human-readable format

**Examples**:
```bash
LOG_JSON_OUTPUT=true    # Machine-readable
LOG_JSON_OUTPUT=false   # Human-readable
```

#### SEND_LOGS_TO_OPENSEARCH

**Type**: Boolean
**Required**: No
**Default**: `true`
**Description**: Send logs to OpenSearch for centralized logging

**Values**:
- `true` - Ship logs to OpenSearch
- `false` - Only write to console

**Examples**:
```bash
SEND_LOGS_TO_OPENSEARCH=true   # Production
SEND_LOGS_TO_OPENSEARCH=false  # Development
```

### OpenSearch Logging Configuration

#### OPENSEARCH_LOG_HOST

**Type**: String
**Required**: No
**Default**: `localhost`
**Description**: Hostname for OpenSearch logging cluster

**Examples**:
- Same cluster: `opensearch` (from documents)
- Separate cluster: `opensearch-logs`
- AWS: `opensearch-logs.us-east-1.es.amazonaws.com`

**Notes**: Can be different from document cluster for separation

#### OPENSEARCH_LOG_PORT

**Type**: Integer
**Required**: No
**Default**: `9200`
**Description**: Port for OpenSearch logging cluster

**Examples**:
- `9200` (standard)
- `443` (AWS with VPC)

**Valid Range**: 1-65535

#### OPENSEARCH_LOG_USERNAME

**Type**: String
**Required**: No
**Default**: Empty (no authentication)
**Description**: Username for logging cluster authentication

**Examples**:
- `admin`
- `logging-user`

#### OPENSEARCH_LOG_PASSWORD

**Type**: String
**Required**: No
**Default**: Empty (no authentication)
**Description**: Password for logging cluster authentication

### Datalake Configuration

#### DATALAKE_RAW_BUCKET

**Type**: String
**Required**: No
**Default**: `raw`
**Description**: S3 bucket name for raw ingested data

**Examples**:
- `raw`
- `certus-raw`
- `raw-data-prod`

**Constraints**: Must be valid S3 bucket name

#### DATALAKE_GOLDEN_BUCKET

**Type**: String
**Required**: No
**Default**: `golden`
**Description**: S3 bucket name for processed/golden data

**Examples**:
- `golden`
- `certus-golden`
- `processed-data-prod`

**Constraints**: Must be valid S3 bucket name

#### DATALAKE_DEFAULT_FOLDERS

**Type**: List of strings
**Required**: No
**Default**: `["broker", "support", "marketing", "video", "other"]`
**Description**: Default folder structure in datalake

**Format**: Comma-separated or JSON array
```bash
# Comma-separated
DATALAKE_DEFAULT_FOLDERS=broker,support,marketing,video,other

# JSON array
DATALAKE_DEFAULT_FOLDERS=["broker","support","marketing"]
```

**Examples**:
- `broker,support,marketing`
- `["engineering", "product", "sales"]`

#### EVALUATION_BUCKET

**Type**: String
**Required**: No
**Default**: `evaluation-results`
**Description**: S3 bucket for evaluation and test results

**Examples**:
- `evaluation-results`
- `certus-eval`
- `test-results-prod`

### GitHub Configuration

#### GITHUB_TOKEN

**Type**: String
**Required**: No
**Default**: Empty (GitHub features disabled)
**Description**: GitHub personal access token for repository access

**Examples**:
- `ghp_xxxxxxxxxxxxxxxxxxxxx` (GitHub token format)

**Security**: Use GitHub Secrets in production, never commit

**Scopes Required**:
- `repo` - Full repository access
- `read:org` - Organization access

**Notes**: Only required if using GitHub repository indexing features

---

## Configuration by Deployment Type

### Local Development

```bash
# OpenSearch (must be running)
OPENSEARCH_HOST=http://localhost:9200
OPENSEARCH_INDEX=ask_certus

# AWS (LocalStack)
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
S3_ENDPOINT_URL=http://localhost:4566
AWS_REGION=us-east-1

# LLM
LLM_MODEL=llama3.1:8b
LLM_URL=http://localhost:11434

# MLflow
MLFLOW_TRACKING_URI=http://localhost:5001

# Logging (optional)
LOG_LEVEL=DEBUG
LOG_JSON_OUTPUT=false
SEND_LOGS_TO_OPENSEARCH=false
```

### Docker Compose

```bash
# OpenSearch
OPENSEARCH_HOST=http://opensearch:9200
OPENSEARCH_INDEX=ask_certus
OPENSEARCH_HTTP_AUTH_USER=admin
OPENSEARCH_HTTP_AUTH_PASSWORD=admin

# AWS (LocalStack)
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
S3_ENDPOINT_URL=http://localstack:4566
AWS_REGION=us-east-1

# LLM
LLM_MODEL=llama3.1:8b
LLM_URL=http://ollama:11434

# MLflow
MLFLOW_TRACKING_URI=http://mlflow:5001

# Logging
LOG_LEVEL=INFO
LOG_JSON_OUTPUT=true
SEND_LOGS_TO_OPENSEARCH=true
OPENSEARCH_LOG_HOST=opensearch
OPENSEARCH_LOG_PORT=9200
```

### AWS Production

```bash
# OpenSearch (AWS Elasticsearch Service)
OPENSEARCH_HOST=https://vpc-xxxxx.us-east-1.es.amazonaws.com
OPENSEARCH_INDEX=certus_prod
OPENSEARCH_HTTP_AUTH_USER=admin
OPENSEARCH_HTTP_AUTH_PASSWORD=${SECURE_PASSWORD}

# AWS
AWS_ACCESS_KEY_ID=${IAM_ACCESS_KEY}
AWS_SECRET_ACCESS_KEY=${IAM_SECRET_KEY}
S3_ENDPOINT_URL=https://s3.amazonaws.com
AWS_REGION=us-east-1

# LLM (SageMaker or external)
LLM_MODEL=llama3.1:70b
LLM_URL=https://llm-service.example.com

# MLflow (RDS or external)
MLFLOW_TRACKING_URI=https://mlflow.example.com

# Logging (separate cluster)
LOG_LEVEL=INFO
LOG_JSON_OUTPUT=true
SEND_LOGS_TO_OPENSEARCH=true
OPENSEARCH_LOG_HOST=opensearch-logs.us-east-1.es.amazonaws.com
OPENSEARCH_LOG_PORT=443
OPENSEARCH_LOG_USERNAME=admin
OPENSEARCH_LOG_PASSWORD=${SECURE_PASSWORD}

# GitHub
GITHUB_TOKEN=${GITHUB_PAT}
```

---

## Configuration Validation

### Automatic Validation

All critical variables are validated at startup:

```
================================================================================
CONFIGURATION VALIDATION PASSED
================================================================================
All critical configuration values are present and valid.
================================================================================
```

If validation fails:

```
================================================================================
CONFIGURATION ERRORS - APPLICATION STARTUP FAILED
================================================================================
  [CRITICAL] opensearch_host: Missing required environment variable: OPENSEARCH_HOST
  [CRITICAL] llm_url: URL must start with http:// or https://

Please fix the above errors and try again.
================================================================================
```

### Manual Validation

```python
from certus_ask.core.config_validation import ConfigurationValidator

# Check all
critical_errors, warnings = ConfigurationValidator.validate_all()

# Specific checks
errors = ConfigurationValidator.check_critical_vars()
error = ConfigurationValidator.validate_url("http://example.com", "field")
error = ConfigurationValidator.validate_log_level("INFO")
error = ConfigurationValidator.validate_aws_region("us-east-1")
```

---

## See Also

- [Configuration Management Guide](index.md)
- [Environment Setup](environment-setup.md)
- [Common Issues](index.md#common-issues)
