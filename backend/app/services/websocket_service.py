from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from flask import current_app
from datetime import datetime
import jwt
from ..models import Conversation, Message, Chatbot, Tenant
from .. import db

class WebSocketService:
    def __init__(self):
        self.socketio = SocketIO(
            cors_allowed_origins="*",
            async_mode='eventlet',
            logger=True,
            engineio_logger=True,
            ping_timeout=60,
            ping_interval=25,
            allow_upgrades=True,
            transports=['polling', 'websocket']
        )
        self._active_connections = {}
        self._typing_status = {}
        self.register_handlers()

    def _register_core_handlers(self, namespace=None, require_jwt=True):
        ns = namespace or '/'

        @self.socketio.on('connect', namespace=ns)
        def handle_connect(auth):
            try:
                current_app.logger.info(f"WS connection attempt on {ns}, auth: {auth}")
                user_id = None
                payload = None
                
                if require_jwt:
                    token = None
                    # socket.io v4 sends auth payload from client
                    if isinstance(auth, dict):
                        token = auth.get('token')
                    if not token:
                        current_app.logger.warning(f"No token provided for {ns}")
                        return False
                    payload = self._verify_jwt(token)
                    if not payload:
                        current_app.logger.warning(f"Invalid token for {ns}")
                        return False
                    user_id = payload['user_id']
                else:
                    # Public namespace - no JWT required
                    current_app.logger.info(f"Public namespace connection, no JWT required")
                
                self._active_connections[self.socketio.sid] = {
                    'connected_at': datetime.utcnow(),
                    'namespace': ns,
                    'user_id': user_id,
                    'payload': payload
                }
                current_app.logger.info(f"WS connected successfully on {ns}, user_id: {user_id}")
                emit('connection_established', {'status': 'connected', 'namespace': ns})
                return True
            except Exception as e:
                current_app.logger.error(f"WS connect error ({ns}): {e}")
                return False

        @self.socketio.on('disconnect', namespace=ns)
        def handle_disconnect():
            self._active_connections.pop(self.socketio.sid, None)

        @self.socketio.on('join_conversation', namespace=ns)
        def handle_join_conversation(data):
            try:
                conversation_id = int(data.get('conversation_id'))
                room = f"conversation_{conversation_id}"
                join_room(room)
                emit('joined_conversation', {'conversation_id': conversation_id, 'status': 'joined'})
            except Exception as e:
                current_app.logger.error(f"WS join error: {e}")
                emit('error', {'message': 'Failed to join conversation'})

        @self.socketio.on('send_message', namespace=ns)
        def handle_send_message(data):
            try:
                conversation_id = int(data.get('conversation_id'))
                chatbot_id = int(data.get('chatbot_id'))
                content = (data.get('content') or '').strip()
                if not content:
                    return
                # Validate conversation and chatbot, ensure tenant match
                conversation = Conversation.query.get(conversation_id)
                chatbot = Chatbot.query.get(chatbot_id)
                if not conversation or not chatbot or conversation.tenant_id != chatbot.tenant_id:
                    emit('error', {'message': 'Invalid conversation/chatbot'})
                    return
                user_msg = Message(
                    conversation_id=conversation_id,
                    content=content,
                    message_type='user',
                    created_at=datetime.utcnow()
                )
                db.session.add(user_msg)
                db.session.commit()
                room = f"conversation_{conversation_id}"
                emit('new_message', user_msg.to_dict(), room=room)
                emit('typing_indicator', {'is_typing': True, 'actor': 'assistant'}, room=room)
                self.socketio.start_background_task(
                    self.generate_ai_response,
                    conversation_id=conversation_id,
                    chatbot_id=chatbot_id,
                    user_message=content,
                    room=room
                )
            except Exception as e:
                current_app.logger.error(f"WS send_message error: {e}")
                emit('error', {'message': 'Failed to send message'})

    def register_handlers(self):
        # Default namespace: require JWT (for app users)
        self._register_core_handlers(namespace='/', require_jwt=True)
        # Public namespace: no JWT, validates via chatbot+conversation
        self._register_core_handlers(namespace='/public', require_jwt=False)

    def generate_ai_response(self, conversation_id, chatbot_id, user_message, room):
        try:
            chatbot = Chatbot.query.get(int(chatbot_id))
            if not chatbot:
                raise ValueError('Chatbot not found')
            ai_message = Message(
                conversation_id=int(conversation_id),
                content="",
                message_type='assistant',
                created_at=datetime.utcnow()
            )
            db.session.add(ai_message)
            db.session.commit()
            # Retrieve context
            context_docs = []
            try:
                context_docs = current_app.vector_service.search_similar(
                    query=user_message, chatbot_id=int(chatbot_id), limit=3
                )
            except Exception as e:
                current_app.logger.warning(f"Vector search failed: {e}")
                context_docs = []
            context_text = "\n".join([getattr(doc, 'page_content', '') for doc in context_docs])
            messages = [
                {"role": "system", "content": f"Use this context if relevant:\n\n{context_text}"},
                {"role": "user", "content": user_message}
            ]
            # Stream response chunks
            full = ""
            try:
                for chunk in current_app.llm_service.generate_stream(messages=messages, model_name=chatbot.model or current_app.config.get('DEFAULT_OPENAI_MODEL', 'gpt-4o-mini')):
                    if not chunk:
                        continue
                    full += chunk
                    ai_message.content = full
                    db.session.commit()
                    emit('message_chunk', {'message_id': ai_message.id, 'chunk': chunk}, room=room)
            except Exception as e:
                current_app.logger.error(f"LLM stream error: {e}")
            # Finalize
            ai_message.content = full or "(no response)"
            db.session.commit()
            emit('message_complete', {'message_id': ai_message.id, 'final_content': ai_message.content}, room=room)
            emit('typing_indicator', {'is_typing': False, 'actor': 'assistant'}, room=room)
        except Exception as e:
            current_app.logger.error(f"AI response error: {e}")
            emit('typing_indicator', {'is_typing': False, 'actor': 'assistant'}, room=room)

    def _verify_jwt(self, token):
        try:
            # Use the same key as auth_service for consistency
            secret_key = current_app.config.get('JWT_SECRET_KEY') or current_app.config.get('SECRET_KEY')
            return jwt.decode(token, secret_key, algorithms=['HS256'])
        except Exception as e:
            current_app.logger.debug(f"JWT verification failed: {e}")
            return None

websocket_service = WebSocketService()
