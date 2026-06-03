from datetime import datetime
from .. import db
class Chatbot(db.Model):
    """Chatbot model for storing chatbot configurations"""
    __tablename__ = 'chatbots'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    type = db.Column(db.String(20), default='general')  # support, sales, general, hr, technical
    status = db.Column(db.String(20), default='active')  # active, inactive, training
    config = db.Column(db.JSON)  # Stores AI model, personality, prompts, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (removed conversations to avoid table existence issues)
    data_sources = db.relationship('DataSource', backref='chatbot', lazy=True)

    def __init__(self, tenant_id, name, description=None, type='general', status='active', config=None):
        self.tenant_id = tenant_id
        self.name = name
        self.description = description
        self.type = type
        self.status = status
        self.config = config or {}

    def to_dict(self):
        """Convert chatbot to dictionary for JSON serialization"""
        config = self.config or {}
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'name': self.name,
            'description': self.description,
            'type': self.type,
            'status': self.status,
            'config': config,
            'ai_provider': config.get('ai_provider', 'openai'),
            'ai_model': config.get('ai_model', 'gpt-4o-mini'),
            'model': config.get('model', config.get('ai_model', 'gpt-4o-mini')),
            'temperature': config.get('temperature', 0.7),
            'top_k': config.get('top_k', 10),  # Default to 10 chunks if not specified
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<Chatbot {self.name}>'
