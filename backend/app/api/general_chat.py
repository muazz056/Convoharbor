"""
General Chat API - Standalone chat endpoint that doesn't require a specific chatbot.
Uses OpenAI GPT-4o by default for general conversations.
"""
from flask import request, current_app, jsonify
from flasgger import swag_from
from datetime import datetime
from . import api, rate_limit
from ..services.llm_service import LLMService
import time

# In-memory storage for general chat sessions (for demo/testing)
# In production, this should use Redis or a database
_GENERAL_CHAT_SESSIONS = {}


@api.route('/general-chat', methods=['POST'], endpoint='general_chat')
@rate_limit(60, 60)  # 60 requests per 60 seconds
@swag_from({
    'tags': ['General Chat'],
    'summary': 'Send a message to general AI assistant',
    'description': 'Standalone chat endpoint using OpenAI GPT-4o. No chatbot configuration required.',
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['message'],
                'properties': {
                    'message': {
                        'type': 'string',
                        'description': 'User message'
                    },
                    'session_id': {
                        'type': 'string',
                        'description': 'Optional session ID for conversation continuity'
                    }
                }
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'AI response',
            'schema': {
                'type': 'object',
                'properties': {
                    'response': {'type': 'string'},
                    'session_id': {'type': 'string'},
                    'timestamp': {'type': 'string'}
                }
            }
        },
        '400': {'description': 'Invalid request'},
        '500': {'description': 'Server error'}
    }
})
def general_chat():
    """Handle general chat messages without requiring a specific chatbot."""
    try:
        data = request.get_json() or {}
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id') or f"general-{int(time.time() * 1000)}"

        if not user_message:
            return jsonify({'error': 'Message is required'}), 400

        current_app.logger.info(f"🤖 General chat request - Session: {session_id}, Message: {user_message[:50]}...")

        # Get or create session history (keep last 10 messages)
        if session_id not in _GENERAL_CHAT_SESSIONS:
            _GENERAL_CHAT_SESSIONS[session_id] = []

        session_history = _GENERAL_CHAT_SESSIONS[session_id]

        # Add user message to history
        session_history.append({
            'role': 'user',
            'content': user_message,
            'timestamp': datetime.utcnow().isoformat()
        })

        # Initialize LLM service
        llm_service = LLMService()

        # Build messages for LLM (LangChain format)
        messages = []

        # Render the system prompt from prompts.yml (general_chat) so we don't
        # have hardcoded persona strings in the .py file.
        from ..services.prompt_service import PromptService
        prompt_svc = PromptService()
        history_str = "\n".join(
            f"{m['role']}: {m['content']}" for m in session_history[-10:]
        ) or "(no prior messages)"

        # System message
        messages.append({
            'role': 'system',
            'content': prompt_svc.render(
                'general_chat',
                target_lang='English',
                history=history_str,
                query=user_message,
            ),
        })

        # Add conversation history (last 10 messages)
        for msg in session_history[-10:]:
            messages.append({
                'role': msg['role'],
                'content': msg['content']
            })

        # Resolve the chat model from Super Admin's AiModel table (no hardcoded names)
        try:
            from ..services.model_resolver import get_default_llm_model
            resolved_model, _ = get_default_llm_model()
        except Exception:  # noqa: BLE001
            resolved_model = None
        if not resolved_model:
            return jsonify({
                'error': 'No active AI model configured',
                'message': 'Super Admin must add at least one model in the AI Models page.'
            }), 400

        # Generate response using the configured model
        try:
            result = llm_service.generate_answer(
                messages=messages,
                model_name=resolved_model,
                user_id=f'general-chat-{session_id}',
                tenant_id='general'
            )

            if not result or not result.get('content'):
                raise Exception('No response content from LLM')

            ai_response = result['content']

            # Add assistant response to history
            session_history.append({
                'role': 'assistant',
                'content': ai_response,
                'timestamp': datetime.utcnow().isoformat()
            })

            # Keep only last 20 messages (10 exchanges)
            if len(session_history) > 20:
                _GENERAL_CHAT_SESSIONS[session_id] = session_history[-20:]

            current_app.logger.info(f"✅ General chat response generated for session: {session_id}")

            # Check if streaming is requested
            if request.headers.get('Accept') == 'text/event-stream':
                # Import streaming function from conversations
                from .conversations import stream_response_chunks
                from flask import Response, stream_with_context
                import json

                def generate_general_stream():
                    try:
                        # Stream the response with typewriter effect
                        for chunk in stream_response_chunks(ai_response, chunk_size=1, delay=0.005):
                            yield chunk
                    except Exception as e:
                        current_app.logger.error(f"General chat streaming error: {e}")
                        yield f"data: {json.dumps({'error': str(e)})}\n\n"

                return Response(
                    stream_with_context(generate_general_stream()),
                    mimetype='text/event-stream',
                    headers={
                        'Cache-Control': 'no-cache',
                        'X-Accel-Buffering': 'no',
                        'Connection': 'keep-alive'
                    }
                )
            else:
                # Regular JSON response for non-streaming requests
                return jsonify({
                    'response': ai_response,
                    'session_id': session_id,
                    'timestamp': datetime.utcnow().isoformat()
                }), 200

        except Exception as llm_error:
            current_app.logger.error(f"❌ LLM error in general chat: {llm_error}")
            return jsonify({
                'error': 'Failed to generate response',
                'message': str(llm_error)
            }), 500

    except Exception as error:
        current_app.logger.error(f"❌ General chat error: {error}")
        return jsonify({
            'error': 'Server error',
            'message': str(error)
        }), 500


@api.route('/general-chat/clear', methods=['POST'], endpoint='clear_general_chat')
@swag_from({
    'tags': ['General Chat'],
    'summary': 'Clear a general chat session',
    'description': 'Delete conversation history for a session',
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['session_id'],
                'properties': {
                    'session_id': {'type': 'string'}
                }
            }
        }
    ],
    'responses': {
        '200': {'description': 'Session cleared'},
        '400': {'description': 'Invalid request'}
    }
})
def clear_general_chat():
    """Clear a general chat session."""
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')

        if not session_id:
            return jsonify({'error': 'session_id is required'}), 400

        if session_id in _GENERAL_CHAT_SESSIONS:
            del _GENERAL_CHAT_SESSIONS[session_id]
            current_app.logger.info(f"🧹 Cleared general chat session: {session_id}")

        return jsonify({
            'message': 'Session cleared successfully',
            'session_id': session_id
        }), 200

    except Exception as error:
        current_app.logger.error(f"❌ Error clearing session: {error}")
        return jsonify({'error': str(error)}), 500
