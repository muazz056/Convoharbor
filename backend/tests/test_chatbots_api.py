"""Tests for the chatbots API endpoints."""
import pytest
from app.models import Chatbot

def test_create_chatbot(client, auth_headers):
    """Test creating a new chatbot."""
    response = client.post('/api/v1/chatbots', json={
        'name': 'Test Chatbot',
        'description': 'A test chatbot',
        'config': {
            'mode': 'strict',
            'ai_model': 'gpt-4o',
            'personality': {
                'role': 'Assistant',
                'tone': 'professional',
                'style': 'concise'
            }
        }
    }, headers=auth_headers)
    
    assert response.status_code == 201
    assert response.json['chatbot']['name'] == 'Test Chatbot'

def test_list_chatbots(client, auth_headers, test_chatbot):
    """Test listing chatbots."""
    response = client.get('/api/v1/chatbots', headers=auth_headers)
    
    assert response.status_code == 200
    assert 'chatbots' in response.json
    assert len(response.json['chatbots']) > 0

def test_get_chatbot(client, auth_headers, test_chatbot):
    """Test getting a single chatbot."""
    response = client.get(
        f'/api/v1/chatbots/{test_chatbot.id}',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert response.json['chatbot']['id'] == test_chatbot.id

def test_update_chatbot(client, auth_headers, test_chatbot):
    """Test updating a chatbot."""
    response = client.put(
        f'/api/v1/chatbots/{test_chatbot.id}',
        json={
            'name': 'Updated Chatbot',
            'description': 'Updated description'
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert response.json['chatbot']['name'] == 'Updated Chatbot'

def test_delete_chatbot(client, auth_headers, test_chatbot):
    """Test deleting a chatbot."""
    response = client.delete(
        f'/api/v1/chatbots/{test_chatbot.id}',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert response.json['success'] is True

def test_get_chatbot_public(client, test_chatbot):
    """Test getting public chatbot information."""
    response = client.get(f'/api/v1/chatbots/{test_chatbot.id}/public')
    
    assert response.status_code == 200
    assert 'chatbot' in response.json
    assert 'prompts' in response.json['chatbot']

def test_send_test_message(client, auth_headers, test_chatbot, mock_vector_service):
    """Test sending a test message."""
    response = client.post(
        f'/api/v1/chatbots/{test_chatbot.id}/test-message',
        json={'content': 'test message'},
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert 'response' in response.json

def test_update_chatbot_config(client, auth_headers, test_chatbot):
    """Test updating chatbot configuration."""
    response = client.put(
        f'/api/v1/chatbots/{test_chatbot.id}/config',
        json={
            'mode': 'permissive',
            'ai_model': 'gpt-4o-turbo',
            'personality': {
                'role': 'Expert',
                'tone': 'friendly',
                'style': 'detailed'
            }
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert response.json['chatbot']['config']['mode'] == 'permissive'

def test_get_chatbot_analytics(client, auth_headers, test_chatbot):
    """Test getting chatbot analytics."""
    response = client.get(
        f'/api/v1/chatbots/{test_chatbot.id}/analytics',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert 'total_conversations' in response.json
    assert 'total_messages' in response.json

# Error cases
def test_create_chatbot_invalid_data(client, auth_headers):
    """Test creating chatbot with invalid data."""
    response = client.post('/api/v1/chatbots', json={
        # Missing required name
        'description': 'Invalid chatbot'
    }, headers=auth_headers)
    
    assert response.status_code == 400

def test_get_nonexistent_chatbot(client, auth_headers):
    """Test getting a chatbot that doesn't exist."""
    response = client.get('/api/v1/chatbots/99999', headers=auth_headers)
    
    assert response.status_code == 404

def test_update_chatbot_invalid_config(client, auth_headers, test_chatbot):
    """Test updating chatbot with invalid config."""
    response = client.put(
        f'/api/v1/chatbots/{test_chatbot.id}/config',
        json={
            'mode': 'invalid_mode'  # Invalid mode
        },
        headers=auth_headers
    )
    
    assert response.status_code == 400

def test_send_test_message_no_content(client, auth_headers, test_chatbot):
    """Test sending empty test message."""
    response = client.post(
        f'/api/v1/chatbots/{test_chatbot.id}/test-message',
        json={'content': ''},
        headers=auth_headers
    )
    
    assert response.status_code == 400
