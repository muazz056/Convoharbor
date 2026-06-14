# app/api/chatbots.py

from flask import request, current_app, jsonify, g
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import re
from . import api
from ..decorators import login_required, super_admin_required
from ..models import Chatbot, DataSource, Tenant, AiModel
from .. import db
from ..services import chatbot_defaults
from flasgger.utils import swag_from


def _context_has_meaningful_content(text):
    """Check if text has enough readable English words vs binary garbage (corrupted embeddings)."""
    if not text or not text.strip():
        return False
    words = re.findall(r'[A-Za-z]{3,}', text)
    return len(words) >= 5


def _context_relevant_to_query(context_text, query):
    """Quick heuristic: if the query's key noun is absent from context, context likely doesn't answer it."""
    if not context_text or not query:
        return True
    query_lower = query.lower()
    context_lower = context_text.lower()
    query_words = [w for w in re.findall(r'[A-Za-z0-9]{4,}', query_lower) if w not in {'what', 'when', 'where', 'why', 'how', 'does', 'is', 'the', 'this', 'that', 'with', 'from', 'have', 'are', 'was', 'were', 'can', 'you', 'tell', 'give', 'some'}]
    if not query_words:
        return True
    for w in query_words:
        if w in context_lower:
            return True
    return False


@api.route('/chatbots', methods=['POST'])
@login_required
@swag_from({
    'tags': ['Chatbot Management'],
    'summary': 'Create a new chatbot',
    'description': """
    ### 🤖 Description
    Creates a new chatbot instance for the authenticated user's tenant. The chatbot can be configured with specific AI models, personality traits, and operational parameters.

    Each tenant can create multiple chatbots for different use cases (support, sales, general assistance, etc.).

    ---
    ### 🔑 Authorization
    Requires authentication. The chatbot will be automatically associated with the user's tenant.
    """,
    'consumes': ['application/json'],
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'description': 'Chatbot configuration data',
            'schema': {
                'type': 'object',
                'required': ['name'],
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Unique name for the chatbot within the tenant',
                        'example': 'Customer Support Bot'
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Brief description of the chatbot\'s purpose',
                        'example': 'Handles customer inquiries and support tickets'
                    },
                    'type': {
                        'type': 'string',
                        'enum': ['support', 'sales', 'general', 'hr', 'technical'],
                        'description': 'Category/type of the chatbot',
                        'example': 'support'
                    },
                    'ai_model': {
                        'type': 'string',
                        'description': 'AI model name to use for this chatbot. Must be an active model configured by Super Admin in the AI Models page.',
                        'example': '<configured-model-name>'
                    },
                    'personality': {
                        'type': 'object',
                        'description': 'Personality configuration for the chatbot',
                        'properties': {
                            'role': {'type': 'string', 'example': 'Customer Support Specialist'},
                            'tone': {'type': 'string', 'example': 'friendly and professional'},
                            'style': {'type': 'string', 'example': 'concise and helpful'},
                            'expertise_areas': {'type': 'array', 'items': {'type': 'string'}, 'example': ['technical support', 'billing', 'account management']}
                        }
                    },
                    'prompts': {
                        'type': 'object',
                        'description': 'Custom prompts and instructions',
                        'properties': {
                            'system_message': {'type': 'string', 'example': 'You are a helpful customer support representative...'},
                            'greeting': {'type': 'string', 'example': 'Hello! How can I assist you today?'},
                            'fallback': {'type': 'string', 'example': 'I apologize, but I need to connect you with a human agent for this request.'}
                        }
                    },
                    'temperature': {
                        'type': 'number',
                        'format': 'float',
                        'minimum': 0.0,
                        'maximum': 1.0,
                        'description': 'Response creativity level (0.0 = factual, 1.0 = creative)',
                        'example': 0.3
                    },
                    'max_tokens': {
                        'type': 'integer',
                        'minimum': 50,
                        'maximum': 4000,
                        'description': 'Maximum tokens per response',
                        'example': 1000
                    },
                    'fallback_model': {
                        'type': 'string',
                        'description': 'Backup model name to use if primary model fails. Must be an active model configured by Super Admin.',
                        'example': '<configured-model-name>'
                    },
                    'status': {
                        'type': 'string',
                        'enum': ['active', 'inactive', 'training'],
                        'description': 'Current status of the chatbot',
                        'example': 'active'
                    }
                }
            }
        }
    ],
    'responses': {
        '201': {
            'description': 'Chatbot created successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'chatbot': {'$ref': '#/definitions/ChatbotResponse'}
                }
            }
        },
        '400': {
            'description': 'Bad Request - Invalid data or duplicate name',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '401': {
            'description': 'Unauthorized - Invalid or missing authentication',
            'schema': {'$ref': '#/definitions/Error'}
        }
    },
    'definitions': {
        'ChatbotResponse': {
            'type': 'object',
            'properties': {
                'id': {'type': 'integer'},
                'name': {'type': 'string'},
                'description': {'type': 'string'},
                'type': {'type': 'string'},
                'status': {'type': 'string'},
                'ai_model': {'type': 'string'},
                'personality': {'type': 'object'},
                'prompts': {'type': 'object'},
                'temperature': {'type': 'number'},
                'max_tokens': {'type': 'integer'},
                'fallback_model': {'type': 'string'},
                'created_at': {'type': 'string', 'format': 'date-time'},
                'updated_at': {'type': 'string', 'format': 'date-time'}
            }
        },
        'Error': {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'message': {'type': 'string'}
            }
        }
    }
})
def create_chatbot():
    """Create a new chatbot for the authenticated user's tenant"""
    data = request.get_json()

    if not data or 'name' not in data:
        return jsonify({'error': 'Missing required field: name'}), 400

    # Get user's tenant ID
    tenant_id = g.tenant_id

    # Validate name uniqueness within tenant
    existing_chatbot = Chatbot.query.filter_by(
        tenant_id=tenant_id,
        name=data['name']
    ).first()

    if existing_chatbot:
        return jsonify({
            'error': 'Chatbot name already exists',
            'message': f'A chatbot named "{data["name"]}" already exists in your organization'
        }), 400

    temperature = data.get('temperature')
    if temperature is not None:
        err = chatbot_defaults.validate_field('temperature', temperature)
        if err:
            return jsonify({'error': 'Invalid temperature', 'message': err}), 400

    max_tokens = data.get('max_tokens')
    if max_tokens is not None:
        err = chatbot_defaults.validate_field('max_tokens', max_tokens)
        if err:
            return jsonify({'error': 'Invalid max_tokens', 'message': err}), 400

    top_k = data.get('top_k')
    if top_k is not None:
        err = chatbot_defaults.validate_field('top_k', top_k)
        if err:
            return jsonify({'error': 'Invalid top_k', 'message': err}), 400

    mode = data.get('mode')
    if mode is not None:
        err = chatbot_defaults.validate_field('mode', mode)
        if err:
            return jsonify({'error': 'Invalid mode', 'message': err}), 400

    ai_model_id = data.get('ai_model_id')
    ai_model_name = data.get('ai_model') or data.get('model')
    ai_model_obj = None
    if ai_model_id:
        ai_model_obj = AiModel.query.filter_by(id=ai_model_id, is_active=True).first()
        if not ai_model_obj:
            return jsonify({'error': f'AI model with id {ai_model_id} not found or inactive'}), 400
        ai_model_name = ai_model_obj.model_name
    elif ai_model_name:
        ai_model_obj = AiModel.query.filter_by(model_name=ai_model_name, is_active=True).first()
        if not ai_model_obj:
            valid_models = [m.model_name for m in AiModel.query.filter_by(is_active=True).all()]
            return jsonify({
                'error': 'Invalid AI model',
                'message': f'Model "{ai_model_name}" is not available. Only models set by super admin are allowed.',
                'valid_models': valid_models
            }), 400
    else:
        ai_model_obj = AiModel.query.filter_by(is_active=True).first()
        if ai_model_obj:
            ai_model_name = ai_model_obj.model_name

    try:
        # If neither ai_model_id nor ai_model_name resolved to an active AiModel row,
        # do NOT invent a hardcoded fallback. The Super Admin must have at least one
        # active model configured. resolve_model() picks the first active model.
        try:
            from ..services.model_resolver import resolve_model
            resolved_name, resolved_provider = resolve_model({
                'ai_model_id': ai_model_obj.id if ai_model_obj else None,
                'ai_model': ai_model_name,
                'ai_provider': data.get('ai_provider'),
            })
        except ValueError as exc:
            return jsonify({
                'error': 'No active AI model configured',
                'message': str(exc),
            }), 400

        config = {
            'ai_model_id': ai_model_obj.id if ai_model_obj else None,
            'ai_model': resolved_name,
            'model': resolved_name,
            'ai_provider': ai_model_obj.provider if ai_model_obj else resolved_provider,
            # Four restricted fields: use the request value if provided,
            # otherwise the .env-backed default. Every consumer in the app
            # reads the effective value through chatbot_defaults.resolve_field
            # so a single source of truth is enforced.
            'temperature': temperature if temperature is not None else chatbot_defaults.get_defaults()['temperature'],
            'max_tokens': max_tokens if max_tokens is not None else chatbot_defaults.get_defaults()['max_tokens'],
            'top_k': top_k if top_k is not None else chatbot_defaults.get_defaults()['top_k'],
            'mode': mode if mode is not None else chatbot_defaults.get_defaults()['mode'],
            'fallback_model': data.get('fallback_model'),
            'personality': data.get('personality', {}),
            'prompts': data.get('prompts', {}),
            'created_by': g.user_id
        }
        # Persist theme configuration if provided during creation
        try:
            theme_cfg = data.get('theme')
            if isinstance(theme_cfg, dict):
                config['theme'] = theme_cfg
        except Exception:
            pass

        # Create new chatbot
        chatbot = Chatbot(
            tenant_id=tenant_id,
            name=data['name'],
            description=data.get('description', ''),
            type=data.get('type', 'general'),
            status=data.get('status', 'active'),
            config=config
        )

        db.session.add(chatbot)
        db.session.commit()

        current_app.logger.info(f"✅ Chatbot created: {chatbot.name} (ID: {chatbot.id}) for tenant {tenant_id}")

        return jsonify({
            'message': 'Chatbot created successfully',
            'chatbot': _format_chatbot_response(chatbot)
        }), 201

    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Database error creating chatbot: {e}")
        return jsonify({
            'error': 'Database error',
            'message': 'Failed to create chatbot due to database constraints'
        }), 400

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Unexpected error creating chatbot: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred while creating the chatbot'
        }), 500


@api.route('/chatbots', methods=['GET'])
@login_required
@swag_from({
    'tags': ['Chatbot Management'],
    'summary': 'List chatbots for the current tenant',
    'description': """
    ### 📋 Description
    Returns a paginated list of all chatbots belonging to the authenticated user's tenant.
    Supports filtering by type and status, and includes pagination for large datasets.

    ---
    ### 🔑 Authorization
    Requires authentication. Only returns chatbots owned by the user's tenant.
    """,
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'page',
            'in': 'query',
            'type': 'integer',
            'minimum': 1,
            'description': 'Page number for pagination',
            'example': 1
        },
        {
            'name': 'per_page',
            'in': 'query',
            'type': 'integer',
            'minimum': 1,
            'maximum': 100,
            'description': 'Number of items per page (max 100)',
            'example': 20
        },
        {
            'name': 'type',
            'in': 'query',
            'type': 'string',
            'enum': ['support', 'sales', 'general', 'hr', 'technical'],
            'description': 'Filter by chatbot type'
        },
        {
            'name': 'status',
            'in': 'query',
            'type': 'string',
            'enum': ['active', 'inactive', 'training'],
            'description': 'Filter by chatbot status'
        }
    ],
    'responses': {
        '200': {
            'description': 'Chatbots retrieved successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'chatbots': {
                        'type': 'array',
                        'items': {'$ref': '#/definitions/ChatbotResponse'}
                    },
                    'pagination': {
                        'type': 'object',
                        'properties': {
                            'page': {'type': 'integer'},
                            'pages': {'type': 'integer'},
                            'total': {'type': 'integer'},
                            'per_page': {'type': 'integer'}
                        }
                    }
                }
            }
        },
        '401': {
            'description': 'Unauthorized',
            'schema': {'$ref': '#/definitions/Error'}
        }
    }
})
def list_chatbots():
    """List all chatbots for the authenticated user's tenant"""
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    # Get filter parameters
    chatbot_type = request.args.get('type')
    status = request.args.get('status')

    # Build query for user's tenant
    query = Chatbot.query.filter_by(tenant_id=g.tenant_id)

    # Apply filters
    if chatbot_type:
        query = query.filter_by(type=chatbot_type)
    if status:
        query = query.filter_by(status=status)

    # Order by creation date (newest first)
    query = query.order_by(Chatbot.created_at.desc())

    # Paginate results
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    chatbots = pagination.items

    # current_app.logger.info(f"📋 Listed {len(chatbots)} chatbots for tenant {g.tenant_id}")

    return jsonify({
        'chatbots': [_format_chatbot_response(bot) for bot in chatbots],
        'pagination': {
            'page': pagination.page,
            'pages': pagination.pages,
            'total': pagination.total,
            'per_page': pagination.per_page
        }
    }), 200


@api.route('/chatbots/all', methods=['GET'])
@login_required
@super_admin_required
@swag_from({
    'tags': ['Super Admin'],
    'summary': 'List ALL chatbots across all tenants (Super Admin only)',
    'description': """
    ### 🔐 Description
    Returns a paginated list of ALL chatbots across ALL tenants. This endpoint is restricted to super administrators only.
    Includes tenant information for each chatbot to help identify ownership.

    ---
    ### 🔑 Authorization
    Requires super admin authentication. Regular users and tenant admins cannot access this endpoint.
    """,
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'page',
            'in': 'query',
            'type': 'integer',
            'minimum': 1,
            'description': 'Page number for pagination',
            'example': 1
        },
        {
            'name': 'per_page',
            'in': 'query',
            'type': 'integer',
            'minimum': 1,
            'maximum': 100,
            'description': 'Number of items per page (max 100)',
            'example': 20
        },
        {
            'name': 'type',
            'in': 'query',
            'type': 'string',
            'enum': ['support', 'sales', 'general', 'hr', 'technical'],
            'description': 'Filter by chatbot type'
        },
        {
            'name': 'status',
            'in': 'query',
            'type': 'string',
            'enum': ['active', 'inactive', 'training'],
            'description': 'Filter by chatbot status'
        }
    ],
    'responses': {
        '200': {
            'description': 'List of all chatbots retrieved successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'chatbots': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'integer'},
                                'name': {'type': 'string'},
                                'description': {'type': 'string'},
                                'type': {'type': 'string'},
                                'status': {'type': 'string'},
                                'ai_model': {'type': 'string'},
                                'tenant_id': {'type': 'integer'},
                                'tenant_name': {'type': 'string'},
                                'created_at': {'type': 'string'},
                                'updated_at': {'type': 'string'}
                            }
                        }
                    },
                    'pagination': {
                        'type': 'object',
                        'properties': {
                            'page': {'type': 'integer'},
                            'pages': {'type': 'integer'},
                            'total': {'type': 'integer'},
                            'per_page': {'type': 'integer'}
                        }
                    }
                }
            }
        },
        '403': {
            'description': 'Forbidden - Super admin access required'
        }
    }
})
def list_all_chatbots():
    """List ALL chatbots across all tenants (Super Admin only)"""
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    # Get filter parameters
    chatbot_type = request.args.get('type')
    status = request.args.get('status')
    email_filter = request.args.get('email')  # New email filter
    search_query = request.args.get('search')  # New search parameter

    # Import User model
    from ..models import User

    # Build query for ALL chatbots with tenant and user information
    # Note: PostgreSQL uses ->> for JSON text extraction and ::int for casting
    query = db.session.query(Chatbot, Tenant, User).join(
        Tenant, Chatbot.tenant_id == Tenant.id
    ).outerjoin(
        User,
        db.and_(
            User.tenant_id == Chatbot.tenant_id,
            User.id == db.cast(
                Chatbot.config.op('->>')('created_by'),
                db.Integer
            )
        )
    )

    # Apply filters
    if chatbot_type:
        query = query.filter(Chatbot.type == chatbot_type)
    if status:
        query = query.filter(Chatbot.status == status)
    if email_filter:
        query = query.filter(User.email.ilike(f'%{email_filter}%'))
    if search_query:
        # Search in chatbot name, description, tenant name, or user email
        search_term = f'%{search_query}%'
        query = query.filter(
            db.or_(
                Chatbot.name.ilike(search_term),
                Chatbot.description.ilike(search_term),
                Tenant.name.ilike(search_term),
                User.email.ilike(search_term)
            )
        )

    # Order by creation date (newest first)
    query = query.order_by(Chatbot.created_at.desc())

    # Paginate results
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    chatbot_tenant_user_tuples = pagination.items

    current_app.logger.info(f"📋 Super admin listed {len(chatbot_tenant_user_tuples)} chatbots across all tenants")

    # Format response with tenant and user information
    chatbots_data = []
    for chatbot, tenant, user in chatbot_tenant_user_tuples:
        chatbot_dict = _format_chatbot_response(chatbot)
        chatbot_dict['tenant_name'] = tenant.name
        chatbot_dict['created_by_email'] = user.email if user else 'Unknown'
        chatbot_dict['created_by_name'] = f"{user.first_name} {user.last_name}".strip() if user and user.first_name else (user.email if user else 'Unknown')
        chatbots_data.append(chatbot_dict)

    # Get unique emails for filter dropdown
    unique_emails_query = db.session.query(User.email).join(
        Chatbot,
        db.and_(
            User.tenant_id == Chatbot.tenant_id,
            User.id == db.cast(
                Chatbot.config.op('->>')('created_by'),
                db.Integer
            )
        )
    ).distinct().order_by(User.email)

    unique_emails = [email[0] for email in unique_emails_query.all() if email[0]]

    return jsonify({
        'chatbots': chatbots_data,
        'pagination': {
            'page': pagination.page,
            'pages': pagination.pages,
            'total': pagination.total,
            'per_page': pagination.per_page
        },
        'filters': {
            'unique_emails': unique_emails
        }
    }), 200


@api.route('/chatbots/<int:chatbot_id>/admin', methods=['GET'])
@login_required
@super_admin_required
@swag_from({
    'tags': ['Super Admin'],
    'summary': 'Get specific chatbot details (Super Admin)',
    'description': """
    ### 🔐 Description
    Returns detailed information about a specific chatbot across any tenant. This endpoint is restricted to super administrators only.

    ---
    ### 🔑 Authorization
    Requires super admin authentication. Regular users and tenant admins cannot access this endpoint.
    """,
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'chatbot_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'Unique identifier of the chatbot'
        }
    ],
    'responses': {
        '200': {
            'description': 'Chatbot details retrieved successfully'
        },
        '404': {
            'description': 'Chatbot not found'
        },
        '403': {
            'description': 'Forbidden - Super admin access required'
        }
    }
})
def get_chatbot_admin(chatbot_id):
    """Get specific chatbot details for super admin (any tenant)"""
    # Super admin can access any chatbot regardless of tenant
    chatbot = Chatbot.query.get_or_404(chatbot_id)

    current_app.logger.info(f"🔍 Super admin retrieved chatbot {chatbot_id} from tenant {chatbot.tenant_id}")

    return jsonify(_format_chatbot_response(chatbot)), 200


@api.route('/chatbots/<int:chatbot_id>', methods=['GET'])
@login_required
@swag_from({
    'tags': ['Chatbot Management'],
    'summary': 'Get specific chatbot details',
    'description': """
    ### 🔍 Description
    Retrieves detailed information about a specific chatbot, including its full configuration.
    Only returns chatbots owned by the authenticated user's tenant.

    ---
    ### 🔑 Authorization
    Requires authentication and chatbot must belong to user's tenant.
    """,
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'chatbot_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'ID of the chatbot to retrieve'
        }
    ],
    'responses': {
        '200': {
            'description': 'Chatbot details retrieved successfully',
            'schema': {'$ref': '#/definitions/ChatbotResponse'}
        },
        '404': {
            'description': 'Chatbot not found or access denied',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '401': {
            'description': 'Unauthorized',
            'schema': {'$ref': '#/definitions/Error'}
        }
    }
})
def get_chatbot(chatbot_id):
    """Get details of a specific chatbot"""
    chatbot = Chatbot.query.filter_by(
        id=chatbot_id,
        tenant_id=g.tenant_id
    ).first()

    if not chatbot:
        return jsonify({
            'error': 'Chatbot not found',
            'message': f'No chatbot found with ID {chatbot_id} in your organization'
        }), 404

    current_app.logger.info(f"🔍 Retrieved chatbot: {chatbot.name} (ID: {chatbot.id})")

    return jsonify(_format_chatbot_response(chatbot)), 200


@api.route('/chatbots/<int:chatbot_id>/admin', methods=['PUT'])
@login_required
@super_admin_required
@swag_from({
    'tags': ['Super Admin'],
    'summary': 'Update chatbot configuration (Super Admin)',
    'description': """
    ### 🔐 Description
    Updates the configuration of any chatbot across any tenant. This endpoint is restricted to super administrators only.
    All fields are optional - only provided fields will be updated.

    ---
    ### 🔑 Authorization
    Requires super admin authentication. Regular users and tenant admins cannot access this endpoint.
    """,
    'consumes': ['application/json'],
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'chatbot_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'Unique identifier of the chatbot'
        },
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'description': 'Updated chatbot configuration',
            'schema': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'description': {'type': 'string'},
                    'type': {'type': 'string'},
                    'ai_model': {'type': 'string'},
                    'temperature': {'type': 'number'},
                    'max_tokens': {'type': 'integer'},
                    'mode': {'type': 'string'},
                    'top_k': {'type': 'integer'},
                    'personality': {'type': 'object'},
                    'prompts': {'type': 'object'},
                    'theme': {'type': 'object'}
                }
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'Chatbot updated successfully'
        },
        '404': {
            'description': 'Chatbot not found'
        },
        '403': {
            'description': 'Forbidden - Super admin access required'
        }
    }
})
def update_chatbot_admin(chatbot_id):
    """Update chatbot configuration for super admin (any tenant)"""
    # Super admin can update any chatbot regardless of tenant
    chatbot = Chatbot.query.get_or_404(chatbot_id)

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Get current config or initialize empty dict
    config = chatbot.config or {}

    # Update basic fields
    if 'name' in data:
        chatbot.name = data['name']
    if 'description' in data:
        chatbot.description = data['description']
    if 'type' in data:
        chatbot.type = data['type']
    if 'status' in data:
        chatbot.status = data['status']

    # Update AI configuration
    ai_model_id = data.get('ai_model_id')
    ai_model_obj = None
    if ai_model_id is not None:
        ai_model_obj = AiModel.query.filter_by(id=ai_model_id, is_active=True).first()
        if not ai_model_obj:
            return jsonify({'error': f'AI model with id {ai_model_id} not found or inactive'}), 400
        config['ai_model_id'] = ai_model_obj.id
        config['ai_model'] = ai_model_obj.model_name
        config['model'] = ai_model_obj.model_name
        config['ai_provider'] = ai_model_obj.provider
    else:
        incoming_model = data.get('ai_model') or data.get('model')
        if incoming_model is not None:
            ai_model = incoming_model
            # Persist under both keys for compatibility
            config['ai_model'] = ai_model
            config['model'] = ai_model
            config['ai_model_id'] = None

            # If provider not explicitly provided, infer from model
            if 'ai_provider' not in data:
                inferred_provider = 'Google Gemini' if str(ai_model).startswith('models/gemini') or str(ai_model).startswith('gemini') else 'OpenAI'
                config['ai_provider'] = inferred_provider

    # Explicit provider provided by super admin wins
    if 'ai_provider' in data:
        config['ai_provider'] = data['ai_provider']
    if 'temperature' in data:
        config['temperature'] = float(data['temperature'])
    if 'max_tokens' in data:
        config['max_tokens'] = int(data['max_tokens'])
    if 'mode' in data:
        config['mode'] = data['mode']
    if 'top_k' in data:
        top_k = data['top_k']
        if not isinstance(top_k, int) or top_k < 1 or top_k > 50:
            return jsonify({
                'error': 'Invalid top_k',
                'message': 'top_k must be an integer between 1 and 50'
            }), 400
        config['top_k'] = top_k

    # Update personality and prompts
    if 'personality' in data:
        config['personality'] = data['personality']
    if 'prompts' in data:
        config['prompts'] = data['prompts']
    if 'theme' in data:
        config['theme'] = data['theme']

    # Save updated config
    current_app.logger.info(f"💾 Super admin updating chatbot {chatbot_id} with data: {data}")
    current_app.logger.info(f"💾 Final config before save: {config}")

    # Force SQLAlchemy to recognize the JSON field has changed
    from sqlalchemy.orm.attributes import flag_modified
    chatbot.config = config
    flag_modified(chatbot, 'config')

    chatbot.updated_at = datetime.utcnow()

    try:
        current_app.logger.info(f"💾 About to commit to database...")
        db.session.commit()
        current_app.logger.info(f"💾 Database commit completed")
        current_app.logger.info(f"✏️ Super admin updated chatbot {chatbot_id} from tenant {chatbot.tenant_id}")
        current_app.logger.info(f"🔍 Config after commit: {chatbot.config}")

        formatted_response = _format_chatbot_response(chatbot)
        current_app.logger.info(f"📤 Returning formatted response: {formatted_response}")

        return jsonify({
            'message': 'Chatbot updated successfully',
            'chatbot': formatted_response
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Error updating chatbot {chatbot_id}: {str(e)}")
        return jsonify({'error': 'Failed to update chatbot'}), 500


@api.route('/chatbots/<int:chatbot_id>', methods=['PUT'])
@login_required
@swag_from({
    'tags': ['Chatbot Management'],
    'summary': 'Update chatbot configuration',
    'description': """
    ### ✏️ Description
    Updates the configuration of an existing chatbot. All fields are optional - only provided fields will be updated.
    The chatbot must belong to the authenticated user's tenant.

    ---
    ### 🔑 Authorization
    Requires authentication and chatbot must belong to user's tenant.
    """,
    'consumes': ['application/json'],
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'chatbot_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'ID of the chatbot to update'
        },
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'description': 'Updated chatbot configuration (all fields optional)',
            'schema': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'description': {'type': 'string'},
                    'type': {'type': 'string', 'enum': ['support', 'sales', 'general', 'hr', 'technical']},
                    'ai_model': {'type': 'string'},
                    'personality': {'type': 'object'},
                    'prompts': {'type': 'object'},
                    'temperature': {'type': 'number', 'minimum': 0.0, 'maximum': 1.0},
                    'max_tokens': {'type': 'integer', 'minimum': 50, 'maximum': 4000},
                    'fallback_model': {'type': 'string'},
                    'status': {'type': 'string', 'enum': ['active', 'inactive', 'training']}
                }
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'Chatbot updated successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'chatbot': {'$ref': '#/definitions/ChatbotResponse'}
                }
            }
        },
        '400': {
            'description': 'Bad Request - Invalid data',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '404': {
            'description': 'Chatbot not found or access denied',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '401': {
            'description': 'Unauthorized',
            'schema': {'$ref': '#/definitions/Error'}
        }
    }
})
def update_chatbot(chatbot_id):
    """Update an existing chatbot configuration"""
    print(f"🔥 UPDATE_CHATBOT CALLED: chatbot_id={chatbot_id}")
    current_app.logger.info(f"🔥 UPDATE_CHATBOT CALLED: chatbot_id={chatbot_id}")

    chatbot = Chatbot.query.filter_by(
        id=chatbot_id,
        tenant_id=g.tenant_id
    ).first()

    if not chatbot:
        return jsonify({
            'error': 'Chatbot not found',
            'message': f'No chatbot found with ID {chatbot_id} in your organization'
        }), 404

    data = request.get_json()
    if not data:
        return jsonify({
            'error': 'Missing request body',
            'message': 'Request must contain JSON data'
        }), 400

    try:
        current_app.logger.info(f"🚀 Updating chatbot {chatbot_id} with data: {data}")
        current_app.logger.info(f"🔍 Current chatbot config: {chatbot.config}")

        # Update basic fields if provided
        if 'name' in data:
            # Check for name uniqueness (excluding current chatbot)
            existing = Chatbot.query.filter_by(
                tenant_id=g.tenant_id,
                name=data['name']
            ).filter(Chatbot.id != chatbot_id).first()

            if existing:
                return jsonify({
                    'error': 'Chatbot name already exists',
                    'message': f'Another chatbot named "{data["name"]}" already exists'
                }), 400

            chatbot.name = data['name']

        if 'description' in data:
            chatbot.description = data['description']

        if 'type' in data:
            chatbot.type = data['type']

        if 'status' in data:
            chatbot.status = data['status']

        # Update configuration fields
        config = chatbot.config or {}

        # Accept both ai_model and model
        incoming_model = data.get('ai_model') or data.get('model')
        current_app.logger.info(f"📝 Processing model update: incoming_model={incoming_model}")

        if incoming_model is not None:
            ai_model = incoming_model
            valid_models = [m.model_name for m in AiModel.query.filter_by(is_active=True).all()]

            current_app.logger.info(f"✅ Valid models from DB: {valid_models}")
            current_app.logger.info(f"🔍 Checking if {ai_model} is in valid models")

            if ai_model not in valid_models:
                current_app.logger.error(f"❌ Invalid model: {ai_model} not in {valid_models}")
                return jsonify({
                    'error': 'Invalid AI model',
                    'message': f'Model "{ai_model}" is not supported',
                    'valid_models': valid_models
                }), 400

            current_app.logger.info(f"✅ Model {ai_model} is valid, updating config")
            config['ai_model'] = ai_model
            config['model'] = ai_model

        # If provider provided explicitly, store it regardless of model change
        if 'ai_provider' in data:
            current_app.logger.info(f"📝 Setting provider from data: {data['ai_provider']}")
            config['ai_provider'] = data['ai_provider']
        # If provider missing but model changed above, infer from the new model
        elif incoming_model is not None:
            inferred_provider = 'Google Gemini' if str(ai_model).startswith('gemini') else 'OpenAI'
            current_app.logger.info(f"📝 Inferring provider from model {ai_model}: {inferred_provider}")
            config['ai_provider'] = inferred_provider

        # ============================================================
        # RESTRICTED FIELDS GATE
        # The four fields below (temperature, max_tokens, mode, top_k)
        # can ONLY be mutated by the Super Admin. Non-super-admin
        # requests that include any of these keys have them silently
        # stripped so the rest of the update (name, theme, personality,
        # etc.) still goes through. Super Admin can change everything.
        # ============================================================
        if chatbot_defaults.is_restricted_update_requested(data):
            if not chatbot_defaults.is_super_admin(getattr(g, 'role', None)):
                attempted = chatbot_defaults.extract_restricted_update(data)
                current_app.logger.info(
                    f"🔒 Non-super-admin (role={getattr(g, 'role', None)}) "
                    f"update — stripping restricted fields: "
                    f"{sorted(attempted.keys())} from chatbot {chatbot_id}"
                )
                for field in chatbot_defaults.RESTRICTED_FIELDS:
                    data.pop(field, None)

        if 'temperature' in data:
            temperature = data['temperature']
            err = chatbot_defaults.validate_field('temperature', temperature)
            if err:
                return jsonify({'error': 'Invalid temperature', 'message': err}), 400
            config['temperature'] = temperature

        if 'max_tokens' in data:
            max_tokens = data['max_tokens']
            err = chatbot_defaults.validate_field('max_tokens', max_tokens)
            if err:
                return jsonify({'error': 'Invalid max_tokens', 'message': err}), 400
            config['max_tokens'] = max_tokens

        if 'fallback_model' in data:
            config['fallback_model'] = data['fallback_model']

        if 'personality' in data:
            config['personality'] = data['personality']

        if 'prompts' in data:
            config['prompts'] = data['prompts']

        if 'theme' in data:
            theme_config = data['theme']
            # Validate theme configuration
            if isinstance(theme_config, dict):
                valid_positions = ['bottom-right', 'bottom-left', 'top-right', 'top-left']
                if 'position' in theme_config and theme_config['position'] not in valid_positions:
                    return jsonify({
                        'error': 'Invalid theme position',
                        'message': f'Position must be one of: {", ".join(valid_positions)}'
                    }), 400

                # Validate color format (basic hex validation)
                if 'primaryColor' in theme_config:
                    color = theme_config['primaryColor']
                    if not isinstance(color, str) or not color.startswith('#') or len(color) != 7:
                        return jsonify({
                            'error': 'Invalid color format',
                            'message': 'Primary color must be a valid hex color (e.g. #6366F1)'
                        }), 400

                config['theme'] = theme_config
                current_app.logger.info(f"🎨 Updated theme configuration: {theme_config}")

        if 'mode' in data:
            mode = data['mode']
            err = chatbot_defaults.validate_field('mode', mode)
            if err:
                return jsonify({'error': 'Invalid mode', 'message': err}), 400
            config['mode'] = mode
            current_app.logger.info(f"🔒 Updated mode configuration: {mode}")

        if 'top_k' in data:
            top_k = data['top_k']
            err = chatbot_defaults.validate_field('top_k', top_k)
            if err:
                return jsonify({'error': 'Invalid top_k', 'message': err}), 400
            config['top_k'] = top_k
            current_app.logger.info(f"📊 Updated top_k configuration: {top_k}")

        # Update the config and modified timestamp
        current_app.logger.info(f"💾 Final config before save: {config}")

        # Force SQLAlchemy to recognize the JSON field has changed
        from sqlalchemy.orm.attributes import flag_modified
        chatbot.config = config
        flag_modified(chatbot, 'config')

        chatbot.updated_at = datetime.utcnow()

        current_app.logger.info(f"💾 About to commit to database...")
        db.session.commit()
        current_app.logger.info(f"💾 Database commit completed")

        current_app.logger.info(f"✅ Chatbot updated: {chatbot.name} (ID: {chatbot.id})")
        current_app.logger.info(f"🔍 Config after commit: {chatbot.config}")

        formatted_response = _format_chatbot_response(chatbot)
        current_app.logger.info(f"📤 Returning formatted response: {formatted_response}")

        return jsonify({
            'message': 'Chatbot updated successfully',
            'chatbot': formatted_response
        }), 200

    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Database error updating chatbot: {e}")
        return jsonify({
            'error': 'Database error',
            'message': 'Failed to update chatbot due to database constraints'
        }), 400

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Unexpected error updating chatbot: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred while updating the chatbot'
        }), 500


@api.route('/chatbots/<int:chatbot_id>', methods=['DELETE'])
@login_required
@swag_from({
    'tags': ['Chatbot Management'],
    'summary': 'Delete a chatbot',
    'description': """
    ### 🗑️ Description
    Permanently deletes a chatbot and all its associated data including conversations and training data.
    This action cannot be undone. The chatbot must belong to the authenticated user's tenant.

    ---
    ### ⚠️ Warning
    This will permanently delete:
    - The chatbot configuration
    - All conversation history
    - Associated training data
    - Usage statistics

    ---
    ### 🔑 Authorization
    Requires authentication and chatbot must belong to user's tenant.
    """,
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'chatbot_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'ID of the chatbot to delete'
        }
    ],
    'responses': {
        '200': {
            'description': 'Chatbot deleted successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'}
                }
            }
        },
        '404': {
            'description': 'Chatbot not found or access denied',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '401': {
            'description': 'Unauthorized',
            'schema': {'$ref': '#/definitions/Error'}
        }
    }
})
def delete_chatbot(chatbot_id):
    """Delete a chatbot permanently"""
    chatbot = Chatbot.query.filter_by(
        id=chatbot_id,
        tenant_id=g.tenant_id
    ).first()

    if not chatbot:
        return jsonify({
            'error': 'Chatbot not found',
            'message': f'No chatbot found with ID {chatbot_id} in your organization'
        }), 404

    try:
        chatbot_name = chatbot.name
        current_app.logger.info(f"🔍 Starting deletion of chatbot: {chatbot_name} (ID: {chatbot_id})")

        # Delete child rows in correct FK order: messages -> conversations -> chatbot
        # 1) Delete messages for all conversations of this chatbot
        try:
            current_app.logger.info(f"🔍 Attempting to delete messages for chatbot {chatbot_id}")
            result = db.session.execute(
                db.text("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE chatbot_id = :chatbot_id)"),
                {"chatbot_id": chatbot.id}
            )
            db.session.commit()
            current_app.logger.info(f"🗑️ Deleted {result.rowcount} messages for chatbot {chatbot_id}")
        except Exception as msg_error:
            db.session.rollback()
            current_app.logger.warning(f"⚠️ Could not delete messages (table may not exist): {msg_error}")

        # 2) Delete notifications referencing these conversations
        try:
            current_app.logger.info(f"🔍 Attempting to delete notifications for chatbot {chatbot_id}")
            result = db.session.execute(
                db.text("DELETE FROM notifications WHERE conversation_id IN (SELECT id FROM conversations WHERE chatbot_id = :chatbot_id)"),
                {"chatbot_id": chatbot.id}
            )
            db.session.commit()
            current_app.logger.info(f"🗑️ Deleted {result.rowcount} notifications for chatbot {chatbot_id}")
        except Exception as notif_error:
            db.session.rollback()
            current_app.logger.warning(f"⚠️ Could not delete notifications: {notif_error}")

        # 3) Delete conversation_feedback referencing these conversations
        try:
            current_app.logger.info(f"🔍 Attempting to delete conversation_feedback for chatbot {chatbot_id}")
            result = db.session.execute(
                db.text("DELETE FROM conversation_feedback WHERE conversation_id IN (SELECT id FROM conversations WHERE chatbot_id = :chatbot_id)"),
                {"chatbot_id": chatbot.id}
            )
            db.session.commit()
            current_app.logger.info(f"🗑️ Deleted {result.rowcount} conversation_feedback for chatbot {chatbot_id}")
        except Exception as fb_error:
            db.session.rollback()
            current_app.logger.warning(f"⚠️ Could not delete conversation_feedback: {fb_error}")

        # 5) Delete conversations
        try:
            current_app.logger.info(f"🔍 Attempting to delete conversations for chatbot {chatbot_id}")
            result = db.session.execute(
                db.text("DELETE FROM conversations WHERE chatbot_id = :chatbot_id"),
                {"chatbot_id": chatbot.id}
            )
            db.session.commit()
            current_app.logger.info(f"🗑️ Deleted {result.rowcount} conversations for chatbot {chatbot_id}")
        except Exception as conv_error:
            db.session.rollback()
            current_app.logger.warning(f"⚠️ Could not delete conversations (table may not exist): {conv_error}")

        # 6) Try to delete associated data sources
        try:
            current_app.logger.info(f"🔍 Attempting to delete data sources for chatbot {chatbot_id}")
            deleted_count = DataSource.query.filter_by(chatbot_id=chatbot.id).count()
            DataSource.query.filter_by(chatbot_id=chatbot.id).delete()
            db.session.commit()
            current_app.logger.info(f"🗑️ Deleted {deleted_count} data sources for chatbot {chatbot_id}")
        except Exception as ds_error:
            db.session.rollback()
            current_app.logger.warning(f"⚠️ Could not delete data sources: {ds_error}")

        # 7) Delete document embeddings (vector store entries) for this chatbot
        try:
            current_app.logger.info(f"🔍 Attempting to delete document embeddings for chatbot {chatbot_id}")
            result = db.session.execute(
                db.text("DELETE FROM document_embeddings WHERE chatbot_id = :chatbot_id"),
                {"chatbot_id": chatbot.id}
            )
            db.session.commit()
            current_app.logger.info(f"🗑️ Deleted {result.rowcount} document embeddings for chatbot {chatbot_id}")
        except Exception as emb_error:
            db.session.rollback()
            current_app.logger.warning(f"⚠️ Could not delete document embeddings (table may not exist): {emb_error}")

        # 8) Delete the chatbot using raw SQL to avoid relationship issues
        try:
            current_app.logger.info(f"🔍 Attempting to delete chatbot {chatbot_id} directly")
            result = db.session.execute(
                db.text("DELETE FROM chatbots WHERE id = :chatbot_id AND tenant_id = :tenant_id"),
                {"chatbot_id": chatbot.id, "tenant_id": g.tenant_id}
            )
            db.session.commit()

            if result.rowcount > 0:
                current_app.logger.info(f"🗑️ Successfully deleted chatbot: {chatbot_name} (ID: {chatbot_id})")
                return jsonify({
                    'message': f'Chatbot "{chatbot_name}" has been permanently deleted'
                }), 200
            else:
                current_app.logger.error(f"❌ No chatbot was deleted - may have been deleted already")
                return jsonify({
                    'error': 'Chatbot not found',
                    'message': 'Chatbot may have already been deleted'
                }), 404

        except Exception as chatbot_error:
            db.session.rollback()
            current_app.logger.error(f"❌ Error deleting chatbot directly: {chatbot_error}")
            raise chatbot_error

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Error deleting chatbot: {e}")
        current_app.logger.error(f"❌ Error type: {type(e)}")
        current_app.logger.error(f"❌ Error args: {e.args}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred while deleting the chatbot'
        }), 500


@api.route('/chatbots/<int:chatbot_id>/admin', methods=['DELETE'])
@login_required
@super_admin_required
@swag_from({
    'tags': ['Super Admin'],
    'summary': 'Delete any chatbot (Super Admin)',
    'description': """
    ### 🗑️ Description
    Permanently deletes any chatbot across any tenant and all its associated data including conversations and training data.
    This action cannot be undone. This endpoint is restricted to super administrators only.

    ---
    ### ⚠️ Warning
    This will permanently delete:
    - The chatbot configuration
    - All conversation history
    - Associated training data
    - Usage statistics

    ---
    ### 🔑 Authorization
    Requires super admin authentication. Regular users and tenant admins cannot access this endpoint.
    """,
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'chatbot_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'ID of the chatbot to delete'
        }
    ],
    'responses': {
        '200': {
            'description': 'Chatbot deleted successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'}
                }
            }
        },
        '404': {
            'description': 'Chatbot not found'
        },
        '403': {
            'description': 'Forbidden - Super admin access required'
        }
    }
})
def delete_chatbot_admin(chatbot_id):
    """Delete any chatbot permanently (Super Admin only)"""
    # Super admin can delete any chatbot regardless of tenant
    chatbot = Chatbot.query.get_or_404(chatbot_id)

    try:
        chatbot_name = chatbot.name
        chatbot_tenant_id = chatbot.tenant_id

        current_app.logger.info(f"🗑️ Super admin deleting chatbot: {chatbot_name} (ID: {chatbot_id}) from tenant {chatbot_tenant_id}")

        # 1) Delete messages first
        try:
            current_app.logger.info(f"🔍 [Admin] Attempting to delete messages for chatbot {chatbot_id}")
            db.session.execute(
                db.text("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE chatbot_id = :chatbot_id)"),
                {"chatbot_id": chatbot.id}
            )
            db.session.commit()
        except Exception:
            db.session.rollback()

        # 2) Delete notifications referencing these conversations
        try:
            current_app.logger.info(f"🔍 [Admin] Attempting to delete notifications for chatbot {chatbot_id}")
            db.session.execute(
                db.text("DELETE FROM notifications WHERE conversation_id IN (SELECT id FROM conversations WHERE chatbot_id = :chatbot_id)"),
                {"chatbot_id": chatbot.id}
            )
            db.session.commit()
        except Exception:
            db.session.rollback()

        # 3) Delete conversation_feedback referencing these conversations
        try:
            current_app.logger.info(f"🔍 [Admin] Attempting to delete conversation_feedback for chatbot {chatbot_id}")
            db.session.execute(
                db.text("DELETE FROM conversation_feedback WHERE conversation_id IN (SELECT id FROM conversations WHERE chatbot_id = :chatbot_id)"),
                {"chatbot_id": chatbot.id}
            )
            db.session.commit()
        except Exception:
            db.session.rollback()

        # 4) Delete conversations
        try:
            current_app.logger.info(f"🔍 [Admin] Attempting to delete conversations for chatbot {chatbot_id}")
            db.session.execute(
                db.text("DELETE FROM conversations WHERE chatbot_id = :chatbot_id"),
                {"chatbot_id": chatbot.id}
            )
            db.session.commit()
            current_app.logger.info(f"🗑️ [Admin] Deleted conversations for chatbot {chatbot_id}")
        except Exception as conv_error:
            db.session.rollback()
            current_app.logger.warning(f"⚠️ [Admin] Could not delete conversations: {conv_error}")

        # 4) Try to delete associated data sources
        try:
            current_app.logger.info(f"🔍 Attempting to delete data sources for chatbot {chatbot_id}")
            deleted_count = DataSource.query.filter_by(chatbot_id=chatbot.id).count()
            DataSource.query.filter_by(chatbot_id=chatbot.id).delete()
            db.session.commit()
            current_app.logger.info(f"🗑️ Deleted {deleted_count} data sources for chatbot {chatbot_id}")
        except Exception as ds_error:
            db.session.rollback()
            current_app.logger.warning(f"⚠️ Could not delete data sources: {ds_error}")

        # Delete document embeddings (vector store entries) for this chatbot
        try:
            current_app.logger.info(f"🔍 Attempting to delete document embeddings for chatbot {chatbot_id}")
            result = db.session.execute(
                db.text("DELETE FROM document_embeddings WHERE chatbot_id = :chatbot_id"),
                {"chatbot_id": chatbot.id}
            )
            db.session.commit()
            current_app.logger.info(f"🗑️ Deleted {result.rowcount} document embeddings for chatbot {chatbot_id}")
        except Exception as emb_error:
            db.session.rollback()
            current_app.logger.warning(f"⚠️ Could not delete document embeddings (table may not exist): {emb_error}")

        # Delete the chatbot using raw SQL to avoid relationship issues
        try:
            current_app.logger.info(f"🔍 Attempting to delete chatbot {chatbot_id} directly")
            result = db.session.execute(
                db.text("DELETE FROM chatbots WHERE id = :chatbot_id"),
                {"chatbot_id": chatbot.id}
            )
            db.session.commit()

            if result.rowcount > 0:
                current_app.logger.info(f"🗑️ Super admin successfully deleted chatbot: {chatbot_name} (ID: {chatbot_id}) from tenant {chatbot_tenant_id}")
                return jsonify({
                    'message': f'Chatbot "{chatbot_name}" has been permanently deleted'
                }), 200
            else:
                current_app.logger.error(f"❌ No chatbot was deleted - may have been deleted already")
                return jsonify({
                    'error': 'Chatbot not found',
                    'message': 'Chatbot may have already been deleted'
                }), 404

        except Exception as chatbot_error:
            db.session.rollback()
            current_app.logger.error(f"❌ Error deleting chatbot directly: {chatbot_error}")
            raise chatbot_error

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Super admin error deleting chatbot: {e}")
        current_app.logger.error(f"❌ Error type: {type(e)}")
        current_app.logger.error(f"❌ Error args: {e.args}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred while deleting the chatbot'
        }), 500


def _format_chatbot_response(chatbot: Chatbot) -> dict:
    """
    Format chatbot model for API response

    Args:
        chatbot: Chatbot model instance

    Returns:
        Formatted chatbot data
    """
    config = chatbot.config or {}

    # Auto-migrate deprecated models on read (performance optimization)
    current_model = config.get('ai_model') or config.get('model')
    if current_model:
        deprecated_models = {
            'models/gemini-pro': 'models/gemini-2.5-flash',
            'gemini-pro': 'models/gemini-2.5-flash',
            'models/gemini-1.5-pro': 'models/gemini-2.5-pro',
            'gemini-1.5-pro': 'models/gemini-2.5-pro',
            'models/gemini-1.5-flash': 'models/gemini-2.5-flash',
            'gemini-1.5-flash': 'models/gemini-2.5-flash',
            'models/gemini-1.5-pro-latest': 'models/gemini-2.5-pro',
            'models/gemini-1.5-flash-latest': 'models/gemini-2.5-flash',
        }

        if current_model in deprecated_models:
            new_model = deprecated_models[current_model]
            # Update the config in memory (will be saved on next update)
            config['ai_model'] = new_model
            config['model'] = new_model
            # Note: We don't save to DB here to avoid write overhead on every read
            # The model will be updated in DB when the chatbot is next modified

    # Resolve all four restricted fields through the single source of truth
    # so the response always reflects the effective value (stored or .env default).
    eff_top_k = chatbot_defaults.resolve_field(config, 'top_k')
    eff_mode = chatbot_defaults.resolve_field(config, 'mode')
    eff_temperature = chatbot_defaults.resolve_field(config, 'temperature')
    eff_max_tokens = chatbot_defaults.resolve_field(config, 'max_tokens')

    return {
        'id': chatbot.id,
        'tenant_id': chatbot.tenant_id,
        'name': chatbot.name,
        'description': chatbot.description,
        'type': chatbot.type,
        'status': chatbot.status,
        'config': config,
        'ai_model_id': config.get('ai_model_id'),
        'ai_provider': config.get('ai_provider'),
        'ai_model': config.get('ai_model'),
        'model': config.get('model', config.get('ai_model')),
        'temperature': eff_temperature,
        'personality': config.get('personality', {}),
        'prompts': config.get('prompts', {}),
        'max_tokens': eff_max_tokens,
        'fallback_model': config.get('fallback_model'),
        'mode': eff_mode,
        'top_k': eff_top_k,
        'theme': config.get('theme', {}),
        'created_at': chatbot.created_at.isoformat() if chatbot.created_at else None,
        'updated_at': chatbot.updated_at.isoformat() if chatbot.updated_at else None
    }


@api.route('/chatbots/<int:chatbot_id>/public', methods=['GET'])
@swag_from({
    'tags': ['Chatbot Management'],
    'summary': 'Get public chatbot information',
    'description': 'Get basic chatbot information for public embed usage (no authentication required)',
    'parameters': [
        {
            'name': 'chatbot_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'Chatbot ID'
        }
    ],
    'responses': {
        '200': {
            'description': 'Chatbot information retrieved successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'chatbot': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer'},
                            'name': {'type': 'string'},
                            'description': {'type': 'string'},
                            'prompts': {'type': 'object'}
                        }
                    }
                }
            }
        },
        '404': {
            'description': 'Chatbot not found',
            'schema': {'$ref': '#/definitions/Error'}
        }
    }
})
def get_public_chatbot(chatbot_id):
    """Get public chatbot information for embed usage"""
    try:
        chatbot = Chatbot.query.get(chatbot_id)
        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404

        # Return only public information including theme config
        public_info = {
            'id': chatbot.id,
            'name': chatbot.name,
            'description': chatbot.description,
            'config': chatbot.config or {},
            'prompts': chatbot.config.get('prompts', {}) if chatbot.config else {}
        }

        return jsonify({'chatbot': public_info}), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching public chatbot info: {str(e)}")
        return jsonify({'error': 'Failed to fetch chatbot information'}), 500


@api.route('/chatbots/<int:chatbot_id>/test-message', methods=['POST'])
@login_required
def send_test_message(chatbot_id):
    """Send a test message to chatbot without storing conversation"""
    try:
        # Get chatbot with tenant verification (convert tenant UUID to internal integer ID)
        from ..models import Tenant
        tenant = Tenant.query.filter_by(tenant_id=g.user_tenant_id).first()
        if not tenant:
            current_app.logger.error(f"Tenant not found for UUID: {g.user_tenant_id}")
            return jsonify({'error': 'Tenant not found'}), 404

        tenant_integer_id = tenant.id

        chatbot = Chatbot.query.filter_by(
            id=chatbot_id,
            tenant_id=tenant_integer_id
        ).first()

        if not chatbot:
            return jsonify({'error': 'Chatbot not found'}), 404

        data = request.get_json()
        message = data.get('message', '').strip()
        conversation_history = data.get('conversation_history', [])

        if not message:
            return jsonify({'error': 'Message is required'}), 400

        # Knowledge-base restriction path (mirror embed chat logic)
        config = chatbot.config or {}
        try:
            from ..services.model_resolver import resolve_model
            ai_model, _ = resolve_model(config)
        except ValueError as exc:
            return jsonify({'error': 'No active AI model configured', 'message': str(exc)}), 400

        # Fetch context from knowledge base using semantic search (same as embed chat)
        context_text = ""
        try:
            if hasattr(current_app, 'vector_service') and current_app.vector_service:
                # Get top_k from chatbot config (resolved through the
                # single source of truth so .env defaults apply).
                config = chatbot.config or {}
                top_k = chatbot_defaults.resolve_field(config, 'top_k')

                # Perform semantic vector search (same method as embed chat)
                search_results = current_app.vector_service.search_similar(
                    query=message,
                    chatbot_id=chatbot_id,
                    limit=top_k
                )

                current_app.logger.info(f"🔍 Test chat vector search found {len(search_results)} results")

                if search_results:
                    # Extract content from search results (same as embed chat).
                    # Deduplicate by (source, content-prefix) so the same
                    # physical chunk ingested multiple times does not flood
                    # the context.
                    context_chunks = []
                    seen_keys = set()
                    seen_sources = set()
                    for idx, result in enumerate(search_results):
                        chunk_content = getattr(result, 'page_content', '') if hasattr(result, 'page_content') else result.get('page_content', '')
                        if not chunk_content:
                            continue
                        metadata = getattr(result, 'metadata', None) or {}
                        if not isinstance(metadata, dict):
                            metadata = {}
                        source = metadata.get('source', 'unknown')
                        seen_sources.add(source)
                        dedup_key = (
                            source,
                            metadata.get('doc_id', ''),
                            metadata.get('chunk_index', -1),
                            chunk_content[:80],
                        )
                        if dedup_key in seen_keys:
                            current_app.logger.info(
                                f"🔍 Test chat chunk {idx+1} skipped (duplicate of earlier chunk)"
                            )
                            continue
                        seen_keys.add(dedup_key)
                        context_chunks.append(chunk_content)
                        current_app.logger.info(
                            f"🔍 Test chat chunk {idx+1} "
                            f"source={source!r} "
                            f"len={len(chunk_content)} "
                            f"preview={chunk_content[:150]!r}"
                        )

                    current_app.logger.info(
                        f"🔍 Test chat retrieved from {len(seen_sources)} source(s): {sorted(seen_sources)}"
                    )

                    context_text = "\n\n".join(context_chunks)
                    current_app.logger.info(f"🔍 Test chat found {len(context_chunks)} matching chunks, total context length: {len(context_text)}")
                else:
                    current_app.logger.info(f"🔍 Test chat found no matching chunks")
            else:
                current_app.logger.warning(f"🔍 Test chat: Vector service not available")
        except Exception as e:
            current_app.logger.warning(f"Test chat KB context fetch error: {e}")

        # Use conversation service to determine restriction based on mode
        from ..services.conversation_service import ConversationService
        conversation_service = ConversationService()

        # Check for greetings and farewells
        is_greeting = conversation_service.is_greeting(message)

        # Smart farewell: check if last assistant message had a follow-up question
        last_assistant_msg = ""
        history = data.get('conversation_history', [])
        for msg in reversed(history):
            if msg.get('role') == 'assistant':
                last_assistant_msg = msg.get('content', '')
                break
        is_farewell = conversation_service.is_smart_farewell(message, last_assistant_msg)

        # Handle greetings and farewells with special responses
        # IMPORTANT: farewell takes priority over greeting — if user says "hi bye"
        # or "thanks" after the conversation is wrapping up, treat as farewell
        if is_farewell:
            farewell_response = conversation_service.get_farewell_response(config)
            # Test mode: include show_rating so the widget shows the rating UI
            return jsonify({
                'success': True,
                'response': farewell_response,
                'show_rating': True,
                'rating_message': 'How would you rate your experience? (Test mode)',
                'message': 'Test farewell processed successfully'
            })
        elif is_greeting:
            greeting_response = conversation_service.get_greeting_response(config)
            return jsonify({'success': True, 'response': greeting_response, 'message': 'Test greeting processed successfully'})

        # Determine restriction based on chatbot mode configuration
        restrict_to_knowledge_base = conversation_service.should_restrict_to_knowledge_base(message, config)

        current_app.logger.info(f"🧪 Test mode: restrict_to_knowledge_base = {restrict_to_knowledge_base}")
        current_app.logger.info(f"🧪 Test mode: Found context = {bool(context_text and context_text.strip())}")
        current_app.logger.info(
            f"🧪 Test mode: Mode = {chatbot_defaults.resolve_field(config, 'mode')}"
        )

        # Build system message with or without restriction
        personality = config.get('personality', {})
        prompts = config.get('prompts', {})
        system_message = prompts.get('system_message', '')
        if not system_message and personality:
            role = personality.get('role', 'AI Assistant')
            tone = personality.get('tone', 'helpful and professional')
            style = personality.get('style', 'clear and concise')
            system_message = f"You are a {role}. Respond in a {tone} manner with a {style} style."

        # All RAG / mode / language logic now lives in prompts.yml.
        # CRITICAL: the test widget must use the EXACT SAME prompt as the
        # embed chat so behavior is consistent for the same chatbot config.
        from ..services.prompt_service import PromptService
        prompt_svc = PromptService()

        target_lang = 'auto'
        chatbot_name = config.get('name', 'this chatbot')
        chatbot_role = personality.get('role', 'AI Assistant')

        if restrict_to_knowledge_base:
            if context_text and context_text.strip() and _context_has_meaningful_content(context_text) and _context_relevant_to_query(context_text, message):
                full_system = system_message + "\n\n" + prompt_svc.render(
                    'rag_system.strict',
                    chatbot_name=chatbot_name,
                    chatbot_role=chatbot_role,
                    target_lang=target_lang,
                    context=context_text,
                )
                current_app.logger.info(
                    f"🧪 Test mode: using prompts.yml rag_system.strict "
                    f"(context length: {len(context_text)})"
                )
            else:
                full_system = system_message + "\n\n" + prompt_svc.render(
                    'rag_system.out_of_scope',
                    chatbot_name=chatbot_name,
                    chatbot_role=chatbot_role,
                    target_lang=target_lang,
                    context='',
                    refusal_message=(
                        "I'm sorry, but I can't find an answer to your "
                        "question right now."
                    ),
                )
                current_app.logger.info(
                    "🧪 Test mode: using prompts.yml rag_system.out_of_scope "
                    "(no context)"
                )
        else:
            full_system = system_message + "\n\n" + prompt_svc.render(
                'rag_system.permissive',
                chatbot_name=chatbot_name,
                chatbot_role=chatbot_role,
                target_lang=target_lang,
                context=context_text or '',
            )
            current_app.logger.info(
                f"🧪 Test mode: using prompts.yml rag_system.permissive "
                f"(context length: {len(context_text or '')})"
            )

        messages = [{"role": "system", "content": full_system}]
        for msg in conversation_history:
            messages.append({"role": msg.get('role', 'user'), "content": msg.get('content', '')})
        messages.append({"role": "user", "content": message})

        ai_response = ""
        if current_app.llm_service:
            try:
                current_app.logger.info(f"🧪 Test mode: Calling LLM with model {ai_model}")
                current_app.logger.info(f"🧪 Test mode: System message preview: {full_system[:200]}...")

                # For strict-mode refusals (no KB context found), override the
                # chatbot's normal temperature to 0.0 and cap max_tokens. This
                # makes the LLM pick the most likely completion given the
                # prompt and prevents it from "generating" training-data hints
                # like "However, I think you might be referencing...".
                if restrict_to_knowledge_base and not (context_text and context_text.strip() and _context_has_meaningful_content(context_text) and _context_relevant_to_query(context_text, message)):
                    call_config = dict(config)
                    call_config['temperature'] = 0.0
                    call_config['max_tokens'] = min(
                        int(call_config.get('max_tokens') or 256),
                        120
                    )
                    current_app.logger.info(
                        "🧪 Test mode: strict refusal path - forcing "
                        f"temperature=0.0, max_tokens={call_config['max_tokens']}"
                    )
                else:
                    call_config = config

                response_data = current_app.llm_service.generate_for_chatbot(
                    messages=messages,
                    chatbot_config=call_config,
                    user_id=str(g.user_id),
                    tenant_id=str(chatbot.tenant_id)
                )
                ai_response = response_data.get('content', '') if response_data else ''

                current_app.logger.info(f"🧪 Test mode: LLM response preview: {ai_response[:100]}...")

            except Exception as e:
                current_app.logger.error(f"LLM generation failed in test mode: {e}")
                ai_response = "I apologize, but I'm having trouble generating a response right now. Please try again."
        else:
            current_app.logger.warning("LLM service not available - using demo response")
            ai_response = f"Demo response from {chatbot.name}. Your message: '{message}'"

        current_app.logger.info(f"🧪 Test mode: Final response: {ai_response}")

        # Check if streaming is requested
        if request.headers.get('Accept') == 'text/event-stream':
            # Import streaming function from conversations
            from .conversations import stream_response_chunks
            from flask import Response, stream_with_context
            import json

            def generate_test_stream():
                try:
                    # Send rating FIRST so widget shows it immediately
                    if is_farewell:
                        import json as _json
                        rating_data = {
                            'show_rating': True,
                            'rating_message': 'How would you rate your experience? (Test mode)',
                            'conversation_id': None
                        }
                        yield f"data: {_json.dumps({'type': 'rating', 'data': rating_data})}\n\n"
                    # Then stream the response with typewriter effect
                    for chunk in stream_response_chunks(ai_response, chunk_size=1, delay=0.005):
                        yield chunk
                except Exception as e:
                    current_app.logger.error(f"Test streaming error: {e}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"

            return Response(
                stream_with_context(generate_test_stream()),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                    'Connection': 'keep-alive'
                }
            )
        else:
            # Regular JSON response for non-streaming requests
            response_payload = {'success': True, 'response': ai_response, 'message': 'Test message processed successfully'}
            # Include show_rating if farewell was detected (safety net)
            if is_farewell:
                response_payload['show_rating'] = True
                response_payload['rating_message'] = 'How would you rate your experience? (Test mode)'
            return jsonify(response_payload)

    except Exception as e:
        current_app.logger.error(f"Error processing test message: {str(e)}")
        return jsonify({'error': 'Failed to process test message'}), 500
