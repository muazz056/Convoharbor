"""Tests for the datasources API endpoints."""
import pytest
from app.models import DataSource

def test_create_datasource(client, auth_headers, test_chatbot):
    """Test creating a new datasource."""
    response = client.post('/api/v1/datasources', json={
        'name': 'Test Source',
        'type': 'web',
        'chatbot_id': test_chatbot.id,
        'config': {
            'url': 'https://example.com',
            'crawl_depth': 2
        }
    }, headers=auth_headers)
    
    assert response.status_code == 201
    assert response.json['datasource']['name'] == 'Test Source'

def test_list_datasources(client, auth_headers, test_datasource):
    """Test listing datasources."""
    response = client.get('/api/v1/datasources', headers=auth_headers)
    
    assert response.status_code == 200
    assert 'datasources' in response.json
    assert len(response.json['datasources']) > 0

def test_get_datasource(client, auth_headers, test_datasource):
    """Test getting a single datasource."""
    response = client.get(
        f'/api/v1/datasources/{test_datasource.id}',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert response.json['datasource']['id'] == test_datasource.id

def test_update_datasource(client, auth_headers, test_datasource):
    """Test updating a datasource."""
    response = client.put(
        f'/api/v1/datasources/{test_datasource.id}',
        json={
            'name': 'Updated Source',
            'config': {
                'url': 'https://example.com/updated',
                'crawl_depth': 3
            }
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert response.json['datasource']['name'] == 'Updated Source'

def test_delete_datasource(client, auth_headers, test_datasource):
    """Test deleting a datasource."""
    response = client.delete(
        f'/api/v1/datasources/{test_datasource.id}',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert response.json['success'] is True

def test_start_web_crawl(client, auth_headers, test_datasource, mock_vector_service):
    """Test starting a web crawl."""
    response = client.post(
        f'/api/v1/datasources/{test_datasource.id}/crawl',
        headers=auth_headers
    )
    
    assert response.status_code == 202
    assert response.json['status'] == 'started'

def test_get_crawl_status(client, auth_headers, test_datasource):
    """Test getting crawl status."""
    response = client.get(
        f'/api/v1/datasources/{test_datasource.id}/status',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert 'status' in response.json
    assert 'progress' in response.json

def test_upload_file(client, auth_headers, test_datasource, test_file):
    """Test uploading a file."""
    response = client.post(
        f'/api/v1/datasources/{test_datasource.id}/upload',
        data={'file': test_file},
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert response.json['success'] is True

def test_process_file(client, auth_headers, test_datasource, mock_vector_service):
    """Test processing an uploaded file."""
    response = client.post(
        f'/api/v1/datasources/{test_datasource.id}/process',
        headers=auth_headers
    )
    
    assert response.status_code == 202
    assert response.json['status'] == 'processing'

def test_get_datasource_stats(client, auth_headers, test_datasource):
    """Test getting datasource statistics."""
    response = client.get(
        f'/api/v1/datasources/{test_datasource.id}/stats',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert 'total_documents' in response.json
    assert 'total_chunks' in response.json

# Error cases
def test_create_datasource_invalid_data(client, auth_headers):
    """Test creating datasource with invalid data."""
    response = client.post('/api/v1/datasources', json={
        # Missing required fields
        'name': 'Invalid Source'
    }, headers=auth_headers)
    
    assert response.status_code == 400

def test_get_nonexistent_datasource(client, auth_headers):
    """Test getting a datasource that doesn't exist."""
    response = client.get('/api/v1/datasources/99999', headers=auth_headers)
    
    assert response.status_code == 404

def test_start_crawl_invalid_url(client, auth_headers, test_datasource):
    """Test starting crawl with invalid URL."""
    response = client.post(
        f'/api/v1/datasources/{test_datasource.id}/crawl',
        json={'url': 'invalid-url'},
        headers=auth_headers
    )
    
    assert response.status_code == 400

def test_upload_invalid_file(client, auth_headers, test_datasource):
    """Test uploading invalid file type."""
    response = client.post(
        f'/api/v1/datasources/{test_datasource.id}/upload',
        data={'file': 'invalid-file'},
        headers=auth_headers
    )
    
    assert response.status_code == 400
