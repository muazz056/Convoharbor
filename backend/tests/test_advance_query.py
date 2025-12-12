# tests/test_advanced_query.py

import json
from unittest.mock import patch, MagicMock

class TestAdvancedQueryFeatures:
    """
    Test suite for advanced features of the /api/query endpoint.
    """

    @patch('app.services.moderation_service.moderate_input_with_ai', return_value=None)
    @patch('app.services.history_service.save_message_pair')
    @patch('app.services.history_service.get_recent_history')
    @patch('app.services.history_service.get_or_create_conversation')
    @patch('app.services.query_processor_service.rewrite_query_with_history')
    @patch('app.services.query_processor_service.process_query_in_one_shot')
    @patch('app.services.embedding_service.generate_embeddings_for_texts', return_value={'openai_embeddings': [[0.1]]})
    @patch('app.services.vector_service.VectorService.query', return_value=[])
    @patch('app.services.llm_service.LLMService.generate_answer', return_value="Test answer")
    def test_follow_up_question_uses_history(
        self, mock_gen_ans, mock_vec_query, mock_embed, mock_proc_query, mock_rewrite,
        mock_get_conv, mock_get_hist, mock_save_pair, mock_moderate, client
    ):
        """
        GIVEN a user asks a follow-up question,
        WHEN the /query endpoint is called with a session_id,
        THEN the query rewriter should be called with the chat history.
        """
        session_id = "test-session-123"
        chat_history = "User: Who is Hasnain?\nAssistant: He is an AI Engineer..."
        follow_up_query = "What about his projects?"
        
        mock_get_hist.return_value = chat_history
        mock_rewrite.return_value = "What projects has Hasnain worked on?"
        mock_proc_query.return_value = {'query_for_embedding': '...'}
        mock_get_conv.return_value = MagicMock()

        response = client.post(
            '/api/query',
            data=json.dumps({"query": follow_up_query, "session_id": session_id}),
            content_type='application/json'
        )

        assert response.status_code == 200
        mock_get_hist.assert_called_once()
        mock_rewrite.assert_called_once_with(chat_history, follow_up_query)

    @patch('app.services.moderation_service.moderate_input_with_ai')
    def test_moderation_blocks_inappropriate_query(self, mock_moderate_input, client):
        """
        GIVEN a user sends a query that the moderation service flags,
        THEN it should return a 400 error.
        """
        mock_moderate_input.return_value = "Request blocked by safety policy."
        
        response = client.post(
            '/api/query',
            data=json.dumps({"query": "inappropriate question"}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        response_data = response.get_json()
        assert "error" in response_data and response_data["error"] == "Request blocked by safety policy."
        mock_moderate_input.assert_called_once_with("inappropriate question")

    @patch('app.services.vector_service.VectorService.delete_by_source')
    def test_delete_document_endpoint(self, mock_delete_by_source, client):
        """
        GIVEN a request to the /api/delete-document endpoint,
        THEN the vector service's delete method should be called.
        """
        mock_delete_by_source.return_value = {"deleted_count": 15, "message": "Success"}
        source_to_delete = "mydoc.pdf"

        response = client.post(
            '/api/delete-document',
            data=json.dumps({"source": source_to_delete}),
            content_type='application/json'
        )

        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data["deleted_count"] == 15
        mock_delete_by_source.assert_called_once_with(source_to_delete)