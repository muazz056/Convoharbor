from flask import Blueprint, request, jsonify, current_app
from functools import wraps

api = Blueprint('api', __name__)

# Lightweight in-memory rate limiter (non-breaking, best-effort)
_RATE_LIMIT_STORE = {}

def rate_limit(max_requests: int = 120, window_seconds: int = 60):
    """Simple per-IP limiter. For production use Redis or a gateway. Keeps existing
    functionality intact; only throttles abusive bursts.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                ip = request.headers.get('X-Forwarded-For', request.remote_addr) or 'unknown'
                key = f"{ip}:{request.endpoint}"
                record = _RATE_LIMIT_STORE.get(key, [])
                now = int(__import__('time').time())
                window_start = now - window_seconds
                record = [t for t in record if t >= window_start]
                if len(record) >= max_requests:
                    return jsonify({'error': 'rate_limit_exceeded'}), 429
                record.append(now)
                _RATE_LIMIT_STORE[key] = record
            except Exception:
                pass  # fail-open
            return fn(*args, **kwargs)
        return wrapper
    return decorator

from . import auth, tenants, users, chatbots, datasources, usage_stats, debug, conversations, widget, analytics, notifications, ai_models, general_chat, jit_access
