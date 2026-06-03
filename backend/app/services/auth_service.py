from datetime import datetime, timedelta
import jwt  # type: ignore
import secrets
from werkzeug.security import generate_password_hash, check_password_hash  # type: ignore
from flask import current_app  # type: ignore
from typing import Optional, Dict, Any, Tuple, TYPE_CHECKING

from .. import db
from .email_service import send_confirmation_email

if TYPE_CHECKING:
    from ..models import User  # For type hints only

class AuthService:
    """Service for handling authentication and authorization."""
    
    def __init__(self):
        self.secret_key = current_app.config['SECRET_KEY']
        self.token_expiry = current_app.config.get('JWT_EXPIRY_HOURS', 24 * 5)  # 5 days default
        
    def hash_password(self, password: str) -> str:
        """Hash a password using Werkzeug's security functions."""
        return generate_password_hash(password)
        
    def verify_password(self, password_hash: str, password: str) -> bool:
        """Verify a password against its hash."""
        return check_password_hash(password_hash, password)
        
    def generate_token(self, user_id: int, tenant_id: str, role: str, token_type: str = 'access', user_data: dict = None) -> str:
        """Generate a JWT token for a user.
        
        Args:
            user_id: The user's ID
            tenant_id: The tenant's ID
            role: The user's role
            token_type: Either 'access' (default) or 'refresh'
            user_data: Optional dict with user info (email, first_name, last_name)
            
        Returns:
            str: JWT token that expires in 5 days for access tokens, 7 days for refresh tokens
        """
        expiry = datetime.utcnow() + timedelta(
            hours=self.token_expiry if token_type == 'access' else 24 * 7  # 7 days for refresh tokens
        )
        
        payload = {
            'user_id': user_id,
            'tenant_id': tenant_id,
            'role': role,
            'type': token_type,
            'exp': expiry
        }
        if user_data:
            payload['email'] = user_data.get('email')
            payload['first_name'] = user_data.get('first_name')
            payload['last_name'] = user_data.get('last_name')
            payload['permissions'] = user_data.get('permissions', {})
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
        
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            if datetime.fromtimestamp(payload['exp']) < datetime.utcnow():
                return None
                
            # Check if user still exists and is active
            from app.models import User
            user = User.query.get(payload.get('user_id'))
            if not user or user.status != 'active':
                return None
                
            return payload
        except jwt.InvalidTokenError:
            return None
            
    def generate_confirmation_token(self) -> str:
        """Generate a secure token for email confirmation."""
        return secrets.token_urlsafe(32)

    def create_user(self, tenant_id: str, email: str, password: str, role: str,
                    first_name: str = None, last_name: str = None) -> Tuple[Any, str]:
        """Create a new user and send confirmation email."""
        from app.models import User
        
        # Super admin is auto-confirmed, no email needed
        if role == 'super_admin':
            user = User(
                tenant_id=tenant_id,
                email=email,
                password_hash=self.hash_password(password),
                role=role,
                first_name=first_name,
                last_name=last_name,
                email_confirmed=True,
                email_confirmed_at=datetime.utcnow(),
                status='active'
            )
            try:
                db.session.add(user)
                db.session.commit()
                return user, None
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error creating super admin: {str(e)}")
                raise

        # Generate confirmation token
        confirmation_token = self.generate_confirmation_token()
        token_expires = datetime.utcnow() + timedelta(hours=24)
        
        user = User(
            tenant_id=tenant_id,
            email=email,
            password_hash=self.hash_password(password),
            role=role,
            first_name=first_name,
            last_name=last_name,
            confirmation_token=confirmation_token,
            confirmation_token_expires=token_expires
        )
        
        try:
            db.session.add(user)
            db.session.commit()
            
            # Send confirmation email
            send_confirmation_email(user, confirmation_token)
            
            return user, confirmation_token
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating user: {str(e)}")
            raise
        
    def confirm_email(self, token: str) -> Tuple[bool, str, Optional[Any]]:
        """Confirm a user's email address using the confirmation token."""
        try:
            from app.models import User
            
            current_app.logger.info(f"Attempting to confirm email with token: {token}")
            user = User.query.filter_by(confirmation_token=token).first()
            
            if not user:
                current_app.logger.warning(f"No user found with token: {token}")
                return False, "Invalid confirmation token", None
                
            if user.email_confirmed:
                # If email is already confirmed, return success with user
                return True, "Email already confirmed", user
                
            if user.confirmation_token_expires < datetime.utcnow():
                return False, "Confirmation token has expired", None
                
            user.email_confirmed = True
            user.email_confirmed_at = datetime.utcnow()
            user.confirmation_token = None
            user.confirmation_token_expires = None
            user.status = 'active'
            db.session.commit()
            return True, "Email confirmed successfully", user
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error confirming email: {str(e)}")
            return False, "An error occurred while confirming email", None

    def authenticate_user(self, email: str, password: str) -> Optional[Any]:
        """Authenticate a user by email and password."""
        from app.models import User
        
        user = User.query.filter_by(email=email).first()
        if not user:
            return None
            
        # Check email confirmation - super admin is always auto-confirmed
        if user.role != 'super_admin' and (not user.email_confirmed or user.status == 'pending'):
            return None
            
        if user and self.verify_password(user.password_hash, password):
            user.last_login = datetime.utcnow()
            db.session.commit()
            return user
        return None
        
    def get_user_permissions(self, user: Any) -> Dict[str, bool]:
        """Get permissions for a user based on their role."""
        # Define role-based permissions according to project requirements
        permissions = {
            'super_admin': {
                'manage_tenants': True,
                'manage_users': True,
                'manage_chatbots': True,
                'upload_documents': True,
                'view_analytics': True,
                'manage_billing': True,
                'access_admin_panel': True,  # MyChatbotCompagny portal
                'access_all_clients': True
            },
            'admin': {
                'manage_tenants': False,
                'manage_users': False,
                'manage_chatbots': True,
                'upload_documents': True,  # Key permission for admin
                'view_analytics': True,
                'manage_billing': False,
                'access_admin_panel': False,
                'access_all_clients': False
            },
            'user': {  # End user who chats with chatbots
                'manage_tenants': False,
                'manage_users': False,
                'manage_chatbots': False,
                'upload_documents': False,
                'view_analytics': False,
                'manage_billing': False,
                'access_admin_panel': False,
                'access_all_clients': False
            }
        }
        return permissions.get(user.role, {})