from datetime import datetime
from .. import db
from ..services.encryption_service import encrypt_field, decrypt_field


SUPPORTED_PROVIDERS = [
    {'id': 'openai', 'name': 'OpenAI', 'api_type': 'openai'},
    {'id': 'claude', 'name': 'Anthropic Claude', 'api_type': 'anthropic'},
    {'id': 'gemini', 'name': 'Google Gemini', 'api_type': 'gemini'},
    {'id': 'groq', 'name': 'Groq', 'api_type': 'groq'},
    {'id': 'qwen', 'name': 'Qwen (Alibaba)', 'api_type': 'openai'},
    {'id': 'deepseek', 'name': 'DeepSeek', 'api_type': 'openai'},
    {'id': 'mistral', 'name': 'Mistral AI', 'api_type': 'openai'},
    {'id': 'xai', 'name': 'xAI (Grok)', 'api_type': 'openai'},
    {'id': 'together', 'name': 'Together AI', 'api_type': 'openai'},
    {'id': 'perplexity', 'name': 'Perplexity', 'api_type': 'openai'},
    {'id': 'openrouter', 'name': 'OpenRouter', 'api_type': 'openai'},
]


class AiModel(db.Model):
    __tablename__ = 'ai_models'

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False, index=True)
    model_name = db.Column(db.String(200), nullable=False)
    display_name = db.Column(db.String(200))
    api_key_encrypted = db.Column(db.Text, nullable=True)
    base_url = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    model_type = db.Column(db.String(20), default='chat')
    context_window = db.Column(db.Integer, nullable=True)
    max_tokens = db.Column(db.Integer, nullable=True)
    temperature = db.Column(db.Float, nullable=True, default=0.7)
    top_k = db.Column(db.Integer, nullable=True, default=10)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def set_api_key(self, plaintext_key):
        if plaintext_key:
            self.api_key_encrypted = encrypt_field(plaintext_key)
        else:
            self.api_key_encrypted = None

    def get_api_key(self):
        if self.api_key_encrypted:
            return decrypt_field(self.api_key_encrypted)
        return None

    def to_dict(self, include_key=False):
        result = {
            'id': self.id,
            'provider': self.provider,
            'model_name': self.model_name,
            'display_name': self.display_name or self.model_name,
            'base_url': self.base_url,
            'is_active': self.is_active,
            'model_type': self.model_type,
            'context_window': self.context_window,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature if self.temperature is not None else 0.7,
            'top_k': self.top_k if self.top_k is not None else 10,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_key:
            result['api_key'] = self.get_api_key()
            if result['api_key']:
                result['api_key_preview'] = result['api_key'][:8] + '...' + result['api_key'][-4:]
        return result

    def __repr__(self):
        return f'<AiModel {self.id}: {self.provider}/{self.model_name}>'
