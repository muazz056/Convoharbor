"""
Tests for the authentication service.
"""
import pytest
from app.services.auth_service import AuthService
from app.models.user import User
from werkzeug.security import generate_password_hash

def test_create_user(auth_service, app):
    """Test user creation."""
    with app.app_context():
        user = auth_service.create_user(
            email="test@example.com",
            password="test123",
            first_name="Test",
            last_name="User"
        )
        assert user.email == "test@example.com"
        assert user.first_name == "Test"
        assert user.last_name == "User"

def test_authenticate_user(auth_service, app):
    """Test user authentication."""
    with app.app_context():
        # Create test user
        user = User(
            email="test@example.com",
            password=generate_password_hash("test123"),
            first_name="Test",
            last_name="User"
        )
        from app.extensions import db
        db.session.add(user)
        db.session.commit()
        
        # Test valid credentials
        authenticated = auth_service.authenticate_user("test@example.com", "test123")
        assert authenticated is not None
        assert authenticated.email == "test@example.com"
        
        # Test invalid password
        authenticated = auth_service.authenticate_user("test@example.com", "wrong")
        assert authenticated is None
        
        # Test non-existent user
        authenticated = auth_service.authenticate_user("nonexistent@example.com", "test123")
        assert authenticated is None

def test_create_access_token(auth_service, app):
    """Test JWT token creation."""
    with app.app_context():
        user = User(
            id=1,
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )
        token = auth_service.create_access_token(user)
        assert token is not None
        assert isinstance(token, str)

def test_verify_access_token(auth_service, app):
    """Test JWT token verification."""
    with app.app_context():
        user = User(
            id=1,
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )
        token = auth_service.create_access_token(user)
        
        # Test valid token
        decoded = auth_service.verify_access_token(token)
        assert decoded is not None
        assert decoded.get('sub') == 1
        
        # Test invalid token
        decoded = auth_service.verify_access_token("invalid-token")
        assert decoded is None

def test_get_user_from_token(auth_service, app):
    """Test getting user from token."""
    with app.app_context():
        # Create and save test user
        user = User(
            email="test@example.com",
            password=generate_password_hash("test123"),
            first_name="Test",
            last_name="User"
        )
        from app.extensions import db
        db.session.add(user)
        db.session.commit()
        
        # Create token
        token = auth_service.create_access_token(user)
        
        # Get user from token
        retrieved_user = auth_service.get_user_from_token(token)
        assert retrieved_user is not None
        assert retrieved_user.email == user.email
