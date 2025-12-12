# chat_project/app/services/document_service.py

import os
import uuid
from flask import current_app
from werkzeug.utils import secure_filename
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader

# Import the new cleaner and the processing service
from . import processing_service
from . import text_cleaner_service # <-- NEW IMPORT

LOADER_MAPPING = {
    ".pdf": PyPDFLoader, ".txt": TextLoader, ".docx": Docx2txtLoader
}

def process_uploaded_files(files):
    """Processes uploaded files using the shared processing service."""
    successful_chunks = []
    failed_files = []

    for file in files:
        filename = secure_filename(file.filename)
        temp_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        try:
            doc_id = str(uuid.uuid4())
            file.save(temp_filepath)
            
            ext = os.path.splitext(filename)[1]
            if ext not in LOADER_MAPPING:
                raise ValueError(f"Unsupported file type: {ext}")
            
            loader = LOADER_MAPPING[ext](temp_filepath)
            documents = loader.load()

            # --- NEW: APPLY THE CLEANING STEP ---
            current_app.logger.info(f"Cleaning content for {filename}...")
            for doc in documents:
                doc.page_content = text_cleaner_service.clean_extracted_text(doc.page_content)
            # --- END OF CLEANING ---

            processed_chunks = processing_service.process_documents_into_chunks(
                documents=documents,
                source_name=filename,
                doc_id=doc_id
            )
            successful_chunks.extend(processed_chunks)
            
            os.remove(temp_filepath)
        except Exception as e:
            failed_files.append({"filename": filename, "error": str(e)})
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)

    return {"successful_chunks": successful_chunks, "failed_files": failed_files}