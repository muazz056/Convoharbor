# app/tasks/notification_tasks.py

import logging
from datetime import datetime, timedelta
from celery import current_task
from .. import db
from ..models.notification import Notification
from ..models.tenant import Tenant
from ..services.notification_service import NotificationService


logger = logging.getLogger(__name__)


def send_notification_task(notification_id: int):
    """Celery task to send a notification"""
    try:
        notification = Notification.query.get(notification_id)
        if not notification:
            logger.error(f"Notification {notification_id} not found")
            return False

        if notification.status != 'pending':
            logger.info(f"Notification {notification_id} already processed (status: {notification.status})")
            return True

        notification_service = NotificationService()

        if notification.type == 'email':
            notification_service._send_email_notification(notification)
        elif notification.type == 'push':
            notification_service._send_push_notification(notification)
        else:
            logger.warning(f"Unknown notification type: {notification.type}")
            return False

        logger.info(f"Successfully processed notification {notification_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to send notification {notification_id}: {str(e)}")

        # Update notification status
        try:
            notification = Notification.query.get(notification_id)
            if notification:
                notification.status = 'failed'
                notification.failed_reason = str(e)
                notification.retry_count += 1
                db.session.commit()
        except Exception:
            pass

        # Retry if not exceeded max retries
        if current_task and hasattr(current_task, 'retry'):
            raise current_task.retry(countdown=60, max_retries=3)

        return False


def send_weekly_reports():
    """Celery task to send weekly reports to users"""
    try:
        logger.info("Starting weekly reports task")

        # Get all tenants with active users
        tenants = Tenant.query.filter_by(is_active=True).all()

        notification_service = NotificationService()
        reports_sent = 0

        for tenant in tenants:
            try:
                # Check if tenant owner wants weekly reports
                if not tenant.owner_id:
                    continue

                prefs = notification_service.get_user_preferences(tenant.id, tenant.owner_id)
                if not prefs or not prefs.weekly_reports:
                    continue

                # Generate weekly report data
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=7)

                # Get basic stats for the week
                from ..models.conversation import Conversation, Message

                conversations_count = Conversation.query.filter(
                    Conversation.tenant_id == tenant.id,
                    Conversation.created_at >= start_date,
                    Conversation.created_at <= end_date
                ).count()

                messages_count = Message.query.join(Conversation).filter(
                    Conversation.tenant_id == tenant.id,
                    Message.created_at >= start_date,
                    Message.created_at <= end_date
                ).count()

                # Create weekly report notification
                title = f"Weekly Report - {tenant.name}"
                message = f"""
Your weekly chatbot activity summary:

📊 This Week's Stats:
• {conversations_count} new conversations
• {messages_count} total messages
• Report period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}

Visit your dashboard for detailed analytics and insights.
                """.strip()

                notification_service.create_notification(
                    tenant_id=tenant.id,
                    user_id=tenant.owner_id,
                    category='weekly_reports',
                    title=title,
                    message=message,
                    notification_type='email' if prefs.email_enabled else 'in_app',
                    data={
                        'conversations_count': conversations_count,
                        'messages_count': messages_count,
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat()
                    }
                )

                reports_sent += 1
                logger.info(f"Weekly report sent to tenant {tenant.id}")

            except Exception as e:
                logger.error(f"Failed to send weekly report to tenant {tenant.id}: {str(e)}")
                continue

        logger.info(f"Weekly reports task completed. Sent {reports_sent} reports.")
        return reports_sent

    except Exception as e:
        logger.error(f"Weekly reports task failed: {str(e)}")
        return 0


def cleanup_old_notifications():
    """Celery task to cleanup old notifications"""
    try:
        logger.info("Starting notification cleanup task")

        # Delete notifications older than 90 days
        cutoff_date = datetime.utcnow() - timedelta(days=90)

        old_notifications = Notification.query.filter(
            Notification.created_at < cutoff_date
        ).all()

        deleted_count = len(old_notifications)

        for notification in old_notifications:
            db.session.delete(notification)

        db.session.commit()

        logger.info(f"Cleanup task completed. Deleted {deleted_count} old notifications.")
        return deleted_count

    except Exception as e:
        db.session.rollback()
        logger.error(f"Notification cleanup task failed: {str(e)}")
        return 0


def retry_failed_notifications():
    """Celery task to retry failed notifications"""
    try:
        logger.info("Starting failed notification retry task")

        # Get failed notifications that haven't exceeded max retries
        failed_notifications = Notification.query.filter(
            Notification.status == 'failed',
            Notification.retry_count < 3,
            Notification.created_at > datetime.utcnow() - timedelta(hours=24)  # Only retry recent failures
        ).all()

        retried_count = 0

        for notification in failed_notifications:
            try:
                # Reset status and queue for retry
                notification.status = 'pending'
                notification.failed_reason = None
                db.session.commit()

                # Queue for delivery
                send_notification_task.delay(notification.id)
                retried_count += 1

            except Exception as e:
                logger.error(f"Failed to retry notification {notification.id}: {str(e)}")
                continue

        logger.info(f"Retry task completed. Queued {retried_count} notifications for retry.")
        return retried_count

    except Exception as e:
        logger.error(f"Failed notification retry task failed: {str(e)}")
        return 0
