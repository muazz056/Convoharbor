"""Tests for the conversations API endpoints."""
import pytest
from datetime import datetime
from app.models import Conversation, Message, Chatbot

def test_create_conversation(client, auth_headers, test_chatbot):
    """Test creating a new conversation."""
    response = client.post('/api/v1/conversations', json={
        'chatbot_id': test_chatbot.id
    }, headers=auth_headers)
    
    assert response.status_code == 201
    assert 'conversation_id' in response.json
    assert 'session_id' in response.json

def test_list_conversations(client, auth_headers, test_conversation):
    """Test listing conversations."""
    response = client.get('/api/v1/conversations', headers=auth_headers)
    
    assert response.status_code == 200
    assert 'conversations' in response.json
    assert len(response.json['conversations']) > 0
    assert 'pagination' in response.json

def test_get_conversation_messages(client, auth_headers, test_conversation, test_messages):
    """Test getting conversation messages."""
    response = client.get(
        f'/api/v1/conversations/{test_conversation.id}/messages',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert 'messages' in response.json
    assert len(response.json['messages']) == len(test_messages)

def test_send_message_json(client, auth_headers, test_conversation, test_chatbot, mock_vector_service):
    """Test sending a message (JSON response)."""
    response = client.post(
        f'/api/v1/conversations/{test_conversation.id}/messages',
        json={
            'content': 'test message',
            'chatbot_id': test_chatbot.id
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert 'user_message' in response.json
    assert 'assistant_message' in response.json

def test_send_message_stream(client, auth_headers, test_conversation, test_chatbot, mock_vector_service):
    """Test sending a message (streaming response)."""
    response = client.post(
        f'/api/v1/conversations/{test_conversation.id}/messages',
        json={
            'content': 'test message',
            'chatbot_id': test_chatbot.id
        },
        headers={**auth_headers, 'Accept': 'text/event-stream'}
    )
    
    assert response.status_code == 200
    assert response.mimetype == 'text/event-stream'

def test_add_conversation_feedback(client, auth_headers, test_conversation):
    """Test adding feedback to a conversation."""
    response = client.post(
        f'/api/v1/conversations/{test_conversation.id}/feedback',
        json={
            'feedback_type': 'rating',
            'rating': 5,
            'feedback_text': 'Great conversation!'
        },
        headers=auth_headers
    )
    
    assert response.status_code == 201
    assert response.json['success'] is True

def test_add_satisfaction_rating(client, auth_headers, test_conversation):
    """Test adding satisfaction rating."""
    response = client.post(
        f'/api/v1/conversations/{test_conversation.id}/satisfaction',
        json={
            'rating': 5,
            'feedback': 'Very helpful!'
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert response.json['success'] is True

def test_delete_conversation(client, auth_headers, test_conversation):
    """Test soft deleting a conversation."""
    response = client.delete(
        f'/api/v1/conversations/{test_conversation.id}',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert response.json['success'] is True

def test_update_conversation_status(client, test_conversation):
    """Test updating conversation status."""
    response = client.put(
        f'/api/v1/conversations/{test_conversation.id}/status',
        json={'status': 'inactive'}
    )
    
    assert response.status_code == 200
    assert response.json['success'] is True
    assert response.json['new_status'] == 'inactive'

def test_cleanup_conversations(client, auth_headers, test_conversation):
    """Test cleaning up old conversations."""
    response = client.post(
        '/api/v1/conversations/cleanup',
        json={'type': 'all'},
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert response.json['success'] is True
    assert 'deleted_count' in response.json

# Error cases
def test_create_conversation_invalid_chatbot(client, auth_headers):
    """Test creating conversation with invalid chatbot ID."""
    response = client.post('/api/v1/conversations', json={
        'chatbot_id': 99999
    }, headers=auth_headers)
    
    assert response.status_code == 404

def test_send_message_invalid_conversation(client, auth_headers, test_chatbot):
    """Test sending message to invalid conversation."""
    response = client.post(
        '/api/v1/conversations/99999/messages',
        json={
            'content': 'test message',
            'chatbot_id': test_chatbot.id
        },
        headers=auth_headers
    )
    
    assert response.status_code == 404

def test_send_message_no_content(client, auth_headers, test_conversation, test_chatbot):
    """Test sending empty message."""
    response = client.post(
        f'/api/v1/conversations/{test_conversation.id}/messages',
        json={
            'content': '',
            'chatbot_id': test_chatbot.id
        },
        headers=auth_headers
    )
    
    assert response.status_code == 400

def test_add_invalid_satisfaction_rating(client, auth_headers, test_conversation):
    """Test adding invalid satisfaction rating."""
    response = client.post(
        f'/api/v1/conversations/{test_conversation.id}/satisfaction',
        json={'rating': 6},  # Invalid rating
        headers=auth_headers
    )
    
    assert response.status_code == 400
