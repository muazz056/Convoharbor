# chat_project/app/services/hyde_service.py

from flask import current_app

def generate_hypothetical_answer(query: str, original_lang: str):
    """
    Generates a hypothetical answer to a user's query to improve retrieval accuracy.

    Args:
        query (str): The user's query (already translated to English).
        original_lang (str): The user's original language.

    Returns:
        A hypothetical document/answer to be used for embedding.
    """
    if not current_app.llm_service:
        current_app.logger.error("HyDE service called, but LLM service is not available.")
        return query # Fallback to the original query

    # We use the 'openai' provider by default for this internal task as it's typically fast and reliable.
    # We could make this configurable.
    provider = 'openai' 
    llm = current_app.llm_service.llm_providers.get(provider)
    
    if not llm:
        current_app.logger.error(f"HyDE service: '{provider}' provider not found.")
        return query # Fallback

    # This prompt is key. It asks the model to generate a document, not just a conversational answer.
    prompt = (
        f"A user speaking '{original_lang}' asked the following question: '{query}'.\n"
        "Please write a short, one-paragraph, fact-based document in English that answers this question. "
        "This document will be used for a vector search. Do not say 'As an AI...' or 'Here is a document...'. "
        "Just write the document."
    )

    try:
        response = llm.invoke(prompt)
        hypothetical_doc = response.content
        current_app.logger.info(f"Generated HyDE document: {hypothetical_doc}")
        # We combine the original query with the hypothetical doc for a robust search vector.
        return f"{query}\n\n{hypothetical_doc}"
    except Exception as e:
        current_app.logger.error(f"Error generating HyDE document: {e}")
        return query # Fallback to the original query if HyDE fails