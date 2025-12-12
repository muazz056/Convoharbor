# app/models/encrypted_credentials.py

"""
Encrypted Credentials Model
Stores sensitive credentials with field-level encryption.
"""

from datetime import datetime
from .. import db
from ..services.encryption_service import encrypt_field, decrypt_field


class EncryptedCredential(db.Model):
    """
    Store sensitive credentials with field-level encryption.
    Used for API keys, tokens, passwords, and other secrets.
    """
    __tablename__ = 'encrypted_credentials'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Owner information
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user = db.relationship('User', backref='encrypted_credentials')
    
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True)
    tenant = db.relationship('Tenant')
    
    # Credential details
    credential_type = db.Column(db.String(100), nullable=False)  # 'api_key', 'oauth_token', 'password', etc.
    service_name = db.Column(db.String(200), nullable=False)  # 'openai', 'gemini', 'stripe', etc.
    
    # Encrypted fields
    encrypted_value = db.Column(db.Text, nullable=False)  # The actual encrypted credential
    encrypted_metadata = db.Column(db.Text, nullable=True)  # Optional encrypted metadata (JSON string)
    
    # Non-encrypted metadata
    label = db.Column(db.String(200), nullable=True)  # User-friendly label
    description = db.Column(db.Text, nullable=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_used_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<EncryptedCredential {self.id}: {self.service_name}>'
    
    def set_value(self, plaintext_value: str):
        """Encrypt and store a credential value."""
        self.encrypted_value = encrypt_field(plaintext_value)
        self.updated_at = datetime.utcnow()
    
    def get_value(self) -> str:
        """Decrypt and return the credential value."""
        self.last_used_at = datetime.utcnow()
        db.session.commit()
        return decrypt_field(self.encrypted_value)
    
    def set_metadata(self, metadata_dict: dict):
        """Encrypt and store metadata as JSON."""
        import json
        metadata_json = json.dumps(metadata_dict)
        self.encrypted_metadata = encrypt_field(metadata_json)
    
    def get_metadata(self) -> dict:
        """Decrypt and return metadata as dictionary."""
        if not self.encrypted_metadata:
            return {}
        
        import json
        decrypted_json = decrypt_field(self.encrypted_metadata)
        return json.loads(decrypted_json) if decrypted_json else {}
    
    def is_expired(self) -> bool:
        """Check if credential has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() >= self.expires_at
    
    def to_dict(self, include_value: bool = False):
        """
        Convert to dictionary for API responses.
        
        Args:
            include_value: If True, include decrypted value (use with caution!)
        """
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'tenant_id': self.tenant_id,
            'credential_type': self.credential_type,
            'service_name': self.service_name,
            'label': self.label,
            'description': self.description,
            'is_active': self.is_active,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_expired': self.is_expired(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None
        }
        
        # Only include decrypted value if explicitly requested
        if include_value:
            result['value'] = self.get_value()
            result['metadata'] = self.get_metadata()
        
        return result


class EncryptedAPIKey(db.Model):
    """
    Encrypted storage for API keys used by chatbots.
    Extends the Chatbot model with secure key storage.
    """
    __tablename__ = 'encrypted_api_keys'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Link to chatbot
    chatbot_id = db.Column(db.Integer, db.ForeignKey('chatbots.id'), nullable=False)
    chatbot = db.relationship('Chatbot', backref='encrypted_api_keys')
    
    # Provider information
    provider = db.Column(db.String(100), nullable=False)  # 'openai', 'gemini', 'anthropic', etc.
    
    # Encrypted API key
    encrypted_key = db.Column(db.Text, nullable=False)
    
    # Key metadata (non-encrypted)
    key_name = db.Column(db.String(200), nullable=True)  # User-friendly name
    is_primary = db.Column(db.Boolean, default=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Usage tracking
    last_used_at = db.Column(db.DateTime, nullable=True)
    usage_count = db.Column(db.Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<EncryptedAPIKey {self.id}: {self.provider}>'
    
    def set_key(self, plaintext_key: str):
        """Encrypt and store the API key."""
        self.encrypted_key = encrypt_field(plaintext_key)
        self.updated_at = datetime.utcnow()
    
    def get_key(self) -> str:
        """Decrypt and return the API key."""
        self.last_used_at = datetime.utcnow()
        self.usage_count += 1
        db.session.commit()
        return decrypt_field(self.encrypted_key)
    
    def to_dict(self, include_key: bool = False):
        """
        Convert to dictionary for API responses.
        
        Args:
            include_key: If True, include decrypted key (use with extreme caution!)
        """
        result = {
            'id': self.id,
            'chatbot_id': self.chatbot_id,
            'provider': self.provider,
            'key_name': self.key_name,
            'is_primary': self.is_primary,
            'is_active': self.is_active,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'usage_count': self.usage_count,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        # Only include key if explicitly requested (for debugging/migration only)
        if include_key:
            result['key'] = self.get_key()
            result['key_preview'] = f"{self.get_key()[:8]}...{self.get_key()[-4:]}"
        
        return result

