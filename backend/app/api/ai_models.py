from flask import request, current_app, jsonify, g
from . import api
from ..decorators import login_required, super_admin_required
from ..models import AiModel, SUPPORTED_PROVIDERS
from .. import db
from datetime import datetime


@api.route('/admin/providers', methods=['GET'])
@super_admin_required
def list_providers():
    return jsonify({'providers': SUPPORTED_PROVIDERS})


@api.route('/admin/models', methods=['GET'])
@super_admin_required
def list_all_models():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    provider = request.args.get('provider')
    active_only = request.args.get('active_only', 'false').lower() == 'true'

    query = AiModel.query
    if provider:
        query = query.filter_by(provider=provider)
    if active_only:
        query = query.filter_by(is_active=True)
    query = query.order_by(AiModel.provider, AiModel.model_name)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    models = [m.to_dict(include_key=False) for m in pagination.items]

    return jsonify({
        'models': models,
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages
    })


@api.route('/admin/models', methods=['POST'])
@super_admin_required
def create_model():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    provider = data.get('provider')
    model_name = data.get('model_name')

    if not provider or not model_name:
        return jsonify({'error': 'provider and model_name are required'}), 400

    valid_ids = [p['id'] for p in SUPPORTED_PROVIDERS]
    if provider not in valid_ids:
        return jsonify({'error': f'Invalid provider. Must be one of: {", ".join(valid_ids)}'}), 400

    existing = AiModel.query.filter_by(provider=provider, model_name=model_name).first()
    if existing:
        return jsonify({'error': f'Model {provider}/{model_name} already exists'}), 409

    model = AiModel(
        provider=provider,
        model_name=model_name,
        display_name=data.get('display_name', model_name),
        base_url=data.get('base_url'),
        is_active=data.get('is_active', True),
        model_type=data.get('model_type', 'chat'),
        context_window=data.get('context_window'),
        max_tokens=data.get('max_tokens'),
        created_by=g.user_id
    )
    api_key = data.get('api_key')
    if api_key:
        model.set_api_key(api_key)

    db.session.add(model)
    db.session.commit()

    current_app.logger.info(f"AI model created: {provider}/{model_name} by user {g.user_id}")
    return jsonify({'message': 'Model created', 'model': model.to_dict(include_key=False)}), 201


@api.route('/admin/models/<int:model_id>', methods=['GET'])
@super_admin_required
def get_model(model_id):
    model = AiModel.query.get_or_404(model_id)
    return jsonify({'model': model.to_dict(include_key=True)})


@api.route('/admin/models/<int:model_id>', methods=['PUT'])
@super_admin_required
def update_model(model_id):
    model = AiModel.query.get_or_404(model_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if 'provider' in data:
        valid_ids = [p['id'] for p in SUPPORTED_PROVIDERS]
        if data['provider'] not in valid_ids:
            return jsonify({'error': f'Invalid provider. Must be one of: {", ".join(valid_ids)}'}), 400
        model.provider = data['provider']
    if 'model_name' in data:
        model.model_name = data['model_name']
    if 'display_name' in data:
        model.display_name = data['display_name']
    if 'base_url' in data:
        model.base_url = data['base_url']
    if 'is_active' in data:
        model.is_active = data['is_active']
    if 'model_type' in data:
        model.model_type = data['model_type']
    if 'context_window' in data:
        model.context_window = data['context_window']
    if 'max_tokens' in data:
        model.max_tokens = data['max_tokens']
    if 'api_key' in data:
        model.set_api_key(data['api_key'])

    model.updated_at = datetime.utcnow()
    db.session.commit()

    current_app.logger.info(f"AI model updated: {model.id} by user {g.user_id}")
    return jsonify({'message': 'Model updated', 'model': model.to_dict(include_key=False)})


@api.route('/admin/models/<int:model_id>', methods=['DELETE'])
@super_admin_required
def delete_model(model_id):
    model = AiModel.query.get_or_404(model_id)
    db.session.delete(model)
    db.session.commit()

    current_app.logger.info(f"AI model deleted: {model.id} by user {g.user_id}")
    return jsonify({'message': 'Model deleted'})


@api.route('/models', methods=['GET'])
@login_required
def list_active_models():
    provider = request.args.get('provider')
    query = AiModel.query.filter_by(is_active=True)
    if provider:
        query = query.filter_by(provider=provider)
    models = query.order_by(AiModel.provider, AiModel.model_name).all()

    grouped = {}
    for m in models:
        d = m.to_dict(include_key=False)
        grouped.setdefault(m.provider, []).append(d)

    return jsonify({
        'models': [m.to_dict(include_key=False) for m in models],
        'grouped_by_provider': grouped
    })


@api.route('/ai-models/test', methods=['POST'])
@login_required
def test_ai_model():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    model = data.get('model')
    prompt = data.get('prompt')
    model_id = data.get('model_id')

    if not model and not model_id:
        return jsonify({'error': 'model name or model_id is required'}), 400
    if not prompt:
        return jsonify({'error': 'prompt is required'}), 400

    temperature = data.get('temperature', 0.7)
    max_tokens = data.get('max_tokens', 1000)

    if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2:
        return jsonify({'error': 'Temperature must be between 0 and 2'}), 400
    if not isinstance(max_tokens, int) or max_tokens < 1 or max_tokens > 4000:
        return jsonify({'error': 'Max tokens must be between 1 and 4000'}), 400

    current_app.logger.info(f"AI Model Test: {model or model_id} for user {g.user_id}")

    if not current_app.llm_service:
        return jsonify({'success': False, 'error': 'AI model service is not available'}), 500

    messages = [
        {"role": "system", "content": "You are a helpful AI assistant. Provide clear, accurate, and informative responses."},
        {"role": "user", "content": prompt}
    ]

    import time
    start_time = time.time()

    try:
        if model_id:
            ai_model = AiModel.query.get(model_id)
            if not ai_model:
                return jsonify({'success': False, 'error': f'Model ID {model_id} not found'}), 404
            response_data = current_app.llm_service.generate_answer_with_model(
                messages=messages,
                ai_model=ai_model,
                user_id=str(g.user_id),
                tenant_id=str(g.user_tenant_id)
            )
            model_used = ai_model.display_name
        else:
            response_data = current_app.llm_service.generate_answer(
                messages=messages,
                model_name=model,
                user_id=str(g.user_id),
                tenant_id=str(g.user_tenant_id)
            )
            model_used = model

        end_time = time.time()
        response_time = round((end_time - start_time) * 1000)

        if response_data and response_data.get('content'):
            return jsonify({
                'success': True,
                'response': response_data['content'],
                'model': model_used,
                'tokens': response_data.get('usage', {}).get('total_tokens', 0),
                'response_time': response_time
            })
        else:
            return jsonify({
                'success': False,
                'error': f'No response received from model {model_used}'
            }), 500

    except Exception as llm_error:
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000)
        error_message = str(llm_error)
        if 'not found' in error_message.lower() or 'invalid model' in error_message.lower():
            return jsonify({'success': False, 'error': f'Model is not available or not supported'}), 400
        elif 'rate limit' in error_message.lower():
            return jsonify({'success': False, 'error': 'Rate limit exceeded. Please try again later.'}), 429
        elif 'quota' in error_message.lower() or 'billing' in error_message.lower():
            return jsonify({'success': False, 'error': 'API quota exceeded or billing issue.'}), 402
        else:
            return jsonify({'success': False, 'error': f'Model service error: {error_message}'}), 500


@api.route('/ai-models/health', methods=['GET'])
@login_required
def check_models_health():
    try:
        models = AiModel.query.filter_by(is_active=True).all()
        health_results = {}

        for ai_model in models:
            try:
                import time
                start_time = time.time()
                do_real_check = request.args.get('real_check', 'false').lower() == 'true'

                if do_real_check and current_app.llm_service:
                    messages = [{"role": "user", "content": "Hello"}]
                    response_data = current_app.llm_service.generate_answer_with_model(
                        messages=messages,
                        ai_model=ai_model,
                        user_id=str(g.user_id),
                        tenant_id=str(g.user_tenant_id)
                    )
                    end_time = time.time()
                    response_time = round((end_time - start_time) * 1000)
                    status = 'healthy' if response_data and response_data.get('content') else 'degraded'
                else:
                    end_time = time.time()
                    response_time = round((end_time - start_time) * 1000)
                    status = 'available'

                health_results[ai_model.display_name] = {
                    'status': status,
                    'response_time': response_time,
                    'last_checked': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'provider': ai_model.provider
                }
            except Exception as model_error:
                health_results[ai_model.display_name] = {
                    'status': 'down',
                    'response_time': 0,
                    'last_checked': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'provider': ai_model.provider,
                    'error': str(model_error)
                }

        if not health_results:
            health_results = {'default': {'status': 'no_models', 'note': 'No active models found in database'}}

        return jsonify({'models': health_results})
    except Exception as e:
        current_app.logger.error(f"Health Check Error: {e}")
        return jsonify({'error': 'Health check failed'}), 500
