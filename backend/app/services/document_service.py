import os
import uuid
import tempfile
from flask import current_app
from werkzeug.utils import secure_filename
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader

from . import processing_service
from . import text_cleaner_service

LOADER_MAPPING = {
    ".pdf": PyPDFLoader, ".txt": TextLoader, ".docx": Docx2txtLoader
}


def process_uploaded_files(files, api_keys=None):
    successful_chunks = []
    failed_files = []
    file_doc_ids = {}

    cloudinary_service = getattr(current_app, 'cloudinary_service', None)

    for file in files:
        filename = secure_filename(file.filename)
        temp_dir = tempfile.mkdtemp()
        temp_filepath = os.path.join(temp_dir, filename)

        try:
            doc_id = str(uuid.uuid4())
            file_doc_ids[filename] = doc_id
            file.save(temp_filepath)

            if cloudinary_service:
                try:
                    cloudinary_result = cloudinary_service.upload_temp_file(temp_filepath)
                    current_app.logger.info(f"Uploaded {filename} to Cloudinary: {cloudinary_result['public_id']}")
                except Exception as ce:
                    current_app.logger.warning(f"Cloudinary upload failed for {filename}, using local: {ce}")
                    cloudinary_result = None
            else:
                cloudinary_result = None

            ext = os.path.splitext(filename)[1]
            if ext not in LOADER_MAPPING:
                raise ValueError(f"Unsupported file type: {ext}")

            loader = LOADER_MAPPING[ext](temp_filepath)
            documents = loader.load()

            current_app.logger.info(f"Cleaning content for {filename}...")
            for doc in documents:
                doc.page_content = text_cleaner_service.clean_extracted_text(doc.page_content)

            processed_chunks = processing_service.process_documents_into_chunks(
                documents=documents,
                source_name=filename,
                doc_id=doc_id,
                api_keys=api_keys
            )
            successful_chunks.extend(processed_chunks)

            os.remove(temp_filepath)
            os.rmdir(temp_dir)

            if cloudinary_service and cloudinary_result:
                try:
                    cloudinary_service.delete_file(cloudinary_result['public_id'])
                    current_app.logger.info(f"Deleted {filename} from Cloudinary after processing")
                except Exception as ce:
                    current_app.logger.warning(f"Failed to delete {filename} from Cloudinary: {ce}")

        except Exception as e:
            failed_files.append({"filename": filename, "error": str(e)})
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

    return {"successful_chunks": successful_chunks, "failed_files": failed_files, "doc_ids": file_doc_ids}
