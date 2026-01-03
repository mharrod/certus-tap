# Certus Trust Service Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml uv.lock ./

# Create placeholder README.md so pyproject.toml validation passes
RUN echo "# Certus TAP" > README.md

RUN pip install --upgrade pip && \
    pip install uv && \
    uv sync --frozen --no-dev --all-extras

# Copy application code
COPY certus_trust ./certus_trust
COPY certus_integrity ./certus_integrity

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "certus_trust.main:app", "--host", "0.0.0.0", "--port", "8000"]
