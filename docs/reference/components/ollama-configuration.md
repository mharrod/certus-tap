# Ollama & LLM Configuration

## Purpose
Describe how Certus TAP connects to an LLM for the RAG pipeline, starting with the default local Ollama setup and expanding to external providers.

## Audience & Prerequisites
- Operators running the stack locally for demos or tests.
- Developers swapping the default generator (e.g., to OpenAI, Anthropic).
- Familiarity with `.env`, `certus_ask/core/config.py`, and `certus_ask/pipelines/rag.py`.

## Overview
- `.env` ships with `LLM_URL=http://host.docker.internal:11434` and `LLM_MODEL=llama3.1:8b`, expecting an Ollama daemon on the host.
- The backend calls the generator defined in `pipelines/rag.py`; swap implementations to talk to remote APIs.
- Health checks and `/v1/ask` rely on the configured LLM, so connectivity must be verified after changes.

## Key Concepts

### Default Local Flow
1. Start Ollama on the host:
   ```bash
   ollama run llama3.1:8b
   ```
2. `.env` entries:
   ```bash
   LLM_MODEL=llama3.1:8b
   LLM_URL=http://host.docker.internal:11434
   ```
3. The backend (running in Docker) communicates via `host.docker.internal` to the host’s Ollama port.

### Switching Models
- Pull the desired model: `ollama pull deepseek-r1:8b`.
- Update `.env` `LLM_MODEL=deepseek-r1:8b`.
- Restart the backend container (`docker compose up -d ask-certus-backend`).

### Remote Providers
- Replace the generator in `certus_ask/pipelines/rag.py` (e.g., `OpenAIGenerator`, Azure, Anthropic).
- Extend `Settings` in `certus_ask/core/config.py` with required API keys/URLs.
- Sample `.env` entries:
  ```bash
  LLM_URL=https://api.openai.com/v1
  LLM_MODEL=gpt-4o-mini
  OPENAI_API_KEY=sk-...
  ```

### Health Checks
- `/v1/ask` fails fast if the generator can’t reach the LLM.
- Quick connectivity tests:
  ```bash
  # From host
  curl http://localhost:11434/api/tags
  curl http://localhost:11434/api/generate -d '{"prompt":"hi"}'

  # From container (ensures networking works)
  docker compose exec ask-certus-backend curl -s http://host.docker.internal:11434/api/tags
  ```

## Workflows / Operations
1. **Local Demo**
   - Run `ollama run llama3.1:8b` on host.
   - `just up` (starts backend, LocalStack, OpenSearch).
   - Hit `/v1/ask` or use the Streamlit console “Ask Certus” workflow to verify.

2. **Swap to Different Ollama Model**
   - `ollama pull <model>`
   - Update `.env` `LLM_MODEL`.
   - `docker compose restart ask-certus-backend`.

3. **Use Cloud Provider**
   - Install provider SDK (update Dockerfile or requirements).
   - Implement new generator in `pipelines/rag.py`.
   - Update `.env` with API keys.
   - Rebuild backend image (`docker compose build --no-cache ask-certus-backend`).
   - Run `/scripts/preflight.sh` to confirm `/v1/ask` works.

## Configuration / Interfaces
- `.env` keys: `LLM_URL`, `LLM_MODEL`, provider-specific keys (`OPENAI_API_KEY`, etc.).
- `Settings` (`certus_ask/core/config.py`) exposes these to the pipeline.
- `certus_ask/pipelines/rag.py` wires the generator (`Generator` or provider-specific classes).

## Troubleshooting / Gotchas
- **500 from `/v1/ask`:** Check backend logs; most failures come from missing LLM connection or model not loaded.
- **Container can’t reach host:** Ensure Docker Desktop/Colima supports `host.docker.internal`; alternative is to expose Ollama on 0.0.0.0 and point `LLM_URL` to `http://<host-ip>:11434`.
- **Dependency mismatch:** After editing `pipelines/rag.py`, rebuild the backend image so new SDKs are installed.
- **Performance:** Large models may exhaust VRAM/CPU; switch to smaller ones or offload to managed APIs.

## Related Documents
- [Standardized Response Format](../api/api-response.md) – `/v1/ask` payload structure.
- [Streamlit Console](streamlit-console.md) – UI for Ask Certus testing.
- [Logging – Usage](../logging/usage.md) – Inspect generator logs when troubleshooting.
