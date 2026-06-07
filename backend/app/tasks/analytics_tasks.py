# app/tasks/analytics_tasks.py

import logging
from datetime import datetime
from flask import current_app
from .. import db
from ..models.tenant import Tenant
from ..services.notification_service import NotificationService
from ..services.token_tracking_service import TokenTrackingService


logger = logging.getLogger(__name__)


def check_usage_alerts():
    """Celery task to check usage thresholds and send alerts"""
    try:
        logger.info("Starting usage alerts check task")

        # Get all active tenants
        tenants = Tenant.query.filter_by(is_active=True).all()

        notification_service = NotificationService()
        token_service = TokenTrackingService()
        alerts_sent = 0

        for tenant in tenants:
            try:
                # Check monthly usage
                end_date = datetime.utcnow()
                start_date = end_date.replace(day=1)  # First day of current month

                # Get usage stats
                usage_stats = token_service.get_usage_statistics(
                    tenant_id=tenant.id,
                    start_date=start_date,
                    end_date=end_date
                )

                if not usage_stats:
                    continue

                total_cost = usage_stats.get('total_cost', 0)
                total_tokens = usage_stats.get('total_tokens', 0)

                # Define thresholds (these could be configurable per tenant)
                cost_thresholds = [50, 100, 200, 500]  # USD
                token_thresholds = [100000, 500000, 1000000, 5000000]  # tokens

                # Check cost thresholds
                for threshold in cost_thresholds:
                    if total_cost >= threshold:
                        # Check if we already sent this alert this month
                        existing_alert = db.session.query(
                            db.exists().where(
                                db.and_(
                                    notification_service.Notification.tenant_id == tenant.id,
                                    notification_service.Notification.category == 'usage_alerts',
                                    notification_service.Notification.created_at >= start_date,
                                    notification_service.Notification.data['alert_type'].astext == 'cost_threshold',
                                    notification_service.Notification.data['threshold'].astext == str(threshold)
                                )
                            )
                        ).scalar()

                        if not existing_alert:
                            notification_service.send_usage_alert(
                                tenant_id=tenant.id,
                                alert_type='cost_threshold',
                                current_usage=total_cost,
                                threshold=threshold,
                                period='monthly'
                            )
                            alerts_sent += 1
                            logger.info(f"Cost alert sent to tenant {tenant.id}: ${total_cost:.2f} >= ${threshold}")

                # Check token thresholds
                for threshold in token_thresholds:
                    if total_tokens >= threshold:
                        # Check if we already sent this alert this month
                        existing_alert = db.session.query(
                            db.exists().where(
                                db.and_(
                                    notification_service.Notification.tenant_id == tenant.id,
                                    notification_service.Notification.category == 'usage_alerts',
                                    notification_service.Notification.created_at >= start_date,
                                    notification_service.Notification.data['alert_type'].astext == 'token_threshold',
                                    notification_service.Notification.data['threshold'].astext == str(threshold)
                                )
                            )
                        ).scalar()

                        if not existing_alert:
                            notification_service.send_usage_alert(
                                tenant_id=tenant.id,
                                alert_type='token_threshold',
                                current_usage=total_tokens,
                                threshold=threshold,
                                period='monthly'
                            )
                            alerts_sent += 1
                            logger.info(f"Token alert sent to tenant {tenant.id}: {total_tokens:,} >= {threshold:,}")

            except Exception as e:
                logger.error(f"Failed to check usage alerts for tenant {tenant.id}: {str(e)}")
                continue

        logger.info(f"Usage alerts check completed. Sent {alerts_sent} alerts.")
        return alerts_sent

    except Exception as e:
        logger.error(f"Usage alerts check task failed: {str(e)}")
        return 0


def generate_analytics_export(tenant_id: int, export_params: dict):
    """Celery task to generate analytics export asynchronously"""
    try:
        logger.info(f"Starting analytics export for tenant {tenant_id}")

        from ..api.analytics import get_analytics_overview, get_analytics_timeseries, get_performance_analytics
        from flask import g
        import json
        import csv
        import io

        # Mock Flask context for the task
        app = current_app._get_current_object()

        with app.app_context():
            # Set up mock request context
            g.user_tenant_id = str(tenant_id)  # Convert to string as expected by endpoints

            # Get analytics data
            overview_data = get_analytics_overview()
            timeseries_data = get_analytics_timeseries()
            performance_data = get_performance_analytics()

            # Combine data
            export_data = {
                'tenant_id': tenant_id,
                'generated_at': datetime.utcnow().isoformat(),
                'export_params': export_params,
                'overview': overview_data.get_json() if hasattr(overview_data, 'get_json') else overview_data,
                'timeseries': timeseries_data.get_json() if hasattr(timeseries_data, 'get_json') else timeseries_data,
                'performance': performance_data.get_json() if hasattr(performance_data, 'get_json') else performance_data
            }

            # Generate export file
            export_format = export_params.get('format', 'json')

            if export_format == 'csv':
                # Convert to CSV format
                output = io.StringIO()

                # Write overview data
                writer = csv.writer(output)
                writer.writerow(['Metric', 'Value'])

                if isinstance(export_data['overview'], dict):
                    for key, value in export_data['overview'].items():
                        if isinstance(value, (int, float, str)):
                            writer.writerow([key, value])

                export_content = output.getvalue()
                output.close()

            else:
                # JSON format
                export_content = json.dumps(export_data, indent=2, default=str)

            # Store export result (in a real implementation, this would be saved to S3 or similar)
            # For now, we'll create a notification with the export data
            notification_service = NotificationService()

            notification_service.create_notification(
                tenant_id=tenant_id,
                category='system_updates',
                title='Analytics Export Ready',
                message=f'Your analytics export ({export_format.upper()}) has been generated successfully.',
                notification_type='in_app',
                data={
                    'export_type': 'analytics',
                    'format': export_format,
                    'size': len(export_content),
                    'generated_at': datetime.utcnow().isoformat()
                }
            )

            logger.info(f"Analytics export completed for tenant {tenant_id}")
            return {
                'success': True,
                'tenant_id': tenant_id,
                'format': export_format,
                'size': len(export_content)
            }

    except Exception as e:
        logger.error(f"Analytics export failed for tenant {tenant_id}: {str(e)}")

        # Send failure notification
        try:
            notification_service = NotificationService()
            notification_service.create_notification(
                tenant_id=tenant_id,
                category='system_updates',
                title='Analytics Export Failed',
                message='Your analytics export failed to generate. Please try again or contact support.',
                notification_type='in_app',
                priority='high',
                data={
                    'export_type': 'analytics',
                    'error': str(e),
                    'failed_at': datetime.utcnow().isoformat()
                }
            )
        except Exception:
            pass

        return {
            'success': False,
            'tenant_id': tenant_id,
            'error': str(e)
        }


def cleanup_old_analytics_data():
    """Celery task to cleanup old analytics data"""
    try:
        logger.info("Starting analytics data cleanup task")

        # This would clean up old analytics data, logs, etc.
        # For now, it's a placeholder

        logger.info("Analytics cleanup task completed")
        return True

    except Exception as e:
        logger.error(f"Analytics cleanup task failed: {str(e)}")
        return False
