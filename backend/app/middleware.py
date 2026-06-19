from functools import wraps
from flask import request, g, current_app, jsonify
from werkzeug.local import LocalProxy
from .services.db_service import db_service
from .models import User


def get_tenant_id():
    tenant_id = request.headers.get('X-Tenant-ID')
    if not tenant_id:
        host = request.headers.get('Host', '')
        if '.' in host:
            host.split('.')[0]
    return tenant_id


def get_current_tenant():
    if 'tenant' not in g:
        tenant_id = get_tenant_id()
        if tenant_id:
            from .models import Tenant
            g.tenant = Tenant.query.filter_by(tenant_id=tenant_id).first()
        else:
            g.tenant = None
    return g.tenant


current_tenant = LocalProxy(get_current_tenant)


def tenant_required(f):
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
    if request.method == 'OPTIONS':
        return '', 204

    public_endpoints = [
        'api.auth_login',
        'api.auth_signup',
        'api.auth_logout',
        'api.confirm_email',
        'api.resend_confirmation',
        'api.refresh_token',
        'api.forgot_password',
        'api.verify_reset_code',
        'api.reset_password',
        'api.google_authorize',
        'api.google_callback',
        'api.generate_widget_script',
        'api.create_conversation',
        'api.get_conversation',
        'api.get_conversation_messages_public',
        'api.send_message',
        'api.get_public_chatbot',
        'api.update_conversation_status',
        'api.add_satisfaction_rating',
        'api.general_chat',
        'api.clear_general_chat'
    ]
    if request.endpoint in public_endpoints:
        return

    tenant = get_current_tenant()

    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        payload = current_app.auth_service.verify_token(token)
        if payload:
            g.user_id = payload['user_id']
            g.user_role = payload['role']
            g.user_tenant_id = payload['tenant_id']

            if tenant and str(g.user_tenant_id) != str(tenant.id):
                return jsonify({'error': 'Access denied: tenant mismatch'}), 403

            g.db_session = db_service.get_session(tenant.tenant_id if tenant else None)

            redis_service = getattr(current_app, 'redis_service', None)
            if redis_service and g.user_id:
                request.headers.get('X-Forwarded-For', request.remote_addr) or 'unknown'
                allowed, _, _ = redis_service.check_rate_limit(
                    f"endpoint:{g.user_id}:{request.endpoint}",
                    max_requests=200,
                    window=60
                )
                if not allowed:
                    return jsonify({'error': 'rate_limit_exceeded'}), 429

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

    if not request.endpoint or not request.endpoint.startswith('api.'):
        return

    if request.endpoint.startswith('api.public_'):
        return

    return jsonify({'error': 'Authentication required'}), 401


def teardown_tenant_context(exception=None):
    session = g.pop('db_session', None)
    if session:
        session.remove()
