from flask import Blueprint, request, jsonify, current_app
from functools import wraps

api = Blueprint('api', __name__)


def rate_limit(max_requests: int = 120, window_seconds: int = 60):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                ip = request.headers.get('X-Forwarded-For', request.remote_addr) or 'unknown'
                key = f"{ip}:{request.endpoint}"

                redis_service = getattr(current_app, 'redis_service', None)
                if redis_service:
                    allowed, remaining, reset_at = redis_service.check_rate_limit(key, max_requests, window_seconds)
                    if not allowed:
                        return jsonify({'error': 'rate_limit_exceeded'}), 429
                else:
                    pass
            except Exception:
                pass

            return fn(*args, **kwargs)
        return wrapper
    return decorator


from . import auth, tenants, users, chatbots, datasources, usage_stats, debug, conversations, widget, analytics, notifications, ai_models, general_chat, jit_access
