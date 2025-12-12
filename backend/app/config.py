import os
from datetime import timedelta

class Config:
    """Base config."""
    # Base paths
    BASE_DIR = os.path.dirname(os.path.dirname(__file__))
    
    # Upload folder for documents
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    
    # Prompt configuration
    PROMPT_CONFIG_PATH = os.path.join(BASE_DIR, 'prompts.yml')
    # Existing configurations
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Database Configuration (logical dual-DB with single URL fallback)
    # Safe defaults: fall back to sqlite if no DB URL is provided to avoid parsing errors
    USER_DB_URL = os.environ.get('USER_DB_URL') or os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    ADMIN_DB_URL = os.environ.get('ADMIN_DB_URL') or USER_DB_URL  # falls back to same DB if not provided

    SQLALCHEMY_DATABASE_URI = USER_DB_URL
    SQLALCHEMY_BINDS = {
        'admin': ADMIN_DB_URL
    }
    # Add robust connection pooling options to handle database connection drops
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,  # Recycle connections before they are timed out by the server
        'pool_pre_ping': True # Check if a connection is alive before using it
    }
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-jwt-secret-key')
    JWT_EXPIRY_HOURS = 24 * 5  # 5 days for access tokens
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=5)  # 5 days
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)  # 7 days for refresh tokens
    
    # Email settings - all loaded from environment
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() in ['true', '1', 't']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() in ['true', '1', 't']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', MAIL_USERNAME)
    
    # Frontend URL for email confirmation
    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
    
    # AI Service Configuration
    AI_SERVICE_URL = os.environ.get('AI_SERVICE_URL', 'http://localhost:5000')
    AI_SERVICE_API_KEY = os.environ.get('AI_SERVICE_API_KEY')
    AI_SERVICE_TIMEOUT = int(os.environ.get('AI_SERVICE_TIMEOUT', '30'))
    
    # API Keys
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', 'your-openai-api-key')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'your-gemini-api-key')
    
    # Helicone Configuration for LLM Observability
    HELICONE_API_KEY = os.environ.get('HELICONE_API_KEY', 'sk-helicone-vpx5dzy-idqepxq-umbbb3i-diulcoi')
    HELICONE_ENABLED = os.environ.get('HELICONE_ENABLED', 'True').lower() in ['true', '1', 't']

    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    
    # Application URLs
    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

    # File upload settings
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'doc'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # AWS S3 Configuration for secure uploads
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_S3_BUCKET = os.environ.get('AWS_S3_BUCKET')
    AWS_S3_REGION = os.environ.get('AWS_S3_REGION', 'us-east-1')
    
    # Default AI model settings
    DEFAULT_LLM_PROVIDER = 'gemini'  # Changed to Gemini due to OpenAI region restrictions
    DEFAULT_EMBEDDING_PROVIDER = 'openai'
    DEFAULT_OPENAI_MODEL = 'gpt-4o-mini'
    DEFAULT_GEMINI_MODEL = 'models/gemini-2.5-flash'  # Langchain requires models/ prefix
    GEMINI_EMBEDDING_MODEL = 'models/embedding-001'
    
    # Valid models configuration - using correct API formats
    VALID_MODELS = {
        'openai': ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
        'gemini': ['models/gemini-2.5-flash', 'models/gemini-2.5-pro', 'models/gemini-2.0-flash', 'models/gemini-2.0-flash-exp']
    }
    
    # Retrieval settings
    RETRIEVAL_SCORE_THRESHOLD = 0.4

    # Document processing settings
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 150

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
        # Log to stderr
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