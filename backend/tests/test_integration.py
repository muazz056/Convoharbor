"""Integration tests for web crawling and chat flows."""
import pytest
from app.models import Chatbot, DataSource, Conversation, Message

def test_web_crawl_to_chat_flow(client, auth_headers, mock_vector_service):
    """Test complete flow from web crawling to chat interaction."""
    # 1. Create a chatbot
    chatbot_response = client.post('/api/v1/chatbots', json={
        'name': 'Integration Test Bot',
        'description': 'Test bot for integration testing',
        'config': {
            'mode': 'strict',
            'ai_model': 'gpt-4o'
        }
    }, headers=auth_headers)
    assert chatbot_response.status_code == 201
    chatbot_id = chatbot_response.json['chatbot']['id']
    
    # 2. Create a datasource
    datasource_response = client.post('/api/v1/datasources', json={
        'name': 'Test Website',
        'type': 'web',
        'chatbot_id': chatbot_id,
        'config': {
            'url': 'https://example.com',
            'crawl_depth': 1
        }
    }, headers=auth_headers)
    assert datasource_response.status_code == 201
    datasource_id = datasource_response.json['datasource']['id']
    
    # 3. Start web crawl
    crawl_response = client.post(
        f'/api/v1/datasources/{datasource_id}/crawl',
        headers=auth_headers
    )
    assert crawl_response.status_code == 202
    
    # 4. Create a conversation
    conv_response = client.post('/api/v1/conversations', json={
        'chatbot_id': chatbot_id
    }, headers=auth_headers)
    assert conv_response.status_code == 201
    conversation_id = conv_response.json['conversation_id']
    
    # 5. Send a test message
    message_response = client.post(
        f'/api/v1/conversations/{conversation_id}/messages',
        json={
            'content': 'What information do you have?',
            'chatbot_id': chatbot_id
        },
        headers=auth_headers
    )
    assert message_response.status_code == 200
    assert 'assistant_message' in message_response.json

def test_file_upload_to_chat_flow(client, auth_headers, test_file, mock_vector_service):
    """Test complete flow from file upload to chat interaction."""
    # 1. Create a chatbot
    chatbot_response = client.post('/api/v1/chatbots', json={
        'name': 'File Test Bot',
        'description': 'Test bot for file processing',
        'config': {
            'mode': 'strict',
            'ai_model': 'gpt-4o'
        }
    }, headers=auth_headers)
    assert chatbot_response.status_code == 201
    chatbot_id = chatbot_response.json['chatbot']['id']
    
    # 2. Create a datasource
    datasource_response = client.post('/api/v1/datasources', json={
        'name': 'Test Files',
        'type': 'file',
        'chatbot_id': chatbot_id
    }, headers=auth_headers)
    assert datasource_response.status_code == 201
    datasource_id = datasource_response.json['datasource']['id']
    
    # 3. Upload file
    upload_response = client.post(
        f'/api/v1/datasources/{datasource_id}/upload',
        data={'file': test_file},
        headers=auth_headers
    )
    assert upload_response.status_code == 200
    
    # 4. Process file
    process_response = client.post(
        f'/api/v1/datasources/{datasource_id}/process',
        headers=auth_headers
    )
    assert process_response.status_code == 202
    
    # 5. Create a conversation
    conv_response = client.post('/api/v1/conversations', json={
        'chatbot_id': chatbot_id
    }, headers=auth_headers)
    assert conv_response.status_code == 201
    conversation_id = conv_response.json['conversation_id']
    
    # 6. Send a test message
    message_response = client.post(
        f'/api/v1/conversations/{conversation_id}/messages',
        json={
            'content': 'What is in the uploaded file?',
            'chatbot_id': chatbot_id
        },
        headers=auth_headers
    )
    assert message_response.status_code == 200
    assert 'assistant_message' in message_response.json

def test_streaming_chat_flow(client, auth_headers, test_chatbot, mock_vector_service):
    """Test streaming chat interaction."""
    # 1. Create a conversation
    conv_response = client.post('/api/v1/conversations', json={
        'chatbot_id': test_chatbot.id
    }, headers=auth_headers)
    assert conv_response.status_code == 201
    conversation_id = conv_response.json['conversation_id']
    
    # 2. Send a streaming message
    response = client.post(
        f'/api/v1/conversations/{conversation_id}/messages',
        json={
            'content': 'Tell me a story',
            'chatbot_id': test_chatbot.id
        },
        headers={**auth_headers, 'Accept': 'text/event-stream'}
    )
    
    assert response.status_code == 200
    assert response.mimetype == 'text/event-stream'
    
    # Check that we can read the stream
    for chunk in response.response:
        assert chunk.startswith(b'data: ')

def test_conversation_feedback_flow(client, auth_headers, test_chatbot):
    """Test conversation with feedback flow."""
    # 1. Create a conversation
    conv_response = client.post('/api/v1/conversations', json={
        'chatbot_id': test_chatbot.id
    }, headers=auth_headers)
    assert conv_response.status_code == 201
    conversation_id = conv_response.json['conversation_id']
    
    # 2. Send a message
    message_response = client.post(
        f'/api/v1/conversations/{conversation_id}/messages',
        json={
            'content': 'Hello',
            'chatbot_id': test_chatbot.id
        },
        headers=auth_headers
    )
    assert message_response.status_code == 200
    
    # 3. Add thumbs up feedback
    feedback_response = client.post(
        f'/api/v1/conversations/{conversation_id}/feedback',
        json={
            'feedback_type': 'thumbs_up'
        },
        headers=auth_headers
    )
    assert feedback_response.status_code == 201
    
    # 4. Add satisfaction rating
    rating_response = client.post(
        f'/api/v1/conversations/{conversation_id}/satisfaction',
        json={
            'rating': 5,
            'feedback': 'Great conversation!'
        },
        headers=auth_headers
    )
    assert rating_response.status_code == 200
