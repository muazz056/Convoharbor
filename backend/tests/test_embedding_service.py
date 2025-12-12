"""
Tests for the embedding service.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.embedding_service import EmbeddingService

def test_init_local_model(embedding_service):
    """Test local model initialization."""
    assert embedding_service.local_model is not None

def test_init_openai_client(embedding_service):
    """Test OpenAI client initialization."""
    with patch('openai.Embedding') as mock_embedding:
        embedding_service._init_openai_client()
        assert embedding_service.openai_client is not None

def test_get_embeddings_local(embedding_service):
    """Test getting embeddings using local model."""
    texts = ["test text 1", "test text 2"]
    
    # Mock local model
    embedding_service.local_model = MagicMock()
    embedding_service.local_model.encode.return_value = [[0.1] * 384, [0.2] * 384]
    
    embeddings = embedding_service.get_embeddings(texts)
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 384
    embedding_service.local_model.encode.assert_called_once_with(texts)

def test_get_embeddings_openai(embedding_service):
    """Test getting embeddings using OpenAI."""
    texts = ["test text 1", "test text 2"]
    mock_response = {
        "data": [
            {"embedding": [0.1] * 1536},
            {"embedding": [0.2] * 1536}
        ]
    }
    
    with patch('openai.Embedding.create') as mock_create:
        mock_create.return_value = mock_response
        embedding_service.use_local = False  # Force OpenAI mode
        
        embeddings = embedding_service.get_embeddings(texts)
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 1536
        mock_create.assert_called_once()

def test_get_embeddings_batch(embedding_service):
    """Test getting embeddings in batches."""
    texts = [f"test text {i}" for i in range(10)]  # 10 texts
    
    # Mock local model
    embedding_service.local_model = MagicMock()
    embedding_service.local_model.encode.return_value = [[0.1] * 384] * 5  # Return 5 embeddings at a time
    
    embeddings = embedding_service.get_embeddings(texts, batch_size=5)
    assert len(embeddings) == 10
    assert embedding_service.local_model.encode.call_count == 2  # Called twice with batch_size=5

def test_get_embeddings_error_handling(embedding_service):
    """Test error handling in get_embeddings."""
    texts = ["test text"]
    
    # Test local model error
    embedding_service.local_model = MagicMock()
    embedding_service.local_model.encode.side_effect = Exception("Model error")
    
    with pytest.raises(Exception):
        embedding_service.get_embeddings(texts)
    
    # Test OpenAI error
    with patch('openai.Embedding.create') as mock_create:
        mock_create.side_effect = Exception("API error")
        embedding_service.use_local = False  # Force OpenAI mode
        
        with pytest.raises(Exception):
            embedding_service.get_embeddings(texts)

def test_get_single_embedding(embedding_service):
    """Test getting a single embedding."""
    text = "test text"
    
    # Mock local model
    embedding_service.local_model = MagicMock()
    embedding_service.local_model.encode.return_value = [[0.1] * 384]
    
    embedding = embedding_service.get_single_embedding(text)
    assert len(embedding) == 384
    embedding_service.local_model.encode.assert_called_once_with([text])

def test_embedding_dimension(embedding_service):
    """Test embedding dimension consistency."""
    text = "test text"
    
    # Test local model dimension
    embedding_service.local_model = MagicMock()
    embedding_service.local_model.encode.return_value = [[0.1] * 384]
    local_embedding = embedding_service.get_single_embedding(text)
    assert len(local_embedding) == 384
    
    # Test OpenAI dimension
    mock_response = {
        "data": [
            {"embedding": [0.1] * 1536}
        ]
    }
    with patch('openai.Embedding.create') as mock_create:
        mock_create.return_value = mock_response
        embedding_service.use_local = False  # Force OpenAI mode
        
        openai_embedding = embedding_service.get_single_embedding(text)
        assert len(openai_embedding) == 1536
