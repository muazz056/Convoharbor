# # chat_project/app/__init__.py

import os
import eventlet

# Monkey patch for WebSocket support
eventlet.monkey_patch()

import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_mail import Mail
from flasgger import Swagger
from .config import config

# Services will be imported inside create_app to avoid circular imports

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
mail = Mail()

# Services will be initialized in create_app function to avoid circular imports


def create_app(config_name='default'):
    """Application factory function."""
    app = Flask(__name__)

    # CORS will be configured later after config is loaded

    # Load configuration
    app.config.from_object(config[config_name])

    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/unanswered_queries.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.unanswered_logger = logging.getLogger('unanswered_queries')
    app.unanswered_logger.addHandler(file_handler)
    app.unanswered_logger.setLevel(logging.INFO)

    # Configure Flasgger Swagger UI
    _app_name = os.environ.get('APP_NAME') or app.config.get('APP_NAME') or 'Convoharbor'
    _backend_url = os.environ.get('BACKEND_URL') or app.config.get('BACKEND_URL') or 'http://localhost:5001'
    # Derive host from BACKEND_URL (strip protocol)
    _backend_host = _backend_url.replace('http://', '').replace('https://', '').rstrip('/')
    _scheme = 'https' if _backend_url.startswith('https://') else 'http'

    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": 'apispec',
                "route": '/apispec.json',
                "rule_filter": lambda rule: True,  # all in
                "model_filter": lambda tag: True,  # all in
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/docs/",
        "title": f"{_app_name} Multi-Tenant API",
        "version": "1.0.0",
        "description": "This API provides a secure, multi-tenant platform for managing AI chatbots, document processing, and conversations.",
        "termsOfService": "",
        "contact": {
            "name": f"{_app_name} Support",
            "url": f"https://{_app_name.lower()}.com/support",
            "email": f"support@{_app_name.lower()}.com"
        },
        "license": {
            "name": "Proprietary",
            "url": f"https://{_app_name.lower()}.com/license"
        }
    }

    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": f"{_app_name} Multi-Tenant API",
            "description": "This API provides a secure, multi-tenant platform for managing AI chatbots, document processing, and conversations.",
            "contact": {
                "name": f"{_app_name} Support",
                "url": f"https://{_app_name.lower()}.com/support",
                "email": f"support@{_app_name.lower()}.com"
            },
            "license": {
                "name": "Proprietary",
                "url": f"https://{_app_name.lower()}.com/license"
            },
            "version": "1.0.0"
        },
        "host": _backend_host,
        "basePath": "/api/v1",
        "schemes": [_scheme],
        "securityDefinitions": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "JWT token in the format: Bearer <token>"
            }
        },
        "security": [{"Bearer": []}],
        "consumes": ["application/json"],
        "produces": ["application/json"]
    }

    # Initialize Flasgger
    Swagger(app, config=swagger_config, template=swagger_template)

    app.config['SQLALCHEMY_POOL_RECYCLE'] = 280  # Recycle connections after 280 seconds (less than most timeouts)
    app.config['SQLALCHEMY_POOL_PRE_PING'] = True

    # Ensure upload directory exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    # Initialize CORS with dynamic origin from config
    # The origin must be in a list, even if it's just one.
    frontend_url = app.config.get('FRONTEND_URL', '').rstrip('/')
    cors_origins = [frontend_url]
    # Also allow localhost for development
    if 'localhost' in (frontend_url or ''):
        cors_origins.append('http://localhost:3000')
        cors_origins.append('https://localhost:3000')
    CORS(app,
         resources={r"/api/*": {"origins": cors_origins}},
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization", "X-Tenant-ID", "X-Requested-With"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"])

    # ============================================================
    # Initialize Redis (optional - controlled by REDIS_ENABLED)
    # ============================================================
    if app.config.get('REDIS_ENABLED', False):
        try:
            from .services.redis_service import RedisService
            app.redis_service = RedisService(
                redis_url=app.config.get('REDIS_URL', 'redis://localhost:6379/0'),
                socket_timeout=app.config.get('REDIS_SOCKET_TIMEOUT', 5),
                cache_ttl=app.config.get('REDIS_CACHE_TTL', 300),
                rate_limit=app.config.get('REDIS_RATE_LIMIT', 120),
                app=app
            )
            app.logger.info("Redis service initialized on startup")
        except Exception as e:
            app.logger.warning(f"Redis initialization failed (set REDIS_ENABLED=false to skip): {e}")
            app.redis_service = None
    else:
        app.redis_service = None
        app.logger.info("Redis disabled (set REDIS_ENABLED=true to enable)")

    # Initialize Cloudinary service
    try:
        from .services.cloudinary_service import CloudinaryService
        app.cloudinary_service = CloudinaryService(app)
        app.logger.info("Cloudinary service initialized")
    except Exception as e:
        app.logger.warning(f"Cloudinary initialization skipped: {e}")
        app.cloudinary_service = None

    # Initialize services and attach to app context
    with app.app_context():
        try:
            from .services.database_service import DatabaseService
            from .services.auth_service import AuthService
            from .services.config_service import ConfigService
            from .services.tenant_service import TenantService
            from .services.ai_connector import AIConnectorService
            from .services.token_tracking_service import TokenTrackingService
            from .services.vector_service import VectorService
            from .services.llm_service import LLMService
            from .services.prompt_service import PromptService
            from .services.embedding_service import generate_embeddings_for_texts
            from .services.websocket_service import websocket_service
            from .services.intent_analysis_service import IntentAnalysisService

            app.db_service = DatabaseService()
            app.auth_service = AuthService()
            app.config_service = ConfigService()
            app.tenant_service = TenantService()
            app.ai_connector = AIConnectorService()
            app.token_tracker = TokenTrackingService()
            app.vector_service = VectorService()
            app.llm_service = LLMService()
            app.prompt_service = PromptService()

            class EmbeddingServiceWrapper:
                def generate_embeddings_for_texts(self, texts, on_batch_start=None, on_batch_done=None):
                    return generate_embeddings_for_texts(
                        texts,
                        on_batch_start=on_batch_start,
                        on_batch_done=on_batch_done,
                    )

            app.embedding_service = EmbeddingServiceWrapper()

            websocket_service.socketio.init_app(app)
            app.websocket_service = websocket_service
            app.socketio = websocket_service.socketio

            app.intent_analysis_service = IntentAnalysisService()

        except (ValueError, ImportError) as e:
            app.logger.error(f"Could not initialize a service: {e}")
            app.db_service = None
            app.auth_service = None
            app.config_service = None
            app.tenant_service = None
            app.ai_connector = None
            app.token_tracker = None
            app.vector_service = None
            app.llm_service = None
            app.prompt_service = None
            app.embedding_service = None
            app.websocket_service = None

    # Register tenant middleware
    from .middleware import setup_tenant_context, teardown_tenant_context
    app.before_request(setup_tenant_context)
    app.teardown_appcontext(teardown_tenant_context)

    # Register blueprints
    from .main import main as main_blueprint
    from .api import api as api_blueprint

    # Register blueprints with URL prefixes
    app.register_blueprint(main_blueprint, url_prefix='/api/v1')
    # Register API blueprint with /api/v1 prefix to match Swagger docs
    app.register_blueprint(api_blueprint, url_prefix='/api/v1')

    # Register CLI commands
    from .cli_commands import seed_ai_models_command, list_ai_models_command
    app.cli.add_command(seed_ai_models_command)
    app.cli.add_command(list_ai_models_command)

    # Register the stuck-data-source watchdog. On startup (and on every
    # call to /api/v1/admin/datasources/sweep) we mark any DataSource
    # that has been in 'processing' / 'pending' for too long as 'failed'
    # so the UI does not get stuck on "uploading…" forever.
    _sweep_and_log(app)

    return app


def _sweep_and_log(app):
    """Run the stuck-data-source sweep once at startup."""
    try:
        # Import lazily so this module can finish loading even if the
        # datasources blueprint isn't imported yet at app construction.
        from .api.datasources import sweep_stuck_data_sources
        with app.app_context():
            result = sweep_stuck_data_sources(max_age_seconds=600)
            if result.get('marked_failed', 0) > 0:
                app.logger.warning(
                    f"🧹 Startup sweep: marked {result['marked_failed']} "
                    f"stuck data source(s) as 'failed'"
                )
    except Exception as e:  # noqa: BLE001
        app.logger.warning(f"Startup data-source sweep skipped: {e}")


# Import models here to make them accessible for Flask-Migrate
from . import models  # noqa: E402,F401
