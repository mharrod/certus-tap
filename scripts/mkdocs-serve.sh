#!/usr/bin/env bash
set -euo pipefail

ADDRESS=${MKDOCS_ADDRESS:-127.0.0.1}
PORT=${MKDOCS_PORT:-8001}

# Prefer zensical.toml if it exists, otherwise fall back to mkdocs.yml
if [ -f "zensical.toml" ]; then
    CONFIG_FILE=${MKDOCS_CONFIG:-zensical.toml}
else
    CONFIG_FILE=${MKDOCS_CONFIG:-mkdocs.yml}
fi

# Find uv - check venv first, then PATH
if [ -f ".venv/bin/uv" ]; then
    UV_CMD=".venv/bin/uv"
else
    UV_CMD="uv"
fi

# Run inside the project environment so MkDocs plugins (awesome-pages, etc.) stay available
exec "${UV_CMD}" run --with zensical zensical serve -f "${CONFIG_FILE}" -a "${ADDRESS}:${PORT}" "$@"
