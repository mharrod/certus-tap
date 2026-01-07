#!/bin/bash
# Pre-commit security check for Certus TAP
# Prevents committing sensitive data, secrets, and large files

set -e

echo "🔒 Running Certus TAP security checks..."

EXIT_CODE=0

# Color codes for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Function to print colored messages
error() {
    echo -e "${RED}❌ $1${NC}"
    EXIT_CODE=1
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Check 1: No .env files (only .env.example allowed)
echo "Checking for .env files..."
if git diff --cached --name-only | grep -E "^\.env$" | grep -v "\.env\.example"; then
    error "Found .env file staged. Only .env.example should be committed!"
    echo "  Run: git reset HEAD .env"
else
    success "No .env files staged"
fi

# Check 2: No private keys
echo "Checking for private keys..."
if git diff --cached --name-only | grep -E "\.(key|pem|pfx|p12)$"; then
    error "Private key files detected!"
    echo "  Found: $(git diff --cached --name-only | grep -E '\.(key|pem|pfx|p12)$')"
else
    success "No private keys detected"
fi

# Check 3: No Certus evidence bundles (sensitive logs)
echo "Checking for evidence bundles..."
if git diff --cached --name-only | grep -E "(evidence|\.sig$|\.intoto\.json)"; then
    error "Evidence bundles or signatures detected!"
    echo "  These contain sensitive request logs and should not be committed"
    echo "  Found: $(git diff --cached --name-only | grep -E '(evidence|\.sig$|\.intoto\.json)')"
else
    success "No evidence bundles staged"
fi

# Check 4: No credential files
echo "Checking for credential files..."
if git diff --cached --name-only | grep -iE "(credential|secret|password)"; then
    warning "Files with suspicious names detected:"
    git diff --cached --name-only | grep -iE "(credential|secret|password)" || true
    echo "  Review these files to ensure they don't contain secrets"
fi

# Check 5: Check for secrets in staged content (basic patterns)
echo "Scanning staged content for secrets..."
SECRETS_FOUND=0

# AWS keys
if git diff --cached | grep -E "AKIA[0-9A-Z]{16}"; then
    error "AWS Access Key detected in staged changes!"
    SECRETS_FOUND=1
fi

# GitHub PATs
if git diff --cached | grep -E "ghp_[0-9a-zA-Z]{36}"; then
    error "GitHub Personal Access Token detected!"
    SECRETS_FOUND=1
fi

# Generic API keys (basic pattern)
if git diff --cached | grep -E "(api_key|apikey|api-key)\s*[:=]\s*['\"][^'\"]{20,}['\"]"; then
    error "Potential API key detected!"
    SECRETS_FOUND=1
fi

# Private key headers
if git diff --cached | grep -E "BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY"; then
    error "Private key content detected in diff!"
    SECRETS_FOUND=1
fi

if [ $SECRETS_FOUND -eq 0 ]; then
    success "No obvious secrets detected in staged content"
fi

# Check 6: Large files (GitHub limit is 100MB, warn at 50MB)
echo "Checking for large files..."
LARGE_FILES=$(git diff --cached --name-only | xargs -I {} sh -c 'if [ -f "{}" ] && [ $(stat -f%z "{}" 2>/dev/null || stat -c%s "{}" 2>/dev/null) -gt 52428800 ]; then echo "{}"; fi' || true)

if [ -n "$LARGE_FILES" ]; then
    warning "Large files detected (>50MB):"
    echo "$LARGE_FILES"
    echo "  GitHub has a 100MB file size limit"
    echo "  Consider using Git LFS or excluding these files"
fi

# Check 7: Certus-specific sensitive directories
echo "Checking Certus-specific directories..."
SENSITIVE_DIRS="certus-evidence/|compliance-reports/|audit-reports/|.artifacts/"
if git diff --cached --name-only | grep -E "$SENSITIVE_DIRS"; then
    error "Files from sensitive directories detected:"
    git diff --cached --name-only | grep -E "$SENSITIVE_DIRS" || true
    echo "  These directories should be in .gitignore"
else
    success "No files from sensitive directories"
fi

# Check 8: Docker override files (often contain secrets)
echo "Checking for Docker override files..."
if git diff --cached --name-only | grep -E "docker-compose\.override\.yml"; then
    error "docker-compose.override.yml detected!"
    echo "  This file often contains local secrets and should not be committed"
else
    success "No Docker override files staged"
fi

# Summary
echo ""
echo "=================================="
if [ $EXIT_CODE -eq 0 ]; then
    success "All security checks passed!"
else
    error "Security checks failed. Fix the issues above before committing."
    echo ""
    echo "To skip these checks (NOT RECOMMENDED):"
    echo "  git commit --no-verify"
fi
echo "=================================="

exit $EXIT_CODE
