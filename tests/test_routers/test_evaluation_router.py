import json
import sys
from types import SimpleNamespace

import pytest

# Check if evaluation dependencies are available
try:
    import mlflow

    EVAL_AVAILABLE = True
except ImportError:
    EVAL_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not EVAL_AVAILABLE, reason="Evaluation features require 'mlflow' (install with: pip install 'certus-tap[eval]')"
)


@pytest.fixture(autouse=True)
def stub_llm_test_case(monkeypatch):
    """Provide a lightweight stand-in for deepeval.test_case.LLMTestCase."""

    class DummyLLMTestCase:
        def __init__(self, input, actual_output, expected_output, retrieval_context):
            self.input = input
            self.actual_output = actual_output
            self.expected_output = expected_output
            self.retrieval_context = retrieval_context

    monkeypatch.setitem(sys.modules, "deepeval.test_case", SimpleNamespace(LLMTestCase=DummyLLMTestCase))
    return DummyLLMTestCase


def test_generate_test_cases_endpoint_returns_file(test_client, monkeypatch, tmp_path):
    """Happy-path generation returns a JSON file streamed via FileResponse."""
    documents = [{"content": "doc"}]
    test_cases = [{"query": "Q1"}]
    output_path = tmp_path / "cases.json"
    output_path.write_text(json.dumps(test_cases), encoding="utf-8")

    monkeypatch.setattr("certus_ask.routers.evaluation.retrieve_documents", lambda *args, **kwargs: documents)
    monkeypatch.setattr("certus_ask.routers.evaluation.generate_test_cases", lambda docs, *_: test_cases)
    monkeypatch.setattr("certus_ask.routers.evaluation.save_test_cases_to_file", lambda _: output_path)

    response = test_client.post("/v1/evaluation/generate-test-cases", params={"index_name": "demo"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.content == output_path.read_bytes()


def test_generate_test_cases_endpoint_handles_missing_documents(test_client, monkeypatch):
    """When no documents exist, the endpoint should return 404."""
    monkeypatch.setattr("certus_ask.routers.evaluation.retrieve_documents", lambda *args, **kwargs: [])

    response = test_client.post("/v1/evaluation/generate-test-cases", params={"index_name": "missing"})

    assert response.status_code == 404
    assert "No documents" in response.json()["detail"]


def test_evaluate_test_cases_endpoint_logs_results(test_client, monkeypatch):
    """Evaluation should parse the payload, call the evaluator, and log to MLflow when requested."""
    payload = json.dumps([
        {
            "query": "What is TAP?",
            "generated_answer": "A Trust & Assurance Platform.",
            "ground_truth": "It is Certus TAP.",
            "context": "Certus TAP description.",
        }
    ])
    evaluation_results = [
        {
            "query": "What is TAP?",
            "context": "Certus TAP description.",
            "ground_truth": "It is Certus TAP.",
            "generated_answer": "A Trust & Assurance Platform.",
            "scores": {"correctness": {"score": 0.95, "reason": "Accurate answer"}},
        }
    ]
    log_calls: list[dict] = []

    monkeypatch.setattr("certus_ask.routers.evaluation.evaluate_test_cases", lambda cases: evaluation_results)
    monkeypatch.setattr("certus_ask.routers.evaluation.log_to_mlflow", lambda results: log_calls.append(results))

    response = test_client.post(
        "/v1/evaluation/evaluate-test-cases",
        params={"log_to_mlflow_flag": "true"},
        files={"file": ("cases.json", payload.encode("utf-8"), "application/json")},
    )

    assert response.status_code == 200
    assert response.json()["evaluation_results"] == evaluation_results
    assert log_calls == [evaluation_results]


def test_evaluate_test_cases_endpoint_rejects_invalid_json(test_client):
    """Invalid JSON should trigger a 400 before evaluation occurs."""
    response = test_client.post(
        "/v1/evaluation/evaluate-test-cases",
        files={"file": ("cases.json", b"not-json", "application/json")},
    )

    assert response.status_code == 400
    assert "valid JSON" in response.json()["detail"]


def test_generate_evaluate_endpoint_runs_pipeline(test_client, monkeypatch):
    """Combined generation + evaluation should return evaluation payload and log when requested."""
    documents = [{"content": "doc"}]
    test_cases = [{"query": "Q1"}]
    evaluation_results = [
        {
            "query": "Q1",
            "context": "doc",
            "ground_truth": "Answer",
            "generated_answer": "Response",
            "scores": {"correctness": {"score": 0.9, "reason": "Good"}},
        }
    ]
    log_calls = []

    monkeypatch.setattr("certus_ask.routers.evaluation.retrieve_documents", lambda *args, **kwargs: documents)
    monkeypatch.setattr("certus_ask.routers.evaluation.generate_test_cases", lambda *args, **kwargs: test_cases)
    monkeypatch.setattr("certus_ask.routers.evaluation.evaluate_test_cases", lambda cases: evaluation_results)
    monkeypatch.setattr("certus_ask.routers.evaluation.log_to_mlflow", lambda results: log_calls.append(results))

    response = test_client.post(
        "/v1/evaluation/generate-evaluate",
        params={
            "index_name": "demo",
            "num_documents": 1,
            "num_questions_per_doc": 1,
            "total_questions": 1,
            "log_to_mlflow_flag": "true",
        },
    )

    assert response.status_code == 200
    assert response.json()["evaluation_results"] == evaluation_results
    assert log_calls == [evaluation_results]
