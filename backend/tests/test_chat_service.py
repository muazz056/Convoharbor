"""
Tests for the chat service.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.chat_service import ChatService

def test_prepare_messages(chat_service):
    """Test message preparation for LLM."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"}
    ]
    
    prepared = chat_service._prepare_messages(messages)
    assert len(prepared) == 3
    assert all(msg.get("role") in ["user", "assistant"] for msg in prepared)
    assert all(msg.get("content") for msg in prepared)

def test_get_response_with_openai(chat_service, mock_openai_response):
    """Test getting response from OpenAI."""
    with patch('openai.ChatCompletion.create') as mock_create:
        mock_create.return_value = mock_openai_response
        
        response = chat_service.get_response_with_openai(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4",
            temperature=0.7
        )
        
        assert response == "Test response"
        mock_create.assert_called_once()

def test_get_response_with_gemini(chat_service, mock_gemini_response):
    """Test getting response from Gemini."""
    with patch('google.generativeai.GenerativeModel') as MockModel:
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_gemini_response
        MockModel.return_value = mock_instance
        
        response = chat_service.get_response_with_gemini(
            messages=[{"role": "user", "content": "Hello"}],
            model="gemini-pro",
            temperature=0.7
        )
        
        assert response == "Test response"
        mock_instance.generate_content.assert_called_once()

def test_get_response_with_context(chat_service, mock_openai_response):
    """Test getting response with context."""
    with patch('openai.ChatCompletion.create') as mock_create:
        mock_create.return_value = mock_openai_response
        
        context = "This is some context information."
        query = "What can you tell me about this?"
        
        response = chat_service.get_response_with_context(
            context=context,
            query=query,
            conversation_history=[],
            mode="strict",
            model="gpt-4"
        )
        
        assert response == "Test response"
        mock_create.assert_called_once()

def test_detect_intent(chat_service, mock_openai_response):
    """Test intent detection."""
    with patch('openai.ChatCompletion.create') as mock_create:
        mock_create.return_value = mock_openai_response
        
        intent = chat_service.detect_intent("Thank you for your help!")
        assert isinstance(intent, dict)
        assert "is_farewell" in intent

def test_handle_streaming_response(chat_service):
    """Test handling streaming response."""
    chunks = [
        {"choices": [{"delta": {"content": "Hello"}}]},
        {"choices": [{"delta": {"content": " world"}}]},
        {"choices": [{"delta": {"content": "!"}}]}
    ]
    
    accumulated = ""
    for chunk in chunks:
        content = chat_service._handle_streaming_chunk(chunk)
        if content:
            accumulated += content
    
    assert accumulated == "Hello world!"
