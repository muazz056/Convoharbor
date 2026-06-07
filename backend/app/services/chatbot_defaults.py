"""Single source of truth for chatbot config defaults.

Every consumer (chatbot create, chatbot update, test chat, embed chat,
model resolver, vector search, llm service) MUST go through this module
to read default values for `top_k`, `mode`, `temperature`, and
`max_tokens`. This guarantees the .env file is the only place the
defaults live, and that any change is reflected everywhere in the
application.

Super-admin gating:
- Only the Super Admin can change top_k / mode / temperature / max_tokens
  on an existing chatbot. Other roles (tenant_admin, user) can update
  every other chatbot field (name, description, personality, prompts,
  theme, status, ai_model, fallback_model) but their requests MUST NOT
  alter the four restricted fields. If a non-super-admin request
  includes any of them, the update is rejected with 403.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from flask import current_app

# The four fields that are super-admin-only
RESTRICTED_FIELDS = ('mode', 'temperature', 'max_tokens', 'top_k')


def _config():
    """Return the live Flask config object (tests can monkeypatch this)."""
    return current_app.config


def get_defaults() -> Dict[str, Any]:
    """Return the current default values for the four restricted fields.

    Reads from `current_app.config` which is populated from .env at startup.
    """
    cfg = _config()
    return {
        'top_k': int(cfg.get('DEFAULT_TOP_K', 10)),
        'mode': str(cfg.get('DEFAULT_MODE', 'strict')),
        'temperature': float(cfg.get('DEFAULT_TEMPERATURE', 0.7)),
        'max_tokens': int(cfg.get('DEFAULT_MAX_TOKENS', 2048)),
    }


def get_bounds() -> Dict[str, Any]:
    """Return the validation bounds for the four restricted fields."""
    cfg = _config()
    return {
        'top_k': (int(cfg.get('TOP_K_MIN', 1)), int(cfg.get('TOP_K_MAX', 50))),
        'mode': ('strict', 'permissive'),
        'temperature': (
            float(cfg.get('TEMPERATURE_MIN', 0.0)),
            float(cfg.get('TEMPERATURE_MAX', 2.0)),
        ),
        'max_tokens': (
            int(cfg.get('MAX_TOKENS_MIN', 64)),
            int(cfg.get('MAX_TOKENS_MAX', 32000)),
        ),
    }


def apply_defaults(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a new config dict with all four restricted fields filled in
    with the default values if they are missing. Existing values are kept.

    Use this everywhere a chatbot's config dict is read so that any
    consumer (LLM call, vector search, prompt builder) sees the same
    effective value regardless of whether the value was stored on the
    chatbot or simply absent and falling back to the .env default.
    """
    config = dict(config or {})
    defaults = get_defaults()
    for field in RESTRICTED_FIELDS:
        if field not in config or config[field] is None:
            config[field] = defaults[field]
    return config


def resolve_field(config: Optional[Dict[str, Any]], field: str) -> Any:
    """Resolve a single restricted field to its effective value.

    Returns the stored value if present, otherwise the .env default.
    """
    if field not in RESTRICTED_FIELDS:
        raise ValueError(
            f"resolve_field only supports {RESTRICTED_FIELDS}, got {field!r}"
        )
    config = config or {}
    if field in config and config[field] is not None:
        return config[field]
    return get_defaults()[field]


def validate_field(field: str, value: Any) -> Optional[str]:
    """Validate a single restricted field value. Returns None if valid,
    otherwise an error message string suitable for a 400 response.
    """
    bounds = get_bounds()
    if field == 'top_k':
        if not isinstance(value, int) or isinstance(value, bool):
            return 'top_k must be an integer'
        lo, hi = bounds['top_k']
        if value < lo or value > hi:
            return f'top_k must be an integer between {lo} and {hi}'
        return None

    if field == 'mode':
        if value not in bounds['mode']:
            return f'mode must be one of: {", ".join(bounds["mode"])}'
        return None

    if field == 'temperature':
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return 'temperature must be a number'
        lo, hi = bounds['temperature']
        if value < lo or value > hi:
            return f'temperature must be a number between {lo} and {hi}'
        return None

    if field == 'max_tokens':
        if not isinstance(value, int) or isinstance(value, bool):
            return 'max_tokens must be an integer'
        lo, hi = bounds['max_tokens']
        if value < lo or value > hi:
            return f'max_tokens must be an integer between {lo} and {hi}'
        return None

    return f'Unknown restricted field: {field}'


def is_super_admin(role: Optional[str]) -> bool:
    """Return True if the given role is allowed to mutate restricted fields."""
    if not role:
        return False
    cfg = _config()
    super_role = str(cfg.get('SUPER_ADMIN_ROLE', 'super_admin'))
    return role == super_role


def extract_restricted_update(data: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the four restricted fields out of an incoming update payload.
    Returns only the fields that were actually provided (not None).
    """
    out: Dict[str, Any] = {}
    for field in RESTRICTED_FIELDS:
        if field in data and data[field] is not None:
            out[field] = data[field]
    return out


def is_restricted_update_requested(data: Dict[str, Any]) -> bool:
    """Return True if the incoming payload attempts to change any of the
    four restricted fields (i.e. the key is present in the payload).
    """
    return any(field in data for field in RESTRICTED_FIELDS)
