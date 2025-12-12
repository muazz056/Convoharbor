from functools import wraps
from flask import request, g, current_app, jsonify
from werkzeug.local import LocalProxy
from flask_cors import CORS
from .services.db_service import db_service
from .models import User

def get_tenant_id():
    """Get tenant ID from request headers or subdomain."""
    tenant_id = request.headers.get('X-Tenant-ID')
    if not tenant_id:
        # Try to get tenant from subdomain
        host = request.headers.get('Host', '')
        if '.' in host:
            subdomain = host.split('.')[0]
            # TODO: Look up tenant by subdomain
            pass
    return tenant_id

def get_current_tenant():
    """Get the current tenant from the global context."""
    if 'tenant' not in g:
        tenant_id = get_tenant_id()
        if tenant_id:
            from .models import Tenant
            g.tenant = Tenant.query.filter_by(tenant_id=tenant_id).first()
        else:
            g.tenant = None
    return g.tenant

# Create a proxy for accessing the current tenant
current_tenant = LocalProxy(get_current_tenant)

def tenant_required(f):
    """Decorator to require a valid tenant for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        tenant = get_current_tenant()
        if not tenant:
            return {'error': 'Tenant not found'}, 404
        if tenant.status != 'active':
            return {'error': 'Tenant is not active'}, 403
        return f(*args, **kwargs)
    return decorated_function

def setup_tenant_context():
    """Middleware to set up tenant context for each request."""
    # Explicitly handle OPTIONS pre-flight requests
    if request.method == 'OPTIONS':
        # The CORS extension will add the necessary headers.
        # We just need to return a successful response.
        return jsonify({'status': 'ok'}), 200
        
    # Skip auth check for public endpoints
    public_endpoints = [
        'api.auth_login',
        'api.auth_signup',
        'api.auth_logout',
        'api.confirm_email',
        'api.resend_confirmation',
        'api.refresh_token',
        'api.upload_callback',  # S3 upload notification must be public
        'api.google_authorize', # Google OAuth start must be public
        'api.google_callback',   # Google OAuth callback must be public
        'api.generate_widget_script',  # Widget embed script generator handles its own auth
        'api.create_conversation',  # Public conversation creation
        'api.get_conversation',  # Public conversation validation for embeds
        'api.send_message',  # Public message sending for embeds
        'api.get_public_chatbot',  # Public chatbot info for embeds
        'api.update_conversation_status',  # Public status update for embed chats
        'api.add_satisfaction_rating',  # Public satisfaction rating for embed chats
        'api.general_chat',  # Public general AI chat endpoint (no specific chatbot required)
        'api.clear_general_chat'  # Public general chat session clear
    ]
    if request.endpoint in public_endpoints:
        return
        
    # Get tenant from request
    tenant = get_current_tenant()
    
    # Get user from token
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        payload = current_app.auth_service.verify_token(token)
        if payload:
            g.user_id = payload['user_id']
            g.user_role = payload['role']
            g.user_tenant_id = payload['tenant_id']
            
            # Default Deny: Ensure user belongs to the correct tenant
            if tenant and str(g.user_tenant_id) != str(tenant.id):
                return jsonify({'error': 'Access denied: tenant mismatch'}), 403
                
            # Set up tenant-specific database session
            g.db_session = db_service.get_session(tenant.tenant_id if tenant else None)
            
            # Check if user has required permissions
            if hasattr(request, 'view_args') and request.view_args:
                required_permissions = getattr(request.endpoint, '_required_permissions', [])
                if required_permissions:
                    user = User.query.get(g.user_id)
                    if not user:
                        return jsonify({'error': 'User not found'}), 404
                        
                    user_permissions = current_app.auth_service.get_user_permissions(user)
                    for permission in required_permissions:
                        if not user_permissions.get(permission, False):
                            return jsonify({
                                'error': 'Permission denied',
                                'required_permission': permission
                            }), 403
            return
            
    # Default Deny: No valid token
    # Skip auth check for non-API routes and missing endpoints
    if not request.endpoint or not request.endpoint.startswith('api.'):
        return
        
    # Skip auth check for public API endpoints
    if request.endpoint.startswith('api.public_'):
        return
        
    return jsonify({'error': 'Authentication required'}), 401

def teardown_tenant_context(exception=None):
    """Clean up tenant context after each request."""
    session = g.pop('db_session', None)
    if session:
        session.remove()
