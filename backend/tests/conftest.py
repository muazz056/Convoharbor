"""
Global pytest fixtures and configuration.
"""
import pytest
from flask import Flask
from app import create_app
from app.services.auth_service import AuthService
from app.services.vector_service import VectorService
from app.services.embedding_service import EmbeddingService
from app.services.chat_service import ChatService
from app.services.web_extraction_service import WebExtractionService

@pytest.fixture
def app():
    """Create and configure a test Flask application instance."""
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'JWT_SECRET_KEY': 'test-secret-key',
        'OPENAI_API_KEY': 'test-openai-key',
        'GOOGLE_API_KEY': 'test-google-key',
        'PINECONE_API_KEY': 'test-pinecone-key',
        'PINECONE_ENVIRONMENT': 'test-env',
        'DEMO_MODE': True  # Use local embeddings
    })
    
    # Initialize extensions and services
    with app.app_context():
        from app.extensions import db
        db.create_all()
        
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
def auth_service(app):
    """Create an AuthService instance."""
    return AuthService()

@pytest.fixture
def vector_service(app):
    """Create a VectorService instance."""
    return VectorService()

@pytest.fixture
def embedding_service(app):
    """Create an EmbeddingService instance."""
    return EmbeddingService()

@pytest.fixture
def chat_service(app):
    """Create a ChatService instance."""
    return ChatService()

@pytest.fixture
def web_extraction_service(app):
    """Create a WebExtractionService instance."""
    return WebExtractionService()

@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    return {
        "choices": [{
            "message": {
                "content": "Test response",
                "role": "assistant"
            }
        }]
    }

@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response."""
    return {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": "Test response"
                }]
            }
        }]
    }

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