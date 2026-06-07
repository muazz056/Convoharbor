from typing import Dict, Any, Optional
from flask import current_app, g
from ..models import Tenant


class ConfigService:
    """Service for managing tenant-specific configurations."""

    def __init__(self):
        self._tenant_configs = {}

    def get_tenant_config(self, tenant_id: str) -> Dict[str, Any]:
        """Get configuration for a specific tenant."""
        if tenant_id not in self._tenant_configs:
            tenant = Tenant.query.filter_by(tenant_id=tenant_id).first()
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")

            # Merge tenant-specific config with default config
            config = {
                # Database settings
                'database_url': tenant.database_url,

                # Feature flags
                'features': {
                    'multi_language': True,
                    'analytics': True,
                    'lead_generation': True,
                    'live_chat': True,
                    'webhooks': True
                },

                # API limits
                'limits': {
                    'max_chatbots': 10,
                    'max_conversations_per_day': 1000,
                    'max_tokens_per_request': 4000,
                    'max_file_size_mb': 10
                },

                # Integration settings
                'integrations': {
                    'openai': {
                        'enabled': True,
                        'model': 'gpt-4-turbo'
                    },
                    'gemini': {
                        'enabled': True,
                        'model': 'gemini-1.5-pro-latest'
                    }
                },

                # UI customization
                'ui': {
                    'theme': 'light',
                    'primary_color': '#6366F1',
                    'logo_url': None,
                    'company_name': tenant.name
                }
            }

            # Override with tenant-specific settings
            if tenant.config:
                self._deep_update(config, tenant.config)

            self._tenant_configs[tenant_id] = config

        return self._tenant_configs[tenant_id]

    def update_tenant_config(self, tenant_id: str, new_config: Dict[str, Any]) -> None:
        """Update configuration for a specific tenant."""
        tenant = Tenant.query.filter_by(tenant_id=tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        # Update tenant config in database
        if tenant.config is None:
            tenant.config = {}
        self._deep_update(tenant.config, new_config)

        # Update cached config
        if tenant_id in self._tenant_configs:
            self._deep_update(self._tenant_configs[tenant_id], new_config)

        current_app.db.session.commit()

    def clear_tenant_config_cache(self, tenant_id: Optional[str] = None) -> None:
        """Clear cached configurations."""
        if tenant_id:
            self._tenant_configs.pop(tenant_id, None)
        else:
            self._tenant_configs.clear()

    def _deep_update(self, d: Dict[str, Any], u: Dict[str, Any]) -> None:
        """Recursively update a dictionary."""
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._deep_update(d[k], v)
            else:
                d[k] = v

    def get_current_config(self) -> Dict[str, Any]:
        """Get configuration for the current tenant."""
        tenant = getattr(g, 'tenant', None)
        if not tenant:
            raise ValueError("No tenant context found")
        return self.get_tenant_config(tenant.tenant_id)
