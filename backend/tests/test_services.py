# tests/test_services.py

import io
from unittest.mock import patch, MagicMock
from pytest_mock import mocker
from werkzeug.datastructures import FileStorage
from langchain_core.documents import Document

from app.services import document_service, embedding_service, scraped_content_service

def create_mock_file(filename="test.txt", content=b"dummy content"):
    return FileStorage(stream=io.BytesIO(content), filename=filename)

class TestDocumentService:
    """Tests for the document processing service."""

    @patch('app.services.text_cleaner_service.clean_extracted_text', side_effect=lambda x: x)
    @patch('app.services.processing_service.language_service.detect_language_with_llm', return_value='en')
    # We don't need to patch the dictionary here anymore if we do it inside with mocker.
    def test_process_single_valid_file(self, mock_detect_lang, mock_cleaner, app, mocker): # <-- ADD mocker
        # ARRANGE
        mock_loader_instance = MagicMock()
        mock_loader_instance.load.return_value = [Document(page_content="English content.")]
        mock_loader_class = MagicMock(return_value=mock_loader_instance)
        
        # --- CORRECT FIX ---
        mocker.patch.dict(document_service.LOADER_MAPPING, {'.pdf': mock_loader_class})
        
        mock_file = create_mock_file("test_en.pdf")
        
        # ACT
        results = document_service.process_uploaded_files([mock_file])

        # ASSERT
        assert not results["failed_files"]
        assert len(results["successful_chunks"]) == 1
        assert results["successful_chunks"][0].metadata['source'] == 'test_en.pdf'

    def test_process_unsupported_file_type(self, app):
        files = [create_mock_file("image.jpg")]
        results = document_service.process_uploaded_files(files)
        assert len(results["failed_files"]) == 1
        assert "Unsupported file type: .jpg" in results["failed_files"][0]['error']

class TestEmbeddingService:
    """Tests for the embedding generation service."""
    
    @patch('app.services.embedding_service.OpenAIEmbeddings')
    def test_generate_embeddings_openai(self, mock_openai_embed, app):
        mock_openai_embed.return_value.embed_documents.return_value = [[0.1, 0.2]]
        
        results = embedding_service.generate_embeddings_for_texts(["test text"])
        
        assert results.get("error") is None
        assert results["embeddings"] == [[0.1, 0.2]]
        assert results["provider"] == "openai"

class TestScrapedContentService:
    """Tests for the scraped content processing service."""
    
    @patch('app.services.scraped_content_service.processing_service.process_documents_into_chunks')
    def test_process_scraped_data_successfully(self, mock_process_chunks, app):
        """
        GIVEN valid scraped content and a URL,
        WHEN process_scraped_data is called,
        THEN it should call the chunking service with the correct document.
        """
        # ARRANGE
        source_url = "https://example.com"
        content = "This is the scraped content."
        # We don't care about the return value for this test, only that it's called.
        mock_process_chunks.return_value = []

        # ACT
        scraped_content_service.process_scraped_data(source_url, content)

        # ASSERT
        # This is the most important check: was our mocked function called at all?
        mock_process_chunks.assert_called_once()

        # For debugging, let's see what it was called with.
        # This will print to the pytest output if the test fails.
        print("Mock process_documents_into_chunks call_args:", mock_process_chunks.call_args)
        
        # Now, a more robust check of the arguments
        args, kwargs = mock_process_chunks.call_args
        
        # Check the 'documents' keyword argument
        passed_documents = kwargs.get('documents')
        assert passed_documents is not None
        assert len(passed_documents) == 1
        assert isinstance(passed_documents[0], Document)
        assert passed_documents[0].page_content == content
        assert passed_documents[0].metadata['source'] == source_url