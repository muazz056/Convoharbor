from datetime import datetime
from app import db


class Conversation(db.Model):
    __tablename__ = 'conversations'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(255), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True)
    chatbot_id = db.Column(db.Integer, db.ForeignKey('chatbots.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Conversation metadata
    title = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), default='active')  # active, archived, deleted
    language = db.Column(db.String(10), default='en')

    # Website tracking fields (NEW)
    source_domain = db.Column(db.String(255), nullable=True)
    source_url = db.Column(db.Text(), nullable=True)
    source_platform = db.Column(db.String(50), default='web', nullable=True)
    source_metadata = db.Column(db.JSON(), nullable=True)

    # Conversation ending and satisfaction fields (NEW)
    conversation_ended = db.Column(db.Boolean, default=False, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    satisfaction_rating = db.Column(db.Integer, nullable=True)  # 1-5 stars
    satisfaction_feedback = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    messages = db.relationship('Message', backref='conversation', lazy='dynamic', cascade='all, delete-orphan')
    feedback = db.relationship('ConversationFeedback', backref='conversation', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Conversation {self.id}: {self.session_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'tenant_id': self.tenant_id,
            'chatbot_id': self.chatbot_id,
            'user_id': self.user_id,
            'title': self.title,
            'status': self.status,
            'language': self.language,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'message_count': self.messages.count(),
            # NEW: Website tracking fields (with safe defaults)
            'source_domain': getattr(self, 'source_domain', None),
            'source_url': getattr(self, 'source_url', None),
            'source_platform': getattr(self, 'source_platform', 'web'),
            'source_metadata': getattr(self, 'source_metadata', {}),
            # NEW: Conversation ending and satisfaction fields
            'conversation_ended': getattr(self, 'conversation_ended', False),
            'ended_at': self.ended_at.isoformat() if getattr(self, 'ended_at', None) else None,
            'satisfaction_rating': getattr(self, 'satisfaction_rating', None),
            'satisfaction_feedback': getattr(self, 'satisfaction_feedback', None)
        }


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False)

    # Message content
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), nullable=False)  # 'user', 'assistant', 'system'

    # Message metadata
    role = db.Column(db.String(100), nullable=True)  # AI persona/role used
    model_used = db.Column(db.String(100), nullable=True)  # AI model used for response
    provider = db.Column(db.String(50), nullable=True)  # openai, gemini, etc.

    # Performance metrics
    response_time = db.Column(db.Float, nullable=True)  # Response time in seconds
    token_count = db.Column(db.Integer, nullable=True)  # Token count for the message

    # Source information (for RAG)
    sources = db.Column(db.JSON, nullable=True)  # Source documents used
    confidence_score = db.Column(db.Float, nullable=True)  # Confidence in the response

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Message {self.id}: {self.message_type}>'

    def to_dict(self):
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'content': self.content,
            'message_type': self.message_type,
            'role': self.role,
            'model_used': self.model_used,
            'provider': self.provider,
            'response_time': self.response_time,
            'token_count': self.token_count,
            'sources': self.sources,
            'confidence_score': self.confidence_score,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ConversationFeedback(db.Model):
    __tablename__ = 'conversation_feedback'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=True)

    # Feedback data
    rating = db.Column(db.Integer, nullable=True)  # 1-5 star rating
    feedback_type = db.Column(db.String(50), nullable=False)  # 'thumbs_up', 'thumbs_down', 'rating', 'comment'
    feedback_text = db.Column(db.Text, nullable=True)  # Optional comment

    # User information
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user_email = db.Column(db.String(255), nullable=True)  # For anonymous feedback

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<ConversationFeedback {self.id}: {self.feedback_type}>'

    def to_dict(self):
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'message_id': self.message_id,
            'rating': self.rating,
            'feedback_type': self.feedback_type,
            'feedback_text': self.feedback_text,
            'user_id': self.user_id,
            'user_email': self.user_email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
