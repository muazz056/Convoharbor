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

        // Create iframe with website context
        var iframe = document.createElement('iframe');
        var contextParam = encodeURIComponent(JSON.stringify(websiteContext));
        iframe.src = \"{chat_widget_url}?website_context=\" + contextParam;
        iframe.style.border = 'none';
        iframe.style.position = 'fixed';
        iframe.style.top = '0';
        iframe.style.left = '0';
        iframe.style.width = '100%';
        iframe.style.height = '100%';
        iframe.style.zIndex = '9999';
        iframe.style.pointerEvents = 'auto';
        iframe.style.background = 'transparent';
        iframe.allow = 'clipboard-write;';

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
