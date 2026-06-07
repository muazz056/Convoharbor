# app/services/ai_connector.py

import requests
from typing import Optional, Dict, Any, List
from flask import current_app
import time
from urllib.parse import urljoin

from .model_resolver import resolve_model


class AIConnectorService:
    """
    AI Gateway Service - Unified interface to Flask AI microservice
    Handles all communication with the external AI service endpoints
    """

    def __init__(self):
        """Initialize AI Connector with configuration"""
        self.base_url = current_app.config.get('AI_SERVICE_URL', 'http://localhost:5000')
        self.api_key = current_app.config.get('AI_SERVICE_API_KEY')
        self.timeout = current_app.config.get('AI_SERVICE_TIMEOUT', 30)
        self.max_retries = 3
        self.retry_delay = 1  # seconds

        # Ensure base URL has proper format
        if not self.base_url.endswith('/'):
            self.base_url += '/'

        current_app.logger.info(f"🔗 AIConnector initialized with base_url: {self.base_url}")

    def _make_request(self, method: str, endpoint: str, data: Any = None, files: Any = None,
                      headers: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make HTTP request to AI service with retry logic and error handling

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: JSON data for request body
            files: Files for multipart upload
            headers: Additional headers

        Returns:
            Response JSON data

        Raises:
            Exception: If all retry attempts fail
        """
        url = urljoin(self.base_url, endpoint.lstrip('/'))

        # Prepare headers
        request_headers = {
            'User-Agent': 'ConvoPilot-AIConnector/1.0'
        }

        if self.api_key:
            request_headers['Authorization'] = f'Bearer {self.api_key}'

        if headers:
            request_headers.update(headers)

        # Don't set Content-Type for multipart uploads (files)
        if not files and data is not None:
            request_headers['Content-Type'] = 'application/json'

        # Retry logic
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                current_app.logger.info(f"🌐 Making {method} request to {url} (attempt {attempt + 1}/{self.max_retries})")

                if method.upper() == 'GET':
                    response = requests.get(url, headers=request_headers, timeout=self.timeout, params=data)
                elif method.upper() == 'POST':
                    if files:
                        # For file uploads
                        response = requests.post(url, headers=request_headers, files=files,
                                                 data=data, timeout=self.timeout)
                    else:
                        # For JSON data
                        response = requests.post(url, headers=request_headers,
                                                 json=data, timeout=self.timeout)
                elif method.upper() == 'PUT':
                    response = requests.put(url, headers=request_headers, json=data, timeout=self.timeout)
                elif method.upper() == 'DELETE':
                    response = requests.delete(url, headers=request_headers, timeout=self.timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Log response details
                current_app.logger.info(f"📥 Response: {response.status_code} from {url}")

                # Handle response
                if response.status_code >= 200 and response.status_code < 300:
                    try:
                        result = response.json()
                        current_app.logger.info(f"✅ Successful API call to {endpoint}")
                        return result
                    except ValueError:
                        current_app.logger.warning(f"⚠️ Non-JSON response from {endpoint}: {response.text[:200]}")
                        return {"message": "Success", "raw_response": response.text}

                elif response.status_code >= 400 and response.status_code < 500:
                    # Client errors - don't retry
                    error_msg = f"Client error {response.status_code} from AI service: {response.text}"
                    current_app.logger.error(f"❌ {error_msg}")
                    raise Exception(error_msg)

                else:
                    # Server errors - retry
                    error_msg = f"Server error {response.status_code} from AI service: {response.text}"
                    current_app.logger.warning(f"⚠️ {error_msg} - will retry")
                    last_exception = Exception(error_msg)

            except requests.exceptions.RequestException as e:
                current_app.logger.warning(f"⚠️ Request failed (attempt {attempt + 1}): {str(e)}")
                last_exception = e

            # Wait before retry (except on last attempt)
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff

        # All retries failed
        error_msg = f"All {self.max_retries} attempts failed for {endpoint}: {str(last_exception)}"
        current_app.logger.error(f"❌ {error_msg}")
        raise Exception(error_msg)

    def process_document(self, files: List, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process documents using AI service

        Args:
            files: List of file objects to process
            tenant_id: Optional tenant ID for tracking

        Returns:
            Processing results with chunks and metadata
        """
        current_app.logger.info(f"📄 Processing {len(files)} documents via AI service")

        try:
            # Prepare files for upload
            file_data = {}
            for i, file in enumerate(files):
                file_data[f'files'] = (file.filename, file.stream, file.content_type)

            # Add tenant context if available
            form_data = {}
            if tenant_id:
                form_data['tenant_id'] = tenant_id

            # Call AI service
            result = self._make_request('POST', '/api/v1/process-document',
                                        data=form_data, files=file_data)

            current_app.logger.info(f"✅ Document processing completed: {result.get('processed_chunks', 0)} chunks")
            return result

        except Exception as e:
            current_app.logger.error(f"❌ Document processing failed: {str(e)}")
            return {
                "error": f"Document processing failed: {str(e)}",
                "processed_chunks": 0,
                "chunks": [],
                "failed_files": [{"filename": f.filename, "error": str(e)} for f in files]
            }

    def generate_embeddings(self, chunks: List[Dict], provider: str = 'openai') -> Dict[str, Any]:
        """
        Generate embeddings for text chunks

        Args:
            chunks: List of text chunks with metadata
            provider: Embedding provider ('openai' or 'gemini')

        Returns:
            Embeddings results
        """
        current_app.logger.info(f"🔢 Generating embeddings for {len(chunks)} chunks using {provider}")

        try:
            payload = {
                "chunks": chunks,
                "provider": provider
            }

            result = self._make_request('POST', '/api/v1/generate-embedding', data=payload)

            processed_count = len(result.get('processed_chunks', []))
            current_app.logger.info(f"✅ Embeddings generated for {processed_count} chunks")
            return result

        except Exception as e:
            current_app.logger.error(f"❌ Embedding generation failed: {str(e)}")
            return {
                "error": f"Embedding generation failed: {str(e)}",
                "processed_chunks": [],
                "errors": {"embedding_service": str(e)}
            }

    def query_knowledge_base(self, query: str, session_id: Optional[str] = None,
                             chatbot_config: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """
        Query the knowledge base using AI service

        Args:
            query: User query text
            session_id: Conversation session ID
            chatbot_config: Chatbot-specific configuration
            **kwargs: Additional query parameters

        Returns:
            Query response with answer and sources
        """
        current_app.logger.info(f"🤖 Querying knowledge base: '{query[:50]}...'")

        try:
            # Build request payload
            payload = {
                "query": query
            }

            if session_id:
                payload["session_id"] = session_id

            # Apply chatbot configuration if provided
            if chatbot_config:
                if 'ai_model' in chatbot_config or 'ai_model_id' in chatbot_config or 'ai_provider' in chatbot_config:
                    try:
                        model_name, model_provider = resolve_model(chatbot_config)
                        payload['model'] = model_name
                        payload['llm_provider'] = model_provider
                    except ValueError as exc:
                        current_app.logger.error(f"❌ Cannot resolve AI model: {exc}")
                        return {
                            "error": str(exc),
                            "answer": "AI model is not configured. Please ask your Super Admin to add a model in the AI Models page.",
                            "sources": [],
                            "context_used": 0
                        }

                if 'temperature' in chatbot_config:
                    payload['temperature'] = chatbot_config['temperature']

                if 'personality' in chatbot_config:
                    payload['role'] = chatbot_config['personality'].get('role', 'General Assistant')

            # Add additional parameters
            payload.update(kwargs)

            result = self._make_request('POST', '/api/v1/query', data=payload)

            current_app.logger.info(f"✅ Knowledge base query completed successfully")
            return result

        except Exception as e:
            current_app.logger.error(f"❌ Knowledge base query failed: {str(e)}")
            return {
                "error": f"Knowledge base query failed: {str(e)}",
                "answer": "I apologize, but I'm experiencing technical difficulties. Please try again later.",
                "sources": [],
                "session_id": session_id or "error_session"
            }

    def process_scraped_content(self, source_url: str, content: str,
                                tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process web scraped content

        Args:
            source_url: Original URL of the content
            content: Scraped text content
            tenant_id: Optional tenant ID for tracking

        Returns:
            Processing results with chunks
        """
        current_app.logger.info(f"🕸️ Processing scraped content from: {source_url}")

        try:
            payload = {
                "source_url": source_url,
                "content": content
            }

            if tenant_id:
                payload["tenant_id"] = tenant_id

            result = self._make_request('POST', '/api/v1/process-scraped-content', data=payload)

            processed_count = result.get('processed_chunks', 0)
            current_app.logger.info(f"✅ Scraped content processed: {processed_count} chunks from {source_url}")
            return result

        except Exception as e:
            current_app.logger.error(f"❌ Scraped content processing failed: {str(e)}")
            return {
                "error": f"Scraped content processing failed: {str(e)}",
                "processed_chunks": 0,
                "chunks": []
            }

    def upsert_chunks(self, processed_chunks: List[Dict], provider: str = 'openai') -> Dict[str, Any]:
        """
        Upsert processed chunks to vector database

        Args:
            processed_chunks: List of chunks with embeddings
            provider: Embedding provider used

        Returns:
            Upsert results
        """
        current_app.logger.info(f"📤 Upserting {len(processed_chunks)} chunks to vector database")

        try:
            payload = {
                "processed_chunks": processed_chunks,
                "provider": provider
            }

            result = self._make_request('POST', '/api/v1/upsert-chunks', data=payload)

            upserted_count = result.get('upserted_count', 0)
            current_app.logger.info(f"✅ Successfully upserted {upserted_count} chunks")
            return result

        except Exception as e:
            current_app.logger.error(f"❌ Chunk upsert failed: {str(e)}")
            return {
                "error": f"Chunk upsert failed: {str(e)}",
                "upserted_count": 0
            }

    def delete_document(self, source: str) -> Dict[str, Any]:
        """
        Delete document from vector database

        Args:
            source: Source filename to delete

        Returns:
            Deletion results
        """
        current_app.logger.info(f"🗑️ Deleting document: {source}")

        try:
            payload = {"source": source}
            result = self._make_request('POST', '/api/v1/delete-document', data=payload)

            deleted_count = result.get('deleted_count', 0)
            current_app.logger.info(f"✅ Deleted {deleted_count} chunks for document: {source}")
            return result

        except Exception as e:
            current_app.logger.error(f"❌ Document deletion failed: {str(e)}")
            return {
                "error": f"Document deletion failed: {str(e)}",
                "deleted_count": 0
            }

    def health_check(self) -> Dict[str, Any]:
        """
        Check health status of AI service

        Returns:
            Health status information
        """
        try:
            # Try a simple endpoint to check if service is alive
            result = self._make_request('GET', '/api/v1/')
            return {
                "status": "healthy",
                "ai_service_url": self.base_url,
                "response": result
            }
        except Exception as e:
            current_app.logger.error(f"❌ AI service health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "ai_service_url": self.base_url,
                "error": str(e)
            }

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the AI connector service

        Returns:
            Service configuration and status
        """
        return {
            "service_name": "AI Connector Service",
            "version": "1.0.0",
            "base_url": self.base_url,
            "has_api_key": bool(self.api_key),
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "supported_endpoints": [
                "/process-document",
                "/generate-embedding",
                "/query",
                "/process-scraped-content",
                "/upsert-chunks",
                "/delete-document"
            ]
        }
