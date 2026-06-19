import os
from datetime import timedelta


class Config:
    """Base config."""
    BASE_DIR = os.path.dirname(os.path.dirname(__file__))

    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

    PROMPT_CONFIG_PATH = os.path.join(BASE_DIR, 'prompts.yml')

    # App Branding
    APP_NAME = os.environ.get('APP_NAME', 'Convoharbor')

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

    # Redis Configuration (optional - set REDIS_ENABLED=true to enable)
    REDIS_ENABLED = os.environ.get('REDIS_ENABLED', 'False').lower() in ['true', '1', 't']
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
    REDIS_CACHE_TTL = int(os.environ.get('REDIS_CACHE_TTL', '300'))
    REDIS_SOCKET_TIMEOUT = int(os.environ.get('REDIS_SOCKET_TIMEOUT', '5'))
    REDIS_RATE_LIMIT = int(os.environ.get('REDIS_RATE_LIMIT', '120'))

    # Cloudinary Configuration (File Storage)
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')
    CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL')
    # Default upload folder = APP_NAME (lowercased), set CLOUDINARY_UPLOAD_FOLDER to override
    CLOUDINARY_UPLOAD_FOLDER = os.environ.get('CLOUDINARY_UPLOAD_FOLDER') or APP_NAME.lower()

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

    # Embedding Service Selection
    EMBEDDINGS_SERVICE_USE = os.environ.get('EMBEDDINGS_SERVICE_USE', 'openai')
    OPENAI_API_BASE = os.environ.get('OPENAI_API_BASE', 'https://api.openai.com/v1')
    OPENAI_EMBEDDING_MODEL = os.environ.get('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-large')
    GEMINI_API_BASE_URL = os.environ.get('GEMINI_API_BASE_URL', 'generativelanguage.googleapis.com')
    GEMINI_EMBEDDING_MODEL = os.environ.get('GEMINI_EMBEDDING_MODEL', 'models/gemini-embedding-2')
    GEMINI_EMBEDDING_FALLBACK_MODEL = os.environ.get('GEMINI_EMBEDDING_FALLBACK_MODEL', 'models/gemini-embedding-001')
    EMBEDDING_MAX_RETRIES = int(os.environ.get('EMBEDDING_MAX_RETRIES', '3'))
    EMBEDDING_RETRY_BASE_DELAY = float(os.environ.get('EMBEDDING_RETRY_BASE_DELAY', '2.0'))
    LOCAL_EMBEDDING_MODEL = os.environ.get('LOCAL_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    LOCAL_EMBEDDING_DIMENSION = int(os.environ.get('LOCAL_EMBEDDING_DIMENSION', '384'))

    # =============================================================
    # Gemini rate limit (free tier = 100 embedding requests per
    # minute per model). The sliding-window limiter in
    # services/rate_limiter.py uses these values to back off
    # automatically when the quota is exhausted.
    # =============================================================
    GEMINI_RATE_LIMIT_PER_MINUTE = int(os.environ.get('GEMINI_RATE_LIMIT_PER_MINUTE', '100'))
    GEMINI_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get('GEMINI_RATE_LIMIT_WINDOW_SECONDS', '60'))

    # Encryption
    ENCRYPTION_SALT = os.environ.get('ENCRYPTION_SALT') or 'change-this-salt-in-production'

    # Retrieval & Document Processing Settings
    RETRIEVAL_SCORE_THRESHOLD = float(os.environ.get('RETRIEVAL_SCORE_THRESHOLD', '0.4'))
    CHUNK_SIZE = int(os.environ.get('CHUNK_SIZE', '1000'))
    CHUNK_OVERLAP = int(os.environ.get('CHUNK_OVERLAP', '150'))

    # =============================================================
    # Chatbot Config Defaults (used when fields are missing from
    # the chatbot's stored config). Only the Super Admin can change
    # these per-chatbot values via the chatbot update API.
    # =============================================================
    DEFAULT_TOP_K = int(os.environ.get('DEFAULT_TOP_K', '10'))
    DEFAULT_MODE = os.environ.get('DEFAULT_MODE', 'strict')
    DEFAULT_TEMPERATURE = float(os.environ.get('DEFAULT_TEMPERATURE', '0.7'))
    DEFAULT_MAX_TOKENS = int(os.environ.get('DEFAULT_MAX_TOKENS', '2048'))

    # Validation bounds for chatbot config fields
    TOP_K_MIN = int(os.environ.get('TOP_K_MIN', '1'))
    TOP_K_MAX = int(os.environ.get('TOP_K_MAX', '50'))
    TEMPERATURE_MIN = float(os.environ.get('TEMPERATURE_MIN', '0.0'))
    TEMPERATURE_MAX = float(os.environ.get('TEMPERATURE_MAX', '2.0'))
    MAX_TOKENS_MIN = int(os.environ.get('MAX_TOKENS_MIN', '64'))
    MAX_TOKENS_MAX = int(os.environ.get('MAX_TOKENS_MAX', '32000'))

    # Roles allowed to mutate top_k / mode / temperature / max_tokens
    SUPER_ADMIN_ROLE = 'super_admin'


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
        app.logger.info(f'{cls.APP_NAME} startup')


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
