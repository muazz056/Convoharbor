# app/api/usage_stats.py

from datetime import datetime, timedelta
from flask import request, current_app, jsonify, g
from . import api
from ..decorators import login_required
from ..models import Chatbot
from ..services.token_tracking_service import TokenTrackingService
from flasgger.utils import swag_from


@api.route('/usage/stats', methods=['GET'])
@login_required
@swag_from({
    'tags': ['Usage & Analytics'],
    'summary': 'Get token usage statistics for tenant',
    'description': """
    ### 📊 Description
    Retrieves comprehensive token usage and cost analytics for the authenticated user's tenant.
    Supports filtering by date range, chatbot, and includes cost breakdowns by provider and operation type.

    Perfect for:
    - Monitoring AI costs and usage
    - Understanding which chatbots consume most resources
    - Identifying cost optimization opportunities
    - Generating billing reports

    ---
    ### 💰 Cost Analytics Features
    - Total token usage and costs
    - Breakdown by AI provider (OpenAI, Gemini)
    - Operation-specific costs (queries, embeddings, processing)
    - Per-chatbot usage statistics
    - Daily usage trends
    - Cost alerts and recommendations

    ---
    ### 🔑 Authorization
    Requires authentication. Only shows usage data for user's tenant.
    """,
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'start_date',
            'in': 'query',
            'type': 'string',
            'format': 'date',
            'description': 'Start date for statistics (ISO format, defaults to 30 days ago)',
            'example': '2024-01-01'
        },
        {
            'name': 'end_date',
            'in': 'query',
            'type': 'string',
            'format': 'date',
            'description': 'End date for statistics (ISO format, defaults to now)',
            'example': '2024-01-31'
        },
        {
            'name': 'chatbot_id',
            'in': 'query',
            'type': 'integer',
            'description': 'Optional filter by specific chatbot ID'
        },
        {
            'name': 'include_trends',
            'in': 'query',
            'type': 'boolean',
            'description': 'Include daily usage trends (default: true)',
            'example': True
        },
        {
            'name': 'include_recommendations',
            'in': 'query',
            'type': 'boolean',
            'description': 'Include cost optimization recommendations (default: true)',
            'example': True
        }
    ],
    'responses': {
        '200': {
            'description': 'Usage statistics retrieved successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'tenant_id': {'type': 'integer'},
                    'chatbot_id': {'type': 'integer', 'description': 'If filtered by specific chatbot'},
                    'period': {
                        'type': 'object',
                        'properties': {
                            'start': {'type': 'string', 'format': 'date-time'},
                            'end': {'type': 'string', 'format': 'date-time'}
                        }
                    },
                    'total_tokens': {'type': 'integer', 'description': 'Total tokens consumed'},
                    'total_cost': {'type': 'number', 'format': 'float', 'description': 'Total cost in USD'},
                    'usage_by_provider': {
                        'type': 'object',
                        'description': 'Breakdown by AI provider (OpenAI, Gemini, etc.)',
                        'additionalProperties': {
                            'type': 'object',
                            'properties': {
                                'tokens': {'type': 'integer'},
                                'cost': {'type': 'number'},
                                'requests': {'type': 'integer'}
                            }
                        }
                    },
                    'usage_by_operation': {
                        'type': 'object',
                        'description': 'Breakdown by operation type (query, embedding, etc.)',
                        'additionalProperties': {
                            'type': 'object',
                            'properties': {
                                'tokens': {'type': 'integer'},
                                'cost': {'type': 'number'},
                                'requests': {'type': 'integer'}
                            }
                        }
                    },
                    'usage_by_chatbot': {
                        'type': 'object',
                        'description': 'Breakdown by chatbot',
                        'additionalProperties': {
                            'type': 'object',
                            'properties': {
                                'tokens': {'type': 'integer'},
                                'cost': {'type': 'number'},
                                'requests': {'type': 'integer'}
                            }
                        }
                    },
                    'daily_usage': {
                        'type': 'object',
                        'description': 'Daily usage breakdown',
                        'additionalProperties': {
                            'type': 'object',
                            'properties': {
                                'tokens': {'type': 'integer'},
                                'cost': {'type': 'number'},
                                'requests': {'type': 'integer'}
                            }
                        }
                    },
                    'trends': {
                        'type': 'array',
                        'description': 'Daily usage trends (if requested)',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'date': {'type': 'string', 'format': 'date'},
                                'tokens': {'type': 'integer'},
                                'cost': {'type': 'number'},
                                'requests': {'type': 'integer'}
                            }
                        }
                    },
                    'alerts': {
                        'type': 'array',
                        'description': 'Cost alerts and warnings',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'level': {'type': 'string', 'enum': ['info', 'warning', 'critical']},
                                'message': {'type': 'string'},
                                'current_cost': {'type': 'number'},
                                'threshold': {'type': 'number'},
                                'period': {'type': 'string'}
                            }
                        }
                    },
                    'recommendations': {
                        'type': 'array',
                        'description': 'Cost optimization recommendations (if requested)',
                        'items': {'type': 'string'}
                    }
                }
            }
        },
        '400': {
            'description': 'Bad Request - Invalid parameters',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '401': {
            'description': 'Unauthorized',
            'schema': {'$ref': '#/definitions/Error'}
        }
    }
})
def get_usage_statistics():
    """Get token usage statistics for the current tenant"""
    # Parse date parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    try:
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        else:
            start_date = datetime.utcnow() - timedelta(days=30)

        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        else:
            end_date = datetime.utcnow()

    except ValueError:
        return jsonify({
            'error': 'Invalid date format',
            'message': 'Dates should be in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)'
        }), 400

    # Validate date range
    if start_date >= end_date:
        return jsonify({
            'error': 'Invalid date range',
            'message': 'Start date must be before end date'
        }), 400

    # Optional chatbot filter
    chatbot_id = request.args.get('chatbot_id', type=int)
    if chatbot_id:
        # Verify chatbot belongs to user's tenant
        chatbot = Chatbot.query.filter_by(
            id=chatbot_id,
            tenant_id=g.tenant_id
        ).first()

        if not chatbot:
            return jsonify({
                'error': 'Chatbot not found',
                'message': f'No chatbot found with ID {chatbot_id} in your organization'
            }), 400

    # Feature flags
    include_trends = request.args.get('include_trends', 'true').lower() == 'true'
    include_recommendations = request.args.get('include_recommendations', 'true').lower() == 'true'

    try:
        # Initialize token tracking service
        token_service = TokenTrackingService()

        # Get usage statistics
        usage_stats = token_service.get_tenant_usage(
            tenant_id=g.tenant_id,
            start_date=start_date,
            end_date=end_date,
            chatbot_id=chatbot_id
        )

        # Add optional data
        if include_trends:
            days_diff = (end_date - start_date).days
            usage_stats['trends'] = token_service.get_usage_trends(
                tenant_id=g.tenant_id,
                days=max(days_diff, 7)  # At least 7 days for meaningful trends
            )

        if include_recommendations:
            # Get cost alerts
            usage_stats['alerts'] = token_service.get_cost_alerts(g.tenant_id)

            # Get recommendations from the usage report
            report = token_service.export_usage_report(
                tenant_id=g.tenant_id,
                start_date=start_date,
                end_date=end_date
            )
            usage_stats['recommendations'] = report['recommendations']

        current_app.logger.info(
            f"📊 Usage statistics retrieved for tenant {g.tenant_id}: "
            f"{usage_stats['total_tokens']} tokens, ${usage_stats['total_cost']:.4f}"
        )

        return jsonify(usage_stats), 200

    except Exception as e:
        current_app.logger.error(f"❌ Error retrieving usage statistics: {e}")
        return jsonify({
            'error': 'Statistics retrieval failed',
            'message': 'An error occurred while retrieving usage statistics'
        }), 500


@api.route('/usage/cost-estimate', methods=['POST'])
@login_required
@swag_from({
    'tags': ['Usage & Analytics'],
    'summary': 'Estimate cost for planned AI operations',
    'description': """
    ### 💡 Description
    Calculates estimated costs for planned AI operations before execution.
    Useful for budgeting, cost planning, and helping users understand pricing.

    Supports all available AI models and providers with real-time pricing.

    ---
    ### 🔑 Authorization
    Requires authentication.
    """,
    'consumes': ['application/json'],
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['operations'],
                'properties': {
                    'operations': {
                        'type': 'array',
                        'description': 'List of AI operations to estimate',
                        'items': {
                            'type': 'object',
                            'required': ['provider', 'model', 'input_tokens'],
                            'properties': {
                                'provider': {
                                    'type': 'string',
                                    'enum': ['openai', 'gemini'],
                                    'description': 'AI provider',
                                    'example': 'openai'
                                },
                                'model': {
                                    'type': 'string',
                                    'description': 'Specific model to use. Must be an active model configured by Super Admin.',
                                    'example': '<configured-model-name>'
                                },
                                'input_tokens': {
                                    'type': 'integer',
                                    'minimum': 1,
                                    'description': 'Estimated input tokens',
                                    'example': 1000
                                },
                                'output_tokens': {
                                    'type': 'integer',
                                    'minimum': 0,
                                    'description': 'Estimated output tokens (default: 0)',
                                    'example': 500
                                },
                                'operation': {
                                    'type': 'string',
                                    'description': 'Type of operation',
                                    'example': 'query'
                                },
                                'description': {
                                    'type': 'string',
                                    'description': 'Optional description of the operation',
                                    'example': 'Customer support queries'
                                }
                            }
                        }
                    }
                }
            }
        }
    ],
    'responses': {
        '200': {
            'description': 'Cost estimate calculated successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'total_cost': {'type': 'number', 'format': 'float', 'description': 'Total estimated cost in USD'},
                    'total_tokens': {'type': 'integer', 'description': 'Total tokens across all operations'},
                    'operations': {
                        'type': 'array',
                        'description': 'Detailed cost breakdown per operation',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'provider': {'type': 'string'},
                                'model': {'type': 'string'},
                                'input_tokens': {'type': 'integer'},
                                'output_tokens': {'type': 'integer'},
                                'input_cost': {'type': 'number'},
                                'output_cost': {'type': 'number'},
                                'total_cost': {'type': 'number'},
                                'cost_per_token': {'type': 'number'}
                            }
                        }
                    },
                    'cost_by_provider': {
                        'type': 'object',
                        'description': 'Cost breakdown by provider',
                        'additionalProperties': {'type': 'number'}
                    }
                }
            }
        },
        '400': {
            'description': 'Bad Request - Invalid operations data',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '401': {
            'description': 'Unauthorized',
            'schema': {'$ref': '#/definitions/Error'}
        }
    }
})
def estimate_cost():
    """Estimate costs for planned AI operations"""
    data = request.get_json()

    if not data or 'operations' not in data or not isinstance(data['operations'], list):
        return jsonify({
            'error': 'Invalid request',
            'message': 'Request must contain an "operations" array'
        }), 400

    operations = data['operations']
    if not operations:
        return jsonify({
            'error': 'Empty operations list',
            'message': 'At least one operation must be provided'
        }), 400

    try:
        token_service = TokenTrackingService()

        total_cost = 0.0
        total_tokens = 0
        estimated_operations = []
        cost_by_provider = {}

        for op in operations:
            # Validate required fields
            if not all(key in op for key in ['provider', 'model', 'input_tokens']):
                return jsonify({
                    'error': 'Invalid operation',
                    'message': 'Each operation must have provider, model, and input_tokens'
                }), 400

            provider = op['provider']
            model = op['model']
            input_tokens = op['input_tokens']
            output_tokens = op.get('output_tokens', 0)

            # Validate provider and model
            if provider not in token_service.MODEL_PRICING:
                return jsonify({
                    'error': 'Invalid provider',
                    'message': f'Provider "{provider}" is not supported',
                    'supported_providers': list(token_service.MODEL_PRICING.keys())
                }), 400

            if model not in token_service.MODEL_PRICING[provider]:
                return jsonify({
                    'error': 'Invalid model',
                    'message': f'Model "{model}" is not supported for provider "{provider}"',
                    'supported_models': list(token_service.MODEL_PRICING[provider].keys())
                }), 400

            # Calculate cost for this operation
            cost_info = token_service.estimate_cost(
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )

            operation_total = input_tokens + output_tokens
            total_tokens += operation_total
            total_cost += cost_info['total_cost']

            # Track cost by provider
            provider_key = f"{provider}:{model}"
            if provider_key not in cost_by_provider:
                cost_by_provider[provider_key] = 0.0
            cost_by_provider[provider_key] += cost_info['total_cost']

            estimated_operations.append({
                'provider': provider,
                'model': model,
                'operation': op.get('operation', 'unknown'),
                'description': op.get('description', ''),
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': operation_total,
                'input_cost': cost_info['input_cost'],
                'output_cost': cost_info['output_cost'],
                'total_cost': cost_info['total_cost'],
                'cost_per_token': cost_info['cost_per_token']
            })

        current_app.logger.info(
            f"💡 Cost estimate calculated for tenant {g.tenant_id}: "
            f"{len(operations)} operations, {total_tokens} tokens, ${total_cost:.6f}"
        )

        return jsonify({
            'total_cost': round(total_cost, 6),
            'total_tokens': total_tokens,
            'operations': estimated_operations,
            'cost_by_provider': {k: round(v, 6) for k, v in cost_by_provider.items()},
            'estimate_timestamp': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        current_app.logger.error(f"❌ Error calculating cost estimate: {e}")
        return jsonify({
            'error': 'Cost estimation failed',
            'message': 'An error occurred while calculating the cost estimate'
        }), 500


@api.route('/usage/export', methods=['GET'])
@login_required
@swag_from({
    'tags': ['Usage & Analytics'],
    'summary': 'Export detailed usage report',
    'description': """
    ### 📄 Description
    Exports a comprehensive usage report for the tenant including:
    - Detailed usage statistics
    - Cost breakdowns
    - Usage trends over time
    - Cost optimization recommendations
    - Billing-ready summaries

    Perfect for generating monthly/quarterly reports for billing or analysis.

    ---
    ### 🔑 Authorization
    Requires authentication. Only exports data for user's tenant.
    """,
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'start_date',
            'in': 'query',
            'type': 'string',
            'format': 'date',
            'required': True,
            'description': 'Start date for report (ISO format)',
            'example': '2024-01-01'
        },
        {
            'name': 'end_date',
            'in': 'query',
            'type': 'string',
            'format': 'date',
            'required': True,
            'description': 'End date for report (ISO format)',
            'example': '2024-01-31'
        },
        {
            'name': 'format',
            'in': 'query',
            'type': 'string',
            'enum': ['json', 'csv'],
            'description': 'Export format (default: json)',
            'example': 'json'
        }
    ],
    'responses': {
        '200': {
            'description': 'Usage report exported successfully',
            'schema': {
                'type': 'object',
                'properties': {
                    'report_info': {
                        'type': 'object',
                        'properties': {
                            'tenant_id': {'type': 'integer'},
                            'generated_at': {'type': 'string'},
                            'period': {'type': 'object'},
                            'format': {'type': 'string'}
                        }
                    },
                    'summary': {'type': 'object', 'description': 'Usage summary statistics'},
                    'trends': {'type': 'array', 'description': 'Daily usage trends'},
                    'alerts': {'type': 'array', 'description': 'Cost alerts'},
                    'recommendations': {'type': 'array', 'description': 'Optimization recommendations'}
                }
            }
        },
        '400': {
            'description': 'Bad Request - Invalid date range',
            'schema': {'$ref': '#/definitions/Error'}
        },
        '401': {
            'description': 'Unauthorized',
            'schema': {'$ref': '#/definitions/Error'}
        }
    }
})
def export_usage_report():
    """Export detailed usage report for the tenant"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    export_format = request.args.get('format', 'json').lower()

    if not start_date_str or not end_date_str:
        return jsonify({
            'error': 'Missing date parameters',
            'message': 'Both start_date and end_date are required'
        }), 400

    try:
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
    except ValueError:
        return jsonify({
            'error': 'Invalid date format',
            'message': 'Dates should be in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)'
        }), 400

    if start_date >= end_date:
        return jsonify({
            'error': 'Invalid date range',
            'message': 'Start date must be before end date'
        }), 400

    # Limit report period to avoid very large exports
    max_days = 365  # 1 year max
    if (end_date - start_date).days > max_days:
        return jsonify({
            'error': 'Date range too large',
            'message': f'Maximum report period is {max_days} days'
        }), 400

    try:
        token_service = TokenTrackingService()

        # Generate comprehensive report
        report = token_service.export_usage_report(
            tenant_id=g.tenant_id,
            start_date=start_date,
            end_date=end_date,
            format=export_format
        )

        current_app.logger.info(
            f"📄 Usage report exported for tenant {g.tenant_id}: "
            f"{(end_date - start_date).days} days, format: {export_format}"
        )

        return jsonify(report), 200

    except Exception as e:
        current_app.logger.error(f"❌ Error exporting usage report: {e}")
        return jsonify({
            'error': 'Report export failed',
            'message': 'An error occurred while generating the usage report'
        }), 500
