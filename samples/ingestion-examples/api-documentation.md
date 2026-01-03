# Certus TAP API Documentation

## Authentication

All API endpoints require a workspace ID in the URL path:
```
/v1/{workspace_id}/endpoint
```

Common workspace IDs:
- `default` - Default workspace for all users
- `my-project` - Custom workspace for a specific project
- `security-team` - Workspace for security scanning results

## Document Ingestion Endpoints

### Upload Single Document
**POST** `/v1/{workspace_id}/index/`

Upload a single document file (PDF, TXT, DOCX, etc.)

Request:
```
Content-Type: multipart/form-data
uploaded_file: <binary file data>
```

Response:
```json
{
  "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Indexed document filename.pdf",
  "document_count": 42,
  "metadata_preview": [...]
}
```

### Upload Folder
**POST** `/v1/{workspace_id}/index_folder/`

Upload all documents from a local folder (recursive)

Request:
```json
{
  "local_directory": "/path/to/documents"
}
```

Response:
```json
{
  "ingestion_id": "550e8400-e29b-41d4-a716-446655440001",
  "message": "Indexed 15 files from /path/to/documents",
  "processed_files": 15,
  "failed_files": 2,
  "quarantined_documents": 3,
  "document_count": 127
}
```

### Upload from S3
**POST** `/v1/{workspace_id}/index/s3`

Index documents from an S3 bucket

Request:
```json
{
  "bucket_name": "raw",
  "prefix": "corpus"
}
```

### Query Documents
**POST** `/v1/{workspace_id}/ask`

Ask a question and retrieve relevant documents

Request:
```json
{
  "question": "What are the key security policies?"
}
```

Response:
```json
{
  "reply": "Based on the documents, the key security policies include...",
  "sources": [
    {
      "document": "security-policy.md",
      "score": 0.95,
      "chunk": "..."
    }
  ]
}
```

## Security Scanning Endpoints

### Upload Security Scan
**POST** `/v1/{workspace_id}/index/security`

Upload SARIF, SPDX, or other security scan results

Request:
```
Content-Type: multipart/form-data
uploaded_file: <SARIF or SPDX file>
format: auto|sarif|spdx|jsonpath
```

Response:
```json
{
  "ingestion_id": "550e8400-e29b-41d4-a716-446655440002",
  "message": "Indexed 42 items from scan.sarif (Neo4j + OpenSearch)",
  "findings_indexed": 42,
  "document_count": 512
}
```

## Best Practices

1. **Use workspace isolation** - Different projects should use different workspaces
2. **Monitor ingestion progress** - Check the metadata_preview in responses
3. **Handle PII carefully** - Use strict mode for documents with sensitive data
4. **Batch efficiently** - Use S3 ingestion for large document sets
5. **Test before production** - Use the preflight script to validate your setup

For more details, see the full API documentation.
