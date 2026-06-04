import time

from flask import current_app
from langchain_openai import OpenAIEmbeddings


def _gemini_embed(texts: list[str], api_key: str, model_name: str, api_endpoint: str, max_retries: int = 3, base_delay: float = 2.0) -> list[list[float]]:
    """Embed texts using Google Gemini v1 API (not v1beta)."""
    from google.ai.generativelanguage_v1 import GenerativeServiceClient
    from google.ai.generativelanguage_v1.types import (
        BatchEmbedContentsRequest,
        EmbedContentRequest,
    )
    from google.api_core import client_options as client_options_lib
    from google.api_core.exceptions import ResourceExhausted

    client = GenerativeServiceClient(
        client_options=client_options_lib.ClientOptions(
            api_key=api_key,
            api_endpoint=api_endpoint,
        ),
    )
    requests = [
        EmbedContentRequest(
            model=model_name,
            content={"parts": [{"text": t}]},
            task_type="RETRIEVAL_DOCUMENT",
        )
        for t in texts
    ]
    batch_request = BatchEmbedContentsRequest(requests=requests, model=model_name)

    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            response = client.batch_embed_contents(batch_request)
            return [list(e.values) for e in response.embeddings]
        except ResourceExhausted as e:
            last_exception = e
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                current_app.logger.warning(
                    f"Gemini rate limited (429) on {model_name}, retrying in {delay:.0f}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delay)
                continue
            raise
    raise last_exception or RuntimeError("Gemini embedding failed")


def generate_embeddings_for_texts(texts: list[str]) -> dict:
    provider = current_app.config.get('EMBEDDINGS_SERVICE_USE', 'openai')

    if provider == 'gemini':
        api_key = current_app.config.get('GEMINI_API_KEY', '')
        if not api_key or api_key.startswith('your-'):
            current_app.logger.error("GEMINI_API_KEY not configured for embeddings")
            return {"embeddings": None, "provider": "gemini", "error": "GEMINI_API_KEY not configured"}
        api_endpoint = current_app.config.get('GEMINI_API_BASE_URL', 'generativelanguage.googleapis.com')
        max_retries = current_app.config.get('EMBEDDING_MAX_RETRIES', 3)
        base_delay = current_app.config.get('EMBEDDING_RETRY_BASE_DELAY', 2.0)
        model_names = list(dict.fromkeys([
            current_app.config.get('GEMINI_EMBEDDING_MODEL', 'models/gemini-embedding-2'),
            current_app.config.get('GEMINI_EMBEDDING_FALLBACK_MODEL', 'models/gemini-embedding-001'),
        ]))
        for model_name in model_names:
            try:
                embeddings = _gemini_embed(texts, api_key, model_name, api_endpoint, max_retries, base_delay)
                current_app.logger.info(f"Gemini embeddings generated: {len(embeddings)} vectors (model={model_name})")
                return {"embeddings": embeddings, "provider": "gemini"}
            except Exception as e:
                current_app.logger.warning(f"Gemini embedding model {model_name} failed: {e}")
                continue
        current_app.logger.error("All Gemini embedding models failed")
        return {"embeddings": None, "provider": "gemini", "error": "All Gemini embedding models failed"}

    # Default: openai
    api_key = current_app.config.get('OPENAI_API_KEY', '')
    if not api_key or api_key.startswith('your-'):
        current_app.logger.error("OPENAI_API_KEY not configured for embeddings")
        return {"embeddings": None, "provider": "openai", "error": "OPENAI_API_KEY not configured"}
    try:
        model_name = current_app.config.get('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-large')
        embedder = OpenAIEmbeddings(
            model=model_name,
            api_key=api_key
        )
        embeddings = embedder.embed_documents(texts)
        current_app.logger.info(f"OpenAI embeddings generated: {len(embeddings)} vectors")
        return {"embeddings": embeddings, "provider": "openai"}
    except Exception as e:
        current_app.logger.error(f"OpenAI embeddings failed: {str(e)}")
        return {"embeddings": None, "provider": "openai", "error": str(e)}
