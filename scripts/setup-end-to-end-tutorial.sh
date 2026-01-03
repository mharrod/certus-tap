#!/bin/bash
# Setup script for End-to-End Workflow Tutorial
# Ensures all services are configured correctly for the tutorial

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Certus End-to-End Tutorial Setup ===${NC}\n"

# 1. Check if sample artifacts exist
echo -e "${YELLOW}[1/6]${NC} Checking sample artifacts..."
if [ ! -d "samples/non-repudiation/scan-artifacts" ]; then
    echo -e "${RED}✗ Sample artifacts not found${NC}"
    echo "Please ensure samples/non-repudiation/scan-artifacts/ exists"
    exit 1
fi
echo -e "${GREEN}✓ Sample artifacts found${NC}\n"

# 2. Check docker-compose.yml for sample mode
echo -e "${YELLOW}[2/6]${NC} Checking docker-compose configuration..."
COMPOSE_FILE="certus_assurance/deploy/docker-compose.yml"
if grep -q "CERTUS_ASSURANCE_USE_SAMPLE_MODE=true" "$COMPOSE_FILE"; then
    echo -e "${GREEN}✓ Sample mode enabled${NC}\n"
else
    echo -e "${YELLOW}⚠ Sample mode not enabled${NC}"
    echo "Would you like to enable sample mode? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        sed -i.bak 's/CERTUS_ASSURANCE_USE_SAMPLE_MODE=false/CERTUS_ASSURANCE_USE_SAMPLE_MODE=true/' "$COMPOSE_FILE"
        echo -e "${GREEN}✓ Enabled sample mode${NC}\n"
    else
        echo -e "${YELLOW}⚠ Continuing with production mode (scans will be slower)${NC}\n"
    fi
fi

# 3. Stop existing services
echo -e "${YELLOW}[3/6]${NC} Stopping existing services..."
just down > /dev/null 2>&1 || true
echo -e "${GREEN}✓ Services stopped${NC}\n"

# 4. Start all required services
echo -e "${YELLOW}[4/6]${NC} Starting all services..."
just up
sleep 5
echo -e "${GREEN}✓ Services started${NC}\n"

# 5. Wait for services to be ready
echo -e "${YELLOW}[5/6]${NC} Waiting for services to be ready..."
MAX_WAIT=60
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if curl -s http://localhost:8056/health > /dev/null 2>&1; then
        break
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    echo -n "."
done
echo ""

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo -e "${RED}✗ Services failed to start${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Services ready${NC}\n"

# 6. Verify configuration
echo -e "${YELLOW}[6/6]${NC} Verifying configuration..."

# Check Assurance service mode
SCANNING_MODE=$(curl -s http://localhost:8056/health | jq -r '.scanning_mode')
echo "  Assurance scanning mode: ${SCANNING_MODE}"

# Check other services
SERVICES=(
    "http://localhost:8057/v1/health|Trust"
    "http://localhost:8100/health|Transform"
    "http://localhost:8000/health|Ask"
)

ALL_OK=true
for service in "${SERVICES[@]}"; do
    IFS='|' read -r url name <<< "$service"
    if curl -s "$url" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} ${name} service ready"
    else
        echo -e "  ${RED}✗${NC} ${name} service not ready"
        ALL_OK=false
    fi
done

# Check S3 buckets
echo -e "\nChecking S3 buckets..."
if docker exec localstack awslocal s3 ls s3://raw > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Raw bucket exists"
else
    echo -e "  ${YELLOW}⚠${NC} Creating raw bucket..."
    docker exec localstack awslocal s3 mb s3://raw
fi

if docker exec localstack awslocal s3 ls s3://golden > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Golden bucket exists"
else
    echo -e "  ${YELLOW}⚠${NC} Creating golden bucket..."
    docker exec localstack awslocal s3 mb s3://golden
fi

echo ""
if [ "$ALL_OK" = true ]; then
    echo -e "${GREEN}✓ All services ready!${NC}\n"
    echo -e "${GREEN}=== Setup Complete ===${NC}"
    echo ""
    echo "You can now follow the tutorial at:"
    echo "  docs/learn/assurance/end-to-end-workflow.md"
    echo ""
    echo "Quick test:"
    echo "  curl http://localhost:8056/health | jq ."
    echo ""
    if [ "$SCANNING_MODE" = "sample" ]; then
        echo -e "${GREEN}Using sample mode - scans will complete in seconds${NC}"
    else
        echo -e "${YELLOW}Using production mode - scans will take 2-5 minutes${NC}"
    fi
else
    echo -e "${RED}✗ Some services are not ready${NC}"
    echo "Run: docker compose logs <service-name>"
    exit 1
fi
