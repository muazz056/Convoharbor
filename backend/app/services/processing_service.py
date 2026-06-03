from flask import current_app
from langchain.text_splitter import RecursiveCharacterTextSplitter


def process_documents_into_chunks(documents: list, source_name: str, doc_id: str, api_keys: dict = None) -> list:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=current_app.config['CHUNK_SIZE'],
        chunk_overlap=current_app.config['CHUNK_OVERLAP']
    )
    chunks = text_splitter.split_documents(documents)

    for chunk in chunks:
        chunk.metadata.update({
            'doc_id': doc_id,
            'source': source_name,
            'language': 'und'
        })

    return chunks
