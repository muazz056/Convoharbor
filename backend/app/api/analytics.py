from flask import jsonify, request, g, current_app
from datetime import datetime, timedelta
from sqlalchemy import func, or_
from app import db
from ..decorators import login_required
from . import api
import logging

# Direct imports
from ..models import Chatbot, Tenant
from ..models.conversation import Conversation, Message, ConversationFeedback

logger = logging.getLogger(__name__)


@api.route('/analytics/overview', methods=['GET'])
@login_required
def get_analytics_overview():
    """
    Get overview analytics for the current tenant
    Query params:
    - chatbot_id (optional): Filter by specific chatbot
    - days (optional): Number of days to look back (default: 30)
    """
    try:
        # Get tenant integer ID
        tenant = Tenant.query.filter_by(tenant_id=g.user_tenant_id).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        tenant_integer_id = tenant.id

        # Get query parameters
        chatbot_id = request.args.get('chatbot_id', type=int)
        days = request.args.get('days', default=30, type=int)

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Base query filters
        base_filters = [
            Conversation.tenant_id == tenant_integer_id,
            Conversation.created_at >= start_date,
            Conversation.status != 'deleted'
        ]

        if chatbot_id:
            base_filters.append(Conversation.chatbot_id == chatbot_id)

        # Total conversations - count distinct to avoid duplicates
        total_conversations = db.session.query(Conversation.id).filter(*base_filters).distinct().count()

        # Active conversations (not archived/inactive)
        active_conversations = db.session.query(Conversation.id).filter(
            *base_filters,
            Conversation.status == 'active'
        ).distinct().count()

        # Total messages - use distinct count to avoid duplicates
        total_messages = db.session.query(Message.id).join(Conversation).filter(*base_filters).distinct().count()
        user_messages = db.session.query(Message.id).join(Conversation).filter(
            *base_filters,
            Message.message_type == 'user'
        ).distinct().count()
        assistant_messages = db.session.query(Message.id).join(Conversation).filter(
            *base_filters,
            Message.message_type == 'assistant'
        ).distinct().count()

        # Average response time
        avg_response_time = db.session.query(func.avg(Message.response_time)).join(Conversation).filter(
            *base_filters,
            Message.message_type == 'assistant',
            Message.response_time.isnot(None)
        ).scalar() or 0

        # Feedback metrics - use distinct count (legacy thumbs up/down system)
        total_feedback = db.session.query(ConversationFeedback.id).join(Conversation).filter(*base_filters).distinct().count()
        positive_feedback = db.session.query(ConversationFeedback.id).join(Conversation).filter(
            *base_filters,
            or_(
                ConversationFeedback.feedback_type == 'thumbs_up',
                ConversationFeedback.rating >= 4
            )
        ).distinct().count()

        # Calculate satisfaction rate from conversation ratings — count UNIQUE conversations with ratings
        # (even though ConversationFeedback stores every submission, we count distinct conversation_ids
        # so the rate stays mathematically consistent)
        rated_subquery = db.session.query(ConversationFeedback.conversation_id).filter(
            ConversationFeedback.feedback_type == 'rating',
            Conversation.status != 'deleted',
            Conversation.tenant_id == tenant_integer_id
        ).join(Conversation, ConversationFeedback.conversation_id == Conversation.id).distinct().subquery()

        all_rated_conversations = db.session.query(rated_subquery.c.conversation_id).distinct().count()

        all_positive_rated_conversations = db.session.query(ConversationFeedback.conversation_id).filter(
            ConversationFeedback.feedback_type == 'rating',
            ConversationFeedback.rating >= 4,
            Conversation.status != 'deleted',
            Conversation.tenant_id == tenant_integer_id
        ).join(Conversation, ConversationFeedback.conversation_id == Conversation.id).distinct().count()

        # Count ALL conversations for this tenant (no date restriction) — used as
        # denominator for satisfaction rate so the rate shows ALL chatbots combined
        all_conversations = db.session.query(Conversation.id).filter(
            Conversation.tenant_id == tenant_integer_id,
            Conversation.status != 'deleted'
        ).distinct().count()

        # Also get date-restricted counts for the period card
        period_rated_subquery = db.session.query(ConversationFeedback.conversation_id).filter(
            ConversationFeedback.feedback_type == 'rating',
            Conversation.created_at >= start_date,
            Conversation.status != 'deleted',
            Conversation.tenant_id == tenant_integer_id
        ).join(Conversation, ConversationFeedback.conversation_id == Conversation.id).distinct().subquery()

        rated_conversations = db.session.query(period_rated_subquery.c.conversation_id).distinct().count()

        positive_rated_conversations = db.session.query(ConversationFeedback.conversation_id).filter(
            ConversationFeedback.feedback_type == 'rating',
            ConversationFeedback.rating >= 4,
            Conversation.created_at >= start_date,
            Conversation.status != 'deleted',
            Conversation.tenant_id == tenant_integer_id
        ).join(Conversation, ConversationFeedback.conversation_id == Conversation.id).distinct().count()

        # Satisfaction rate over ALL conversations (combining all chatbots, all time)
        if all_conversations > 0:
            overall_satisfaction_rate = (all_rated_conversations / all_conversations * 100)
        else:
            overall_satisfaction_rate = 0

        current_app.logger.info(f"📊 Overall satisfaction: {all_rated_conversations}/{all_conversations} = {overall_satisfaction_rate:.1f}% (all-time rated / all-time total)")

        # Get conversation end satisfaction ratings from ConversationFeedback
        conversation_satisfaction_query = db.session.query(
            func.avg(ConversationFeedback.rating).label('avg_rating'),
            func.count(ConversationFeedback.id).label('rating_count')
        ).join(Conversation, ConversationFeedback.conversation_id == Conversation.id).filter(
            Conversation.tenant_id == tenant_integer_id,
            Conversation.status != 'deleted',
            ConversationFeedback.feedback_type == 'rating',
            Conversation.created_at >= start_date
        ).first()

        avg_conversation_rating = float(conversation_satisfaction_query.avg_rating) if conversation_satisfaction_query.avg_rating else 0.0
        conversation_rating_count = conversation_satisfaction_query.rating_count or 0

        # Top chatbots by message count - simplified query first
        top_chatbots_base = db.session.query(
            Chatbot.id,
            Chatbot.name,
            func.count(Message.id).label('message_count')
        ).select_from(Chatbot).join(Conversation).outerjoin(Message).filter(
            Conversation.tenant_id == tenant_integer_id,
            Conversation.created_at >= start_date,
            Conversation.status != 'deleted'
        ).group_by(Chatbot.id, Chatbot.name).order_by(
            func.count(Message.id).desc()
        ).limit(5).all()

        # Calculate satisfaction rates for each chatbot separately
        top_chatbots = []
        for bot in top_chatbots_base:
            # Get satisfaction data for this chatbot from ConversationFeedback (all time)
            satisfaction_data = db.session.query(
                func.count(ConversationFeedback.id).label('rated_submissions'),
                func.avg(ConversationFeedback.rating).label('avg_rating'),
                func.count(func.distinct(ConversationFeedback.conversation_id)).label('rated_conversations')
            ).join(Conversation, ConversationFeedback.conversation_id == Conversation.id).filter(
                Conversation.tenant_id == tenant_integer_id,
                Conversation.chatbot_id == bot.id,
                Conversation.status != 'deleted',
                ConversationFeedback.feedback_type == 'rating'
            ).first()

            # Satisfaction rate uses all_conversations as denominator (same as Feedback page)
            satisfaction_rate = 0
            rated_conversations = satisfaction_data.rated_conversations or 0
            rated_submissions = satisfaction_data.rated_submissions or 0
            avg_rating = float(satisfaction_data.avg_rating) if satisfaction_data.avg_rating else 0.0

            if all_conversations > 0:
                satisfaction_rate = (rated_conversations / all_conversations * 100)

            top_chatbots.append({
                'id': bot.id,
                'name': bot.name,
                'message_count': bot.message_count,
                'satisfaction_rate': round(satisfaction_rate, 1),
                'avg_rating': round(float(satisfaction_data.avg_rating), 2) if satisfaction_data.avg_rating else 0.0,
                'rated_conversations': rated_conversations
            })

        # Platform distribution
        platform_stats = db.session.query(
            Conversation.source_platform,
            func.count(Conversation.id).label('count')
        ).filter(*base_filters).group_by(Conversation.source_platform).all()

        # AI Provider usage
        provider_stats = db.session.query(
            Message.provider,
            func.count(Message.id).label('count')
        ).join(Conversation).filter(
            *base_filters,
            Message.message_type == 'assistant',
            Message.provider.isnot(None)
        ).group_by(Message.provider).all()

        return jsonify({
            'success': True,
            'data': {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'conversations': {
                    'total': total_conversations,
                    'active': active_conversations,
                    'inactive': total_conversations - active_conversations
                },
                'messages': {
                    'total': total_messages,
                    'user': user_messages,
                    'assistant': assistant_messages,
                    'avg_per_conversation': round(total_messages / total_conversations, 2) if total_conversations > 0 else 0
                },
                'performance': {
                    'avg_response_time': round(avg_response_time, 2) if avg_response_time else 0,
                    'satisfaction_rate': round(overall_satisfaction_rate, 1)
                },
                'feedback': {
                    'total': total_feedback,
                    'positive': positive_feedback,
                    'legacy_satisfaction_rate': round((positive_feedback / total_feedback * 100) if total_feedback > 0 else 0, 1),
                    'satisfaction_rate': round(overall_satisfaction_rate, 1),
                    'avg_conversation_rating': round(avg_conversation_rating, 2),
                    'conversation_rating_count': conversation_rating_count,
                    'rated_conversations': all_rated_conversations,
                    'positive_rated_conversations': all_positive_rated_conversations
                },
                'top_chatbots': top_chatbots,
                'platforms': [
                    {
                        'platform': stat.source_platform or 'web',
                        'count': stat.count
                    }
                    for stat in platform_stats
                ],
                'providers': [
                    {
                        'provider': stat.provider,
                        'count': stat.count
                    }
                    for stat in provider_stats
                ]
            }
        })

    except Exception as e:
        logger.error(f"Error getting analytics overview: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get analytics overview'
        }), 500


@api.route('/analytics/timeseries', methods=['GET'])
@login_required
def get_analytics_timeseries():
    """
    Get time-series analytics data
    """
    try:
        # Get tenant integer ID
        tenant = Tenant.query.filter_by(tenant_id=g.user_tenant_id).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        tenant_integer_id = tenant.id

        # Get query parameters
        chatbot_id = request.args.get('chatbot_id', type=int)
        days = request.args.get('days', default=30, type=int)
        granularity = request.args.get('granularity', default='day')

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Base query filters
        base_filters = [
            Conversation.tenant_id == tenant_integer_id,
            Conversation.created_at >= start_date,
            Conversation.status != 'deleted'
        ]

        if chatbot_id:
            base_filters.append(Conversation.chatbot_id == chatbot_id)

        # Determine date truncation based on granularity
        if granularity == 'hour':
            date_trunc = func.date_trunc('hour', Conversation.created_at)
        elif granularity == 'week':
            date_trunc = func.date_trunc('week', Conversation.created_at)
        else:  # day
            date_trunc = func.date_trunc('day', Conversation.created_at)

        # Conversations over time - use distinct count
        conversations_timeseries = db.session.query(
            date_trunc.label('period'),
            func.count(func.distinct(Conversation.id)).label('count')
        ).filter(*base_filters).group_by('period').order_by('period').all()

        # Messages over time - use distinct count
        messages_timeseries = db.session.query(
            func.date_trunc(granularity, Message.created_at).label('period'),
            func.count(func.distinct(Message.id)).label('count')
        ).join(Conversation).filter(*base_filters).group_by('period').order_by('period').all()

        # Response times over time
        response_times = db.session.query(
            func.date_trunc(granularity, Message.created_at).label('period'),
            func.avg(Message.response_time).label('avg_response_time')
        ).join(Conversation).filter(
            *base_filters,
            Message.message_type == 'assistant',
            Message.response_time.isnot(None)
        ).group_by('period').order_by('period').all()

        # Debug: Log response time data to help diagnose empty graph
        current_app.logger.info(f"📊 Response time debug: Found {len(response_times)} data points for tenant {tenant_integer_id}")
        if not response_times:
            # Check if we have any messages with response times
            total_messages = db.session.query(Message).join(Conversation).filter(
                *base_filters,
                Message.message_type == 'assistant'
            ).count()

            messages_with_times = db.session.query(Message).join(Conversation).filter(
                *base_filters,
                Message.message_type == 'assistant',
                Message.response_time.isnot(None)
            ).count()

            current_app.logger.warning(
                f"⚠️ No response time data found. Total assistant messages: {total_messages}, "
                f"Messages with response times: {messages_with_times}"
            )
        else:
            for rt in response_times[:3]:  # Log first 3 entries
                current_app.logger.info(f"📊 Sample data - Period: {rt.period}, Avg Response: {rt.avg_response_time:.2f}s")

        return jsonify({
            'success': True,
            'data': {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'granularity': granularity
                },
                'conversations': [
                    {
                        'period': conv.period.isoformat(),
                        'count': conv.count
                    }
                    for conv in conversations_timeseries
                ],
                'messages': [
                    {
                        'period': msg.period.isoformat(),
                        'count': msg.count
                    }
                    for msg in messages_timeseries
                ],
                'response_times': [
                    {
                        'period': rt.period.isoformat(),
                        'avg_response_time': round(rt.avg_response_time, 2) if rt.avg_response_time else 0
                    }
                    for rt in response_times
                ]
            }
        })

    except Exception as e:
        logger.error(f"Error getting timeseries analytics: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get timeseries analytics'
        }), 500


@api.route('/analytics/performance', methods=['GET'])
@login_required
def get_performance_analytics():
    """
    Get detailed performance analytics
    """
    try:
        # Get tenant integer ID
        tenant = Tenant.query.filter_by(tenant_id=g.user_tenant_id).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        tenant_integer_id = tenant.id

        chatbot_id = request.args.get('chatbot_id', type=int)
        days = request.args.get('days', default=30, type=int)

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Base query filters
        base_filters = [
            Conversation.tenant_id == tenant_integer_id,
            Conversation.created_at >= start_date,
            Conversation.status != 'deleted'
        ]

        if chatbot_id:
            base_filters.append(Conversation.chatbot_id == chatbot_id)

        # Response time statistics by provider
        provider_performance = db.session.query(
            Message.provider,
            func.avg(Message.response_time).label('avg_response_time'),
            func.min(Message.response_time).label('min_response_time'),
            func.max(Message.response_time).label('max_response_time'),
            func.count(Message.id).label('message_count')
        ).join(Conversation).filter(
            *base_filters,
            Message.message_type == 'assistant',
            Message.response_time.isnot(None)
        ).group_by(Message.provider).all()

        # Token usage by provider
        token_usage = db.session.query(
            Message.provider,
            func.sum(Message.token_count).label('total_tokens'),
            func.avg(Message.token_count).label('avg_tokens'),
            func.count(Message.id).label('message_count')
        ).join(Conversation).filter(
            *base_filters,
            Message.message_type == 'assistant',
            Message.token_count.isnot(None)
        ).group_by(Message.provider).all()

        # Model usage statistics
        model_usage = db.session.query(
            Message.model_used,
            Message.provider,
            func.count(Message.id).label('usage_count'),
            func.avg(Message.response_time).label('avg_response_time')
        ).join(Conversation).filter(
            *base_filters,
            Message.message_type == 'assistant',
            Message.model_used.isnot(None)
        ).group_by(Message.model_used, Message.provider).order_by(
            func.count(Message.id).desc()
        ).all()

        return jsonify({
            'success': True,
            'data': {
                'provider_performance': [
                    {
                        'provider': perf.provider,
                        'avg_response_time': round(perf.avg_response_time, 2) if perf.avg_response_time else 0,
                        'min_response_time': round(perf.min_response_time, 2) if perf.min_response_time else 0,
                        'max_response_time': round(perf.max_response_time, 2) if perf.max_response_time else 0,
                        'message_count': perf.message_count
                    }
                    for perf in provider_performance
                ],
                'token_usage': [
                    {
                        'provider': usage.provider,
                        'total_tokens': usage.total_tokens or 0,
                        'avg_tokens': round(usage.avg_tokens, 2) if usage.avg_tokens else 0,
                        'message_count': usage.message_count
                    }
                    for usage in token_usage
                ],
                'model_usage': [
                    {
                        'model': usage.model_used,
                        'provider': usage.provider,
                        'usage_count': usage.usage_count,
                        'avg_response_time': round(usage.avg_response_time, 2) if usage.avg_response_time else 0
                    }
                    for usage in model_usage
                ]
            }
        })

    except Exception as e:
        logger.error(f"Error getting performance analytics: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get performance analytics'
        }), 500


@api.route('/health/live', methods=['GET'])
def health_live():
    """Liveness probe - basic health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'convopilot-api'
    })


@api.route('/health/ready', methods=['GET'])
def health_ready():
    """Readiness probe - check database connectivity"""
    try:
        # Simple database check
        db.session.execute('SELECT 1')
        return jsonify({
            'status': 'ready',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'convopilot-api',
            'checks': {
                'database': 'healthy'
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'not_ready',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'convopilot-api',
            'checks': {
                'database': 'unhealthy'
            },
            'error': str(e)
        }), 503


@api.route('/analytics/export', methods=['POST'])
@login_required
def export_analytics():
    """Export analytics data asynchronously"""
    try:
        # Convert tenant UUID to integer ID
        tenant = Tenant.query.filter_by(tenant_id=g.user_tenant_id).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404

        tenant_id = tenant.id

        # Get export parameters
        data = request.get_json() or {}
        export_params = {
            'format': data.get('format', 'json'),  # json, csv
            'days': int(data.get('days', 30)),
            'include_timeseries': data.get('include_timeseries', True),
            'include_performance': data.get('include_performance', True),
            'chatbot_id': data.get('chatbot_id')
        }

        # Validate format
        if export_params['format'] not in ['json', 'csv']:
            return jsonify({'error': 'Invalid format. Supported formats: json, csv'}), 400

        # Queue export task
        try:
            from ..tasks.analytics_tasks import generate_analytics_export
            task = generate_analytics_export.delay(tenant_id, export_params)

            return jsonify({
                'message': 'Analytics export queued successfully',
                'task_id': task.id,
                'export_params': export_params,
                'estimated_completion': '2-5 minutes'
            })

        except ImportError:
            # Fallback if Celery not available - generate immediately
            from flask import current_app
            current_app.logger.warning("Celery not available, generating export synchronously")

            # Generate export data immediately
            overview_response = get_analytics_overview()
            timeseries_response = get_analytics_timeseries() if export_params['include_timeseries'] else None
            performance_response = get_performance_analytics() if export_params['include_performance'] else None

            export_data = {
                'tenant_id': tenant_id,
                'generated_at': datetime.utcnow().isoformat(),
                'export_params': export_params,
                'overview': overview_response.get_json() if hasattr(overview_response, 'get_json') else overview_response[0],
                'timeseries': timeseries_response.get_json() if timeseries_response and hasattr(timeseries_response, 'get_json') else (timeseries_response[0] if timeseries_response else None),
                'performance': performance_response.get_json() if performance_response and hasattr(performance_response, 'get_json') else (performance_response[0] if performance_response else None)
            }

            if export_params['format'] == 'csv':
                # Convert to CSV format
                import csv
                import io

                output = io.StringIO()
                writer = csv.writer(output)

                # Write headers
                writer.writerow(['Metric', 'Value', 'Category'])

                # Write overview data
                if export_data['overview']:
                    for key, value in export_data['overview'].items():
                        if isinstance(value, (int, float, str)):
                            writer.writerow([key, value, 'overview'])

                export_content = output.getvalue()
                output.close()

                return jsonify({
                    'message': 'Analytics export generated successfully',
                    'format': 'csv',
                    'data': export_content,
                    'size': len(export_content)
                })
            else:
                # JSON format
                return jsonify({
                    'message': 'Analytics export generated successfully',
                    'format': 'json',
                    'data': export_data
                })

    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Failed to export analytics: {str(e)}")
        return jsonify({'error': 'Failed to export analytics data'}), 500
