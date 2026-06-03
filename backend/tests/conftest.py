"""
Global pytest fixtures and configuration.
"""
import pytest
from unittest.mock import MagicMock, patch
from flask import Flask
from app import db
from app.config import TestingConfig


@pytest.fixture
def app():
    """Create and configure a test Flask application instance."""
    app = Flask(__name__)
    app.config.from_object(TestingConfig)
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'JWT_SECRET_KEY': 'test-secret-key',
        'OPENAI_API_KEY': 'test-openai-key',
        'GOOGLE_API_KEY': 'test-google-key',
    })

    db.init_app(app)

    with app.app_context():
        db.create_all()
        from app.models.document_embedding import DocumentEmbedding

    return app


@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return app.test_client()


@pytest.fixture
def auth_headers():
    """Create authentication headers for protected endpoints."""
    return {
        'Authorization': 'Bearer test-token',
        'Content-Type': 'application/json'
    }


@pytest.fixture
def vector_service(app):
    """Create a VectorService instance with mocked DB."""
    from app.services.vector_service import VectorService
    with patch('app.services.vector_service.DocumentEmbedding'):
        with patch('app.services.vector_service.PGVECTOR_AVAILABLE', True):
            with patch('app.services.vector_service.db'):
                with app.app_context():
                    svc = VectorService.__new__(VectorService)
                    svc._invalidate_vector_cache = MagicMock()
                    return svc


@pytest.fixture
def mock_vector_results():
    """Mock vector search results."""
    return [{
        "id": "test-id",
        "score": 0.95,
        "metadata": {
            "source": "test-source",
            "page_content": "Test content"
        }
    }]
