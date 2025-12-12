# app/services/token_tracking_service.py

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from flask import current_app
from sqlalchemy import func, and_, or_
from ..models import TokenUsage
from .. import db
from ..models.datasource import DataSource


class TokenTrackingService:
    """
    Service for tracking token usage and calculating costs across all AI operations
    """
    
    # Model pricing per 1K tokens (as of 2024)
    MODEL_PRICING = {
        'openai': {
            'gpt-4o': {'input': 0.005, 'output': 0.015},
            'gpt-4o-mini': {'input': 0.00015, 'output': 0.0006},
            'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
            'gpt-3.5-turbo': {'input': 0.001, 'output': 0.002},
            'text-embedding-3-small': {'input': 0.00002, 'output': 0.0},
            'text-embedding-3-large': {'input': 0.00013, 'output': 0.0},
            'text-embedding-ada-002': {'input': 0.0001, 'output': 0.0}
        },
        'gemini': {
            'gemini-1.5-pro': {'input': 0.00125, 'output': 0.005},
            'gemini-1.5-flash-latest': {'input': 0.000075, 'output': 0.0003},
            'gemini-1.5-flash': {'input': 0.000075, 'output': 0.0003},
            'gemini-pro': {'input': 0.0005, 'output': 0.0015},
            'embedding-001': {'input': 0.00001, 'output': 0.0}
        }
    }
    
    def __init__(self):
        """Initialize token tracking service"""
        current_app.logger.info("💰 TokenTrackingService initialized")
    
    def track_usage(self, 
                   tenant_id: int,
                   provider: str,
                   model: str,
                   operation: str,
                   input_tokens: int = 0,
                   output_tokens: int = 0,
                   chatbot_id: Optional[int] = None,
                   request_id: Optional[str] = None,
                   session_id: Optional[str] = None,
                   data_source_id: Optional[int] = None,
                   metadata: Optional[Dict] = None) -> TokenUsage:
        """
        Track token usage for a specific operation
        
        Args:
            tenant_id: ID of the tenant
            provider: AI provider ('openai', 'gemini')
            model: Specific model used
            operation: Type of operation ('query', 'embedding', 'processing')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            chatbot_id: Optional chatbot ID
            request_id: Optional request tracking ID
            session_id: Optional conversation session ID
            data_source_id: Optional data source ID for processing operations
            metadata: Optional additional metadata
            
        Returns:
            TokenUsage record created
        """
        try:
            total_tokens = input_tokens + output_tokens
            
            # Calculate costs
            input_cost, output_cost, total_cost = self._calculate_costs(
                provider, model, input_tokens, output_tokens
            )
            
            # Create usage record
            usage = TokenUsage(
                tenant_id=tenant_id,
                chatbot_id=chatbot_id,
                provider=provider,
                model=model,
                operation=operation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                input_cost=input_cost,
                output_cost=output_cost,
                total_cost=total_cost,
                request_id=request_id,
                session_id=session_id,
                data_source_id=data_source_id,
                meta_data=metadata or {}
            )
            
            db.session.add(usage)
            db.session.commit()
            
            current_app.logger.info(
                f"💰 Token usage tracked: {total_tokens} tokens "
                f"(${total_cost:.6f}) for tenant {tenant_id}"
            )
            
            return usage
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"❌ Error tracking token usage: {e}")
            raise e
    
    def get_tenant_usage(self, 
                        tenant_id: int,
                        start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None,
                        chatbot_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get usage statistics for a tenant
        
        Args:
            tenant_id: Tenant ID
            start_date: Start date for filtering (default: last 30 days)
            end_date: End date for filtering (default: now)
            chatbot_id: Optional filter by specific chatbot
            
        Returns:
            Usage statistics dictionary
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # Base query
        query = TokenUsage.query.filter(
            TokenUsage.tenant_id == tenant_id,
            TokenUsage.created_at >= start_date,
            TokenUsage.created_at <= end_date
        )
        
        if chatbot_id:
            query = query.filter(TokenUsage.chatbot_id == chatbot_id)
        
        # Get all usage records
        usage_records = query.all()
        
        if not usage_records:
            return {
                'tenant_id': tenant_id,
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'total_tokens': 0,
                'total_cost': 0.0,
                'usage_by_provider': {},
                'usage_by_operation': {},
                'usage_by_chatbot': {},
                'daily_usage': []
            }
        
        # Aggregate data
        total_tokens = sum(record.total_tokens for record in usage_records)
        total_cost = sum(float(record.total_cost) for record in usage_records)
        
        # Usage by provider
        usage_by_provider = {}
        for record in usage_records:
            key = f"{record.provider}:{record.model}"
            if key not in usage_by_provider:
                usage_by_provider[key] = {
                    'tokens': 0,
                    'cost': 0.0,
                    'requests': 0
                }
            usage_by_provider[key]['tokens'] += record.total_tokens
            usage_by_provider[key]['cost'] += float(record.total_cost)
            usage_by_provider[key]['requests'] += 1
        
        # Usage by operation
        usage_by_operation = {}
        for record in usage_records:
            op = record.operation
            if op not in usage_by_operation:
                usage_by_operation[op] = {
                    'tokens': 0,
                    'cost': 0.0,
                    'requests': 0
                }
            usage_by_operation[op]['tokens'] += record.total_tokens
            usage_by_operation[op]['cost'] += float(record.total_cost)
            usage_by_operation[op]['requests'] += 1
        
        # Usage by chatbot
        usage_by_chatbot = {}
        for record in usage_records:
            bot_id = record.chatbot_id or 'unassigned'
            if bot_id not in usage_by_chatbot:
                usage_by_chatbot[bot_id] = {
                    'tokens': 0,
                    'cost': 0.0,
                    'requests': 0
                }
            usage_by_chatbot[bot_id]['tokens'] += record.total_tokens
            usage_by_chatbot[bot_id]['cost'] += float(record.total_cost)
            usage_by_chatbot[bot_id]['requests'] += 1
        
        # Daily usage breakdown
        daily_usage = {}
        for record in usage_records:
            day = record.created_at.date().isoformat()
            if day not in daily_usage:
                daily_usage[day] = {
                    'tokens': 0,
                    'cost': 0.0,
                    'requests': 0
                }
            daily_usage[day]['tokens'] += record.total_tokens
            daily_usage[day]['cost'] += float(record.total_cost)
            daily_usage[day]['requests'] += 1
        
        return {
            'tenant_id': tenant_id,
            'chatbot_id': chatbot_id,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_tokens': total_tokens,
            'total_cost': round(total_cost, 6),
            'usage_by_provider': usage_by_provider,
            'usage_by_operation': usage_by_operation,
            'usage_by_chatbot': usage_by_chatbot,
            'daily_usage': dict(sorted(daily_usage.items()))
        }
    
    def get_usage_trends(self, 
                        tenant_id: int,
                        days: int = 30) -> List[Dict[str, Any]]:
        """
        Get usage trends over time for a tenant
        
        Args:
            tenant_id: Tenant ID
            days: Number of days to analyze (default: 30)
            
        Returns:
            List of daily usage data points
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Query usage by day
        daily_stats = db.session.query(
            func.date(TokenUsage.created_at).label('date'),
            func.sum(TokenUsage.total_tokens).label('total_tokens'),
            func.sum(TokenUsage.total_cost).label('total_cost'),
            func.count(TokenUsage.id).label('requests')
        ).filter(
            TokenUsage.tenant_id == tenant_id,
            TokenUsage.created_at >= start_date,
            TokenUsage.created_at <= end_date
        ).group_by(
            func.date(TokenUsage.created_at)
        ).order_by('date').all()
        
        # Fill in missing days with zero values
        trends = []
        current_date = start_date.date()
        stats_dict = {stat.date: stat for stat in daily_stats}
        
        while current_date <= end_date.date():
            stat = stats_dict.get(current_date)
            
            trends.append({
                'date': current_date.isoformat(),
                'tokens': int(stat.total_tokens) if stat else 0,
                'cost': float(stat.total_cost) if stat else 0.0,
                'requests': int(stat.requests) if stat else 0
            })
            
            current_date += timedelta(days=1)
        
        return trends
    
    def estimate_cost(self, 
                     provider: str,
                     model: str,
                     input_tokens: int,
                     output_tokens: int) -> Dict[str, float]:
        """
        Estimate cost for a given token usage
        
        Args:
            provider: AI provider
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Cost breakdown dictionary
        """
        input_cost, output_cost, total_cost = self._calculate_costs(
            provider, model, input_tokens, output_tokens
        )
        
        return {
            'input_cost': float(input_cost),
            'output_cost': float(output_cost),
            'total_cost': float(total_cost),
            'cost_per_token': float(total_cost) / (input_tokens + output_tokens) if (input_tokens + output_tokens) > 0 else 0.0
        }
    
    def get_cost_alerts(self, tenant_id: int) -> List[Dict[str, Any]]:
        """
        Check for cost threshold alerts
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            List of cost alerts
        """
        alerts = []
        
        # Get current month usage
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        monthly_usage = self.get_tenant_usage(tenant_id, month_start, now)
        monthly_cost = monthly_usage['total_cost']
        
        # Example thresholds (in production, these would be configurable per tenant)
        thresholds = [
            {'level': 'info', 'amount': 10.0, 'message': 'Monthly usage has exceeded $10'},
            {'level': 'warning', 'amount': 50.0, 'message': 'Monthly usage has exceeded $50'},
            {'level': 'critical', 'amount': 100.0, 'message': 'Monthly usage has exceeded $100'}
        ]
        
        for threshold in thresholds:
            if monthly_cost >= threshold['amount']:
                alerts.append({
                    'level': threshold['level'],
                    'message': threshold['message'],
                    'current_cost': monthly_cost,
                    'threshold': threshold['amount'],
                    'period': 'monthly'
                })
        
        # Daily usage alerts
        yesterday = now - timedelta(days=1)
        daily_usage = self.get_tenant_usage(tenant_id, yesterday, now)
        daily_cost = daily_usage['total_cost']
        
        if daily_cost >= 10.0:  # $10 per day alert
            alerts.append({
                'level': 'warning',
                'message': f'Daily usage on {yesterday.date()} exceeded $10',
                'current_cost': daily_cost,
                'threshold': 10.0,
                'period': 'daily'
            })
        
        return alerts
    
    def _calculate_costs(self, 
                        provider: str,
                        model: str,
                        input_tokens: int,
                        output_tokens: int) -> tuple[float, float, float]:
        """
        Calculate costs for token usage
        
        Args:
            provider: AI provider
            model: Model name
            input_tokens: Input token count
            output_tokens: Output token count
            
        Returns:
            Tuple of (input_cost, output_cost, total_cost)
        """
        try:
            # Get pricing for provider/model
            provider_pricing = self.MODEL_PRICING.get(provider.lower(), {})
            model_pricing = provider_pricing.get(model, {})
            
            if not model_pricing:
                current_app.logger.warning(
                    f"⚠️ No pricing found for {provider}:{model}, using default rates"
                )
                # Default fallback pricing
                model_pricing = {'input': 0.001, 'output': 0.002}
            
            # Calculate costs (pricing is per 1K tokens)
            input_cost = (input_tokens / 1000.0) * model_pricing.get('input', 0.0)
            output_cost = (output_tokens / 1000.0) * model_pricing.get('output', 0.0)
            total_cost = input_cost + output_cost
            
            return input_cost, output_cost, total_cost
            
        except Exception as e:
            current_app.logger.error(f"❌ Error calculating costs: {e}")
            return 0.0, 0.0, 0.0
    
    def cleanup_old_records(self, days_to_keep: int = 90):
        """
        Clean up old token usage records to manage database size
        
        Args:
            days_to_keep: Number of days of records to retain
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            deleted_count = TokenUsage.query.filter(
                TokenUsage.created_at < cutoff_date
            ).delete()
            
            db.session.commit()
            
            current_app.logger.info(
                f"🧹 Cleaned up {deleted_count} token usage records older than {days_to_keep} days"
            )
            
            return deleted_count
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"❌ Error cleaning up token usage records: {e}")
            raise e
    
    def export_usage_report(self, 
                           tenant_id: int,
                           start_date: datetime,
                           end_date: datetime,
                           format: str = 'json') -> Dict[str, Any]:
        """
        Export detailed usage report for a tenant
        
        Args:
            tenant_id: Tenant ID
            start_date: Report start date
            end_date: Report end date
            format: Export format ('json', 'csv')
            
        Returns:
            Formatted usage report
        """
        usage_data = self.get_tenant_usage(tenant_id, start_date, end_date)
        trends = self.get_usage_trends(tenant_id, (end_date - start_date).days)
        alerts = self.get_cost_alerts(tenant_id)
        
        report = {
            'report_info': {
                'tenant_id': tenant_id,
                'generated_at': datetime.utcnow().isoformat(),
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'format': format
            },
            'summary': usage_data,
            'trends': trends,
            'alerts': alerts,
            'recommendations': self._generate_cost_recommendations(usage_data)
        }
        
        return report
    
    def _generate_cost_recommendations(self, usage_data: Dict[str, Any]) -> List[str]:
        """Generate cost optimization recommendations"""
        recommendations = []
        
        total_cost = usage_data['total_cost']
        usage_by_provider = usage_data['usage_by_provider']
        usage_by_operation = usage_data['usage_by_operation']
        
        # High usage recommendations
        if total_cost > 50:
            recommendations.append(
                "Consider implementing response caching to reduce repeated queries"
            )
        
        # Model optimization
        for provider_model, data in usage_by_provider.items():
            if 'gpt-4' in provider_model and data['cost'] > 20:
                recommendations.append(
                    f"Consider using GPT-4o-mini instead of {provider_model} for simpler queries to reduce costs"
                )
        
        # Operation optimization
        if 'query' in usage_by_operation and usage_by_operation['query']['cost'] > 30:
            recommendations.append(
                "High query costs detected - consider optimizing prompts and using lower temperature settings"
            )
        
        if not recommendations:
            recommendations.append("Usage is within optimal ranges - no specific recommendations at this time")
        
        return recommendations
