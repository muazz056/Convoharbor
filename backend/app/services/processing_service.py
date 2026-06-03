from flask import current_app
from langchain.text_splitter import RecursiveCharacterTextSplitter

from . import language_service

def process_documents_into_chunks(documents: list, source_name: str, doc_id: str, api_keys: dict = None) -> list:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=current_app.config['CHUNK_SIZE'],
        chunk_overlap=current_app.config['CHUNK_OVERLAP']
    )
    chunks = text_splitter.split_documents(documents)

    content_sample = " ".join(doc.page_content for doc in documents[:2])[:1000]
    gemini_key = (api_keys or {}).get('gemini')
    detected_lang = language_service.detect_language_with_llm(content_sample, api_key=gemini_key)

    for chunk in chunks:
        chunk.metadata.update({
            'doc_id': doc_id,
            'source': source_name,
            'language': detected_lang
        })

    return chunks
