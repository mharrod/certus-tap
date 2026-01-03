from haystack import Pipeline
from haystack.components.builders import PromptBuilder
from haystack.components.embedders import SentenceTransformersTextEmbedder

try:
    from opensearch_haystack.document_stores import OpenSearchDocumentStore  # type: ignore[import]
    from opensearch_haystack.retrievers import OpenSearchEmbeddingRetriever  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - compatibility fallback
    from haystack_integrations.components.retrievers.opensearch import (  # type: ignore[import]
        OpenSearchEmbeddingRetriever,
    )
    from haystack_integrations.document_stores.opensearch import OpenSearchDocumentStore  # type: ignore[import]

try:
    from ollama_haystack import OllamaGenerator  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - compatibility fallback
    try:
        from ollama_haystack.generator import OllamaGenerator  # type: ignore[import]
    except ModuleNotFoundError:
        from haystack_integrations.components.generators.ollama import OllamaGenerator  # type: ignore[import]

from certus_ask.core.config import settings

RAG_PROMPT_TEMPLATE = """
You are a defensive security assistant helping engineers interpret scan output.
Use only the supplied context, which already scopes the question to approved
defensive workflows. Summaries should be terse but specific—call out rule IDs,
locations, and severities when present. If the context does not mention the
requested topic, reply with "No relevant findings in the current workspace." Do
not invent data or lean on general security knowledge.

Context:
{% for document in documents %}
{{ document.content }}
{% endfor %}

Question: {{ query }}
"""


def create_rag_pipeline(document_store: OpenSearchDocumentStore) -> Pipeline:
    pipeline = Pipeline()
    pipeline.add_component("embedder", SentenceTransformersTextEmbedder(model="sentence-transformers/all-MiniLM-L6-v2"))
    pipeline.add_component("retriever", OpenSearchEmbeddingRetriever(document_store=document_store))
    pipeline.add_component(
        "prompt_builder",
        PromptBuilder(template=RAG_PROMPT_TEMPLATE, required_variables=["documents", "query"]),
    )
    pipeline.add_component("llm", OllamaGenerator(model=settings.llm_model, url=settings.llm_url))

    pipeline.connect("embedder", "retriever")
    pipeline.connect("retriever", "prompt_builder.documents")
    pipeline.connect("prompt_builder", "llm")

    return pipeline
