#!/bin/bash
# Initialize S3 buckets for Certus TAP
set -e

echo "Creating S3 buckets..."
awslocal s3 mb s3://raw 2>/dev/null || echo "Bucket 'raw' already exists"
awslocal s3 mb s3://golden 2>/dev/null || echo "Bucket 'golden' already exists"

echo "S3 buckets initialized successfully"
awslocal s3 ls
