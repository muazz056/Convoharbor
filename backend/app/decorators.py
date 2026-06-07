from functools import wraps
from flask import request, current_app, g, jsonify
from typing import Optional, List, Union


def get_token_from_header() -> Optional[str]:
    """Extract JWT token from the Authorization header."""
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header.split(' ')[1]
    return None


def login_required(f):
    """Decorator to require authentication for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_token_from_header()
        if not token:
            return {'error': 'Authentication required'}, 401

        auth_service = current_app.auth_service
        payload = auth_service.verify_token(token)
        if not payload:
            return {'error': 'Invalid or expired token'}, 401

        # Store user info in request context
        g.user_id = payload['user_id']

        # Convert tenant UUID to integer ID for database queries
        from .models import Tenant
        tenant = Tenant.query.filter_by(tenant_id=payload['tenant_id']).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        g.tenant_id = tenant.id  # Use integer ID for database queries

        g.role = payload['role']

        return f(*args, **kwargs)
    return decorated_function


def require_permissions(permissions: Union[str, List[str]]):
    """Decorator to require specific permissions for a route."""
    if isinstance(permissions, str):
        permissions = [permissions]

    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            from app.models import User

            user = User.query.get(g.user_id)
            if not user:
                return {'error': 'User not found'}, 404

            user_permissions = current_app.auth_service.get_user_permissions(user)

            # Check if user has all required permissions
            for permission in permissions:
                if not user_permissions.get(permission, False):
                    return {
                        'error': 'Permission denied',
                        'required_permission': permission
                    }, 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def super_admin_required(f):
    """Decorator to require super admin role."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if g.role != 'super_admin':
            return {'error': 'Super admin access required'}, 403
        return f(*args, **kwargs)
    return decorated_function


def tenant_admin_required(f):
    """Decorator to require tenant admin role."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if g.role not in ['super_admin', 'tenant_admin']:
            return {'error': 'Tenant admin access required'}, 403
        return f(*args, **kwargs)
    return decorated_function


def public_endpoint(f):
    """Mark an endpoint as public (no authentication required)."""
    f._public = True
    return f


def require_permissions_attr(*permissions):
    """Decorator that just attaches required permissions to a route handler.

    Actual permission checking is performed by the middleware (setup_tenant_context),
    which reads `f._required_permissions`. Use this when the route itself should
    be public/authenticated by `login_required` but the middleware will perform
    the fine-grained permission check.
    """
    def decorator(f):
        f._required_permissions = permissions
        return f
    return decorator
