"""
Tests for the vector service.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.vector_service import VectorService

def test_init_local_vector_db(vector_service):
    """Test local vector database initialization."""
    assert vector_service.local_model is not None
    assert vector_service.local_index is not None

def test_init_pinecone(vector_service):
    """Test Pinecone initialization."""
    with patch('pinecone.init') as mock_init:
        with patch('pinecone.Index') as mock_index:
            vector_service._init_pinecone()
            mock_init.assert_called_once()
            mock_index.assert_called_once()

def test_search_similar_local(vector_service, mock_vector_results):
    """Test searching similar documents in local mode."""
    query = "test query"
    k = 3
    
    # Mock local model and index
    vector_service.local_model = MagicMock()
    vector_service.local_model.encode.return_value = [0.1] * 384  # Mock embedding
    vector_service.local_index = MagicMock()
    vector_service.local_index.search.return_value = mock_vector_results
    
    results = vector_service.search_similar(query, k=k)
    assert len(results) == 1
    assert results[0]["score"] == 0.95
    assert results[0]["metadata"]["source"] == "test-source"

def test_search_similar_pinecone(vector_service):
    """Test searching similar documents in Pinecone."""
    query = "test query"
    k = 3
    
    # Mock Pinecone index
    mock_results = {
        "matches": [{
            "id": "test-id",
            "score": 0.95,
            "metadata": {
                "source": "test-source",
                "page_content": "Test content"
            }
        }]
    }
    
    with patch.object(vector_service, '_get_pinecone_index') as mock_get_index:
        mock_index = MagicMock()
        mock_index.query.return_value = mock_results
        mock_get_index.return_value = mock_index
        
        vector_service.use_local = False  # Force Pinecone mode
        results = vector_service.search_similar(query, k=k)
        
        assert len(results) == 1
        assert results[0]["score"] == 0.95
        assert results[0]["metadata"]["source"] == "test-source"

def test_add_texts_local(vector_service):
    """Test adding texts to local vector store."""
    texts = ["text1", "text2"]
    metadatas = [{"source": "source1"}, {"source": "source2"}]
    
    # Mock local model and index
    vector_service.local_model = MagicMock()
    vector_service.local_model.encode.return_value = [[0.1] * 384, [0.2] * 384]
    vector_service.local_index = MagicMock()
    
    vector_service.add_texts(texts, metadatas=metadatas)
    vector_service.local_index.add.assert_called_once()

def test_add_texts_pinecone(vector_service):
    """Test adding texts to Pinecone."""
    texts = ["text1", "text2"]
    metadatas = [{"source": "source1"}, {"source": "source2"}]
    
    with patch.object(vector_service, '_get_pinecone_index') as mock_get_index:
        mock_index = MagicMock()
        mock_get_index.return_value = mock_index
        
        vector_service.use_local = False  # Force Pinecone mode
        vector_service.add_texts(texts, metadatas=metadatas)
        
        mock_index.upsert.assert_called_once()

def test_delete_by_source_local(vector_service):
    """Test deleting documents by source from local store."""
    source = "test-source"
    
    # Mock local index
    vector_service.local_index = MagicMock()
    vector_service.delete_by_source(source)
    vector_service.local_index.delete.assert_called_once()

def test_delete_by_source_pinecone(vector_service):
    """Test deleting documents by source from Pinecone."""
    source = "test-source"
    
    with patch.object(vector_service, '_get_pinecone_index') as mock_get_index:
        mock_index = MagicMock()
        mock_get_index.return_value = mock_index
        
        vector_service.use_local = False  # Force Pinecone mode
        vector_service.delete_by_source(source)
        
        mock_index.delete.assert_called_once()
