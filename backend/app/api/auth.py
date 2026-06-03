from flask import request, current_app, jsonify, g, redirect, url_for
from flasgger import swag_from
from datetime import datetime, timedelta
import os
import json
import uuid
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

from flask import request, jsonify, redirect, url_for, current_app, g
from ..models import User, Tenant
from .. import db
from . import api
from ..decorators import login_required
from flasgger.utils import swag_from
from ..services.email_service import send_confirmation_email


def validate_password_strength(password):
    errors = []
    if len(password) < 8:
        errors.append("at least 8 characters")
    if not re.search(r'[A-Z]', password):
        errors.append("an uppercase letter")
    if not re.search(r'[a-z]', password):
        errors.append("a lowercase letter")
    if not re.search(r'\d', password):
        errors.append("a digit")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_-]', password):
        errors.append("a special character")
    return errors

AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://www.googleapis.com/oauth2/v4/token"
USER_INFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"
SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]


@api.route('/auth/oauth/google/authorize')
@swag_from({
    'tags': ['Authentication', 'OAuth'],
    'summary': 'Redirect to Google for authentication',
    'description': 'Starts the Google OAuth2 flow by redirecting the user to Google\'s consent screen.',
    'security': [],
    'responses': {
        '302': {
            'description': 'Redirecting to Google for authentication.'
        }
    }
})
def google_authorize():
    """Redirect user to Google for authentication."""
    google = OAuth2Session(
        current_app.config['GOOGLE_CLIENT_ID'],
        scope=SCOPES,
        redirect_uri=url_for('api.google_callback', _external=True)
    )
    authorization_url, state = google.authorization_url(
        AUTHORIZATION_BASE_URL,
        access_type="offline",
        prompt="select_account"
    )

    redis_service = getattr(current_app, 'redis_service', None)
    if redis_service:
        redis_service.set_session(f"oauth_state:{state}", {"state": state}, ttl=600)
    else:
        from flask import session
        session['oauth_state'] = state

    return redirect(authorization_url)


@api.route('/auth/oauth/google/callback')
@swag_from({
    'tags': ['Authentication', 'OAuth'],
    'summary': 'Handle Google OAuth callback',
    'description': 'Handles the callback from Google, exchanges the code for a token, gets user info, and logs the user in or signs them up.',
    'security': [],
    'responses': {
        '302': {
            'description': 'Redirecting to the frontend application with an authentication token.'
        },
        '400': {
            'description': 'OAuth flow error, e.g., state mismatch or missing code.'
        }
    }
})
def google_callback():
    """Callback handler for Google OAuth."""
    state = request.args.get('state')

    redis_service = getattr(current_app, 'redis_service', None)
    if redis_service:
        stored_state_data = redis_service.get_session(f"oauth_state:{state}")
        if not stored_state_data:
            return jsonify(error="State mismatch, possible CSRF attack."), 400
        redis_service.delete_session(f"oauth_state:{state}")
    else:
        from flask import session
        if state != session.get('oauth_state'):
            return jsonify(error="State mismatch, possible CSRF attack."), 400

    google = OAuth2Session(
        current_app.config['GOOGLE_CLIENT_ID'],
        state=state,
        redirect_uri=url_for('api.google_callback', _external=True)
    )

    token = google.fetch_token(
        TOKEN_URL,
        client_secret=current_app.config['GOOGLE_CLIENT_SECRET'],
        authorization_response=request.url
    )

    user_info = google.get(USER_INFO_URL).json()

    email = user_info.get('email')
    if not email:
        return jsonify(error="Email not provided by Google."), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        unique_tenant_id = str(uuid.uuid4())
        oauth_tenant = Tenant(
            name=f"{user_info.get('given_name', 'Admin')} {user_info.get('family_name', 'User')}'s Organization",
            tenant_id=unique_tenant_id,
            domain=f"{email.split('@')[0]}.convopilot.com",
            type="convopilot"
        )
        db.session.add(oauth_tenant)
        db.session.commit()

        user = User(
            tenant_id=oauth_tenant.id,
            email=email,
            first_name=user_info.get('given_name'),
            last_name=user_info.get('family_name'),
            role='admin',
            status='active',
            email_confirmed=True,
            email_confirmed_at=datetime.utcnow(),
            oauth_provider='google',
            oauth_id=user_info.get('id')
        )
        db.session.add(user)
        db.session.commit()

    jwt_token = current_app.auth_service.generate_token(
        user.id,
        user.tenant.tenant_id,
        user.role
    )

    user_data = {
        'id': user.id,
        'email': user.email,
        'firstName': user.first_name,
        'lastName': user.last_name,
        'role': user.role,
        'tenant_id': user.tenant_id
    }

    frontend_callback_url = (
        f"{current_app.config['FRONTEND_URL']}/oauth-callback"
        f"?token={jwt_token}"
        f"&user={json.dumps(user_data)}"
    )

    return redirect(frontend_callback_url)


@api.route('/test', methods=['GET', 'OPTIONS'])
def test():
    """Test endpoint to verify CORS is working."""
    return jsonify({'message': 'CORS is working!', 'status': 'success'})


@api.route('/auth/signup', methods=['POST', 'OPTIONS'], endpoint='auth_signup')
@swag_from({
    'tags': ['Authentication'],
    'summary': 'Register a new admin user',
    'description': 'Create a new administrator account for document management',
    'security': [],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['email', 'password', 'tenant_id'],
                'properties': {
                    'email': {'type': 'string', 'format': 'email', 'description': 'User email address'},
                    'password': {'type': 'string', 'format': 'password', 'description': 'User password (min 8 characters)'},
                    'tenant_id': {'type': 'string', 'description': 'ID of the tenant to register under'},
                    'first_name': {'type': 'string', 'description': 'User first name'},
                    'last_name': {'type': 'string', 'description': 'User last name'},
                    'role': {'type': 'string', 'enum': ['admin'], 'default': 'admin', 'description': 'Role is always admin for this endpoint'}
                }
            }
        }
    ],
    'responses': {
        '201': {'description': 'User registered successfully'},
        '400': {'description': 'Invalid input'},
        '409': {'description': 'Email already registered'}
    }
})
def signup():
    """Register a new user."""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json()
    current_app.logger.info(f"Signup request received: {data}")

    required_fields = ['email', 'password']
    if not all(field in data for field in required_fields):
        return jsonify({
            'error': 'Missing required fields',
            'required': required_fields
        }), 400

    role = 'admin'

    password_errors = validate_password_strength(data['password'])
    if password_errors:
        return jsonify({
            'error': 'Password is not strong enough',
            'requirements': password_errors
        }), 400

    existing_user = User.query.filter_by(email=data['email']).first()
    if existing_user:
        if existing_user.status == 'pending' or not existing_user.email_confirmed:
            return jsonify({
                'error': 'Email already registered but not confirmed',
                'status': 'unconfirmed',
                'message': 'Please check your email for confirmation link or request a new one'
            }), 409
        return jsonify({'error': 'Email already registered'}), 409

    try:
        unique_tenant_id = str(uuid.uuid4())
        admin_tenant = Tenant(
            name=f"{data.get('first_name', 'Admin')} {data.get('last_name', 'User')}'s Organization",
            tenant_id=unique_tenant_id,
            domain=f"{data['email'].split('@')[0]}.convopilot.com",
            type="convopilot"
        )
        db.session.add(admin_tenant)
        db.session.commit()

        try:
            user, confirmation_token = current_app.auth_service.create_user(
                tenant_id=admin_tenant.id,
                email=data['email'],
                password=data['password'],
                role=role,
                first_name=data.get('first_name'),
                last_name=data.get('last_name')
            )

            # Super admin auto-confirmed immediately, no email required
            if role == 'super_admin':
                user.email_confirmed = True
                user.email_confirmed_at = datetime.utcnow()
                user.status = 'active'
                db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Account created successfully.'
                if role == 'super_admin'
                else 'Account created successfully. Please check your email to confirm your account.',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'firstName': user.first_name,
                    'lastName': user.last_name,
                    'role': user.role
                }
            }), 201

        except Exception as e:
            current_app.logger.error(f"Error during signup: {str(e)}")
            return jsonify({
                'success': False,
                'message': 'An error occurred during signup. Please try again.'
            }), 500

    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@api.route('/auth/login', methods=['POST', 'OPTIONS'], endpoint='auth_login')
@swag_from({
    'tags': ['Authentication'],
    'summary': 'Login user',
    'description': 'Authenticate user and return access token',
    'security': [],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['email', 'password'],
                'properties': {
                    'email': {'type': 'string', 'format': 'email', 'description': 'User email address'},
                    'password': {'type': 'string', 'format': 'password', 'description': 'User password'}
                }
            }
        }
    ],
    'responses': {
        '200': {'description': 'Login successful'},
        '401': {'description': 'Authentication failed'},
        '403': {'description': 'Account inactive'}
    }
})
def login():
    """Authenticate a user and return a token."""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    try:
        data = request.get_json()
        current_app.logger.info(f"Login request received: {data}")

        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'error': 'Email and password required'}), 400

        user = current_app.auth_service.authenticate_user(
            data['email'],
            data['password']
        )

        if not user:
            existing_user = User.query.filter_by(email=data['email']).first()
            if existing_user:
                if existing_user.role != 'super_admin' and (existing_user.status == 'pending' or not existing_user.email_confirmed):
                    return jsonify({
                        'error': 'Please confirm your email before logging in',
                        'status': 'unconfirmed',
                        'message': 'Check your email for confirmation link or request a new one'
                    }), 401
                if current_app.auth_service.verify_password(existing_user.password_hash, data['password']):
                    return jsonify({
                        'error': 'Please confirm your email before logging in',
                        'status': 'unconfirmed',
                        'message': 'Check your email for confirmation link or request a new one'
                    }), 401
            return jsonify({'error': 'Invalid email or password'}), 401

        if user.status != 'active':
            return jsonify({'error': 'Account is not active'}), 403

        tenant = Tenant.query.get(user.tenant_id)
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404

        token = current_app.auth_service.generate_token(
            user.id,
            tenant.tenant_id,
            user.role
        )

        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'permissions': current_app.auth_service.get_user_permissions(user),
                'tenant_id': user.tenant_id
            }
        })
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'An error occurred during login'}), 500


@api.route('/auth/token/refresh', methods=['POST'])
def refresh_token():
    """Refresh an expired JWT token."""
    data = request.get_json()
    if not data or 'refresh_token' not in data:
        return jsonify({'error': 'Refresh token required'}), 400

    payload = current_app.auth_service.verify_token(data['refresh_token'])
    if not payload:
        return jsonify({'error': 'Invalid or expired refresh token'}), 401

    user = User.query.get(payload['user_id'])
    if not user or user.status != 'active':
        return jsonify({'error': 'User not found or inactive'}), 401

    from app.models import Tenant
    tenant = Tenant.query.get(user.tenant_id)
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    access_token = current_app.auth_service.generate_token(
        user.id,
        tenant.tenant_id,
        user.role,
        token_type='access'
    )

    refresh_token = current_app.auth_service.generate_token(
        user.id,
        tenant.tenant_id,
        user.role,
        token_type='refresh'
    )

    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': user.id,
            'email': user.email,
            'role': user.role,
            'tenant_id': user.tenant_id
        }
    })


@api.route('/auth/logout', methods=['POST', 'OPTIONS'], endpoint='auth_logout')
@swag_from({
    'tags': ['Authentication'],
    'summary': 'Logout user',
    'description': 'Invalidate user session and clear tokens',
    'security': [],
    'responses': {
        '200': {'description': 'Logout successful'}
    }
})
def logout():
    """Logout user and invalidate tokens."""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    return jsonify({
        'success': True,
        'message': 'Successfully logged out'
    })


@api.route('/auth/confirm-email/<token>', methods=['GET', 'OPTIONS'], endpoint='confirm_email')
@swag_from({
    'tags': ['Authentication'],
    'summary': 'Confirm email address',
    'description': 'Confirm user email address using confirmation token',
    'parameters': [
        {
            'name': 'token',
            'in': 'path',
            'required': True,
            'type': 'string',
            'description': 'Email confirmation token'
        }
    ],
    'responses': {
        '200': {'description': 'Email confirmed successfully'},
        '400': {'description': 'Invalid or expired token'}
    }
})
def confirm_email(token):
    """Confirm user's email address."""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    current_app.logger.info(f"Received confirmation request for token: {token}")
    success, message, user = current_app.auth_service.confirm_email(token)
    current_app.logger.info(f"Confirmation result: success={success}, message={message}")
    status_code = 200 if success else 400

    if success and user:
        from app.models import Tenant
        tenant = Tenant.query.get(user.tenant_id)
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404

        auth_token = current_app.auth_service.generate_token(
            user.id,
            tenant.tenant_id,
            user.role
        )

        return jsonify({
            'success': success,
            'message': message,
            'token': auth_token,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'permissions': current_app.auth_service.get_user_permissions(user),
                'tenant_id': user.tenant_id
            }
        }), status_code

    return jsonify({
        'success': success,
        'message': message
    }), status_code


@api.route('/auth/check-email', methods=['POST', 'OPTIONS'])
def check_email():
    """Check email status and return if it's unconfirmed."""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({'error': 'Email is required'}), 400

    user = User.query.filter_by(email=data['email']).first()
    if not user:
        return jsonify({'error': 'Email not found'}), 404

    return jsonify({
        'status': 'unconfirmed' if not user.email_confirmed else 'confirmed',
        'email': user.email
    })


@api.route('/auth/validate-token', methods=['GET', 'OPTIONS'])
@login_required
@swag_from({
    'tags': ['Authentication'],
    'summary': 'Validate authentication token',
    'description': 'Check if the current authentication token is valid and user still exists',
    'security': [{'Bearer': []}],
    'responses': {
        '200': {'description': 'Token is valid'},
        '401': {'description': 'Token is invalid or user not found'}
    }
})
def validate_token():
    """Validate the current authentication token and user existence."""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    try:
        user = User.query.get(g.user_id)

        if not user:
            return jsonify({
                'valid': False,
                'error': 'User not found',
                'message': 'Your account has been deleted'
            }), 401

        if user.status != 'active':
            return jsonify({
                'valid': False,
                'error': 'Account disabled',
                'message': 'Your account has been disabled'
            }), 401

        return jsonify({
            'valid': True,
            'user_id': user.id,
            'message': 'Token is valid'
        }), 200

    except Exception as e:
        current_app.logger.error(f"Token validation error: {e}")
        return jsonify({
            'valid': False,
            'error': 'Validation failed',
            'message': 'Unable to validate token'
        }), 401


@api.route('/auth/resend-confirmation', methods=['POST', 'OPTIONS'])
@swag_from({
    'tags': ['Authentication'],
    'summary': 'Resend confirmation email',
    'description': 'Resend confirmation email for unconfirmed accounts',
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['email'],
                'properties': {
                    'email': {'type': 'string', 'format': 'email', 'description': 'Email address to resend confirmation'}
                }
            }
        }
    ],
    'responses': {
        '200': {'description': 'Confirmation email sent successfully'},
        '400': {'description': 'Invalid request or email already confirmed'},
        '404': {'description': 'Email not found'}
    }
})
def resend_confirmation():
    """Resend confirmation email."""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({'error': 'Email is required'}), 400

    user = User.query.filter_by(email=data['email']).first()
    if not user:
        return jsonify({'error': 'Email not found'}), 404

    if user.email_confirmed and user.status == 'active':
        return jsonify({'error': 'Email is already confirmed'}), 400

    try:
        confirmation_token = current_app.auth_service.generate_confirmation_token()
        token_expires = datetime.utcnow() + timedelta(hours=24)

        user.confirmation_token = confirmation_token
        user.confirmation_token_expires = token_expires

        db.session.commit()

        try:
            send_confirmation_email(user, confirmation_token)
            current_app.logger.info(f"Confirmation email resent to {user.email}")

            return jsonify({
                'success': True,
                'message': 'Confirmation email has been resent. Please check your inbox.'
            })

        except Exception as email_error:
            current_app.logger.error(f"Failed to send confirmation email: {str(email_error)}")
            return jsonify({
                'success': False,
                'error': 'Failed to send confirmation email. Please try again or contact support.'
            }), 500

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resending confirmation: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }), 500


@api.route('/auth/me', methods=['GET'])
@login_required
def get_current_user():
    """Get the current authenticated user's details."""
    user = User.query.get_or_404(g.user_id)

    return jsonify({
        'id': user.id,
        'email': user.email,
        'role': user.role,
        'tenant_id': user.tenant_id,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'status': user.status,
        'last_login': user.last_login.isoformat() if user.last_login else None,
        'permissions': current_app.auth_service.get_user_permissions(user)
    })
