# Certus Assurance Service Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV GIT_TERMINAL_PROMPT=0

# Tool versions
ENV TRIVY_VERSION=0.54.1
ENV SYFT_VERSION=1.17.0
ENV COSIGN_VERSION=2.2.2

WORKDIR /app

# Install system dependencies (including Node.js for JavaScript scanning)
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    git \
    ca-certificates \
    tar \
    gzip \
    nodejs \
    npm && \
    rm -rf /var/lib/apt/lists/* && \
    git config --global http.postBuffer 524288000

# Install Python dependencies
COPY pyproject.toml uv.lock ./

# Create placeholder README.md so pyproject.toml validation passes
RUN echo "# Certus TAP" > README.md

RUN pip install --upgrade pip && \
    pip install uv

# Copy application code first (needed for dependencies)
COPY certus_assurance ./certus_assurance
COPY certus_integrity ./certus_integrity
COPY dagger_modules ./dagger_modules
COPY samples ./samples

# Sync dependencies
RUN uv sync --frozen --no-dev --all-extras

# Install Python security tools
RUN uv pip install ruff bandit detect-secrets

# Install Node.js security tools (as root before switching to appuser)
RUN npm install -g \
    eslint@8.57.0 \
    eslint-plugin-security@1.7.1 \
    @microsoft/eslint-formatter-sarif@3.0.0 \
    retire@5.4.0

# Install Trivy
RUN mkdir -p /tmp/trivy-install && \
    cd /tmp/trivy-install && \
    curl -fsSL https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz -o trivy.tgz && \
    tar -xzf trivy.tgz && \
    mv trivy /usr/local/bin/trivy && \
    chmod +x /usr/local/bin/trivy && \
    rm -rf /tmp/trivy-install

# Install Syft
RUN mkdir -p /tmp/syft-install && \
    cd /tmp/syft-install && \
    curl -fsSL https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}/syft_${SYFT_VERSION}_linux_amd64.tar.gz -o syft.tgz && \
    tar -xzf syft.tgz && \
    mv syft /usr/local/bin/syft && \
    chmod +x /usr/local/bin/syft && \
    rm -rf /tmp/syft-install

# Install Cosign
RUN mkdir -p /tmp/cosign-install && \
    cd /tmp/cosign-install && \
    curl -fsSL https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-linux-amd64 -o cosign && \
    mv cosign /usr/local/bin/cosign && \
    chmod +x /usr/local/bin/cosign && \
    rm -rf /tmp/cosign-install

# Install Opengrep
RUN curl -fsSL https://raw.githubusercontent.com/opengrep/opengrep/main/install.sh | bash && \
    ln -sf "$HOME/.opengrep/cli/latest/opengrep" /usr/local/bin/opengrep && \
    chmod +x /usr/local/bin/opengrep

# Create Trivy cache directory
RUN mkdir -p /tmp/trivy-cache && chmod 777 /tmp/trivy-cache
ENV TRIVY_CACHE_DIR=/tmp/trivy-cache

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /tmp/certus-assurance && \
    chown -R appuser:appuser /tmp/certus-assurance

USER appuser

# Install security_module as appuser (with dependencies like dagger-io)
RUN uv pip install -e ./dagger_modules/security

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "certus_assurance.service:app", "--host", "0.0.0.0", "--port", "8000"]
