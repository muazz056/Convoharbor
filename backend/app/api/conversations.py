from flask import request, current_app, jsonify, g, Response, stream_with_context
from flasgger import swag_from
from datetime import datetime, timedelta
import time
import json
import re
from . import api, rate_limit
from ..decorators import login_required
from ..models import Conversation, Message, ConversationFeedback, Chatbot, Tenant
from .. import db
from ..services import chatbot_defaults
from sqlalchemy import desc, func


def _context_has_meaningful_content(text):
    """Check if text has enough readable English words to be usable as context (vs binary garbage from corrupted embeddings)."""
    if not text or not text.strip():
        return False
    words = re.findall(r'[A-Za-z]{3,}', text)
    return len(words) >= 5


def _context_relevant_to_query(context_text, query):
    """Quick heuristic: if the query mentions a specific noun/term that is completely absent from the context, the context likely does not answer the query. Returns True if we should proceed with context, False if we should fall back to out_of_scope."""
    if not context_text or not query:
        return True
    query_lower = query.lower()
    context_lower = context_text.lower()
    # Extract significant words (4+ chars) from the query
    query_words = [w for w in re.findall(r'[A-Za-z0-9]{4,}', query_lower) if w not in {'what', 'when', 'where', 'why', 'how', 'does', 'is', 'the', 'this', 'that', 'with', 'from', 'have', 'are', 'was', 'were', 'can', 'you', 'tell', 'give', 'some'}]
    if not query_words:
        return True
    # If ANY significant query word appears in context, consider it relevant enough
    for w in query_words:
        if w in context_lower:
            return True
    return False


def stream_response_chunks(text, chunk_size=1, delay=0.005):
    """
    Stream response text word-by-word with typewriter effect.

    Args:
        text: The full response text to stream
        chunk_size: Number of words per chunk (1 for true typewriter effect)
        delay: Delay between chunks in seconds (0.005 for fast typewriter)

    Yields:
        SSE-formatted chunks of text
    """
    if not text:
        return

    # Ensure text is a string
    if not isinstance(text, str):
        text = str(text)

    # Split by individual words and spaces for true typewriter effect
    words = re.findall(r'\S+|\s+', text)

    accumulated_text = ""

    for word in words:
        accumulated_text += word

        # Send each word/space individually for typewriter effect
        yield f"data: {json.dumps({'content': word, 'accumulated': accumulated_text})}\n\n"

        # Only add delay for actual words (not spaces) and make it faster
        if word.strip():
            time.sleep(delay)


@api.route('/conversations', methods=['POST'], endpoint='create_conversation')
@rate_limit(90, 60)
@swag_from({
    'tags': ['Conversations'],
    'summary': 'Create a new conversation',
    'description': 'Create a conversation for a chatbot. Public endpoint; secures by chatbot ownership.',
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['chatbot_id'],
                'properties': {
                    'chatbot_id': {'type': 'integer'},
                    'session_id': {'type': 'string'}
                }
            }
        }
    ],
    'responses': {
        '201': {
            'description': 'Conversation created',
            'schema': {
                'type': 'object',
                'properties': {
                    'conversation_id': {'type': 'integer'},
                    'session_id': {'type': 'string'}
                }
            }
        },
        '404': {'description': 'Chatbot not found'}
    }
})
def create_conversation():
    try:
        data = request.get_json() or {}
        chatbot_id = data.get('chatbot_id')
        session_id = data.get('session_id')

        # Check if frontend explicitly indicates this is an embed conversation
        is_embed_request = data.get('is_embed', False)
        custom_title = data.get('title')

        # NEW: Extract website context (optional - won't break existing functionality)
        website_context = data.get('website_context', {})
        source_domain = website_context.get('domain') if website_context else None
        source_url = website_context.get('url') if website_context else None

        # DEBUG: Log what we received
        current_app.logger.info(f"🔧 CREATE_CONVERSATION DEBUG:")
        current_app.logger.info(f"   ├─ Request data: {data}")
        current_app.logger.info(f"   ├─ Website context: {website_context}")
        current_app.logger.info(f"   ├─ Source domain: {source_domain}")
        current_app.logger.info(f"   └─ Source URL: {source_url}")

        if not chatbot_id:
            return jsonify({'error': 'chatbot_id is required'}), 400

        # Verify chatbot exists
        chatbot = Chatbot.query.filter_by(id=chatbot_id).first()
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404

        # Determine conversation type - prioritize frontend indication
        is_embed = is_embed_request or (not hasattr(g, 'user_id') or getattr(g, 'user_id', None) is None)

        # Use custom title if provided, otherwise generate default
        if custom_title:
            title = custom_title
        elif source_domain:  # NEW: Use domain in title if available
            title = f"Embed Chat - {source_domain}"
        else:
            title = f"Embed Chat - {chatbot.name}" if is_embed else f"Admin Chat - {chatbot.name}"

        current_app.logger.info(f"🔧 Creating conversation: chatbot_id={chatbot_id}, is_embed={is_embed}, title='{title}', domain={source_domain}")

        # Create conversation with basic fields (always works)
        conv_data = {
            'session_id': session_id or f"sess-{datetime.utcnow().timestamp()}",
            'tenant_id': chatbot.tenant_id,
            'chatbot_id': chatbot.id,
            'user_id': getattr(g, 'user_id', None) if hasattr(g, 'user_id') else None,
            'title': title,
            'status': 'active',
            'language': 'en'
        }

        # NEW: Add website tracking fields only if they exist in the model (backward compatible)
        try:
            # Check if the model has the new fields
            if hasattr(Conversation, 'source_domain'):
                conv_data.update({
                    'source_domain': source_domain,
                    'source_url': source_url,
                    'source_platform': 'web',
                    'source_metadata': website_context
                })
                current_app.logger.info(f"🌐 Added website tracking: domain={source_domain}, url={source_url}")
                current_app.logger.info(f"🌐 Full conv_data: {conv_data}")
            else:
                current_app.logger.warning(f"⚠️ Conversation model does not have source_domain field")
        except Exception as e:
            current_app.logger.warning(f"⚠️ Website tracking fields not available: {e}")

        current_app.logger.info(f"🔧 Final conversation data: {conv_data}")

        conv = Conversation(**conv_data)
        db.session.add(conv)
        db.session.commit()

        # Save welcome message if provided (so it appears in message history on reload)
        welcome_message = data.get('welcome_message')
        if welcome_message:
            from ..models.conversation import Message
            welcome_msg = Message(
                conversation_id=conv.id,
                content=welcome_message,
                message_type='assistant',
                created_at=datetime.utcnow()
            )
            db.session.add(welcome_msg)
            db.session.commit()
            current_app.logger.info(f"💬 Saved welcome message for conversation {conv.id}")

        current_app.logger.info(f"✅ Created conversation {conv.id} with title: '{conv.title}' for domain: {source_domain or 'unknown'}")

        # DEBUG: Verify the created conversation
        created_conv = Conversation.query.get(conv.id)
        if created_conv:
            current_app.logger.info(f"🔍 Verification - Created conv: title={created_conv.title}, domain={getattr(created_conv, 'source_domain', 'MISSING')}")

        # Send notification for new conversation (non-blocking)
        try:
            from ..services.notification_service import NotificationService
            notification_service = NotificationService()

            # Only send notifications for embed conversations (external users)
            if is_embed and source_domain:
                notification_service.send_conversation_started_notification(
                    tenant_id=chatbot.tenant_id,
                    chatbot_id=chatbot_id,
                    conversation_id=conv.id,
                    source_domain=source_domain
                )
        except Exception as e:
            # Don't fail the conversation creation if notification fails
            current_app.logger.error(f"Failed to send conversation notification: {str(e)}")

        return jsonify({'conversation_id': conv.id, 'session_id': conv.session_id}), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Error creating conversation: {e}")
        return jsonify({'error': 'Failed to create conversation'}), 500


@api.route('/conversations', methods=['GET'], endpoint='list_conversations')
@login_required
@swag_from({
    'tags': ['Conversations'],
    'summary': 'List conversations',
    'description': 'Get paginated list of conversations with optional filters',
    'parameters': [
        {
            'name': 'chatbot_id',
            'in': 'query',
            'type': 'integer',
            'description': 'Filter by chatbot ID'
        },
        {
            'name': 'status',
            'in': 'query',
            'type': 'string',
            'enum': ['active', 'archived', 'deleted'],
            'description': 'Filter by conversation status'
        },
        {
            'name': 'start_date',
            'in': 'query',
            'type': 'string',
            'format': 'date',
            'description': 'Filter conversations from this date (YYYY-MM-DD)'
        },
        {
            'name': 'end_date',
            'in': 'query',
            'type': 'string',
            'format': 'date',
            'description': 'Filter conversations until this date (YYYY-MM-DD)'
        },
        {
            'name': 'page',
            'in': 'query',
            'type': 'integer',
            'default': 1,
            'description': 'Page number'
        },
        {
            'name': 'per_page',
            'in': 'query',
            'type': 'integer',
            'default': 20,
            'description': 'Items per page (max 100)'
        }
    ],
    'responses': {
        '200': {
            'description': 'List of conversations',
            'schema': {
                'type': 'object',
                'properties': {
                    'conversations': {
                        'type': 'array',
                        'items': {'$ref': '#/definitions/Conversation'}
                    },
                    'pagination': {
                        'type': 'object',
                        'properties': {
                            'page': {'type': 'integer'},
                            'per_page': {'type': 'integer'},
                            'total': {'type': 'integer'},
                            'pages': {'type': 'integer'}
                        }
                    }
                }
            }
        }
    }
})
def list_conversations():
    """Get paginated list of conversations with filters."""
    try:
        # Get query parameters
        chatbot_id = request.args.get('chatbot_id', type=int)
        status = request.args.get('status', 'active')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)

        # Build query with tenant filtering
        # Convert tenant UUID to integer ID for database query
        from ..models import Tenant
        tenant = Tenant.query.filter_by(tenant_id=g.user_tenant_id).first()
        if not tenant:
            current_app.logger.error(f"Tenant not found for UUID: {g.user_tenant_id}")
            return jsonify({'error': 'Tenant not found'}), 404

        tenant_integer_id = tenant.id
        query = Conversation.query.filter_by(tenant_id=tenant_integer_id)

        # Debug: Count total conversations for this tenant
        total_conversations = query.count()
        current_app.logger.info(f"🔍 Total conversations for tenant: {total_conversations}")

        # Apply filters
        if chatbot_id:
            current_app.logger.info(f"🔍 Filtering by chatbot_id: {chatbot_id}")
            # Verify chatbot belongs to user's tenant
            chatbot = Chatbot.query.filter_by(id=chatbot_id, tenant_id=tenant_integer_id).first()
            if not chatbot:
                current_app.logger.warning(f"🔍 Chatbot {chatbot_id} not found for tenant {g.user_tenant_id}")
                return jsonify({'error': 'Chatbot not found'}), 404
            query = query.filter_by(chatbot_id=chatbot_id)
            filtered_count = query.count()
            current_app.logger.info(f"🔍 Conversations for chatbot {chatbot_id}: {filtered_count}")

        if status:
            query = query.filter_by(status=status)

        if start_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                query = query.filter(Conversation.created_at >= start_dt)
            except ValueError:
                return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400

        if end_date:
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(Conversation.created_at < end_dt)
            except ValueError:
                return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400

        # Order by most recent first
        query = query.order_by(desc(Conversation.created_at))

        # Paginate
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

        conversations = []
        for conv in pagination.items:
            conv_dict = conv.to_dict()

            # Add chatbot name
            if conv.chatbot_id:
                chatbot = Chatbot.query.get(conv.chatbot_id)
                conv_dict['chatbot_name'] = chatbot.name if chatbot else 'Unknown'

            # Add latest message preview
            latest_message = conv.messages.order_by(desc(Message.created_at)).first()
            if latest_message:
                conv_dict['latest_message'] = {
                    'content': latest_message.content[:100] + '...' if len(latest_message.content) > 100 else latest_message.content,
                    'message_type': latest_message.message_type,
                    'created_at': latest_message.created_at.isoformat()
                }

            conversations.append(conv_dict)

        current_app.logger.info(f"🔍 Returning {len(conversations)} conversations to frontend")
        current_app.logger.info(f"🔍 Pagination: page={pagination.page}, total={pagination.total}")

        return jsonify({
            'success': True,
            'conversations': conversations,
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error listing conversations: {str(e)}")
        return jsonify({'error': 'Failed to fetch conversations'}), 500


@api.route('/conversations/debug', methods=['GET'])
@login_required
@swag_from({
    'tags': ['Conversations'],
    'summary': 'Debug conversation storage',
    'description': 'Debug endpoint to check conversation and message counts',
    'responses': {
        '200': {
            'description': 'Debug information',
            'schema': {
                'type': 'object',
                'properties': {
                    'tenant_id': {'type': 'integer'},
                    'total_conversations': {'type': 'integer'},
                    'total_messages': {'type': 'integer'},
                    'conversations_by_chatbot': {'type': 'object'},
                    'recent_conversations': {'type': 'array'}
                }
            }
        }
    }
})
def debug_conversations():
    """Debug endpoint to check conversation storage"""
    try:
        from ..models import Message

        tenant_id = g.user_tenant_id

        # Count total conversations for this tenant
        total_conversations = Conversation.query.filter_by(tenant_id=tenant_id).count()

        # Count total messages for this tenant
        total_messages = db.session.query(Message).join(Conversation).filter(
            Conversation.tenant_id == tenant_id
        ).count()

        # Count conversations by chatbot
        conversations_by_chatbot = {}
        chatbots = Chatbot.query.filter_by(tenant_id=tenant_id).all()
        for chatbot in chatbots:
            count = Conversation.query.filter_by(
                tenant_id=tenant_id,
                chatbot_id=chatbot.id
            ).count()
            conversations_by_chatbot[f"{chatbot.name} (ID: {chatbot.id})"] = count

        # Get recent conversations
        recent_conversations = []
        recent_convs = Conversation.query.filter_by(tenant_id=tenant_id).order_by(
            desc(Conversation.created_at)
        ).limit(5).all()

        for conv in recent_convs:
            chatbot = Chatbot.query.get(conv.chatbot_id)
            recent_conversations.append({
                'id': conv.id,
                'title': conv.title,
                'chatbot_name': chatbot.name if chatbot else 'Unknown',
                'session_id': conv.session_id,
                'user_id': conv.user_id,
                'message_count': conv.messages.count(),
                'created_at': conv.created_at.isoformat()
            })

        return jsonify({
            'success': True,
            'tenant_id': tenant_id,
            'total_conversations': total_conversations,
            'total_messages': total_messages,
            'conversations_by_chatbot': conversations_by_chatbot,
            'recent_conversations': recent_conversations
        })

    except Exception as e:
        current_app.logger.error(f"Error in debug endpoint: {str(e)}")
        return jsonify({'error': 'Debug failed'}), 500


@api.route('/conversations/<int:conversation_id>', methods=['GET'], endpoint='get_conversation')
def get_conversation(conversation_id):
    """Get a single conversation by ID. Public endpoint for validation."""
    try:
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404

        return jsonify({
            'conversation': {
                'id': conversation.id,
                'status': conversation.status,
                'title': conversation.title,
                'chatbot_id': conversation.chatbot_id,
                'created_at': conversation.created_at.isoformat() if conversation.created_at else None
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"❌ Error getting conversation {conversation_id}: {e}")
        return jsonify({'error': 'Failed to get conversation'}), 500


@api.route('/conversations/<int:conversation_id>/messages', methods=['GET'], endpoint='get_conversation_messages')
@login_required
@swag_from({
    'tags': ['Conversations'],
    'summary': 'Get conversation messages',
    'description': 'Get all messages in a specific conversation',
    'parameters': [
        {
            'name': 'conversation_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'Conversation ID'
        }
    ],
    'responses': {
        '200': {
            'description': 'Conversation messages',
            'schema': {
                'type': 'object',
                'properties': {
                    'conversation': {'$ref': '#/definitions/Conversation'},
                    'messages': {
                        'type': 'array',
                        'items': {'$ref': '#/definitions/Message'}
                    }
                }
            }
        },
        '404': {
            'description': 'Conversation not found'
        }
    }
})
def get_conversation_messages(conversation_id):
    """Get all messages in a conversation."""
    try:
        current_app.logger.info(f"Fetching messages for conversation {conversation_id}")
        current_app.logger.info(f"User tenant ID: {getattr(g, 'user_tenant_id', 'None')}")

        # Get conversation - temporarily remove tenant verification for debugging
        conversation = Conversation.query.filter_by(id=conversation_id).first()

        if not conversation:
            current_app.logger.error(f"Conversation {conversation_id} not found")
            return jsonify({'error': 'Conversation not found'}), 404

        current_app.logger.info(f"Found conversation: {conversation.title}, tenant: {conversation.tenant_id}")

        # Get messages ordered chronologically
        messages = Message.query.filter_by(
            conversation_id=conversation_id
        ).order_by(Message.created_at).all()

        current_app.logger.info(f"Found {len(messages)} messages")

        # Convert to dict
        messages_data = []
        for msg in messages:
            try:
                msg_dict = msg.to_dict()
                messages_data.append(msg_dict)
            except Exception as msg_error:
                current_app.logger.error(f"Error converting message {msg.id} to dict: {msg_error}")
                raise msg_error

        # Convert conversation to dict
        try:
            conversation_dict = conversation.to_dict()
        except Exception as conv_error:
            current_app.logger.error(f"Error converting conversation to dict: {conv_error}")
            raise conv_error

        return jsonify({
            'success': True,
            'conversation': conversation_dict,
            'messages': messages_data
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching conversation messages: {str(e)}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Failed to fetch messages: {str(e)}'}), 500


@api.route('/conversations/<int:conversation_id>/messages/public', methods=['GET'], endpoint='get_conversation_messages_public')
@swag_from({
    'tags': ['Conversations'],
    'summary': 'Get conversation messages (public)',
    'description': 'Get all messages in a specific conversation. Public endpoint for embeds.',
    'parameters': [
        {
            'name': 'conversation_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'Conversation ID'
        }
    ],
    'responses': {
        '200': {
            'description': 'Conversation messages',
            'schema': {
                'type': 'object',
                'properties': {
                    'conversation': {'$ref': '#/definitions/Conversation'},
                    'messages': {
                        'type': 'array',
                        'items': {'$ref': '#/definitions/Message'}
                    }
                }
            }
        },
        '404': {
            'description': 'Conversation not found'
        }
    }
})
def get_conversation_messages_public(conversation_id):
    """Get all messages in a conversation (public endpoint for embeds)."""
    try:
        current_app.logger.info(f"📥 Public: Fetching messages for conversation {conversation_id}")

        # Get conversation
        conversation = Conversation.query.filter_by(id=conversation_id).first()

        if not conversation:
            current_app.logger.error(f"❌ Conversation {conversation_id} not found")
            return jsonify({'error': 'Conversation not found'}), 404

        # Allow access to conversations that came from an embed (have source_domain)
        # or were created without a user_id (embed conversations).
        is_embed = getattr(conversation, 'source_domain', None) or not conversation.user_id
        if not is_embed:
            current_app.logger.error(f"❌ Conversation {conversation_id} is not an embed conversation")
            return jsonify({'error': 'Access denied'}), 403

        current_app.logger.info(f"✅ Found embed conversation: {conversation.title}")

        # Get messages ordered chronologically
        messages = Message.query.filter_by(
            conversation_id=conversation_id
        ).order_by(Message.created_at).all()

        current_app.logger.info(f"📨 Found {len(messages)} messages")

        # Convert to dict
        messages_data = []
        for msg in messages:
            try:
                msg_dict = msg.to_dict()
                messages_data.append(msg_dict)
            except Exception as msg_error:
                current_app.logger.error(f"❌ Error converting message {msg.id} to dict: {msg_error}")
                raise msg_error

        return jsonify({
            'success': True,
            'messages': messages_data
        })

    except Exception as e:
        current_app.logger.error(f"❌ Error fetching conversation messages: {str(e)}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Failed to fetch messages: {str(e)}'}), 500


@api.route('/conversations/<int:conversation_id>/messages', methods=['POST'], endpoint='send_message')
@rate_limit(120, 60)
@swag_from({
    'tags': ['Conversations'],
    'summary': 'Send a message to a conversation',
    'description': 'Send a message and get AI response. Supports both JSON and SSE streaming. Public endpoint for embeds.',
    'parameters': [
        {
            'name': 'conversation_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'Conversation ID'
        },
        {
            'name': 'Accept',
            'in': 'header',
            'type': 'string',
            'description': 'Set to "text/event-stream" for progressive response streaming'
        },
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['content', 'chatbot_id'],
                'properties': {
                    'content': {'type': 'string'},
                    'chatbot_id': {'type': 'integer'}
                }
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'Message sent and AI response generated (JSON or SSE stream)',
            'schema': {
                'type': 'object',
                'properties': {
                    'user_message': {'$ref': '#/definitions/Message'},
                    'assistant_message': {'$ref': '#/definitions/Message'}
                }
            }
        },
        '404': {'description': 'Conversation not found'}
    }
})
def send_message(conversation_id):
    """Send a message to a conversation and get AI response. Supports streaming via SSE."""

    # Check if client wants streaming
    accept_header = request.headers.get('Accept', '')
    wants_streaming = 'text/event-stream' in accept_header

    if wants_streaming:
        current_app.logger.info(f"🌊 Streaming mode requested for conversation {conversation_id}")
        return send_message_stream(conversation_id)
    else:
        current_app.logger.info(f"📦 Standard JSON mode for conversation {conversation_id}")
        return send_message_json(conversation_id)


def send_message_json(conversation_id):
    """Original non-streaming JSON response."""
    try:
        data = request.get_json() or {}
        content = data.get('content', '').strip()
        chatbot_id = data.get('chatbot_id')

        if not content:
            return jsonify({'error': 'Message content is required'}), 400
        if not chatbot_id:
            return jsonify({'error': 'chatbot_id is required'}), 400

        # Get conversation and verify it exists
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404

        # Get chatbot and verify it exists
        chatbot = Chatbot.query.get(chatbot_id)
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404

        # Verify conversation belongs to the chatbot
        if conversation.chatbot_id != chatbot_id:
            return jsonify({'error': 'Conversation does not belong to this chatbot'}), 400

        # Create user message
        user_message = Message(
            conversation_id=conversation_id,
            content=content,
            message_type='user',
            created_at=datetime.utcnow()
        )
        db.session.add(user_message)

        # Initialize conversation service for greeting/farewell detection
        from ..services.conversation_service import ConversationService
        conversation_service = ConversationService()

        # Generate AI response
        start_time = time.time()
        try:
            # Check if this is a greeting or farewell message
            is_greeting = conversation_service.is_greeting(content)

            # Get last assistant message for smart farewell detection
            last_assistant_msg = ""
            try:
                last_msg = Message.query.filter_by(
                    conversation_id=conversation_id,
                    message_type='assistant'
                ).order_by(Message.created_at.desc()).first()
                if last_msg:
                    last_assistant_msg = last_msg.content or ""
            except Exception:
                pass
            is_farewell = conversation_service.is_smart_farewell(content, last_assistant_msg)

            # Detect conversation ending
            if is_farewell:
                conversation_service.detect_conversation_ending(content, conversation_id, last_assistant_msg)

            # === EARLY EXIT: farewell gets rating INSTANTLY, skip RAG/LLM ===
            if is_farewell:
                config = chatbot.config or {}
                content_lower = content.lower()
                if 'thank' in content_lower:
                    rating_message = "You're welcome! How would you rate our conversation?"
                elif any(word in content_lower for word in ['bye', 'goodbye']):
                    rating_message = "Thanks for chatting! How was your experience?"
                elif any(word in content_lower for word in ['done', 'finish']):
                    rating_message = "Great! Before you go, how would you rate our chat?"
                else:
                    rating_message = "How would you rate your experience with me today?"

                farewell_response = conversation_service.get_farewell_response(config)
                return jsonify({
                    'success': True,
                    'response': farewell_response,
                    'message': 'Message processed successfully',
                    'show_rating': True,
                    'rating_message': rating_message,
                    'conversation_id': conversation_id
                })

            # === REST OF RAG/LLM ONLY FOR NON-FAREWELL MESSAGES ===
            # Get context from processed chunks stored in database/vector store
            context_text = ""

            try:
                current_app.logger.info(f"🔍 Vector search for: '{content}' in chatbot {chatbot_id}")

                # Use proper vector search instead of manual keyword matching
                if hasattr(current_app, 'vector_service') and current_app.vector_service:
                    # Get top_k from chatbot config (resolved through the
                    # single source of truth so .env defaults apply).
                    config = chatbot.config or {}
                    top_k = chatbot_defaults.resolve_field(config, 'top_k')

                    # Perform semantic vector search
                    search_results = current_app.vector_service.search_similar(
                        query=content,
                        chatbot_id=chatbot_id,
                        limit=top_k
                    )

                    current_app.logger.info(f"🔍 Vector search returned {len(search_results)} results for chatbot {chatbot_id}")

                    if search_results:
                        # === DETAILED RAG RETRIEVAL LOGGING ===
                        # Log every retrieved chunk with its source, score, and content
                        # preview so we can verify retrieval is correct for this query.
                        current_app.logger.info(
                            f"📚 RAG RETRIEVAL: {len(search_results)} chunks for query "
                            f"'{content[:80]}' (chatbot_id={chatbot_id})"
                        )
                        for idx, result in enumerate(search_results, 1):
                            if hasattr(result, 'page_content'):
                                chunk_content = result.page_content or ''
                                metadata = getattr(result, 'metadata', {}) or {}
                                score = (
                                    getattr(result, 'score', None)
                                    or metadata.get('score')
                                    or metadata.get('distance')
                                )
                            else:
                                chunk_content = result.get('page_content', '') or ''
                                metadata = result.get('metadata', {}) or {}
                                score = (
                                    result.get('score')
                                    or metadata.get('score')
                                    or metadata.get('distance')
                                )
                            source = (
                                metadata.get('source')
                                or metadata.get('url')
                                or metadata.get('file_name')
                                or metadata.get('doc_id')
                                or 'unknown'
                            )
                            current_app.logger.info(
                                f"   [{idx}] source={source!r} "
                                f"score={score!r} "
                                f"len={len(chunk_content)} "
                                f"preview={chunk_content[:120]!r}"
                            )
                        # === END RETRIEVAL LOGGING ===

                        # Extract content from search results, deduplicating
                        # identical chunks (same source + doc_id + chunk_index
                        # + content prefix) so the LLM does not see the
                        # same paragraph repeated 4x.
                        context_chunks = []
                        seen_keys = set()
                        for result in search_results:
                            chunk_content = getattr(result, 'page_content', '') if hasattr(result, 'page_content') else result.get('page_content', '')
                            if not chunk_content:
                                continue
                            metadata = getattr(result, 'metadata', None) or {}
                            if not isinstance(metadata, dict):
                                metadata = {}
                            dedup_key = (
                                metadata.get('source', ''),
                                metadata.get('doc_id', ''),
                                metadata.get('chunk_index', -1),
                                chunk_content[:80],
                            )
                            if dedup_key in seen_keys:
                                continue
                            seen_keys.add(dedup_key)
                            context_chunks.append(chunk_content)

                        context_text = "\n\n".join(context_chunks)
                        current_app.logger.info(
                            f"🔍 Vector search: {len(search_results)} retrieved -> "
                            f"{len(context_chunks)} unique chunks, "
                            f"context length: {len(context_text)}"
                        )
                    else:
                        current_app.logger.info(f"🔍 Vector search found no matching chunks")
                else:
                    current_app.logger.warning(f"🔍 Vector service not available")

            except Exception as e:
                current_app.logger.error(f"Vector search failed: {e}")
                context_text = ""

            # Get chatbot configuration for knowledge base restriction
            config = chatbot.config or {}
            # Check if we should restrict to knowledge base based on mode and message type
            restrict_to_knowledge_base = conversation_service.should_restrict_to_knowledge_base(content, config)

            current_app.logger.info(f"🔍 Database chunk search: context length: {len(context_text)}")
            current_app.logger.info(f"🔍 Context text preview: {repr(context_text[:200])}...")
            current_app.logger.info(f"🔒 Knowledge base restriction enabled: {restrict_to_knowledge_base}")

            # Check if we have relevant context from the knowledge base
            current_app.logger.info(f"🔍 Checking fallback condition: restrict={restrict_to_knowledge_base}, context_empty={not context_text}, context_strip_empty={not context_text.strip() if context_text else True}")
            if restrict_to_knowledge_base and (not context_text or not context_text.strip() or not _context_has_meaningful_content(context_text) or not _context_relevant_to_query(context_text, content)):
                current_app.logger.warning(f"🔍 FALLBACK TRIGGERED: No context found for query: '{content}' in chatbot {chatbot_id}")

                # No broader search needed with simple text search approach

                # If still no context after broader search, return fallback message
                if not context_text or not context_text.strip() or not _context_has_meaningful_content(context_text) or not _context_relevant_to_query(context_text, content):
                    # Check if this is strict mode for better messaging
                    mode = config.get('mode', 'strict')
                    if mode == 'strict':
                        fallback_message = config.get('prompts', {}).get('fallback',
                                                                         "I'm sorry, I don't have that information available right now. Could you try rephrasing your question, or say hello to get started?"
                                                                         )
                    else:
                        fallback_message = config.get('prompts', {}).get('fallback',
                                                                         "I don't have that specific information on hand. Could you try rephrasing your question, or I can connect you with our team for more details."
                                                                         )

                    # Create assistant message with fallback
                    response_time = time.time() - start_time
                    fallback_model_name = config.get('ai_model')
                    if not fallback_model_name:
                        try:
                            from ..services.model_resolver import resolve_model
                            fallback_model_name, _ = resolve_model(config)
                        except ValueError:
                            fallback_model_name = None
                    assistant_message = Message(
                        conversation_id=conversation_id,
                        content=fallback_message,
                        message_type='assistant',
                        model_used=fallback_model_name,
                        provider=config.get('ai_provider'),
                        response_time=response_time,
                        created_at=datetime.utcnow()
                    )
                    db.session.add(assistant_message)
                    db.session.commit()

                    return jsonify({
                        'success': True,
                        'user_message': user_message.to_dict(),
                        'assistant_message': assistant_message.to_dict()
                    })
                # If broader search found context, continue with normal processing

            # Get chatbot configuration (already loaded above)
            try:
                from ..services.model_resolver import resolve_model
                ai_model, ai_provider = resolve_model(config)
            except ValueError:
                ai_model = config.get('ai_model')
                ai_provider = config.get('ai_provider')
            temperature = chatbot_defaults.resolve_field(config, 'temperature')

            # Build enhanced system message with chatbot personality + RAG mode
            personality = config.get('personality', {})
            prompts = config.get('prompts', {})

            system_message = prompts.get('system_message', '')
            if not system_message and personality:
                role = personality.get('role', 'AI Assistant')
                tone = personality.get('tone', 'helpful and professional')
                style = personality.get('style', 'clear and concise')
                system_message = f"You are a {role}. Respond in a {tone} manner with a {style} style."

            # All RAG / mode / language logic now lives in prompts.yml
            from ..services.prompt_service import PromptService
            prompt_svc = PromptService()

            _mode = config.get('mode', 'strict')  # noqa: F841
            target_lang = 'auto'
            chatbot_name = config.get('name', 'this chatbot')
            chatbot_role = personality.get('role', 'AI Assistant')

            if restrict_to_knowledge_base:
                if context_text and context_text.strip() and _context_has_meaningful_content(context_text) and _context_relevant_to_query(context_text, content):
                    full_system_message = system_message + "\n\n" + prompt_svc.render(
                        'rag_system.strict',
                        chatbot_name=chatbot_name,
                        chatbot_role=chatbot_role,
                        target_lang=target_lang,
                        context=context_text,
                    )
                else:
                    full_system_message = system_message + "\n\n" + prompt_svc.render(
                        'rag_system.out_of_scope',
                        chatbot_name=chatbot_name,
                        chatbot_role=chatbot_role,
                        target_lang=target_lang,
                        context='',
                        refusal_message="I'm sorry, but I can't find an answer to your question right now.",
                    )
            else:
                full_system_message = system_message + "\n\n" + prompt_svc.render(
                    'rag_system.permissive',
                    chatbot_name=chatbot_name,
                    chatbot_role=chatbot_role,
                    target_lang=target_lang,
                    context=context_text or '',
                )

            history_messages = Message.query.filter_by(
                conversation_id=conversation_id
            ).order_by(Message.created_at.desc()).limit(20).all()
            history_messages.reverse()

            messages = [
                {"role": "system", "content": full_system_message},
            ]
            for hmsg in history_messages:
                role = 'assistant' if hmsg.message_type == 'assistant' else 'user'
                messages.append({"role": role, "content": hmsg.content or ''})
            messages.append({"role": "user", "content": content})

            # === LLM CALL LOGGING ===
            # Log exactly what we are about to send to the model so we can
            # verify the RAG prompt and context are correct for each query.
            current_app.logger.info(
                f"🤖 LLM CALL: chatbot={chatbot_id} "
                f"mode={config.get('mode', 'strict')} "
                f"restrict_to_kb={restrict_to_knowledge_base} "
                f"history_msgs={len(messages) - 1} "
                f"system_prompt_len={len(full_system_message)}"
            )
            current_app.logger.info(
                f"📤 SYSTEM PROMPT SENT TO LLM (first 800 chars):\n"
                f"{full_system_message[:800]}"
            )
            current_app.logger.info(
                f"📤 USER MESSAGE SENT TO LLM: {content!r}"
            )
            if context_text:
                current_app.logger.info(
                    f"📦 CONTEXT SENT TO LLM ({len(context_text)} chars total, "
                    f"first 600 chars):\n{context_text[:600]}"
                )
            else:
                current_app.logger.info("📦 CONTEXT SENT TO LLM: (empty)")
            # === END LLM CALL LOGGING ===

            # Handle greetings — farewell is handled via early-exit above
            if is_greeting:
                ai_response = conversation_service.get_greeting_response(config)
                current_app.logger.info(f"👋 Greeting detected, using custom response")
            else:
                # Generate normal AI response
                ai_response = ""
                if current_app.llm_service:
                    try:
                        # For strict-mode refusals (no KB context found), force
                        # temperature=0.0 and cap max_tokens. This stops the
                        # LLM from leaking training-data hints (e.g.
                        # "However, I think you might be referencing...").
                        if (restrict_to_knowledge_base
                                and not (context_text and context_text.strip())):
                            call_config = dict(config)
                            call_config['temperature'] = 0.0
                            call_config['max_tokens'] = min(
                                int(call_config.get('max_tokens') or 256),
                                120
                            )
                            current_app.logger.info(
                                "🔒 Strict refusal path - forcing "
                                f"temperature=0.0, max_tokens={call_config['max_tokens']}"
                            )
                        else:
                            call_config = config

                        response_data = current_app.llm_service.generate_for_chatbot(
                            messages=messages,
                            chatbot_config=call_config,
                            user_id=str(getattr(g, 'user_id', 'anonymous')),
                            tenant_id=str(chatbot.tenant_id)
                        )
                        ai_response = response_data.get('content', '') if response_data else ''
                    except Exception as e:
                        current_app.logger.error(f"LLM generation failed: {e}")
                        ai_response = "I apologize, but I'm having trouble generating a response right now. Please try again."
                else:
                    # Provide a helpful demo response when service is unavailable
                    current_app.logger.warning("LLM service not available - using demo response")
                    ai_response = f"""Hello! This is a demo response.

The AI service is currently not configured with valid API keys. To enable full functionality:

1. Set OPENAI_API_KEY in your environment variables
2. Set GEMINI_API_KEY in your environment variables
3. Restart the Flask application

Your message was: "{content}"

This chatbot is configured to use the {ai_model} model."""

            # Calculate response time
            response_time = time.time() - start_time if 'start_time' in locals() else None

            # Create assistant message with full metadata
            assistant_message = Message(
                conversation_id=conversation_id,
                content=ai_response,
                message_type='assistant',
                model_used=ai_model,
                provider=ai_provider,
                response_time=response_time,
                token_count=None,  # TODO: Add token counting if needed
                sources=None,  # TODO: Add source tracking if needed
                confidence_score=None,  # TODO: Add confidence scoring if needed
                created_at=datetime.utcnow()
            )
            db.session.add(assistant_message)
            db.session.commit()

            # Analyze user intent for conversation ending using GPT-4o with confirmation flow
            # OPTIMIZATION: Only run intent analysis if farewell detected to avoid slowness
            show_rating = False
            rating_message = 'How would you rate your experience?'
            ask_confirmation = False

            try:
                if is_farewell and hasattr(current_app, 'intent_analysis_service') and current_app.intent_analysis_service:
                    # Get recent messages for context (last 6 messages for better pattern detection)
                    recent_messages = Message.query.filter_by(conversation_id=conversation_id)\
                        .order_by(Message.created_at.desc())\
                        .limit(6)\
                        .all()

                    # Build conversation context as list of dicts (correct format)
                    messages_list = []
                    for msg in reversed(recent_messages):  # Reverse to get chronological order
                        messages_list.append({
                            'message_type': msg.message_type,
                            'content': msg.content
                        })

                    # Analyze intent with correct signature: (messages, user_message)
                    intent_result = current_app.intent_analysis_service.analyze_conversation_intent(messages_list, content)

                    # Check for direct rating trigger
                    if intent_result.get('should_show_rating', False):
                        show_rating = True
                        confidence = intent_result.get('confidence', 0.0)
                        patterns = intent_result.get('detected_patterns', [])

                        # Create a personalized rating message
                        if patterns:
                            if any('thank' in p.lower() for p in patterns):
                                rating_message = "You're welcome! How would you rate our conversation?"
                            elif any('bye' in p.lower() or 'goodbye' in p.lower() for p in patterns):
                                rating_message = "Thanks for chatting! How was your experience?"
                            elif any('done' in p.lower() or 'finish' in p.lower() for p in patterns):
                                rating_message = "Great! Before you go, how would you rate our chat?"
                            else:
                                rating_message = "How would you rate your experience with me today?"

                        current_app.logger.info(f"🌟 Intent analysis triggered rating: confidence={confidence:.2f}, patterns={patterns}")

                        # Mark conversation as ended
                        conversation = Conversation.query.get(conversation_id)
                        if conversation:
                            conversation.conversation_ended = True
                            db.session.commit()

                    # Check for confirmation flow
                    elif intent_result.get('should_ask_confirmation', False):
                        ask_confirmation = True
                        confidence = intent_result.get('confidence', 0.0)
                        confirmation_message = intent_result.get('confirmation_message', 'Is there anything else I can help you with today?')

                        current_app.logger.info(f"🤔 Intent analysis suggests asking confirmation: confidence={confidence:.2f}")

                        # Override the AI response with confirmation question
                        ai_response = confirmation_message
                        assistant_message.content = ai_response
                        db.session.commit()

                    else:
                        current_app.logger.info(f"🧠 Intent analysis: continue conversation - {intent_result.get('reason', 'Unknown')}")
                else:
                    current_app.logger.warning("⚠️ Intent analysis service not available")

            except Exception as e:
                current_app.logger.error(f"❌ Error in intent analysis: {e}")

            # FALLBACK: If intent analysis didn't set show_rating but farewell
            # was detected, still trigger rating. This ensures rating appears
            # even when intent analysis service is unavailable or errors.
            if not show_rating and is_farewell:
                conversation_service.detect_conversation_ending(content, conversation_id, last_assistant_msg)
                show_rating = True
                content_lower = content.lower()
                if 'thank' in content_lower:
                    rating_message = "You're welcome! How would you rate our conversation?"
                elif any(w in content_lower for w in ['bye', 'goodbye']):
                    rating_message = "Thanks for chatting! How was your experience?"
                elif any(w in content_lower for w in ['done', 'finish']):
                    rating_message = "Great! Before you go, how would you rate our chat?"
                else:
                    rating_message = "How would you rate your experience with me today?"
                current_app.logger.info(f"🌟 [FALLBACK] Farewell detected, showing rating")

            response_data = {
                'success': True,
                'user_message': user_message.to_dict(),
                'assistant_message': assistant_message.to_dict()
            }

            # Add rating prompt if conversation just ended
            if show_rating:
                response_data['show_rating'] = True
                response_data['rating_message'] = rating_message

            # Add confirmation flag if we asked a confirmation question
            if ask_confirmation:
                response_data['ask_confirmation'] = True

            return jsonify(response_data)

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error generating AI response: {e}")
            return jsonify({'error': 'Failed to generate AI response'}), 500

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error sending message: {e}")
        return jsonify({'error': 'Failed to send message'}), 500


def send_message_stream(conversation_id):
    """Streaming version of send_message using Server-Sent Events."""
    def generate():
        try:
            # Start timing for response time calculation
            start_time = time.time()

            data = request.get_json() or {}
            content = data.get('content', '').strip()
            chatbot_id = data.get('chatbot_id')

            if not content or not chatbot_id:
                yield f"data: {json.dumps({'error': 'Invalid request'})}\n\n"
                return

            # Get conversation and chatbot
            conversation = Conversation.query.get(conversation_id)
            chatbot = Chatbot.query.get(chatbot_id) if conversation else None

            if not conversation or not chatbot:
                yield f"data: {json.dumps({'error': 'Not found'})}\n\n"
                return

            # Save user message to database
            user_message = Message(
                conversation_id=conversation_id,
                content=content,
                message_type='user',
                created_at=datetime.utcnow()
            )
            db.session.add(user_message)
            db.session.commit()

            # Generate AI response with knowledge base search
            from ..services.conversation_service import ConversationService
            conversation_service = ConversationService()

            is_greeting = conversation_service.is_greeting(content)

            # Get last assistant message for smart farewell detection
            last_assistant_msg = ""
            try:
                last_msg = Message.query.filter_by(
                    conversation_id=conversation_id,
                    message_type='assistant'
                ).order_by(Message.created_at.desc()).first()
                if last_msg:
                    last_assistant_msg = last_msg.content or ""
            except Exception:
                pass
            is_farewell = conversation_service.is_smart_farewell(content, last_assistant_msg)

            # Detect conversation ending
            if is_farewell:
                conversation_service.detect_conversation_ending(content, conversation_id, last_assistant_msg)

            # === EARLY EXIT: farewell gets rating INSTANTLY, skip RAG/LLM ===
            if is_farewell:
                config = chatbot.config or {}
                content_lower = content.lower()
                if 'thank' in content_lower:
                    rating_message = "You're welcome! How would you rate our conversation?"
                elif any(word in content_lower for word in ['bye', 'goodbye']):
                    rating_message = "Thanks for chatting! How was your experience?"
                elif any(word in content_lower for word in ['done', 'finish']):
                    rating_message = "Great! Before you go, how would you rate our chat?"
                else:
                    rating_message = "How would you rate your experience with me today?"

                rating_data = {
                    'show_rating': True,
                    'rating_message': rating_message,
                    'conversation_id': conversation_id
                }
                yield f"data: {json.dumps({'type': 'rating', 'data': rating_data})}\n\n"
                current_app.logger.info(f"🌟 [STREAM] Sent rating INSTANTLY: {rating_message}")

                farewell_response = conversation_service.get_farewell_response(config)
                for chunk in stream_response_chunks(farewell_response, chunk_size=1, delay=0.005):
                    yield chunk
                return

            # === REST OF RAG/LLM ONLY FOR NON-FAREWELL MESSAGES ===
            # Get AI configuration
            config = chatbot.config or {}
            try:
                from ..services.model_resolver import resolve_model
                ai_model, ai_provider = resolve_model(config)
            except ValueError:
                ai_model = config.get('ai_model') or config.get('model')
                ai_provider = config.get('ai_provider')

            # Search knowledge base for context
            context_text = ""
            try:
                if hasattr(current_app, 'vector_service') and current_app.vector_service:
                    # Get top_k from chatbot config (resolved through the
                    # single source of truth so .env defaults apply).
                    top_k = chatbot_defaults.resolve_field(config, 'top_k')

                    # Perform semantic vector search
                    search_results = current_app.vector_service.search_similar(
                        query=content,
                        chatbot_id=chatbot.id,
                        limit=top_k
                    )

                    current_app.logger.info(f"🔍 [STREAM] Vector search found {len(search_results)} results")

                    if search_results:
                        # Extract content from search results
                        context_chunks = []
                        for idx, result in enumerate(search_results):
                            chunk_content = getattr(result, 'page_content', '') if hasattr(result, 'page_content') else result.get('page_content', '')
                            if chunk_content:
                                context_chunks.append(chunk_content)
                                current_app.logger.info(f"🔍 [STREAM] Chunk {idx+1} preview: {chunk_content[:150]}...")

                        context_text = "\n\n".join(context_chunks)
                        current_app.logger.info(f"🔍 [STREAM] Found {len(context_chunks)} matching chunks, total context length: {len(context_text)}")
                        current_app.logger.info(f"🔍 [STREAM] Full context preview (first 500 chars): {context_text[:500]}")
                else:
                    current_app.logger.warning(f"🔍 [STREAM] Vector service not available")

            except Exception as e:
                current_app.logger.error(f"[STREAM] Vector search failed: {e}")
                context_text = ""

            # Determine restriction based on chatbot mode
            restrict_to_knowledge_base = conversation_service.should_restrict_to_knowledge_base(content, config)

            current_app.logger.info(f"🌊 [STREAM] Mode: {config.get('mode', 'strict')}, Restrict: {restrict_to_knowledge_base}, Has context: {bool(context_text)}")

            # Build system message with knowledge base context
            personality = config.get('personality', {})
            prompts = config.get('prompts', {})
            system_message = prompts.get('system_message', '')
            if not system_message and personality:
                role = personality.get('role', 'AI Assistant')
                tone = personality.get('tone', 'helpful and professional')
                style = personality.get('style', 'clear and concise')
                system_message = f"You are a {role}. Respond in a {tone} manner with a {style} style."

            # All RAG / mode / language logic now lives in prompts.yml
            from ..services.prompt_service import PromptService
            prompt_svc = PromptService()

            _mode = config.get('mode', 'strict')  # noqa: F841
            target_lang = 'auto'
            chatbot_name = config.get('name', 'this chatbot')
            chatbot_role = personality.get('role', 'AI Assistant')

            if restrict_to_knowledge_base:
                if context_text and context_text.strip() and _context_has_meaningful_content(context_text) and _context_relevant_to_query(context_text, content):
                    full_system_message = system_message + "\n\n" + prompt_svc.render(
                        'rag_system.strict',
                        chatbot_name=chatbot_name,
                        chatbot_role=chatbot_role,
                        target_lang=target_lang,
                        context=context_text,
                    )
                    current_app.logger.info(f"🔒 [STREAM] STRICT MODE LOCKED - Using KB context (length: {len(context_text)})")
                else:
                    current_app.logger.info(f"🔒 [STREAM] STRICT MODE LOCKED - Context empty/garbage ({len(context_text) if context_text else 0} chars), refusing to answer")
                    full_system_message = system_message + "\n\n" + prompt_svc.render(
                        'rag_system.out_of_scope',
                        chatbot_name=chatbot_name,
                        chatbot_role=chatbot_role,
                        target_lang=target_lang,
                        context='',
                        refusal_message="I'm sorry, but I can't find an answer to your question in my database right now.",
                    )
            else:
                if context_text and context_text.strip():
                    full_system_message = system_message + "\n\n" + prompt_svc.render(
                        'rag_system.permissive',
                        chatbot_name=chatbot_name,
                        chatbot_role=chatbot_role,
                        target_lang=target_lang,
                        context=context_text,
                    )
                else:
                    full_system_message = system_message + "\n\n" + prompt_svc.render(
                        'rag_system.permissive',
                        chatbot_name=chatbot_name,
                        chatbot_role=chatbot_role,
                        target_lang=target_lang,
                        context='',
                    )

            # Build conversation history
            recent_messages = Message.query.filter_by(conversation_id=conversation_id)\
                .order_by(Message.created_at.desc())\
                .limit(10)\
                .all()

            messages = [{"role": "system", "content": full_system_message}]
            for msg in reversed(recent_messages[1:]):  # Skip the just-added user message
                role = "assistant" if msg.message_type == 'assistant' else "user"
                messages.append({"role": role, "content": msg.content})
            messages.append({"role": "user", "content": content})

            # === LLM CALL LOGGING (streaming) ===
            # Log the system prompt, user message, and context that we are
            # about to send to the LLM so retrieval / RAG issues are
            # diagnosable from the backend log.
            current_app.logger.info(
                f"🤖 LLM CALL (stream): chatbot={chatbot_id} "
                f"mode={config.get('mode', 'strict')} "
                f"restrict_to_kb={restrict_to_knowledge_base} "
                f"history_msgs={len(messages) - 1} "
                f"system_prompt_len={len(full_system_message)}"
            )
            current_app.logger.info(
                f"📤 SYSTEM PROMPT SENT TO LLM (first 800 chars):\n"
                f"{full_system_message[:800]}"
            )
            current_app.logger.info(
                f"📤 USER MESSAGE SENT TO LLM: {content!r}"
            )
            if context_text:
                current_app.logger.info(
                    f"📦 CONTEXT SENT TO LLM ({len(context_text)} chars total, "
                    f"first 600 chars):\n{context_text[:600]}"
                )
            else:
                current_app.logger.info("📦 CONTEXT SENT TO LLM: (empty)")
            # === END LLM CALL LOGGING ===

            # Generate AI response with real-time streaming
            # NOTE: farewell is handled via early-exit above — only greeting/LLM here
            ai_response = ""

            if is_greeting:
                ai_response = conversation_service.get_greeting_response(config)
                # Stream the greeting response
                for chunk in stream_response_chunks(ai_response, chunk_size=1, delay=0.005):
                    yield chunk
            elif current_app.llm_service:
                try:
                    # Use streaming generation from LLM service
                    accumulated_response = ""

                    # For strict-mode refusals (no KB context found), force
                    # temperature=0.0 and cap max_tokens. This stops the LLM
                    # from leaking training-data hints.
                    if (restrict_to_knowledge_base
                            and not (context_text and context_text.strip())):
                        call_config = dict(config)
                        call_config['temperature'] = 0.0
                        call_config['max_tokens'] = min(
                            int(call_config.get('max_tokens') or 256),
                            120
                        )
                        current_app.logger.info(
                            "🔒 [STREAM] Strict refusal path - forcing "
                            f"temperature=0.0, max_tokens={call_config['max_tokens']}"
                        )
                    else:
                        call_config = config

                    if hasattr(current_app.llm_service, 'generate_answer_stream'):
                        for chunk_data in current_app.llm_service.generate_answer_stream(
                            messages=messages,
                            model_name=ai_model,
                            user_id=str(getattr(g, 'user_id', 'anonymous')),
                            tenant_id=str(chatbot.tenant_id),
                            temperature=call_config.get('temperature', 0.3),
                            max_tokens=call_config.get('max_tokens', 256),
                        ):
                            chunk_content = chunk_data.get('content', '')
                            if chunk_content:
                                accumulated_response += chunk_content
                                yield f"data: {json.dumps({'content': chunk_content, 'accumulated': accumulated_response})}\n\n"
                    else:
                        response_data = current_app.llm_service.generate_for_chatbot(
                            messages=messages,
                            chatbot_config=call_config,
                            user_id=str(getattr(g, 'user_id', 'anonymous')),
                            tenant_id=str(chatbot.tenant_id)
                        )
                        ai_response = response_data.get('content', '') if response_data else ''
                        accumulated_response = ai_response

                        # Stream in chunks for better UX even if not real-time
                        for chunk in stream_response_chunks(ai_response, chunk_size=1, delay=0.005):
                            yield chunk

                    ai_response = accumulated_response

                except Exception as e:
                    current_app.logger.error(f"LLM error: {e}")
                    ai_response = "I apologize, but I'm having trouble generating a response right now."
                    for chunk in stream_response_chunks(ai_response, chunk_size=1, delay=0.005):
                        yield chunk
            else:
                ai_response = "AI service is currently not available. Please try again later."
                for chunk in stream_response_chunks(ai_response, chunk_size=1, delay=0.005):
                    yield chunk

            # Ensure ai_response is a string (not list or other type)
            if isinstance(ai_response, list):
                ai_response = ' '.join(str(item) for item in ai_response)
            elif not isinstance(ai_response, str):
                ai_response = str(ai_response)

            # Calculate response time
            response_time = time.time() - start_time

            # Save assistant message to database after streaming is complete
            assistant_message = Message(
                conversation_id=conversation_id,
                content=ai_response,
                message_type='assistant',
                model_used=ai_model,
                provider=ai_provider,
                response_time=response_time,
                created_at=datetime.utcnow()
            )
            db.session.add(assistant_message)
            db.session.commit()

            # Debug: Log that we saved response time
            current_app.logger.info(f"💾 Saved message with response_time: {response_time:.2f}s")

            current_app.logger.info(f"🌊 Streaming response: {len(ai_response)} chars, type: {type(ai_response)}")

        except Exception as e:
            current_app.logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
            'Connection': 'keep-alive'
        }
    )


@api.route('/conversations/<int:conversation_id>/feedback', methods=['POST'], endpoint='add_conversation_feedback')
@login_required
@swag_from({
    'tags': ['Conversations'],
    'summary': 'Add conversation feedback',
    'description': 'Add feedback/rating to a conversation',
    'parameters': [
        {
            'name': 'conversation_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'Conversation ID'
        },
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['feedback_type'],
                'properties': {
                    'feedback_type': {
                        'type': 'string',
                        'enum': ['thumbs_up', 'thumbs_down', 'rating', 'comment'],
                        'description': 'Type of feedback'
                    },
                    'rating': {
                        'type': 'integer',
                        'minimum': 1,
                        'maximum': 5,
                        'description': 'Rating (1-5 stars, required if feedback_type is rating)'
                    },
                    'feedback_text': {
                        'type': 'string',
                        'description': 'Optional feedback comment'
                    },
                    'message_id': {
                        'type': 'integer',
                        'description': 'Specific message ID if feedback is for a particular message'
                    }
                }
            }
        }
    ],
    'responses': {
        '201': {
            'description': 'Feedback added successfully',
            'schema': {'$ref': '#/definitions/ConversationFeedback'}
        },
        '404': {
            'description': 'Conversation not found'
        }
    }
})
def add_conversation_feedback(conversation_id):
    """Add feedback to a conversation."""
    try:
        data = request.get_json()

        if not data or 'feedback_type' not in data:
            return jsonify({'error': 'feedback_type is required'}), 400

        # Verify conversation exists and belongs to tenant
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            tenant_id=g.user_tenant_id
        ).first()

        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404

        # Validate rating if provided
        if data['feedback_type'] == 'rating':
            if 'rating' not in data or not (1 <= data['rating'] <= 5):
                return jsonify({'error': 'Rating must be between 1 and 5'}), 400

        # Create feedback record
        feedback_type = data['feedback_type']
        rating = data.get('rating')
        feedback = ConversationFeedback(
            conversation_id=conversation_id,
            message_id=data.get('message_id'),
            rating=rating,
            feedback_type=feedback_type,
            feedback_text=data.get('feedback_text'),
            user_id=g.user_id
        )

        db.session.add(feedback)
        db.session.commit()

        # Send notification for feedback (non-blocking)
        try:
            from ..services.notification_service import NotificationService
            notification_service = NotificationService()

            notification_service.send_feedback_notification(
                tenant_id=conversation.chatbot.tenant_id,
                chatbot_id=conversation.chatbot_id,
                conversation_id=conversation_id,
                feedback_type=feedback_type,
                rating=rating
            )
        except Exception as e:
            # Don't fail the feedback submission if notification fails
            current_app.logger.error(f"Failed to send feedback notification: {str(e)}")

        return jsonify({
            'success': True,
            'message': 'Feedback added successfully',
            'feedback': feedback.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding feedback: {str(e)}")
        return jsonify({'error': 'Failed to add feedback'}), 500


@api.route('/conversations/<int:conversation_id>/satisfaction', methods=['POST'])
@swag_from({
    'tags': ['Conversations'],
    'summary': 'Add satisfaction rating to conversation',
    'description': 'Add satisfaction rating when conversation ends',
    'parameters': [
        {
            'name': 'conversation_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'Conversation ID'
        },
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['rating'],
                'properties': {
                    'rating': {
                        'type': 'integer',
                        'minimum': 1,
                        'maximum': 5,
                        'description': 'Satisfaction rating (1-5 stars)'
                    },
                    'feedback': {
                        'type': 'string',
                        'description': 'Optional feedback comment'
                    }
                }
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'Satisfaction rating added successfully'
        },
        '400': {
            'description': 'Invalid rating or conversation not ended'
        },
        '404': {
            'description': 'Conversation not found'
        }
    }
})
def add_satisfaction_rating(conversation_id):
    """Add satisfaction rating to ended conversation."""
    try:
        data = request.get_json() or {}
        rating = data.get('rating')
        feedback = data.get('feedback', '')

        if not rating or not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({'error': 'Rating must be an integer between 1 and 5'}), 400

        # Get conversation and verify it exists
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404

        # Check if conversation has ended or if this is a rating submission that should end it
        if not conversation.conversation_ended:
            current_app.logger.info(f"🔍 Conversation {conversation_id} not marked as ended, but rating submitted - marking as ended now")
            # Mark conversation as ended when rating is submitted
            conversation.conversation_ended = True
            conversation.ended_at = datetime.utcnow()
            db.session.commit()
            current_app.logger.info(f"✅ Conversation {conversation_id} marked as ended for rating submission")

        # Allow re-feedback — overwrite previous rating if exists
        # (users may want to change their rating after re-thinking)

        # Add satisfaction rating using conversation service
        from ..services.conversation_service import ConversationService
        conversation_service = ConversationService()

        current_app.logger.info(f"🌟 Attempting to add rating {rating}/5 to conversation {conversation_id}")

        success = conversation_service.add_satisfaction_rating(conversation_id, rating, feedback)

        if success:
            # Verify the rating was saved
            updated_conversation = Conversation.query.get(conversation_id)
            current_app.logger.info(f"✅ Rating saved! Conversation {conversation_id} now has rating: {updated_conversation.satisfaction_rating}")

            return jsonify({
                'success': True,
                'message': 'Satisfaction rating added successfully',
                'rating': rating
            })
        else:
            current_app.logger.error(f"❌ Failed to save rating for conversation {conversation_id}")
            return jsonify({'error': 'Failed to add satisfaction rating'}), 500

    except Exception as e:
        current_app.logger.error(f"Error adding satisfaction rating: {e}")
        return jsonify({'error': 'Failed to add satisfaction rating'}), 500


@api.route('/conversations/<int:conversation_id>', methods=['DELETE'], endpoint='delete_conversation')
@login_required
@swag_from({
    'tags': ['Conversations'],
    'summary': 'Delete conversation',
    'description': 'Mark a conversation as deleted (soft delete)',
    'parameters': [
        {
            'name': 'conversation_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'Conversation ID'
        }
    ],
    'responses': {
        '200': {
            'description': 'Conversation deleted successfully'
        },
        '404': {
            'description': 'Conversation not found'
        }
    }
})
def delete_conversation(conversation_id):
    """Soft delete a conversation."""
    try:
        # Convert tenant UUID to integer ID for database query
        from ..models import Tenant
        tenant = Tenant.query.filter_by(tenant_id=g.user_tenant_id).first()
        if not tenant:
            current_app.logger.error(f"Tenant not found for UUID: {g.user_tenant_id}")
            return jsonify({'error': 'Tenant not found'}), 404

        tenant_integer_id = tenant.id

        # Get conversation with tenant verification
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            tenant_id=tenant_integer_id
        ).first()

        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404

        # Soft delete by marking as deleted
        conversation.status = 'deleted'
        conversation.updated_at = datetime.utcnow()

        db.session.commit()

        current_app.logger.info(f"✅ Soft deleted conversation {conversation_id}")

        return jsonify({
            'success': True,
            'message': 'Conversation deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting conversation: {str(e)}")
        return jsonify({'error': 'Failed to delete conversation'}), 500


@api.route('/conversations/<conversation_id>/status', methods=['PUT'])
@swag_from({
    'tags': ['Conversations'],
    'summary': 'Update conversation status',
    'description': 'Update the status of a conversation (e.g., mark as inactive when chat is cleared). Public endpoint for embed chats.',
    'parameters': [
        {
            'name': 'conversation_id',
            'in': 'path',
            'type': 'string',
            'required': True,
            'description': 'Conversation ID (can be integer ID or session ID)'
        },
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['status'],
                'properties': {
                    'status': {
                        'type': 'string',
                        'enum': ['active', 'inactive', 'archived'],
                        'description': 'New status for the conversation'
                    }
                }
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'Status updated successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'conversation_id': {'type': 'integer'},
                    'new_status': {'type': 'string'}
                }
            }
        },
        '404': {'description': 'Conversation not found'}
    }
})
def update_conversation_status(conversation_id):
    """Update conversation status (public endpoint for embed chats)."""
    try:
        data = request.get_json() or {}
        new_status = data.get('status')

        if not new_status:
            return jsonify({'error': 'status is required'}), 400

        if new_status not in ['active', 'inactive', 'archived']:
            return jsonify({'error': 'Invalid status. Must be active, inactive, or archived'}), 400

        # Find conversation by ID or session_id
        conversation = None

        # Try to find by integer ID first
        try:
            conv_id = int(conversation_id)
            conversation = Conversation.query.filter_by(id=conv_id).first()
        except ValueError:
            # If not an integer, try to find by session_id
            conversation = Conversation.query.filter_by(session_id=conversation_id).first()

        if not conversation:
            current_app.logger.warning(f"Conversation not found: {conversation_id}")
            return jsonify({'error': 'Conversation not found'}), 404

        # Update status
        old_status = conversation.status
        conversation.status = new_status
        conversation.updated_at = datetime.utcnow()

        db.session.commit()

        current_app.logger.info(f"✅ Updated conversation {conversation.id} status: {old_status} -> {new_status}")

        return jsonify({
            'success': True,
            'message': f'Conversation status updated to {new_status}',
            'conversation_id': conversation.id,
            'old_status': old_status,
            'new_status': new_status
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating conversation status: {e}")
        return jsonify({'error': 'Failed to update conversation status'}), 500


@api.route('/conversations/cleanup', methods=['POST'], endpoint='cleanup_conversations')
@login_required
def cleanup_conversations():
    """Clean up old embed conversations."""
    try:
        data = request.get_json() or {}
        cleanup_type = data.get('type', 'empty')

        # Convert tenant UUID to integer ID for database queries (consistent with other endpoints)
        from ..models import Tenant
        tenant = Tenant.query.filter_by(tenant_id=g.user_tenant_id).first()
        if not tenant:
            current_app.logger.error(f"Tenant not found for UUID: {g.user_tenant_id}")
            return jsonify({'error': 'Tenant not found'}), 404

        tenant_integer_id = tenant.id

        # Get all embed conversations for this tenant (soft-deleted excluded by default model behavior)
        embed_conversations = Conversation.query.filter(
            Conversation.tenant_id == tenant_integer_id,
            Conversation.title.like('%Embed Chat%')
        ).all()

        deleted_count = 0

        if cleanup_type == 'empty':
            # Delete conversations with no messages
            for conv in embed_conversations:
                message_count = Message.query.filter_by(conversation_id=conv.id).count()
                if message_count == 0:
                    db.session.delete(conv)
                    deleted_count += 1

        elif cleanup_type == 'old':
            # Delete conversations older than 1 day
            from datetime import timedelta
            yesterday = datetime.utcnow() - timedelta(days=1)
            for conv in embed_conversations:
                if conv.created_at < yesterday:
                    # Delete messages first
                    Message.query.filter_by(conversation_id=conv.id).delete()
                    db.session.delete(conv)
                    deleted_count += 1

        elif cleanup_type == 'all':
            # Delete ALL embed conversations
            for conv in embed_conversations:
                # Delete messages first
                Message.query.filter_by(conversation_id=conv.id).delete()
                db.session.delete(conv)
                deleted_count += 1

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Cleanup completed successfully. Deleted {deleted_count} conversations.',
            'deleted_count': deleted_count
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error cleaning up conversations: {str(e)}")
        return jsonify({'error': 'Failed to cleanup conversations'}), 500


# =============================================================
# FEEDBACK ENDPOINTS
# =============================================================

@api.route('/conversations/feedback', methods=['GET'])
@login_required
def get_feedback_list():
    """Get all feedback with star ratings for the current tenant (from ConversationFeedback table — every submission preserved)."""
    try:
        tenant = Tenant.query.filter_by(tenant_id=g.user_tenant_id).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404

        chatbot_id = request.args.get('chatbot_id', type=int)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        min_rating = request.args.get('min_rating', type=int)
        max_rating = request.args.get('max_rating', type=int)

        # Query ConversationFeedback (every rating submission) with feedback_type='rating'
        query = ConversationFeedback.query.join(
            Conversation, ConversationFeedback.conversation_id == Conversation.id
        ).filter(
            Conversation.tenant_id == tenant.id,
            Conversation.status != 'deleted',
            ConversationFeedback.feedback_type == 'rating'
        )

        if chatbot_id:
            query = query.filter(Conversation.chatbot_id == chatbot_id)
        if min_rating:
            query = query.filter(ConversationFeedback.rating >= min_rating)
        if max_rating:
            query = query.filter(ConversationFeedback.rating <= max_rating)

        total = query.count()
        feedbacks = query.order_by(ConversationFeedback.created_at.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()

        result = []
        for fb in feedbacks:
            conv = Conversation.query.get(fb.conversation_id)
            chatbot = Chatbot.query.get(conv.chatbot_id) if conv and conv.chatbot_id else None
            result.append({
                'id': fb.id,
                'rating': fb.rating,
                'feedback_text': fb.feedback_text,
                'created_at': fb.created_at.isoformat() if fb.created_at else None,
                'conversation_id': fb.conversation_id,
                'chatbot': {
                    'id': chatbot.id if chatbot else None,
                    'name': chatbot.name if chatbot else 'Unknown'
                } if chatbot else None,
                'source_platform': conv.source_platform or 'web' if conv else 'web',
                'language': conv.language or 'en' if conv else 'en'
            })

        return jsonify({
            'success': True,
            'data': {
                'feedbacks': result,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error getting feedback list: {str(e)}")
        return jsonify({'error': 'Failed to get feedback'}), 500


@api.route('/conversations/feedback/stats', methods=['GET'])
@login_required
def get_feedback_stats():
    """Get aggregated feedback statistics from ConversationFeedback table (every rating submission preserved)."""
    try:
        tenant = Tenant.query.filter_by(tenant_id=g.user_tenant_id).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404

        chatbot_id = request.args.get('chatbot_id', type=int)

        # Build base join: ConversationFeedback → Conversation (for tenant/chatbot filters)
        feedback_query = ConversationFeedback.query.join(
            Conversation, ConversationFeedback.conversation_id == Conversation.id
        ).filter(
            Conversation.tenant_id == tenant.id,
            Conversation.status != 'deleted',
            ConversationFeedback.feedback_type == 'rating'
        )

        if chatbot_id:
            feedback_query = feedback_query.filter(Conversation.chatbot_id == chatbot_id)

        # Total rated submissions (every individual rating, not just unique conversations)
        total_ratings = feedback_query.count()

        # Average rating from all submissions
        avg_result = db.session.query(
            func.avg(ConversationFeedback.rating)
        ).filter(
            ConversationFeedback.id.in_(feedback_query.with_entities(ConversationFeedback.id))
        ).scalar()
        avg_rating = float(avg_result) if avg_result else 0.0

        # Rating distribution (1-5)
        rating_distribution = {}
        for star in range(1, 6):
            count = feedback_query.filter(ConversationFeedback.rating == star).count()
            rating_distribution[str(star)] = count

        # Total feedbacks with text
        total_feedbacks = feedback_query.filter(
            ConversationFeedback.feedback_text.isnot(None),
            ConversationFeedback.feedback_text != ''
        ).count()

        # Total conversations (denominator for rate)
        total_conversations = Conversation.query.filter(
            Conversation.tenant_id == tenant.id,
            Conversation.status != 'deleted'
        ).count()

        return jsonify({
            'success': True,
            'data': {
                'total_ratings': total_ratings,
                'avg_rating': round(avg_rating, 2),
                'rating_distribution': rating_distribution,
                'total_feedbacks': total_feedbacks,
                'satisfaction_rate': round((total_ratings / total_conversations * 100), 1) if total_conversations > 0 else 0
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error getting feedback stats: {str(e)}")
        return jsonify({'error': 'Failed to get feedback stats'}), 500
