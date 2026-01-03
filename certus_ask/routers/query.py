"""Query router for RAG-based question answering.

Provides endpoints for querying documents using the Retrieval-Augmented
Generation (RAG) pipeline.
"""

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from certus_ask.core.exceptions import (
    ExternalServiceError,
    QueryExecutionError,
)
from certus_ask.core.metrics import get_query_metrics
from certus_ask.pipelines.rag import create_rag_pipeline
from certus_ask.schemas.errors import (
    BadRequestErrorResponse,
    InternalServerErrorResponse,
    ServiceUnavailableErrorResponse,
)
from certus_ask.schemas.query import QuestionRequest
from certus_ask.services.opensearch import get_document_store_for_workspace

router = APIRouter(prefix="/v1", tags=["query"])


class QuestionResponse(BaseModel):
    """Response from ask endpoint.

    Attributes:
        answer: Generated answer to the question
    """

    answer: str


@router.post(
    "/{workspace_id}/ask",
    response_model=QuestionResponse,
    responses={
        400: {"model": BadRequestErrorResponse, "description": "Invalid query format"},
        503: {"model": ServiceUnavailableErrorResponse, "description": "Required service unavailable"},
        504: {"model": InternalServerErrorResponse, "description": "Query execution timed out"},
    },
)
async def ask_question(workspace_id: str, request: QuestionRequest) -> QuestionResponse:
    """Ask a question and get an answer using RAG pipeline.

    Uses the Retrieval-Augmented Generation pipeline to find relevant documents
    and generate an answer to the user's question.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/ask" \\
      -H "Content-Type: application/json" \\
      -d '{"question": "What is the privacy policy?"}'
    ```

    **Success Response (200):**
    ```json
    {
      "answer": "Based on the retrieved documents, the privacy policy states that..."
    }
    ```

    **Error Response (400 - Invalid Query):**
    ```json
    {
      "error": "validation_failed",
      "message": "Invalid query: Question text cannot be empty",
      "detail": null
    }
    ```

    **Error Response (503 - Service Unavailable):**
    ```json
    {
      "error": "service_unavailable",
      "message": "Required service unavailable: OpenSearch is not responding",
      "detail": {
        "service": "opensearch"
      }
    }
    ```

    **Error Response (504 - Timeout):**
    ```json
    {
      "error": "timeout",
      "message": "Query execution timed out. Please try again with a shorter question.",
      "detail": null
    }
    ```

    Args:
        request: Question request with user's query text

    Returns:
        QuestionResponse with the generated answer from RAG pipeline

    Raises:
        HTTPException 400: If query format is invalid
        HTTPException 503: If required service (OpenSearch, LLM) is unavailable
        HTTPException 504: If query execution times out
    """
    document_store = get_document_store_for_workspace(workspace_id)
    pipeline = create_rag_pipeline(document_store)

    metrics = get_query_metrics()
    start_time = time.time()

    try:
        result = pipeline.run({
            "embedder": {"text": request.question},
            "retriever": {"top_k": 3},
            "prompt_builder": {"query": request.question},
        })

        # Record successful query
        response_time = time.time() - start_time
        metrics.record_query(response_time=response_time, success=True)

    except TimeoutError as exc:
        # Record failed query
        response_time = time.time() - start_time
        metrics.record_query(response_time=response_time, success=False)

        raise HTTPException(
            status_code=504,
            detail="Query execution timed out. Please try again with a shorter question.",
        ) from exc
    except (ValueError, KeyError) as exc:
        # Record failed query
        response_time = time.time() - start_time
        metrics.record_query(response_time=response_time, success=False)

        raise HTTPException(
            status_code=400,
            detail=f"Invalid query: {exc!s}",
        ) from exc
    except ExternalServiceError as exc:
        # Record failed query
        response_time = time.time() - start_time
        metrics.record_query(response_time=response_time, success=False)

        raise HTTPException(
            status_code=503,
            detail=f"Required service unavailable: {exc.message}",
        ) from exc
    except Exception as exc:
        # Record failed query
        response_time = time.time() - start_time
        metrics.record_query(response_time=response_time, success=False)

        raise QueryExecutionError(
            message="Failed to execute query",
            error_code="query_execution_failed",
            details={"error": str(exc)},
        ) from exc

    if "llm" not in result or "replies" not in result["llm"]:
        # Record failed query
        response_time = time.time() - start_time
        metrics.record_query(response_time=response_time, success=False)

        raise HTTPException(
            status_code=500,
            detail="Unexpected result structure from the RAG pipeline.",
        )

    return QuestionResponse(answer=result["llm"]["replies"][0])
