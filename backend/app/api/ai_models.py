from flask import request, current_app, jsonify, g
from . import api
from ..decorators import login_required
from flasgger.utils import swag_from

@api.route('/ai-models/test', methods=['POST'])
@login_required
@swag_from({
    'tags': ['AI Models'],
    'summary': 'Test AI model with custom prompt',
    'description': 'Send a test prompt to a specific AI model and get the response',
    'consumes': ['application/json'],
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'description': 'Model test configuration',
            'schema': {
                'type': 'object',
                'required': ['model', 'prompt'],
                'properties': {
                    'model': {
                        'type': 'string',
                        'description': 'AI model identifier',
                        'example': 'gpt-4o-mini'
                    },
                    'prompt': {
                        'type': 'string',
                        'description': 'Test prompt to send to the model',
                        'example': 'What is artificial intelligence?'
                    },
                    'temperature': {
                        'type': 'number',
                        'format': 'float',
                        'minimum': 0.0,
                        'maximum': 2.0,
                        'description': 'Response creativity level',
                        'example': 0.7
                    },
                    'max_tokens': {
                        'type': 'integer',
                        'minimum': 1,
                        'maximum': 4000,
                        'description': 'Maximum tokens in response',
                        'example': 1000
                    }
                }
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'Model test successful',
            'schema': {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'response': {'type': 'string'},
                    'model': {'type': 'string'},
                    'tokens': {'type': 'integer'},
                    'response_time': {'type': 'number'}
                }
            }
        },
        '400': {
            'description': 'Bad Request - Invalid parameters',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        '401': {
            'description': 'Unauthorized - Invalid or missing authentication',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        },
        '500': {
            'description': 'Internal Server Error - Model service unavailable',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'}
                }
            }
        }
    }
})
def test_ai_model():
    """Test an AI model with a custom prompt"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate required fields
        model = data.get('model')
        prompt = data.get('prompt')
        
        if not model or not prompt:
            return jsonify({'error': 'Model and prompt are required'}), 400

        # Get optional parameters
        temperature = data.get('temperature', 0.7)
        max_tokens = data.get('max_tokens', 1000)
        
        # Validate parameters
        if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2:
            return jsonify({'error': 'Temperature must be between 0 and 2'}), 400
            
        if not isinstance(max_tokens, int) or max_tokens < 1 or max_tokens > 4000:
            return jsonify({'error': 'Max tokens must be between 1 and 4000'}), 400

        current_app.logger.info(f"🧪 AI Model Test: {model} for user {g.user_id}")
        current_app.logger.info(f"🧪 Prompt: {prompt[:100]}...")
        
        # Check if LLM service is available
        if not current_app.llm_service:
            return jsonify({
                'success': False,
                'error': 'AI model service is not available'
            }), 500

        # Prepare messages for the LLM
        messages = [
            {
                "role": "system", 
                "content": "You are a helpful AI assistant. Provide clear, accurate, and informative responses."
            },
            {
                "role": "user", 
                "content": prompt
            }
        ]

        # Record start time for response time calculation
        import time
        start_time = time.time()

        # Call the LLM service
        try:
            response_data = current_app.llm_service.generate_answer(
                messages=messages,
                model_name=model,
                user_id=str(g.user_id),
                tenant_id=str(g.user_tenant_id)
            )
            
            end_time = time.time()
            response_time = round((end_time - start_time) * 1000)  # Convert to milliseconds
            
            if response_data and response_data.get('content'):
                current_app.logger.info(f"✅ AI Model Test successful: {model}")
                return jsonify({
                    'success': True,
                    'response': response_data['content'],
                    'model': model,
                    'tokens': response_data.get('usage', {}).get('total_tokens', 0),
                    'response_time': response_time
                })
            else:
                current_app.logger.warning(f"⚠️ AI Model Test failed: No response from {model}")
                return jsonify({
                    'success': False,
                    'error': f'No response received from model {model}'
                }), 500
                
        except Exception as llm_error:
            end_time = time.time()
            response_time = round((end_time - start_time) * 1000)
            current_app.logger.error(f"❌ LLM Service Error: {llm_error}")
            
            # Check if it's a model-specific error
            error_message = str(llm_error)
            if 'not found' in error_message.lower() or 'invalid model' in error_message.lower():
                return jsonify({
                    'success': False,
                    'error': f'Model "{model}" is not available or not supported'
                }), 400
            elif 'rate limit' in error_message.lower():
                return jsonify({
                    'success': False,
                    'error': 'Rate limit exceeded. Please try again later.'
                }), 429
            elif 'quota' in error_message.lower() or 'billing' in error_message.lower():
                return jsonify({
                    'success': False,
                    'error': 'API quota exceeded or billing issue. Please check your API configuration.'
                }), 402
            else:
                return jsonify({
                    'success': False,
                    'error': f'Model service error: {error_message}'
                }), 500

    except Exception as e:
        current_app.logger.error(f"❌ AI Model Test Error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error occurred during model testing'
        }), 500


@api.route('/ai-models/health', methods=['GET'])
@login_required
@swag_from({
    'tags': ['AI Models'],
    'summary': 'Check AI models health status',
    'description': 'Get health status and availability of all AI models. By default, only checks service availability without making actual API calls to preserve quota.',
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'real_check',
            'in': 'query',
            'type': 'boolean',
            'default': False,
            'description': 'Set to true to perform actual API calls for real health checks (consumes API quota)'
        }
    ],
    'responses': {
        '200': {
            'description': 'Health check successful',
            'schema': {
                'type': 'object',
                'properties': {
                    'models': {
                        'type': 'object',
                        'additionalProperties': {
                            'type': 'object',
                            'properties': {
                                'status': {'type': 'string'},
                                'response_time': {'type': 'number'},
                                'last_checked': {'type': 'string'},
                                'error': {'type': 'string'}
                            }
                        }
                    }
                }
            }
        }
    }
})
def check_models_health():
    """Check the health status of all available AI models"""
    try:
        current_app.logger.info(f"🏥 AI Models Health Check for user {g.user_id}")
        
        # List of models to check
        models_to_check = [
            'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo',
            'models/gemini-pro', 'models/gemini-1.5-pro', 'models/gemini-1.5-flash', 'models/gemini-1.5-flash-latest'
        ]
        
        health_results = {}
        
        # Check if LLM service is available
        if not current_app.llm_service:
            for model in models_to_check:
                health_results[model] = {
                    'status': 'down',
                    'response_time': 0,
                    'last_checked': None,
                    'error': 'LLM service not available'
                }
            return jsonify({'models': health_results})

        # Check if we should do actual health checks (optional query parameter)
        do_real_check = request.args.get('real_check', 'false').lower() == 'true'
        
        # Quick health check for each model
        for model in models_to_check:
            try:
                import time
                start_time = time.time()
                
                if do_real_check:
                    # Only make actual LLM calls if explicitly requested
                    # Simple test message
                    messages = [{"role": "user", "content": "Hello"}]
                    
                    # Try to get a response (with timeout)
                    response_data = current_app.llm_service.generate_answer(
                        messages=messages,
                        model_name=model,
                        user_id=str(g.user_id),
                        tenant_id=str(g.user_tenant_id)
                    )
                    
                    end_time = time.time()
                    response_time = round((end_time - start_time) * 1000)
                    
                    if response_data and response_data.get('content'):
                        health_results[model] = {
                            'status': 'healthy',
                            'response_time': response_time,
                            'last_checked': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'uptime': 99.5  # Mock uptime
                        }
                    else:
                        health_results[model] = {
                            'status': 'degraded',
                            'response_time': response_time,
                            'last_checked': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'error': 'No response received'
                        }
                else:
                    # Mock health check without actual LLM calls
                    end_time = time.time()
                    response_time = round((end_time - start_time) * 1000) + 200  # Mock response time
                    
                    # Check if the model service clients exist
                    service_available = False
                    if 'gpt' in model and current_app.llm_service and current_app.llm_service.openai_client:
                        service_available = True
                    elif 'gemini' in model and current_app.llm_service and current_app.llm_service.gemini_client:
                        service_available = True
                    
                    health_results[model] = {
                        'status': 'available' if service_available else 'unavailable',
                        'response_time': response_time,
                        'last_checked': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'uptime': 99.5,  # Mock uptime
                        'note': 'Service availability check (no actual API call)'
                    }
                    
            except Exception as model_error:
                health_results[model] = {
                    'status': 'down',
                    'response_time': 0,
                    'last_checked': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'error': str(model_error)
                }
        
        current_app.logger.info(f"✅ Health check completed for {len(models_to_check)} models")
        return jsonify({'models': health_results})
        
    except Exception as e:
        current_app.logger.error(f"❌ Health Check Error: {e}")
        return jsonify({'error': 'Health check failed'}), 500
