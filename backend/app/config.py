import os
from datetime import timedelta


class Config:
    """Base config."""
    BASE_DIR = os.path.dirname(os.path.dirname(__file__))

    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

    PROMPT_CONFIG_PATH = os.path.join(BASE_DIR, 'prompts.yml')

    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database Configuration (Neon DB / PostgreSQL)
    USER_DB_URL = os.environ.get('USER_DB_URL') or os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    ADMIN_DB_URL = os.environ.get('ADMIN_DB_URL') or USER_DB_URL

    SQLALCHEMY_DATABASE_URI = USER_DB_URL
    SQLALCHEMY_BINDS = {
        'admin': ADMIN_DB_URL
    }
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_recycle': 280,
        'pool_pre_ping': True,
        'pool_use_lifo': True,
        'pool_timeout': 30
    }

    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-jwt-secret-key')
    JWT_EXPIRY_HOURS = 24 * 5
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=5)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    # Redis Configuration
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
    REDIS_CACHE_TTL = int(os.environ.get('REDIS_CACHE_TTL', '300'))
    REDIS_SOCKET_TIMEOUT = int(os.environ.get('REDIS_SOCKET_TIMEOUT', '5'))
    REDIS_RATE_LIMIT = int(os.environ.get('REDIS_RATE_LIMIT', '120'))

    # Cloudinary Configuration (File Storage)
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')
    CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL')
    CLOUDINARY_UPLOAD_FOLDER = os.environ.get('CLOUDINARY_UPLOAD_FOLDER', 'convopilot_temp')

    # Brevo (Email Service)
    BREVO_API_KEY = os.environ.get('BREVO_API_KEY')
    BREVO_SENDER_EMAIL = os.environ.get('BREVO_SENDER_EMAIL')

    # Email Settings (SMTP fallback)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp-relay.brevo.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() in ['true', '1', 't']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() in ['true', '1', 't']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', BREVO_SENDER_EMAIL)
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', BREVO_API_KEY)
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', BREVO_SENDER_EMAIL)

    # Application URLs
    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
    BACKEND_URL = os.environ.get('BACKEND_URL', 'http://localhost:5001')

    # AI Service Configuration
    AI_SERVICE_URL = os.environ.get('AI_SERVICE_URL', 'http://localhost:5000')
    AI_SERVICE_API_KEY = os.environ.get('AI_SERVICE_API_KEY')
    AI_SERVICE_TIMEOUT = int(os.environ.get('AI_SERVICE_TIMEOUT', '30'))

    # LLM Provider API Keys
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', 'your-openai-api-key')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'your-gemini-api-key')
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY', 'your-groq-api-key')

    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)

    # File Upload Settings
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'doc'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # Default AI Model Settings
    DEFAULT_LLM_PROVIDER = 'gemini'
    DEFAULT_EMBEDDING_PROVIDER = 'openai'
    DEFAULT_OPENAI_MODEL = 'gpt-4o-mini'
    DEFAULT_GEMINI_MODEL = 'models/gemini-2.5-flash'
    DEFAULT_GROQ_MODEL = 'llama3-70b-8192'
    GEMINI_EMBEDDING_MODEL = 'models/embedding-001'

    VALID_MODELS = {
        'openai': ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
        'gemini': ['models/gemini-2.5-flash', 'models/gemini-2.5-pro', 'models/gemini-2.0-flash', 'models/gemini-2.0-flash-exp'],
        'groq': ['llama3-70b-8192', 'llama3-8b-8192', 'mixtral-8x7b-32768', 'gemma2-9b-it']
    }

    # Retrieval & Document Processing Settings
    RETRIEVAL_SCORE_THRESHOLD = 0.4
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 150

    # pgvector settings
    VECTOR_DIMENSION = 3072
    VECTOR_INDEX_TYPE = 'ivfflat'
    VECTOR_INDEX_LISTS = 100


class DevelopmentConfig(Config):
    """Development config."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'


class TestingConfig(Config):
    """Testing config."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production config."""
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///prod_fallback.db'

    @classmethod
    def init_app(cls, app):
        import logging
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('ConvoPilot startup')


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
