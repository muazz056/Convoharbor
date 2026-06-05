from datetime import datetime
from .. import db
from uuid import uuid4

try:
    from .chatbot import Chatbot as Chatbot
except Exception:
    Chatbot = None


def generate_tenant_id():
    return str(uuid4())


class ClientProfile(db.Model):
    __tablename__ = 'client_profiles'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), unique=True, nullable=False)

    company_size = db.Column(db.String(50))
    industry = db.Column(db.String(100))
    website = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    address = db.Column(db.Text)

    plan = db.Column(db.String(50))
    billing_cycle = db.Column(db.String(20))
    credits_limit = db.Column(db.Integer)
    credits_used = db.Column(db.Integer, default=0)

    allowed_domains = db.Column(db.JSON, default=list)
    api_keys = db.Column(db.JSON, default=dict)
    webhook_config = db.Column(db.JSON, default=dict)

    branding = db.Column(db.JSON, default=dict)
    chat_settings = db.Column(db.JSON, default=dict)
    language_settings = db.Column(db.JSON, default=dict)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ClientProfile tenant_id={self.tenant_id}>'


class Tenant(db.Model):
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(36), unique=True, default=generate_tenant_id, index=True)
    name = db.Column(db.String(255), nullable=False)
    domain = db.Column(db.String(255), unique=True)
    type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='active')
    database_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = db.relationship('User', backref='tenant', lazy='dynamic', cascade="all, delete-orphan")
    chatbots = db.relationship('Chatbot', backref='tenant', lazy='dynamic', cascade="all, delete-orphan")
    profile = db.relationship('ClientProfile', backref='tenant', uselist=False, cascade="all, delete-orphan")

    config = db.Column(db.JSON, default=dict)

    __bind_key__ = None

    def __repr__(self):
        return f'<Tenant {self.name}>'


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    role = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending')
    last_login = db.Column(db.DateTime)
    email_confirmed = db.Column(db.Boolean, default=False)
    email_confirmed_at = db.Column(db.DateTime, nullable=True)
    confirmation_token = db.Column(db.String(100), unique=True, nullable=True)
    confirmation_token_expires = db.Column(db.DateTime, nullable=True)
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    oauth_provider = db.Column(db.String(50))
    oauth_id = db.Column(db.String(255))
    oauth_data = db.Column(db.JSON, default=dict)

    __bind_key__ = None

    def __repr__(self):
        return f'<User {self.email}>'
