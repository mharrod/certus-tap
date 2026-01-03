from pydantic import BaseModel, Field


class MetricScore(BaseModel):
    score: float = Field(..., description="Metric score between 0 and 1.")
    reason: str = Field(..., description="Explanation returned by the evaluation metric.")


class EvaluationResult(BaseModel):
    query: str
    context: str
    ground_truth: str
    generated_answer: str
    scores: dict[str, MetricScore]


class EvaluationResponse(BaseModel):
    evaluation_results: list[EvaluationResult]
