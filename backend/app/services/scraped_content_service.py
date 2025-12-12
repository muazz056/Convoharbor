# app/services/scraped_content_service.py

import uuid
from flask import current_app
from langchain_core.documents import Document

# We will reuse our existing processing service
from . import processing_service

def process_scraped_data(source_url: str, content: str) -> list:
    """
    Processes pre-scraped text content from a URL.
    - Creates a LangChain Document object.
    - Uses the shared processing service to chunk and add metadata.

    Args:
        source_url: The original URL the content was scraped from.
        content: The raw text content scraped from the page.

    Returns:
        A list of processed LangChain Document chunks ready for embedding.
    """
    if not source_url or not content:
        raise ValueError("Both source_url and content must be provided.")

    current_app.logger.info(f"Processing scraped content from URL: {source_url}")
    
    # 1. Create a LangChain Document from the raw text.
    # We use the URL as the primary metadata source.
    document = Document(
        page_content=content,
        metadata={"source": source_url}
    )
    
    # 2. Generate a unique ID for this ingestion batch.
    doc_id = str(uuid.uuid4())

    # 3. Use the existing, powerful processing service to handle chunking and language detection.
    # This is great code reuse!
    processed_chunks = processing_service.process_documents_into_chunks(
        documents=[document], # We pass it as a list of one
        source_name=source_url,
        doc_id=doc_id
    )

    current_app.logger.info(f"Successfully processed scraped content into {len(processed_chunks)} chunks.")
    return processed_chunks