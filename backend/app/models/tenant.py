from datetime import datetime
from .. import db
from uuid import uuid4
# Use single source of truth for Chatbot model to avoid duplication and mapper conflicts
try:
    from .chatbot import Chatbot as Chatbot  # alias into this module's namespace
except Exception:
    # Fallback if import changes later; keeps backward compatibility
    Chatbot = None

def generate_tenant_id():
    return str(uuid4())

class ClientProfile(db.Model):
    """
    Additional profile information for a tenant.
    Stores business-specific information and preferences.
    """
    __tablename__ = 'client_profiles'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), unique=True, nullable=False)
    
    # Business Information
    company_size = db.Column(db.String(50))  # small, medium, enterprise
    industry = db.Column(db.String(100))
    website = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    address = db.Column(db.Text)
    
    # Subscription Details
    plan = db.Column(db.String(50))  # basic, pro, enterprise
    billing_cycle = db.Column(db.String(20))  # monthly, annual
    credits_limit = db.Column(db.Integer)
    credits_used = db.Column(db.Integer, default=0)
    
    # Integration Settings
    allowed_domains = db.Column(db.JSON, default=list)  # List of allowed domains
    api_keys = db.Column(db.JSON, default=dict)  # Encrypted API keys for integrations
    webhook_config = db.Column(db.JSON, default=dict)  # Webhook endpoints and settings
    
    # Customization
    branding = db.Column(db.JSON, default=dict)  # Logo URLs, colors, etc.
    chat_settings = db.Column(db.JSON, default=dict)  # Default chatbot settings
    language_settings = db.Column(db.JSON, default=dict)  # Supported languages
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ClientProfile tenant_id={self.tenant_id}>'

class Tenant(db.Model):
    """
    Represents a tenant in the multi-tenant system.
    A tenant can be either a ConvoPilot client or a MyChatbotCompagny managed client.
    """
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(36), unique=True, default=generate_tenant_id, index=True)
    name = db.Column(db.String(255), nullable=False)
    domain = db.Column(db.String(255), unique=True)
    type = db.Column(db.String(20), nullable=False)  # 'convopilot' or 'managed'
    status = db.Column(db.String(20), default='active')  # active, suspended, deleted
    database_url = db.Column(db.String(500))  # For separate database per tenant
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = db.relationship('User', backref='tenant', lazy='dynamic', cascade="all, delete-orphan")
    chatbots = db.relationship('Chatbot', backref='tenant', lazy='dynamic', cascade="all, delete-orphan")
    profile = db.relationship('ClientProfile', backref='tenant', uselist=False, cascade="all, delete-orphan")
    
    # Tenant configuration
    config = db.Column(db.JSON, default=dict)
    
    def __repr__(self):
        return f'<Tenant {self.name}>'

class User(db.Model):
    """
    Represents a user in the system.
    Users are always associated with a tenant.
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)  # Nullable for OAuth users
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    role = db.Column(db.String(50), nullable=False)  # super_admin, tenant_admin, user
    status = db.Column(db.String(20), default='pending')  # pending, active, inactive, suspended
    last_login = db.Column(db.DateTime)
    email_confirmed = db.Column(db.Boolean, default=False)
    email_confirmed_at = db.Column(db.DateTime, nullable=True)
    confirmation_token = db.Column(db.String(100), unique=True, nullable=True)
    confirmation_token_expires = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # OAuth fields
    oauth_provider = db.Column(db.String(50))  # google, github, microsoft
    oauth_id = db.Column(db.String(255))
    oauth_data = db.Column(db.JSON, default=dict)  # Additional OAuth profile data

    def __repr__(self):
        return f'<User {self.email}>'

# NOTE:
# Chatbot model previously existed here as a duplicate of app/models/chatbot.py
# To prevent confusion and potential mapper conflicts, we now import and alias
# the canonical Chatbot definition from app/models/chatbot.py at the top of this file.
# Any relationship references (e.g., Tenant.chatbots) continue to work via the alias.
