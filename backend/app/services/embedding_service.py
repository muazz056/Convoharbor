from flask import current_app
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings


def generate_embeddings_for_texts(texts: list[str], api_keys: dict = None) -> dict:
    results = {
        "openai_embeddings": None,
        "gemini_embeddings": None,
        "errors": {}
    }

    api_keys = api_keys or {}

    openai_api_key = api_keys.get('openai') or current_app.config['OPENAI_API_KEY']
    if openai_api_key and not openai_api_key.startswith('your-'):
        try:
            openai_embedder = OpenAIEmbeddings(
                model="text-embedding-3-large",
                api_key=openai_api_key
            )
            results["openai_embeddings"] = openai_embedder.embed_documents(texts)
            current_app.logger.info(f"OpenAI embeddings generated: {len(results['openai_embeddings'])} vectors")
        except Exception as e:
            current_app.logger.error(f"OpenAI embeddings failed: {str(e)}")
            results["errors"]["openai"] = f"Failed to generate OpenAI embeddings: {str(e)}"
    else:
        current_app.logger.warning("OpenAI API key not configured")
        results["errors"]["openai"] = "OpenAI API key not provided or is placeholder."

    gemini_api_key = api_keys.get('gemini') or current_app.config['GEMINI_API_KEY']
    if gemini_api_key and not gemini_api_key.startswith('your-'):
        try:
            gemini_embedder = GoogleGenerativeAIEmbeddings(
                model=current_app.config['GEMINI_EMBEDDING_MODEL'],
                google_api_key=gemini_api_key
            )
            results["gemini_embeddings"] = gemini_embedder.embed_documents(texts)
        except Exception as e:
            results["errors"]["gemini"] = f"Failed to generate Gemini embeddings: {str(e)}"
    else:
        results["errors"]["gemini"] = "Gemini API key not provided or is placeholder."

    if results["openai_embeddings"] is None and results["gemini_embeddings"] is None:
        current_app.logger.error("No embedding providers available. Configure OpenAI or Gemini API keys.")

    return results
