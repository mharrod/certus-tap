import json
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests
from botocore.client import BaseClient
from opensearchpy import OpenSearch

from certus_ask.core.config import settings

EVAL_EXTRA_MESSAGE = "Evaluation features require the 'eval' extra. Install with: pip install 'certus-tap[eval]'"

# Import guards for optional evaluation dependencies
try:
    import mlflow
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        ContextualRelevancyMetric,
    )
    from deepeval.test_case import LLMTestCase
except ImportError as exc:
    raise ImportError(EVAL_EXTRA_MESSAGE) from exc


def _create_opensearch_client() -> OpenSearch:
    parsed = urlparse(settings.opensearch_host)
    host = parsed.hostname or settings.opensearch_host
    port = parsed.port or 9200
    scheme = parsed.scheme or "http"

    auth = None
    if settings.opensearch_http_auth_user and settings.opensearch_http_auth_password:
        auth = (settings.opensearch_http_auth_user, settings.opensearch_http_auth_password)

    return OpenSearch(
        hosts=[{"host": host, "port": port, "scheme": scheme}],
        http_auth=auth,
        use_ssl=scheme == "https",
        verify_certs=False,
    )


def retrieve_documents(index_name: str, num_documents: int) -> list[dict]:
    client = _create_opensearch_client()
    query = {"size": num_documents, "query": {"match_all": {}}}
    response = client.search(index=index_name, body=query)
    return [hit["_source"] for hit in response["hits"]["hits"] if "content" in hit["_source"]]


def ollama_generate(prompt: str) -> str:
    headers = {"Content-Type": "application/json"}
    payload = {"model": settings.llm_model, "prompt": prompt}

    try:
        response = requests.post(settings.llm_url, json=payload, headers=headers, stream=True, timeout=120)
        response.raise_for_status()
        full_response = ""
        for chunk in response.iter_lines():
            if chunk:
                json_chunk = json.loads(chunk.decode("utf-8"))
                full_response += json_chunk.get("response", "")
        return full_response.strip()
    except requests.RequestException as exc:
        return f"Error: {exc}"


def generate_questions(content: str, num_questions: int) -> list[str]:
    prompt = f"""
    Generate {num_questions} detailed and relevant questions based on the following content:
    {content}
    """
    response = ollama_generate(prompt)
    return [question.strip() for question in response.split("\n") if question.strip()]


def generate_answer(question: str, context: str) -> str:
    prompt = f"""
    Based on the provided context, answer the question:
    Context: {context}
    Question: {question}
    """
    return ollama_generate(prompt)


def generate_test_cases(documents: list[dict], num_questions_per_doc: int, total_questions: int) -> list[LLMTestCase]:
    test_cases: list[LLMTestCase] = []
    for document in documents:
        content = document.get("content", "")
        if not content:
            continue

        questions = generate_questions(content, num_questions_per_doc)
        for question in questions:
            ground_truth = generate_answer(question, content)
            test_case = LLMTestCase(
                input=question,
                actual_output=ground_truth,
                expected_output=ground_truth,
                retrieval_context=[content],
            )
            test_cases.append(test_case)

            if len(test_cases) >= total_questions:
                return test_cases

    return test_cases


def evaluate_test_cases(test_cases: list[LLMTestCase]) -> list[dict]:
    metrics = {
        "Precision": ContextualPrecisionMetric(threshold=0.7, model=settings.llm_model, include_reason=True),
        "Recall": ContextualRecallMetric(threshold=0.7, model=settings.llm_model, include_reason=True),
        "Relevancy": ContextualRelevancyMetric(threshold=0.7, model=settings.llm_model, include_reason=True),
        "Answer Relevancy": AnswerRelevancyMetric(threshold=0.7, model=settings.llm_model, include_reason=True),
    }

    results: list[dict] = []

    for test_case in test_cases:
        case_result = {
            "query": test_case.input,
            "context": test_case.retrieval_context[0],
            "ground_truth": test_case.expected_output,
            "generated_answer": test_case.actual_output,
            "scores": {},
        }

        for metric_name, metric in metrics.items():
            try:
                score = metric.measure([test_case])
                case_result["scores"][metric_name] = {"score": score, "reason": metric.reason}
            except ValueError as exc:
                case_result["scores"][metric_name] = {"score": 0.0, "reason": str(exc)}

        results.append(case_result)

    return results


def log_to_mlflow(results: list[dict], experiment_name: str = "llama_evaluations") -> None:
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run():
        for i, result in enumerate(results, start=1):
            for metric_name, metric_data in result["scores"].items():
                mlflow.log_metric(f"{metric_name}_score_{i}", metric_data["score"])

        artifact_path = Path("test_cases.json")
        with artifact_path.open("w", encoding="utf-8") as file:
            json.dump(results, file, indent=4)

        mlflow.log_param("total_test_cases", len(results))
        mlflow.log_artifact(str(artifact_path))


def save_test_cases_to_file(test_cases: list[LLMTestCase]) -> Path:
    filename = Path(f"test_cases_{uuid.uuid4()}.json")
    payload = [
        {
            "query": tc.input,
            "context": tc.retrieval_context[0],
            "ground_truth": tc.expected_output,
            "generated_answer": tc.actual_output,
        }
        for tc in test_cases
    ]

    with filename.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=4)

    return filename


def upload_results_to_s3(s3_client: BaseClient, data: list[dict], object_key: str) -> None:
    s3_client.put_object(
        Bucket=settings.evaluation_bucket,
        Key=object_key,
        Body=json.dumps(data, indent=4).encode("utf-8"),
        ContentType="application/json",
    )


__all__ = [
    "evaluate_test_cases",
    "generate_answer",
    "generate_questions",
    "generate_test_cases",
    "log_to_mlflow",
    "ollama_generate",
    "retrieve_documents",
    "save_test_cases_to_file",
    "upload_results_to_s3",
]
