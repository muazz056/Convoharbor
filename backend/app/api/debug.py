# app/api/debug.py

from flask import request, current_app, jsonify
from flask_cors import cross_origin
from . import api
from ..decorators import login_required
from ..services.prompt_service import PromptService
from flasgger.utils import swag_from
import os


@api.route('/debug/gemini', methods=['GET'])
@cross_origin()
@login_required
@swag_from({
    'tags': ['Debug'],
    'summary': 'Test Gemini API functionality',
    'description': 'Comprehensive test of Gemini API key, connection, and basic functionality',
    'produces': ['application/json'],
    'responses': {
        '200': {
            'description': 'Debug results',
            'schema': {
                'type': 'object',
                'properties': {
                    'gemini_status': {'type': 'object'},
                    'api_key_status': {'type': 'object'},
                    'connection_test': {'type': 'object'},
                    'simple_test': {'type': 'object'}
                }
            }
        }
    }
})
def debug_gemini():
    """Debug Gemini API functionality"""
    debug_results = {
        'timestamp': current_app.config.get('TESTING_TIME', 'N/A'),
        'gemini_status': {},
        'api_key_status': {},
        'connection_test': {},
        'simple_test': {}
    }

    try:
        # 1. Check API key configuration
        current_app.logger.info("🔍 [DEBUG] Starting Gemini API debug...")

        gemini_key = current_app.config.get('GEMINI_API_KEY')
        debug_results['api_key_status'] = {
            'configured': bool(gemini_key),
            'key_length': len(gemini_key) if gemini_key else 0,
            'key_prefix': gemini_key[:10] + '...' if gemini_key and len(gemini_key) > 10 else 'N/A',
            'is_placeholder': gemini_key.startswith('your-') if gemini_key else True,
            'env_var_set': 'GEMINI_API_KEY' in os.environ
        }

        current_app.logger.info(f"🔑 [DEBUG] API Key Status: {debug_results['api_key_status']}")

        # 2. Check LLM service initialization
        llm_service = getattr(current_app, 'llm_service', None)
        debug_results['gemini_status'] = {
            'llm_service_exists': llm_service is not None,
            'gemini_client_exists': hasattr(llm_service, 'gemini_client') and llm_service.gemini_client is not None if llm_service else False,
            'gemini_available': llm_service.is_available('gemini') if llm_service else False
        }

        current_app.logger.info(f"🤖 [DEBUG] Gemini Service Status: {debug_results['gemini_status']}")

        # 3. Test basic connection
        if llm_service and llm_service.is_available('gemini'):
            try:
                current_app.logger.info("🔗 [DEBUG] Testing Gemini connection...")

                from ..models import AiModel
                gemini_model = AiModel.query.filter_by(provider='gemini', is_active=True).first()
                gemini_model_name = gemini_model.model_name if gemini_model else 'models/gemini-2.0-flash'

                test_response = llm_service.generate_answer(
                    messages=[{"role": "user", "content": "Hello! Please respond with exactly: 'Gemini API is working correctly.'"}],
                    model_name=gemini_model_name,
                    temperature=0.0
                )
                test_content = test_response.get('content', '') if test_response else ''

                debug_results['connection_test'] = {
                    'success': True,
                    'response': test_content,
                    'response_length': len(test_content) if test_content else 0,
                    'contains_expected': 'Gemini API is working correctly' in test_content if test_content else False,
                    'is_demo_mode': 'demo mode' in test_content.lower() if test_content else False
                }

                current_app.logger.info(f"✅ [DEBUG] Connection test result: {test_response[:100]}...")

            except Exception as e:
                debug_results['connection_test'] = {
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
                current_app.logger.error(f"❌ [DEBUG] Connection test failed: {e}")
        else:
            debug_results['connection_test'] = {
                'success': False,
                'error': 'Gemini service not available',
                'llm_service_available': llm_service is not None,
                'gemini_available': llm_service.is_available('gemini') if llm_service else False
            }

        # 4. Test web extraction capability
        if debug_results['connection_test'].get('success'):
            try:
                current_app.logger.info("🕷️ [DEBUG] Testing web extraction capability...")

                sample_html = """
                <html>
                <head><title>Test Page</title></head>
                <body>
                    <nav>Navigation menu</nav>
                    <main>
                        <h1>Main Article Title</h1>
                        <p>This is the main content of the article. It contains important information that should be extracted.</p>
                        <p>Another paragraph with useful content for the chatbot knowledge base.</p>
                    </main>
                    <aside>Sidebar content</aside>
                    <footer>Footer information</footer>
                </body>
                </html>
                """

                extraction_prompt = (
                    PromptService().render('debug_extraction', html=sample_html)
                )

                extraction_response = llm_service.generate_answer(
                    messages=[{"role": "user", "content": extraction_prompt}],
                    model_name=gemini_model_name,
                    temperature=0.1
                )
                extraction_content = extraction_response.get('content', '') if extraction_response else ''

                debug_results['simple_test'] = {
                    'success': True,
                    'extracted_content': extraction_content,
                    'content_length': len(extraction_content) if extraction_content else 0,
                    'contains_title': 'Main Article Title' in extraction_content if extraction_content else False,
                    'contains_main_content': 'main content of the article' in extraction_content if extraction_content else False,
                    'excludes_nav': 'Navigation menu' not in extraction_content if extraction_content else True,
                    'excludes_footer': 'Footer information' not in extraction_content if extraction_content else True,
                    'is_demo_mode': 'demo mode' in extraction_content.lower() if extraction_content else False
                }

                current_app.logger.info(f"🎯 [DEBUG] Extraction test successful: {len(extraction_response)} chars extracted")

            except Exception as e:
                debug_results['simple_test'] = {
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
                current_app.logger.error(f"❌ [DEBUG] Extraction test failed: {e}")
        else:
            debug_results['simple_test'] = {
                'success': False,
                'error': 'Skipped due to connection test failure'
            }

        # 5. Overall assessment
        overall_status = 'working' if (
            debug_results['api_key_status']['configured']
            and not debug_results['api_key_status']['is_placeholder']
            and debug_results['gemini_status']['gemini_available']
            and debug_results['connection_test'].get('success')
            and not debug_results['connection_test'].get('is_demo_mode')
            and debug_results['simple_test'].get('success')
        ) else 'failed'

        debug_results['overall_status'] = overall_status
        debug_results['summary'] = _generate_debug_summary(debug_results)

        current_app.logger.info(f"🏁 [DEBUG] Overall Gemini status: {overall_status}")

        return jsonify(debug_results), 200

    except Exception as e:
        current_app.logger.error(f"❌ [DEBUG] Debug endpoint failed: {e}")
        return jsonify({
            'error': 'Debug endpoint failed',
            'message': str(e),
            'overall_status': 'error'
        }), 500


def _generate_debug_summary(results):
    """Generate a human-readable summary of debug results"""
    issues = []
    recommendations = []

    # Check API key
    if not results['api_key_status']['configured']:
        issues.append("❌ Gemini API key not configured")
        recommendations.append("Set GEMINI_API_KEY in your .env file")
    elif results['api_key_status']['is_placeholder']:
        issues.append("❌ Gemini API key appears to be a placeholder")
        recommendations.append("Replace with a real Gemini API key from Google AI Studio")
    elif not results['api_key_status']['env_var_set']:
        issues.append("⚠️ GEMINI_API_KEY environment variable not found")
        recommendations.append("Ensure .env file is loaded and contains GEMINI_API_KEY")

    # Check service availability
    if not results['gemini_status']['llm_service_exists']:
        issues.append("❌ LLM service not initialized")
        recommendations.append("Check Flask app initialization and service setup")
    elif not results['gemini_status']['gemini_available']:
        issues.append("❌ Gemini client not available in LLM service")
        recommendations.append("Check Gemini client initialization in LLM service")

    # Check connection
    if not results['connection_test'].get('success'):
        issues.append("❌ Gemini API connection failed")
        if 'error' in results['connection_test']:
            recommendations.append(f"Connection error: {results['connection_test']['error']}")
    elif results['connection_test'].get('is_demo_mode'):
        issues.append("⚠️ Gemini is running in demo mode")
        recommendations.append("Check API key validity and quota limits")

    # Check extraction capability
    if not results['simple_test'].get('success'):
        issues.append("❌ Web content extraction test failed")
        if 'error' in results['simple_test']:
            recommendations.append(f"Extraction error: {results['simple_test']['error']}")

    if not issues:
        return {
            'status': '✅ All tests passed',
            'message': 'Gemini API is working correctly and ready for web extraction',
            'issues': [],
            'recommendations': []
        }
    else:
        return {
            'status': f'❌ {len(issues)} issue(s) found',
            'message': 'Gemini API has configuration or connectivity issues',
            'issues': issues,
            'recommendations': recommendations
        }


@api.route('/debug/test-url', methods=['POST'])
@cross_origin()
@login_required
@swag_from({
    'tags': ['Debug'],
    'summary': 'Test web extraction on a specific URL',
    'description': 'Test the complete web extraction pipeline on a provided URL',
    'consumes': ['application/json'],
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['url'],
                'properties': {
                    'url': {
                        'type': 'string',
                        'format': 'uri',
                        'description': 'URL to test extraction on',
                        'example': 'https://en.wikipedia.org/wiki/Artificial_intelligence'
                    }
                }
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'Extraction test results',
            'schema': {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string'},
                    'fetch_result': {'type': 'object'},
                    'extraction_result': {'type': 'object'},
                    'overall_success': {'type': 'boolean'}
                }
            }
        }
    }
})
def debug_test_url():
    """Test web extraction on a specific URL"""
    data = request.get_json()

    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required'}), 400

    url = data['url']

    try:
        current_app.logger.info(f"🧪 [DEBUG] Testing URL extraction: {url}")

        # Import and test the web extraction service
        from ..services.web_extraction_service import WebExtractionService

        web_extractor = WebExtractionService()
        result = web_extractor.extract_content_from_url(url, "Debug test extraction")

        debug_result = {
            'url': url,
            'timestamp': current_app.config.get('TESTING_TIME', 'N/A'),
            'extraction_result': result,
            'overall_success': result.get('success', False)
        }

        if result.get('success'):
            debug_result['content_preview'] = result['content'][:500] + '...' if len(result['content']) > 500 else result['content']
            debug_result['content_stats'] = {
                'total_length': len(result['content']),
                'word_count': len(result['content'].split()) if result['content'] else 0,
                'line_count': result['content'].count('\n') if result['content'] else 0
            }

        current_app.logger.info(f"🎯 [DEBUG] URL test completed: success={result.get('success')}")

        return jsonify(debug_result), 200

    except Exception as e:
        current_app.logger.error(f"❌ [DEBUG] URL test failed: {e}")
        return jsonify({
            'url': url,
            'error': str(e),
            'error_type': type(e).__name__,
            'overall_success': False
        }), 500
