"""
Tests for the vector service with pgvector.
"""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from app.services.vector_service import VectorService


def test_init(vector_service):
    """Test that VectorService can be instantiated."""
    assert vector_service is not None


@patch('app.services.vector_service.DocumentEmbedding.query')
def test_upsert(mock_query, vector_service):
    """Test upserting chunks with embeddings."""
    mock_filter = MagicMock()
    mock_query.filter_by.return_value = mock_filter
    mock_filter.first.return_value = None

    chunks = [{
        "embeddings": {"openai": [0.1] * 3072},
        "metadata": {"doc_id": "test-doc", "source": "test-source", "chatbot_id": 1},
        "page_content": "Test content"
    }]

    with patch.object(vector_service, '_invalidate_vector_cache'):
        with patch('app.services.vector_service.db') as mock_db:
            result = vector_service.upsert(chunks, provider='openai')

    assert result["upserted_count"] == 1


@patch('app.services.vector_service.db.session')
@patch('app.services.vector_service.DocumentEmbedding')
def test_query(mock_model_class, mock_db_session, vector_service):
    """Test querying similar vectors."""
    mock_row = MagicMock()
    mock_row.id = 1
    mock_row.vector_id = "test-vec"
    mock_row.doc_id = "test-doc"
    mock_row.chunk_index = 0
    mock_row.page_content = "Test content"
    mock_row.source = "test-source"
    mock_row.chatbot_id = 1
    mock_row.tenant_id = 1
    mock_row.provider = "openai"
    mock_row.meta_data = {"doc_id": "test-doc", "source": "test-source"}
    mock_row.embedding_openai = [0.1] * 3072
    mock_row.embedding_gemini = None

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = [(mock_row, 0.05)]

    results = vector_service.query([0.1] * 3072, top_k=5)

    assert len(results) == 1
    assert results[0]["page_content"] == "Test content"
    assert results[0]["metadata"]["source"] == "test-source"
    assert results[0]["score"] == pytest.approx(0.95, abs=0.01)


@patch('app.services.vector_service.db.session')
@patch('app.services.vector_service.DocumentEmbedding')
def test_add_vectors(mock_model_class, mock_db_session, vector_service):
    """Test adding vectors."""
    mock_query = MagicMock()
    mock_model_class.query = mock_query
    mock_filter = MagicMock()
    mock_query.filter_by.return_value = mock_filter
    mock_filter.first.return_value = None

    vectors = [{
        "id": "test-vec",
        "values": [0.1] * 3072,
        "metadata": {
            "doc_id": "test-doc",
            "source": "test-source",
            "page_content": "Test content",
            "chunk_index": 0
        }
    }]

    with patch.object(vector_service, '_invalidate_vector_cache'):
        result = vector_service.add_vectors(vectors)

    assert result["upserted_count"] == 1


def test_delete_by_source(vector_service):
    """Test deleting vectors by source."""
    mock_record = MagicMock()
    mock_record.id = 1

    with patch('app.services.vector_service.DocumentEmbedding.query') as mock_query:
        mock_query.filter_by.return_value.all.return_value = [mock_record]
        mock_query.filter.return_value.delete.return_value = 1

        with patch.object(vector_service, '_invalidate_vector_cache'):
            with patch('app.services.vector_service.db') as mock_db:
                result = vector_service.delete_by_source("test-source")

    assert result["deleted_count"] == 1
    assert result["source"] == "test-source"


def test_get_chunks_by_doc_id(vector_service):
    """Test getting chunks by document ID."""
    mock_record = MagicMock()
    mock_record.id = 1
    mock_record.vector_id = "test-vec"
    mock_record.doc_id = "test-doc"
    mock_record.chunk_index = 0
    mock_record.page_content = "Test content"
    mock_record.source = "test-source"
    mock_record.chatbot_id = 1
    mock_record.tenant_id = 1
    mock_record.meta_data = {"source": "test-source"}
    mock_record.embedding_openai = [0.1] * 3072
    mock_record.embedding_gemini = None

    with patch('app.services.vector_service.DocumentEmbedding.query') as mock_query:
        mock_query.filter_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = [mock_record]

        chunks = vector_service.get_chunks_by_doc_id("test-doc")

    assert len(chunks) == 1
    assert chunks[0]["page_content"] == "Test content"
    assert "openai" in chunks[0]["embeddings"]


def test_vector_count(vector_service):
    """Test vector count."""
    with patch('app.services.vector_service.DocumentEmbedding.query') as mock_query:
        mock_query.count.return_value = 5
        count = vector_service.vector_count()
    assert count == 5


def test_delete_by_source_no_vectors(vector_service):
    """Test delete_by_source with no matching vectors."""
    with patch('app.services.vector_service.DocumentEmbedding.query') as mock_query:
        mock_query.filter_by.return_value.all.return_value = []

        result = vector_service.delete_by_source("nonexistent-source")

    assert result["deleted_count"] == 0
    assert "No vectors found" in result["message"]


def test_search_similar_no_embedding_service(vector_service):
    """Test search_similar when embedding service is not available."""
    with patch('flask.current_app') as mock_app:
        mock_app.embedding_service = None
        mock_app.redis_service = None
        del mock_app.embedding_service

        results = vector_service.search_similar("test query")
        assert results == []


def test_query_empty_embedding(vector_service):
    """Test query with empty embedding raises error."""
    with pytest.raises(ValueError, match="cannot be empty"):
        vector_service.query([], top_k=5)


def test_delete_by_source_empty(vector_service):
    """Test delete_by_source with empty source raises error."""
    with pytest.raises(ValueError, match="cannot be empty"):
        vector_service.delete_by_source("")
