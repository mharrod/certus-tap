# syntax=docker/dockerfile:1.5

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/opt/huggingface
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p "$HF_HOME" \
    && pip install --upgrade pip \
    && pip install uv \
    && uv sync --group backend --frozen --no-dev

RUN pip install --no-cache-dir sentence-transformers

RUN pip install --no-cache-dir playwright \
    && playwright install --with-deps chromium

COPY ask_certus_backend ./ask_certus_backend
COPY samples ./samples

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "ask_certus_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
