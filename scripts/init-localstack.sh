#!/bin/bash
# Initialize LocalStack S3 buckets for Certus services
# This script is executed by LocalStack during initialization

echo "Creating S3 buckets..."

# Use awslocal (LocalStack's CLI wrapper) if available, otherwise use aws CLI
if command -v awslocal &> /dev/null; then
  awslocal s3 mb s3://raw 2>/dev/null || echo "Bucket 'raw' already exists or creation skipped"
  awslocal s3 mb s3://golden 2>/dev/null || echo "Bucket 'golden' already exists or creation skipped"
else
  # Fall back to aws CLI with endpoint URL
  aws s3 mb s3://raw --endpoint-url http://localhost:4566 2>/dev/null || echo "Bucket 'raw' already exists or creation skipped"
  aws s3 mb s3://golden --endpoint-url http://localhost:4566 2>/dev/null || echo "Bucket 'golden' already exists or creation skipped"
fi

echo "LocalStack initialization complete"
