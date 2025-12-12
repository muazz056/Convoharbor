from flask import current_app, url_for
from flask_oauthlib.client import OAuth
from typing import Dict, Any, Optional

class OAuthService:
    """Service for handling OAuth authentication with various providers."""
    
    def __init__(self):
        self.oauth = OAuth(current_app)
        self._setup_providers()
        
    def _setup_providers(self):
        """Initialize OAuth providers."""
        # Google OAuth
        self.google = self.oauth.remote_app(
            'google',
            consumer_key=current_app.config.get('GOOGLE_CLIENT_ID'),
            consumer_secret=current_app.config.get('GOOGLE_CLIENT_SECRET'),
            request_token_params={
                'scope': 'email profile'
            },
            base_url='https://www.googleapis.com/oauth2/v1/',
            request_token_url=None,
            access_token_method='POST',
            access_token_url='https://accounts.google.com/o/oauth2/token',
            authorize_url='https://accounts.google.com/o/oauth2/auth'
        )
        
        # GitHub OAuth
        self.github = self.oauth.remote_app(
            'github',
            consumer_key=current_app.config.get('GITHUB_CLIENT_ID'),
            consumer_secret=current_app.config.get('GITHUB_CLIENT_SECRET'),
            request_token_params={'scope': 'user:email'},
            base_url='https://api.github.com/',
            request_token_url=None,
            access_token_method='POST',
            access_token_url='https://github.com/login/oauth/access_token',
            authorize_url='https://github.com/login/oauth/authorize'
        )
        
        # Microsoft OAuth
        self.microsoft = self.oauth.remote_app(
            'microsoft',
            consumer_key=current_app.config.get('MICROSOFT_CLIENT_ID'),
            consumer_secret=current_app.config.get('MICROSOFT_CLIENT_SECRET'),
            request_token_params={'scope': 'User.Read'},
            base_url='https://graph.microsoft.com/v1.0/',
            request_token_url=None,
            access_token_method='POST',
            access_token_url='https://login.microsoftonline.com/common/oauth2/v2.0/token',
            authorize_url='https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
        )
        
    def get_provider(self, provider_name: str):
        """Get OAuth provider by name."""
        providers = {
            'google': self.google,
            'github': self.github,
            'microsoft': self.microsoft
        }
        return providers.get(provider_name)
        
    def get_callback_url(self, provider: str) -> str:
        """Get OAuth callback URL for a provider."""
        return url_for('api.oauth_callback', provider=provider, _external=True)
        
    async def get_user_info(self, provider: str, resp: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get user information from OAuth provider."""
        provider_app = self.get_provider(provider)
        if not provider_app:
            return None
            
        if provider == 'google':
            user_info = provider_app.get('userinfo')
            if user_info.status == 200:
                return {
                    'email': user_info.data['email'],
                    'first_name': user_info.data.get('given_name'),
                    'last_name': user_info.data.get('family_name'),
                    'picture': user_info.data.get('picture'),
                    'provider': 'google',
                    'provider_id': user_info.data['id']
                }
                
        elif provider == 'github':
            user_info = provider_app.get('user')
            emails = provider_app.get('user/emails')
            if user_info.status == 200 and emails.status == 200:
                primary_email = next(
                    (email['email'] for email in emails.data if email['primary']),
                    emails.data[0]['email']
                )
                name_parts = (user_info.data.get('name') or '').split(' ', 1)
                return {
                    'email': primary_email,
                    'first_name': name_parts[0] if name_parts else None,
                    'last_name': name_parts[1] if len(name_parts) > 1 else None,
                    'picture': user_info.data.get('avatar_url'),
                    'provider': 'github',
                    'provider_id': str(user_info.data['id'])
                }
                
        elif provider == 'microsoft':
            user_info = provider_app.get('me')
            if user_info.status == 200:
                return {
                    'email': user_info.data['userPrincipalName'],
                    'first_name': user_info.data.get('givenName'),
                    'last_name': user_info.data.get('surname'),
                    'picture': None,  # Microsoft Graph API requires additional permissions
                    'provider': 'microsoft',
                    'provider_id': user_info.data['id']
                }
                
        return None
