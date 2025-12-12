from flask import request, current_app, url_for, session, jsonify
from . import api
from ..models import User
from ..services.oauth_service import OAuthService

oauth_service = OAuthService()

@api.route('/auth/oauth/<provider>')
def oauth_authorize(provider):
    """Initiate OAuth flow with a provider."""
    if provider not in ['google', 'github', 'microsoft']:
        return jsonify({'error': 'Invalid OAuth provider'}), 400
        
    # Store the tenant ID in session if provided
    if 'tenant_id' in request.args:
        session['oauth_tenant_id'] = request.args['tenant_id']
        
    provider_app = oauth_service.get_provider(provider)
    if not provider_app:
        return jsonify({'error': 'Provider not configured'}), 400
        
    callback_url = oauth_service.get_callback_url(provider)
    return provider_app.authorize(callback=callback_url)
    
@api.route('/auth/oauth/<provider>/callback')
def oauth_callback(provider):
    """Handle OAuth callback from provider."""
    if provider not in ['google', 'github', 'microsoft']:
        return jsonify({'error': 'Invalid OAuth provider'}), 400
        
    provider_app = oauth_service.get_provider(provider)
    if not provider_app:
        return jsonify({'error': 'Provider not configured'}), 400
        
    # Get OAuth response
    resp = provider_app.authorized_response()
    if resp is None or resp.get('access_token') is None:
        return jsonify({
            'error': 'Access denied',
            'reason': request.args.get('error', 'Unknown error')
        }), 401
        
    # Get user info from provider
    user_info = oauth_service.get_user_info(provider, resp)
    if not user_info:
        return jsonify({'error': 'Failed to get user info'}), 400
        
    # Check if user exists
    user = User.query.filter_by(email=user_info['email']).first()
    
    if user:
        # Update existing user's OAuth info
        user.oauth_provider = provider
        user.oauth_id = user_info['provider_id']
        if not user.first_name:
            user.first_name = user_info['first_name']
        if not user.last_name:
            user.last_name = user_info['last_name']
    else:
        # Create new user
        tenant_id = session.pop('oauth_tenant_id', None)
        if not tenant_id:
            return jsonify({'error': 'No tenant ID provided'}), 400
            
        user = User(
            email=user_info['email'],
            first_name=user_info['first_name'],
            last_name=user_info['last_name'],
            tenant_id=tenant_id,
            role='user',
            oauth_provider=provider,
            oauth_id=user_info['provider_id']
        )
        
    current_app.db.session.add(user)
    current_app.db.session.commit()
    
    # Get tenant to use its UUID for JWT token
    from app.models import Tenant
    tenant = Tenant.query.get(user.tenant_id)
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404
        
    # Generate JWT token
    token = current_app.auth_service.generate_token(
        user.id,
        tenant.tenant_id,  # Use tenant UUID, not user.tenant_id (integer)
        user.role
    )
    
    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'email': user.email,
            'role': user.role,
            'first_name': user.first_name,
            'last_name': user.last_name
        }
    })
