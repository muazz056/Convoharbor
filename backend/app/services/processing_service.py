from flask import current_app
from langchain.text_splitter import RecursiveCharacterTextSplitter

from . import language_service

def process_documents_into_chunks(documents: list, source_name: str, doc_id: str) -> list:
    """
    A shared function to take loaded LangChain documents and process them.
    - Splits documents into chunks.
    - Detects language of the content.
    - Adds consistent metadata.
    """
    # 1. Split the document into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=current_app.config['CHUNK_SIZE'],
        chunk_overlap=current_app.config['CHUNK_OVERLAP']
    )
    chunks = text_splitter.split_documents(documents)

    # 2. Detect language once from a sample of the content
    #    This is more efficient than detecting for every chunk.
    content_sample = " ".join(doc.page_content for doc in documents[:2])[:1000]
    detected_lang = language_service.detect_language_with_llm(content_sample)

    # 3. Add consistent metadata to all chunks
    for chunk in chunks:
        chunk.metadata.update({
            'doc_id': doc_id,
            'source': source_name,
            'language': detected_lang
        })
    
    return chunks