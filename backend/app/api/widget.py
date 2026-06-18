import os
from flask import request, current_app, jsonify, g
from flasgger import swag_from
from . import api
from ..decorators import login_required
from ..models import Chatbot, Tenant


@api.route('/widget/generate-script/<int:chatbot_id>', methods=['GET'])
@login_required
@swag_from({
    'tags': ['Widget'],
    'summary': 'Generate embeddable widget script',
    'description': 'Produces a JavaScript snippet for embedding the chatbot on an external website.',
    'parameters': [
        {
            'name': 'chatbot_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'The ID of the chatbot to embed.'
        }
    ],
    'responses': {
        '200': {
            'description': 'Embeddable script generated successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'script': {
                        'type': 'string',
                        'description': 'The HTML script tag to embed.'
                    }
                }
            }
        },
        '404': {
            'description': 'Chatbot not found or access denied.'
        }
    }
})
def generate_widget_script(chatbot_id):
    """Generates a JavaScript snippet to embed the chatbot widget."""
    # Resolve tenant context (UUID in JWT) -> internal integer id
    tenant_uuid = getattr(getattr(g, 'user', None), 'tenant_id', None)
    if tenant_uuid is None:
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        if not token:
            token = request.args.get('token')
        if token and current_app.auth_service:
            payload = current_app.auth_service.verify_token(token)
            if payload:
                tenant_uuid = payload.get('tenant_id')

    if tenant_uuid is None:
        return jsonify({'error': 'Authentication required'}), 401

    # Map tenant_uuid (tenants.tenant_id) to internal tenants.id
    tenant = Tenant.query.filter_by(tenant_id=str(tenant_uuid)).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    tenant_int_id = tenant.id

    # Verify chatbot belongs to tenant (compare integer id)
    chatbot = Chatbot.query.filter_by(id=chatbot_id, tenant_id=tenant_int_id).first()
    if not chatbot:
        return jsonify({'error': 'Chatbot not found or access denied'}), 404

    # Public chat interface URL (frontend route to implement)
    chat_widget_url = f"{current_app.config['FRONTEND_URL']}/public/chat/{chatbot.id}"

    # App slug used for DOM IDs / storage keys (derived from APP_NAME)
    _app_slug = (os.environ.get('APP_NAME') or current_app.config.get('APP_NAME') or 'Convoharbor').lower()

    # Read position from chatbot theme config (default: bottom-right)
    _config = chatbot.config or {}
    _theme = _config.get('theme', {}) or {}
    _position = _theme.get('position', 'bottom-right')

    # Embeddable JavaScript snippet with website tracking (escape braces for f-string)
    script = f"""
<div id=\"{_app_slug}-widget-container\"></div>
<script>
    (function(){{
      function ready(fn){{ if(document.readyState!='loading'){{fn()}} else {{document.addEventListener('DOMContentLoaded', fn)}} }}
      ready(function(){{
        // Capture website context for tracking
        var websiteContext = {{
          domain: window.location.hostname,
          url: window.location.href,
          path: window.location.pathname,
          referrer: document.referrer,
          title: document.title,
          chatbot_id: {chatbot_id},
          timestamp: new Date().toISOString()
        }};

        // Set up resize listener BEFORE creating iframe
        var _lastW = 0, _lastH = 0;
        var _applySize = function(w, h) {{
          _lastW = w; _lastH = h;
          var f = document.querySelector('iframe[data-convoharbor]');
          if(!f) return;
          // Add 20px offset for widget position, clamp to host viewport
          var cw = Math.min(w + 20, window.innerWidth);
          var ch = Math.min(h + 20, window.innerHeight);
          f.style.width = cw + 'px';
          f.style.height = ch + 'px';
        }};
        window.addEventListener('message', function(e){{
          if(e.data && e.data.type === 'convoharbor_resize'){{
            _applySize(e.data.width, e.data.height);
          }}
        }});
        // Re-apply on host window resize for responsiveness
        window.addEventListener('resize', function(){{
          if(_lastW > 0) _applySize(_lastW, _lastH);
        }});

        // Create iframe with website context
        var iframe = document.createElement('iframe');
        iframe.setAttribute('data-convoharbor','true');
        var contextParam = encodeURIComponent(JSON.stringify(websiteContext));
        iframe.src = \"{chat_widget_url}?website_context=\" + contextParam;
        iframe.style.border = 'none';
        iframe.style.outline = 'none';
        iframe.style.position = 'fixed';
        iframe.style.zIndex = '9999';
        iframe.style.background = 'transparent';
        iframe.style.pointerEvents = 'auto';
        iframe.allow = 'clipboard-write;';
        // Start small (toggle-button size) — ChatWidget sends postMessage
        // to enlarge on open and shrink on close.
        iframe.style.width = '60px';
        iframe.style.height = '60px';
        iframe.style.maxWidth = '100vw';
        iframe.style.maxHeight = '100vh';
        // Position at configured widget corner
        var pos = '{_position}';
        iframe.style.bottom = pos.indexOf('bottom') !== -1 ? '0' : 'auto';
        iframe.style.top = pos.indexOf('top') !== -1 ? '0' : 'auto';
        iframe.style.right = pos.indexOf('right') !== -1 ? '0' : 'auto';
        iframe.style.left = pos.indexOf('left') !== -1 ? '0' : 'auto';

        // Store context for session persistence
        if (typeof(Storage) !== \"undefined\") {{
          sessionStorage.setItem('{_app_slug}_website_context', JSON.stringify(websiteContext));
        }}

        (document.getElementById('{_app_slug}-widget-container')||document.body).appendChild(iframe);
      }});
    }})();
</script>
    """.strip()

    return jsonify({'script': script})
