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
        # Apply centralized defaults so the in-memory model has the four
        # restricted fields populated from the start.
        try:
            from ..services.chatbot_defaults import apply_defaults
            self.config = apply_defaults(config or {})
        except Exception:
            # Fallback: keep raw config (avoids breaking model __init__ in
            # migrations / shell contexts where current_app isn't available).
            self.config = config or {}

    def to_dict(self):
        """Convert chatbot to dictionary for JSON serialization.

        AI model/provider are reported exactly as configured by Super Admin via
        the AI Models page; no hardcoded fallback names are used.

        The four restricted fields (mode, temperature, max_tokens, top_k)
        are resolved through `chatbot_defaults.resolve_field` so the
        effective value is always returned, regardless of whether the
        chatbot row actually has the field stored.
        """
        config = self.config or {}
        try:
            from ..services.chatbot_defaults import resolve_field
            eff_top_k = resolve_field(config, 'top_k')
            eff_temperature = resolve_field(config, 'temperature')
            eff_mode = resolve_field(config, 'mode')
            eff_max_tokens = resolve_field(config, 'max_tokens')
        except Exception:
            # Shell / migration contexts where current_app isn't bound.
            eff_top_k = config.get('top_k', 10)
            eff_temperature = config.get('temperature', 0.7)
            eff_mode = config.get('mode', 'strict')
            eff_max_tokens = config.get('max_tokens', 2048)

        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'name': self.name,
            'description': self.description,
            'type': self.type,
            'status': self.status,
            'config': config,
            'ai_provider': config.get('ai_provider'),
            'ai_model': config.get('ai_model'),
            'model': config.get('model', config.get('ai_model')),
            'temperature': eff_temperature,
            'max_tokens': eff_max_tokens,
            'mode': eff_mode,
            'top_k': eff_top_k,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<Chatbot {self.name}>'
