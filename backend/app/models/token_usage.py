# app/models/token_usage.py

from datetime import datetime
from .. import db


class TokenUsage(db.Model):
    """
    Tracks token usage and costs per tenant/chatbot
    """
    __tablename__ = 'token_usage'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    chatbot_id = db.Column(db.Integer, db.ForeignKey('chatbots.id'), nullable=True, index=True)

    # AI Service details
    provider = db.Column(db.String(50), nullable=False)  # 'openai', 'gemini', etc.
    model = db.Column(db.String(100), nullable=False)  # specific model used
    operation = db.Column(db.String(50), nullable=False)  # 'query', 'embedding', 'processing'

    # Token counts
    input_tokens = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)
    total_tokens = db.Column(db.Integer, default=0)

    # Cost tracking (in USD)
    input_cost = db.Column(db.Numeric(10, 6), default=0.0)  # Cost for input tokens
    output_cost = db.Column(db.Numeric(10, 6), default=0.0)  # Cost for output tokens
    total_cost = db.Column(db.Numeric(10, 6), default=0.0)  # Total cost

    # Context
    request_id = db.Column(db.String(100))  # For tracking individual requests
    session_id = db.Column(db.String(100))  # For conversation sessions
    data_source_id = db.Column(db.Integer, db.ForeignKey('data_sources.id'), nullable=True)

    # Metadata
    meta_data = db.Column(db.JSON, default=dict)  # Additional context/debugging info
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<TokenUsage {self.provider}:{self.model} - {self.total_tokens} tokens @ ${self.total_cost}>'
