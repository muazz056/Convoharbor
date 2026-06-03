from flask import current_app
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings


def generate_embeddings_for_texts(texts: list[str]) -> dict:
    provider = current_app.config.get('EMBEDDINGS_SERVICE_USE', 'openai')

    if provider == 'gemini':
        api_key = current_app.config.get('GEMINI_API_KEY', '')
        if not api_key or api_key.startswith('your-'):
            current_app.logger.error("GEMINI_API_KEY not configured for embeddings")
            return {"embeddings": None, "provider": "gemini", "error": "GEMINI_API_KEY not configured"}
        try:
            model_names = [
                current_app.config.get('GEMINI_EMBEDDING_MODEL', 'models/embedding-001'),
                'models/text-embedding-004',
                'models/gemini-embedding-exp-03-07',
                'models/embedding-001',
            ]
            last_error = None
            for model_name in model_names:
                try:
                    embedder = GoogleGenerativeAIEmbeddings(
                        model=model_name,
                        google_api_key=api_key
                    )
                    embeddings = embedder.embed_documents(texts)
                    current_app.logger.info(f"Gemini embeddings generated: {len(embeddings)} vectors (model={model_name})")
                    return {"embeddings": embeddings, "provider": "gemini"}
                except Exception as e:
                    last_error = e
                    continue
            raise last_error or Exception("No Gemini embedding models worked")
        except Exception as e:
            current_app.logger.error(f"Gemini embeddings failed: {str(e)}")
            return {"embeddings": None, "provider": "gemini", "error": str(e)}

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
