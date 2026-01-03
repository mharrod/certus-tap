from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str = Field(..., description="Natural language question to answer using the RAG pipeline.")
