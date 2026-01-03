#!/bin/bash
set -e

# Load environment variables
if [ ! -f .env ]; then
    echo "❌ .env file not found"
    exit 1
fi

source .env

# Check if variables are set
if [ -z "$GITHUB_PAT" ] || [ -z "$GITHUB_USERNAME" ]; then
    echo "❌ GITHUB_PAT and GITHUB_USERNAME must be set in .env"
    exit 1
fi

echo "🔐 Logging in to ghcr.io as $GITHUB_USERNAME"
echo "$GITHUB_PAT" | docker login ghcr.io -u "$GITHUB_USERNAME" --password-stdin
