# tests/test_rag_pipeline.py

from datetime import datetime
import json
from unittest.mock import patch, MagicMock

# Define mock data that our services will return
MOCK_QUERY_PROCESSOR_OUTPUT = {
    'original_lang': 'en',
    'english_query': 'What is RAG?',
    'sentiment': 'neutral',
    'intent': 'question',
    'complexity': 'simple',
    'query_for_embedding': 'What is RAG?\n\nHypothetical document about RAG...'
}

MOCK_RETRIEVED_CONTEXTS = [
    {
        'score': 0.89,
        'page_content': 'RAG stands for Retrieval-Augmented Generation.',
        'metadata': {'source': 'doc1.pdf', 'language': 'en'}
    },
    {
        'score': 0.85,
        'page_content': 'It is a technique to ground LLMs in factual data.',
        'metadata': {'source': 'doc2.txt', 'language': 'en'}
    }
]

MOCK_FINAL_ANSWER = "Based on the context, RAG stands for Retrieval-Augmented Generation [Source: doc1.pdf] and is a technique to ground LLMs in factual data [Source: doc2.txt]."
MOCK_POLICY_CHECK_PASS = '{"violates_policy": false, "reason": "Acceptable"}'

class TestRAGPipeline:

    @patch('app.services.moderation_service.moderate_input_with_ai', return_value=None)
    @patch('app.services.history_service.save_message_pair')
    @patch('app.services.history_service.get_recent_history', return_value="")
    @patch('app.services.history_service.get_or_create_conversation')
    @patch('app.services.query_processor_service.rewrite_query_with_history', side_effect=lambda _, q: q)
    @patch('app.services.query_processor_service.process_query_in_one_shot')
    @patch('app.services.embedding_service.generate_embeddings_for_texts')
    @patch('app.services.vector_service.VectorService.query')
    @patch('app.services.llm_service.LLMService.generate_answer')
    def test_full_rag_flow_successful(
        self,
        mock_generate_answer,
        mock_vector_query,
        mock_generate_embeddings,
        mock_process_query,
        mock_rewrite_query,
        mock_get_or_create_conv,
        mock_get_history,
        mock_save_pair,
        mock_moderate_input,
        client
    ):
        """
        Tests the entire /api/query endpoint from start to finish,
        mocking external calls and DB interactions.
        """
        # --- ARRANGE: Configure the return values of our mocks ---
        
        mock_process_query.return_value = MOCK_QUERY_PROCESSOR_OUTPUT
        mock_generate_embeddings.return_value = {'openai_embeddings': [[0.1, 0.2, 0.3]]}
        mock_vector_query.return_value = MOCK_RETRIEVED_CONTEXTS
        mock_generate_answer.return_value = MOCK_FINAL_ANSWER
        
        mock_conversation = MagicMock()
        mock_conversation.session_id = "mock-session-id"
        mock_conversation.updated_at = datetime.utcnow()
        mock_get_or_create_conv.return_value = mock_conversation
        mock_save_pair.return_value = 99

        # --- ACT: Send a request to the endpoint ---
        
        request_payload = {"query": "What is RAG?", "role": "Test Role"}
        
        with patch('app.services.language_service.detect_language_with_llm', return_value='en'):
            
            # ACT
            response = client.post(
                '/api/query',
                data=json.dumps(request_payload),
                content_type='application/json'
            )
        
        # --- ASSERT: Check the results ---
        
        assert response.status_code == 200
        
        response_data = response.get_json()
        assert 'answer' in response_data and response_data['answer'] == MOCK_FINAL_ANSWER
        assert 'sources' in response_data and len(response_data['sources']) == 2
        assert response_data['sources'][0]['source'] == 'doc1.pdf'
        assert response_data['session_id'] == "mock-session-id"
        assert response_data['message_id'] == 99
        assert 'session_expires_at' in response_data

        # Verify that our mocks were called correctly
        mock_moderate_input.assert_called_once()
        mock_get_or_create_conv.assert_called_once()
        mock_rewrite_query.assert_called_once()
        mock_process_query.assert_called_once_with(
                "What is RAG?",
                original_lang='en', 
                provider="openai",
                model_name="gpt-4o-mini"
            )
        mock_vector_query.assert_called_once()
        
        # The final answer generation is now called by the prompt service
        # To test it, we'd need to mock the prompt service's build method, 
        # but for this integration test, checking the final output is sufficient.
        
        # We can inspect the arguments of the mock_generate_answer
        final_prompt_call = mock_generate_answer.call_args
        assert final_prompt_call is not None, "Final LLM generate_answer was not called"
        final_prompt = final_prompt_call.args[0]
        assert "RAG stands for Retrieval-Augmented Generation" in final_prompt
        assert "ENGLISH USER QUESTION:\nWhat is RAG?" in final_prompt