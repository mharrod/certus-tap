# syntax=docker/dockerfile:1.5

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/opt/huggingface
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./

# Create placeholder README.md so pyproject.toml validation passes
RUN echo "# Certus TAP" > README.md

RUN apt-get update \
  && apt-get install -y --no-install-recommends git build-essential \
  && rm -rf /var/lib/apt/lists/* \
  && mkdir -p "$HF_HOME" \
  && pip install --upgrade pip \
  && pip install uv \
  && uv sync --frozen --no-dev --all-extras

# Copy actual README.md
COPY README.md ./

# Preload embedding model so runtime never needs to hit Hugging Face
# Skip if SKIP_EMBEDDING_PRELOAD is set to 1 (for faster builds)
ARG SKIP_EMBEDDING_PRELOAD=1
RUN bash -c 'if [ "$SKIP_EMBEDDING_PRELOAD" != "1" ]; then \
  uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer(\"sentence-transformers/all-MiniLM-L6-v2\")"; \
  fi'

COPY certus_ask ./certus_ask
COPY certus_transform ./certus_transform
COPY certus_integrity ./certus_integrity
COPY samples ./samples

# Create a non-root user and switch to it
RUN useradd -m -u 1000 appuser && \
  chown -R appuser:appuser /app && \
  chown -R appuser:appuser "$HF_HOME"

USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "certus_ask.main:app", "--host", "0.0.0.0", "--port", "8000"]
