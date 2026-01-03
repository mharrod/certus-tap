# ADR-0002: Configuration Management with Validation

## Status
**Accepted**

## Date
2025-11-14

## Context

### Problem
Certus-TAP requires configuration for multiple external services (OpenSearch, S3, LLM, MLflow) with different requirements:

1. **Variety of environments** - Local development, Docker, staging, production
2. **Security** - Sensitive credentials must not be hardcoded or exposed
3. **Failure prevention** - Invalid config should be caught at startup, not runtime
4. **Type safety** - Configuration values should be validated types (not strings)
5. **Defaults** - Some config has sensible defaults (log level, bucket names)
6. **Documentation** - Developers need to understand what each variable is

### Constraints
- Application must fail fast on invalid config (not discover issues in production)
- Support multiple Python versions (3.9-3.13)
- Work in Docker, local development, and various deployment platforms
- No external secret management systems required for basic usage

### What We Needed
- Load environment variables from `.env` file
- Type validate all configuration
- Distinguish critical (required) from optional config
- Provide clear error messages
- Not block development with complex setup

## Decision

We chose **Pydantic Settings + python-dotenv + custom validation** because:

### 1. Pydantic for Type Safety
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    opensearch_host: str = Field(..., env="OPENSEARCH_HOST")
    opensearch_port: int = Field(default=9200, env="OPENSEARCH_LOG_PORT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
```
- Type validation: `opensearch_port: int` ensures it's a number
- Raises ValidationError if env var is not convertible
- IDE support: Type hints enable autocomplete
- Industry standard in Python ecosystem

### 2. Python-dotenv for .env Loading
```python
from dotenv import load_dotenv

load_dotenv(".env")  # Load into os.environ
settings = Settings()  # Pydantic reads os.environ
```
- Simple, works everywhere (local, Docker, cloud)
- `.env` file for development (git-ignored for credentials)
- `.env.example` for documentation
- No external dependencies beyond standard python-dotenv

### 3. Fail-Fast Validation at Startup
```python
# In main.py, before anything else
ConfigurationValidator.fail_fast(env_path=".env")
```
- Validates all critical config present
- Validates formats (URLs, log levels, regions)
- Checks pydantic Settings validation
- Exits immediately with helpful error message
- Prevents discovering config errors in production

### 4. Structured Error Messages
```
================================================================================
CONFIGURATION ERRORS - APPLICATION STARTUP FAILED
================================================================================
  [CRITICAL] opensearch_host: Missing required environment variable: OPENSEARCH_HOST
  [CRITICAL] llm_url: URL must start with http:// or https://

Please fix the above errors and try again.
================================================================================
```
- Tells exactly what's wrong
- Suggests how to fix it
- Lists all errors at once (not one at a time)

### 5. Critical vs Optional Distinction
```python
# Critical - app won't start without these
CRITICAL_CONFIG = {
    "opensearch_host": "OpenSearch cluster URL",
    "aws_access_key_id": "AWS credentials",
    ...  # 9 critical variables
}

# Optional - have defaults or are truly optional
OPTIONAL_CONFIG = {
    "github_token": None,
    "log_level": "INFO",
    "datalake_raw_bucket": "raw",
    ...
}
```
- Developers know what must be provided
- Allows graceful degradation (optional features work without GitHub token)

## Architecture

```
Application Startup
        ↓
python-dotenv loads .env
        ↓
ConfigurationValidator runs
├─ Checks critical variables present
├─ Validates URL formats
├─ Validates log levels
├─ Validates AWS regions
├─ Runs pydantic validation
        ↓ (errors found)
    Exit with error messages
        ↓ (all valid)
Pydantic Settings created
        ↓
Application initialization
```

## Consequences

### Positive
✅ **Type safety** - Configuration is validated, not strings
✅ **Fail-fast** - Invalid config caught at startup
✅ **Clear errors** - Developers know exactly what's wrong
✅ **IDE support** - Type hints enable autocomplete
✅ **Extensible** - Easy to add new config values
✅ **Industry standard** - Pydantic is widely used, well-documented
✅ **Zero dependencies** - Beyond what's already used
✅ **Environment agnostic** - Works local, Docker, cloud, etc.

### Negative
❌ **No secret encryption** - `.env` file is plaintext (mitigated by .gitignore)
❌ **Python-specific** - Not language-agnostic (not an issue for Python project)
❌ **Manual secret rotation** - No built-in rotation mechanism

### Neutral
◯ **Validation overhead** - Minimal (<10ms at startup)
◯ **Configuration drift** - Must keep `.env.example` updated

## Alternatives Considered

### 1. Environment Variables Only (No .env File)
```python
opensearch_host = os.environ["OPENSEARCH_HOST"]  # KeyError if missing
```
**Rejected** - Error at runtime, not startup; no type validation; clunky

### 2. YAML/TOML Configuration Files
```yaml
opensearch:
  host: localhost:9200
  index: documents
```
**Rejected** - Adds file management complexity; .env is simpler for Docker

### 3. Hardcoded Defaults
```python
OPENSEARCH_HOST = "http://localhost:9200"  # In code
```
**Rejected** - Security risk; hardcoding prevents different environments; inflexible

### 4. Minimal Validation (No Fail-Fast)
```python
@app.on_event("startup")
async def validate_config():
    # Check config after startup
    if not settings.opensearch_host:
        raise Exception("Missing opensearch_host")
```
**Rejected** - Errors discovered too late; app partially initialized; poor UX

### 5. Complex Secret Management Systems
```
AWS Secrets Manager → Vault → Application
```
**Rejected** - Overkill for early development; can add later if needed; keeps MVP simple

### 6. Single JSON Config File
```json
{
  "opensearch_host": "localhost:9200",
  "aws_access_key_id": "..."
}
```
**Rejected** - Can't version control without exposing secrets; .env pattern better

## Implementation Details

### Configuration Validation (`certus_ask/core/config_validation.py`)

```python
class ConfigurationValidator:
    CRITICAL_CONFIG = {
        "opensearch_host": "...",
        "opensearch_index": "...",
        # 9 critical variables
    }

    OPTIONAL_CONFIG = {
        "github_token": None,
        "log_level": "INFO",
        # 10+ optional variables
    }

    @classmethod
    def fail_fast(cls, env_path: Optional[str] = None) -> None:
        """Validate and exit if errors found"""
        critical_errors, warnings = cls.validate_all(env_path)

        if critical_errors:
            print_errors(critical_errors)
            sys.exit(1)

        if warnings:
            print_warnings(warnings)
```

### Pydantic Settings (`certus_ask/core/config.py`)

```python
class Settings(BaseSettings):
    # Critical variables
    opensearch_host: str = Field(..., env="OPENSEARCH_HOST")
    opensearch_index: str = Field(..., env="OPENSEARCH_INDEX")
    aws_access_key_id: str = Field(..., env="AWS_ACCESS_KEY_ID")

    # Optional with defaults
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    datalake_raw_bucket: str = Field(default="raw", env="DATALAKE_RAW_BUCKET")

    # Optional without defaults
    github_token: str | None = Field(None, env="GITHUB_TOKEN")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

### Startup Integration (`certus_ask/main.py`)

```python
def create_app() -> FastAPI:
    # Validate configuration before doing anything else
    ConfigurationValidator.fail_fast(env_path=".env")

    settings = get_settings()

    # Now safe to use settings in app initialization
    logger.info("app.startup", log_level=settings.log_level)
    ...
```

### Environment File (`.env.example`)

Documented template showing all variables:
```
# Critical - Must be set
OPENSEARCH_HOST=http://opensearch:9200
OPENSEARCH_INDEX=ask_certus

# Optional - Have defaults
LOG_LEVEL=INFO
DATALAKE_RAW_BUCKET=raw

# Optional - No default
GITHUB_TOKEN=
```

## Validation Rules

| Variable | Type | Required | Validation |
|----------|------|----------|-----------|
| `OPENSEARCH_HOST` | URL | Yes | Must start with http/https |
| `OPENSEARCH_INDEX` | String | Yes | Non-empty |
| `AWS_REGION` | String | Yes | Format: `xx-xxxx-#` |
| `LOG_LEVEL` | Enum | No (default: INFO) | Must be DEBUG/INFO/WARNING/ERROR/CRITICAL |
| `LLM_URL` | URL | Yes | Must start with http/https |
| `GITHUB_TOKEN` | String | No | None (optional) |

## Trade-offs Made

| Decision | Why | Trade-off |
|----------|-----|-----------|
| Fail-fast validation | Catch errors early | Startup is slightly slower |
| Pydantic Settings | Type safety + ecosystem | Python-specific |
| .env file | Simple, works everywhere | Plaintext credentials (mitigate with .gitignore) |
| Custom validator | Better control | More code than pure pydantic |
| Critical vs optional | Flexibility | More complexity |

## Migration Path to Advanced Systems

If in future you need:

1. **Secret encryption** - Add `python-dotenv-vault` for encrypted `.env` files
2. **Rotation** - Integrate AWS Secrets Manager (boto3 reads secrets)
3. **Audit logging** - Log config access to OpenSearch
4. **Multi-environment** - Create `.env.dev`, `.env.prod` templates
5. **Vault integration** - Replace `.env` loading with Vault client

No code changes needed, just update where configs are loaded from.

## Related ADRs

- **ADR-0001** - Structured Logging (uses configuration)
- **ADR-0003** - Error Handling (validates input)

## References

### Implementation
- [Configuration Module](../../certus_ask/core/config.py)
- [Configuration Validator](../../certus_ask/core/config_validation.py)
- [Application Factory](../../certus_ask/main.py)

### Documentation
- [Configuration Management Guide](../Configuration/index.md)
- [Configuration Reference](../Configuration/configuration-reference.md)
- [Environment Setup Guide](../Configuration/environment-setup.md)

### Standards
- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [python-dotenv Documentation](https://github.com/theskumar/python-dotenv)
- [12-Factor App - Config](https://12factor.net/config)

## Questions & Answers

**Q: Why not use environment variables only?**
A: `.env` files are more convenient for development and easier to version control (with .gitignore).

**Q: What if I want different config files per environment?**
A: Create `.env.local`, `.env.prod`, etc. Load the appropriate one based on environment.

**Q: How do I rotate secrets?**
A: Currently manual - update `.env`, restart app. Can integrate with AWS Secrets Manager if needed.

**Q: Can I use this in Docker?**
A: Yes! Docker can pass environment variables via docker-compose or -e flags.

**Q: What about CI/CD?**
A: Set environment variables in CI/CD secrets, they'll be passed to application at runtime.

---

**Status**: Accepted and implemented
**Last Updated**: 2025-11-14
