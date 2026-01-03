# Certus Ask Service Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/opt/huggingface
ENV PYTHONPATH=/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml uv.lock ./

# Create placeholder README.md so pyproject.toml validation passes
RUN echo "# Certus TAP" > README.md

RUN pip install --upgrade pip && \
    pip install uv && \
    uv sync --frozen --no-dev --all-extras

# Install sentence-transformers separately
RUN pip install sentence-transformers

# Copy application code
COPY certus_ask ./certus_ask
COPY certus_integrity ./certus_integrity
COPY samples ./samples

# Create non-root user and directories
RUN useradd -m -u 1000 appuser && \
    mkdir -p "$HF_HOME" && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser "$HF_HOME"

USER appuser

# Preload embedding model (optional)
ARG SKIP_EMBEDDING_PRELOAD=1
RUN if [ "$SKIP_EMBEDDING_PRELOAD" != "1" ]; then \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"; \
    fi

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "certus_ask.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
