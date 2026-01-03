import json
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from certus_ask.core.config import settings
from certus_ask.schemas.errors import (
    BadRequestErrorResponse,
    InternalServerErrorResponse,
    NotFoundErrorResponse,
)
from certus_ask.schemas.evaluation import EvaluationResponse
from certus_ask.services import datalake as datalake_service
from certus_ask.services.evaluation import (
    evaluate_test_cases,
    generate_test_cases,
    log_to_mlflow,
    retrieve_documents,
    save_test_cases_to_file,
    upload_results_to_s3,
)
from certus_ask.services.s3 import get_s3_client

router = APIRouter(prefix="/v1/evaluation", tags=["evaluation"])


@router.post(
    "/generate-test-cases",
    responses={
        404: {"model": NotFoundErrorResponse, "description": "No documents found for the index"},
        500: {"model": InternalServerErrorResponse, "description": "Generation failed"},
    },
)
async def generate_test_cases_endpoint(
    index_name: str,
    num_documents: int = Query(1, ge=1, le=50),
    num_questions_per_doc: int = Query(3, ge=1, le=10),
    total_questions: int = Query(5, ge=1, le=100),
    upload_to_s3: bool = Query(False),
) -> FileResponse:
    """Generate test cases from indexed documents.

    Retrieves documents from index and generates question-answer pairs for
    evaluation testing. Optionally uploads generated test cases to S3.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/evaluation/generate-test-cases?index_name=documents&num_documents=5&num_questions_per_doc=3&total_questions=15&upload_to_s3=false"
    ```

    **Success Response (200 - File Download):**
    Downloads a JSON file containing test cases array:
    ```json
    [
      {
        "query": "What is the main topic?",
        "generated_answer": "The document discusses...",
        "ground_truth": "Expected answer text",
        "context": "Relevant document excerpt"
      }
    ]
    ```

    **Error Response (404 - No Documents):**
    ```json
    {
      "error": "index_not_found",
      "message": "No documents found for the supplied index",
      "detail": {
        "index_name": "documents"
      }
    }
    ```

    Args:
        index_name: Name of OpenSearch index to retrieve documents from
        num_documents: Number of documents to sample (1-50, default 1)
        num_questions_per_doc: Questions per document (1-10, default 3)
        total_questions: Total questions to generate (1-100, default 5)
        upload_to_s3: Whether to upload results to S3 evaluation bucket

    Returns:
        FileResponse with JSON file containing test cases

    Raises:
        HTTPException 404: If no documents found in index
        HTTPException 500: If generation fails
    """
    documents = retrieve_documents(index_name, num_documents)
    if not documents:
        raise HTTPException(status_code=404, detail="No documents found for the supplied index.")

    test_cases = generate_test_cases(documents, num_questions_per_doc, total_questions)
    payload_path = save_test_cases_to_file(test_cases)

    if upload_to_s3:
        client = get_s3_client()
        datalake_service.ensure_bucket(client, settings.evaluation_bucket)
        object_key = f"test-cases/{payload_path.name}"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        upload_results_to_s3(client, payload, object_key)

    return FileResponse(
        path=payload_path,
        media_type="application/json",
        filename=payload_path.name,
    )


@router.post(
    "/evaluate-test-cases",
    response_model=EvaluationResponse,
    responses={
        400: {"model": BadRequestErrorResponse, "description": "Invalid file format"},
        500: {"model": InternalServerErrorResponse, "description": "Evaluation failed"},
    },
)
async def evaluate_test_cases_endpoint(
    file: Annotated[UploadFile, File(...)],
    log_to_mlflow_flag: bool = Query(False),
):
    """Evaluate test cases from uploaded JSON file.

    Uploads test cases JSON and runs evaluation metrics (DeepEval framework).
    Optionally logs results to MLflow.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/evaluation/evaluate-test-cases?log_to_mlflow_flag=false" \\
      -H "Content-Type: multipart/form-data" \\
      -F "file=@test_cases.json"
    ```

    **Test Cases JSON Format:**
    ```json
    [
      {
        "query": "What is the main topic?",
        "generated_answer": "The document discusses...",
        "ground_truth": "Expected answer text",
        "context": "Relevant document excerpt"
      }
    ]
    ```

    **Success Response (200):**
    ```json
    {
      "evaluation_results": {
        "test_case_1": {
          "pass": true,
          "score": 0.92,
          "metrics": {
            "faithfulness": 0.95,
            "relevancy": 0.88
          }
        }
      }
    }
    ```

    **Error Response (400 - Invalid File):**
    ```json
    {
      "error": "validation_failed",
      "message": "Uploaded file must be UTF-8 encoded JSON",
      "detail": null
    }
    ```

    Args:
        file: JSON file with test cases (UTF-8 encoded)
        log_to_mlflow_flag: Whether to log results to MLflow (default False)

    Returns:
        EvaluationResponse with evaluation results and metrics

    Raises:
        HTTPException 400: If file is not valid UTF-8 JSON
        HTTPException 500: If evaluation fails
    """
    try:
        raw_payload = (await file.read()).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Uploaded file must be UTF-8 encoded JSON.") from exc
    try:
        raw_test_cases = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Uploaded file is not valid JSON.") from exc

    from deepeval.test_case import LLMTestCase

    test_cases = [
        LLMTestCase(
            input=tc["query"],
            actual_output=tc["generated_answer"],
            expected_output=tc["ground_truth"],
            retrieval_context=[tc["context"]],
        )
        for tc in raw_test_cases
    ]

    results = evaluate_test_cases(test_cases)
    if log_to_mlflow_flag:
        log_to_mlflow(results)

    return {"evaluation_results": results}


@router.post(
    "/import-and-evaluate",
    response_model=EvaluationResponse,
    responses={
        404: {"model": NotFoundErrorResponse, "description": "Test case file not found in S3"},
        500: {"model": InternalServerErrorResponse, "description": "Evaluation failed"},
    },
)
async def import_and_evaluate(object_key: str, log_to_mlflow_flag: bool = Query(False)):
    """Import test cases from S3 and evaluate them.

    Fetches test cases JSON from S3 evaluation bucket, runs evaluation,
    and optionally logs results to MLflow.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/evaluation/import-and-evaluate?object_key=test-cases/batch1.json&log_to_mlflow_flag=false"
    ```

    **Success Response (200):**
    ```json
    {
      "evaluation_results": {
        "test_case_1": {
          "pass": true,
          "score": 0.89,
          "metrics": {
            "faithfulness": 0.92,
            "relevancy": 0.86
          }
        }
      }
    }
    ```

    **Error Response (404 - File Not Found):**
    ```json
    {
      "error": "file_not_found",
      "message": "test-cases/batch1.json not found in evaluation bucket",
      "detail": {
        "bucket": "evaluation-bucket"
      }
    }
    ```

    Args:
        object_key: S3 object key pointing to test cases JSON file
        log_to_mlflow_flag: Whether to log results to MLflow (default False)

    Returns:
        EvaluationResponse with evaluation results and metrics

    Raises:
        HTTPException 404: If test case file not found in S3
        HTTPException 500: If evaluation fails
    """
    from deepeval.test_case import LLMTestCase

    client = get_s3_client()
    datalake_service.ensure_bucket(client, settings.evaluation_bucket)

    try:
        response = client.get_object(Bucket=settings.evaluation_bucket, Key=object_key)
    except client.exceptions.NoSuchKey as exc:
        raise HTTPException(status_code=404, detail=f"{object_key} not found in evaluation bucket.") from exc

    test_cases_data = json.loads(response["Body"].read().decode("utf-8"))
    test_cases = [
        LLMTestCase(
            input=tc["query"],
            actual_output=tc["generated_answer"],
            expected_output=tc["ground_truth"],
            retrieval_context=[tc["context"]],
        )
        for tc in test_cases_data
    ]

    results = evaluate_test_cases(test_cases)
    if log_to_mlflow_flag:
        log_to_mlflow(results)

    return {"evaluation_results": results}


@router.post(
    "/generate-evaluate",
    response_model=EvaluationResponse,
    responses={
        404: {"model": NotFoundErrorResponse, "description": "No documents found for the index"},
        500: {"model": InternalServerErrorResponse, "description": "Generation or evaluation failed"},
    },
)
async def generate_evaluate_endpoint(
    index_name: str,
    num_documents: int = Query(1, ge=1, le=50),
    num_questions_per_doc: int = Query(3, ge=1, le=10),
    total_questions: int = Query(5, ge=1, le=100),
    log_to_mlflow_flag: bool = Query(False),
):
    """Generate and evaluate test cases in one operation.

    Retrieves documents from index, generates test cases, and immediately
    runs evaluation. Optionally logs results to MLflow.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/evaluation/generate-evaluate?index_name=documents&num_documents=3&num_questions_per_doc=2&total_questions=6&log_to_mlflow_flag=false"
    ```

    **Success Response (200):**
    ```json
    {
      "evaluation_results": {
        "test_case_1": {
          "pass": true,
          "score": 0.91,
          "metrics": {
            "faithfulness": 0.93,
            "relevancy": 0.89
          }
        },
        "test_case_2": {
          "pass": false,
          "score": 0.67,
          "metrics": {
            "faithfulness": 0.65,
            "relevancy": 0.69
          }
        }
      }
    }
    ```

    **Error Response (404 - No Documents):**
    ```json
    {
      "error": "index_not_found",
      "message": "No documents found for the supplied index",
      "detail": {
        "index_name": "documents"
      }
    }
    ```

    Args:
        index_name: Name of OpenSearch index to retrieve documents from
        num_documents: Number of documents to sample (1-50, default 1)
        num_questions_per_doc: Questions per document (1-10, default 3)
        total_questions: Total questions to generate (1-100, default 5)
        log_to_mlflow_flag: Whether to log results to MLflow (default False)

    Returns:
        EvaluationResponse with evaluation results and metrics for all test cases

    Raises:
        HTTPException 404: If no documents found in index
        HTTPException 500: If generation or evaluation fails
    """
    documents = retrieve_documents(index_name, num_documents)
    if not documents:
        raise HTTPException(status_code=404, detail="No documents found for the supplied index.")

    test_cases = generate_test_cases(documents, num_questions_per_doc, total_questions)
    results = evaluate_test_cases(test_cases)

    if log_to_mlflow_flag:
        log_to_mlflow(results)

    return {"evaluation_results": results}
