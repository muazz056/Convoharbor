# app/services/notification_service.py

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from flask import current_app
from flask_mail import Message
from .. import db, mail
from ..models.notification import Notification, NotificationPreference
from ..models.tenant import Tenant
from ..models import User


class NotificationService:
    """Service for managing notifications across the platform"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def create_notification(
        self,
        tenant_id: int,
        category: str,
        title: str,
        message: str,
        notification_type: str = 'in_app',
        user_id: Optional[int] = None,
        chatbot_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        priority: str = 'normal',
        data: Optional[Dict] = None
    ) -> Notification:
        """Create a new notification"""
        try:
            notification = Notification(
                tenant_id=tenant_id,
                user_id=user_id,
                chatbot_id=chatbot_id,
                conversation_id=conversation_id,
                type=notification_type,
                category=category,
                priority=priority,
                title=title,
                message=message,
                data=data or {}
            )

            db.session.add(notification)
            db.session.commit()

            self.logger.info(f"Created notification {notification.id} for tenant {tenant_id}")

            # Queue for delivery if not in_app
            if notification_type != 'in_app':
                self._queue_notification_delivery(notification.id)

            return notification

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to create notification: {str(e)}")
            raise

    def send_conversation_started_notification(
        self,
        tenant_id: int,
        chatbot_id: int,
        conversation_id: int,
        source_domain: Optional[str] = None
    ):
        """Send notification when a new conversation starts"""
        try:
            # Get chatbot info
            from ..models.chatbot import Chatbot
            chatbot = Chatbot.query.filter_by(id=chatbot_id, tenant_id=tenant_id).first()
            if not chatbot:
                return

            title = f"New conversation started on {chatbot.name}"
            message = f"A new conversation has started on your chatbot '{chatbot.name}'"

            if source_domain:
                message += f" from {source_domain}"

            # Create in-app notification
            self.create_notification(
                tenant_id=tenant_id,
                category='conversation_started',
                title=title,
                message=message,
                notification_type='in_app',
                chatbot_id=chatbot_id,
                conversation_id=conversation_id,
                data={
                    'chatbot_name': chatbot.name,
                    'source_domain': source_domain,
                    'conversation_id': conversation_id
                }
            )

            # Check if user wants email notifications
            tenant = Tenant.query.get(tenant_id)
            if tenant and tenant.owner_id:
                prefs = self.get_user_preferences(tenant_id, tenant.owner_id)
                if prefs and prefs.conversation_started and prefs.email_enabled:
                    self.create_notification(
                        tenant_id=tenant_id,
                        user_id=tenant.owner_id,
                        category='conversation_started',
                        title=title,
                        message=message,
                        notification_type='email',
                        chatbot_id=chatbot_id,
                        conversation_id=conversation_id,
                        data={
                            'chatbot_name': chatbot.name,
                            'source_domain': source_domain,
                            'conversation_id': conversation_id
                        }
                    )

        except Exception as e:
            self.logger.error(f"Failed to send conversation started notification: {str(e)}")

    def send_feedback_notification(
        self,
        tenant_id: int,
        chatbot_id: int,
        conversation_id: int,
        feedback_type: str,
        rating: Optional[int] = None
    ):
        """Send notification when feedback is received"""
        try:
            from ..models.chatbot import Chatbot
            chatbot = Chatbot.query.filter_by(id=chatbot_id, tenant_id=tenant_id).first()
            if not chatbot:
                return

            title = f"New feedback received for {chatbot.name}"

            if feedback_type == 'thumbs_up':
                message = f"Positive feedback received for your chatbot '{chatbot.name}'"
            elif feedback_type == 'thumbs_down':
                message = f"Negative feedback received for your chatbot '{chatbot.name}'"
            elif rating:
                message = f"Rating of {rating}/5 received for your chatbot '{chatbot.name}'"
            else:
                message = f"Feedback received for your chatbot '{chatbot.name}'"

            self.create_notification(
                tenant_id=tenant_id,
                category='feedback_received',
                title=title,
                message=message,
                notification_type='in_app',
                chatbot_id=chatbot_id,
                conversation_id=conversation_id,
                priority='high' if feedback_type == 'thumbs_down' else 'normal',
                data={
                    'chatbot_name': chatbot.name,
                    'feedback_type': feedback_type,
                    'rating': rating,
                    'conversation_id': conversation_id
                }
            )

        except Exception as e:
            self.logger.error(f"Failed to send feedback notification: {str(e)}")

    def send_usage_alert(
        self,
        tenant_id: int,
        alert_type: str,
        current_usage: float,
        threshold: float,
        period: str = 'monthly'
    ):
        """Send usage alert notifications"""
        try:
            if alert_type == 'cost_threshold':
                title = f"Cost Alert: {period.title()} usage threshold reached"
                message = f"Your {period} AI usage cost has reached ${current_usage:.2f} (threshold: ${threshold:.2f})"
                priority = 'high' if current_usage > threshold * 1.2 else 'normal'
            elif alert_type == 'token_threshold':
                title = f"Token Alert: {period.title()} usage threshold reached"
                message = f"Your {period} token usage has reached {current_usage:,.0f} tokens (threshold: {threshold:,.0f})"
                priority = 'high' if current_usage > threshold * 1.2 else 'normal'
            else:
                title = f"Usage Alert: {alert_type}"
                message = f"Usage alert triggered for {alert_type}"
                priority = 'normal'

            self.create_notification(
                tenant_id=tenant_id,
                category='usage_alerts',
                title=title,
                message=message,
                notification_type='in_app',
                priority=priority,
                data={
                    'alert_type': alert_type,
                    'current_usage': current_usage,
                    'threshold': threshold,
                    'period': period
                }
            )

            # Also send email for high priority alerts
            if priority == 'high':
                tenant = Tenant.query.get(tenant_id)
                if tenant and tenant.owner_id:
                    prefs = self.get_user_preferences(tenant_id, tenant.owner_id)
                    if prefs and prefs.usage_alerts and prefs.email_enabled:
                        self.create_notification(
                            tenant_id=tenant_id,
                            user_id=tenant.owner_id,
                            category='usage_alerts',
                            title=title,
                            message=message,
                            notification_type='email',
                            priority=priority,
                            data={
                                'alert_type': alert_type,
                                'current_usage': current_usage,
                                'threshold': threshold,
                                'period': period
                            }
                        )

        except Exception as e:
            self.logger.error(f"Failed to send usage alert: {str(e)}")

    def get_user_notifications(
        self,
        tenant_id: int,
        user_id: Optional[int] = None,
        limit: int = 50,
        unread_only: bool = False
    ) -> List[Notification]:
        """Get notifications for a user or tenant"""
        try:
            query = Notification.query.filter_by(tenant_id=tenant_id)

            if user_id:
                # Get notifications for specific user or system-wide notifications
                query = query.filter(
                    (Notification.user_id == user_id) | (Notification.user_id.is_(None))
                )

            if unread_only:
                query = query.filter(Notification.read_at.is_(None))

            notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()
            return notifications

        except Exception as e:
            self.logger.error(f"Failed to get user notifications: {str(e)}")
            return []

    def mark_as_read(self, notification_id: int, tenant_id: int) -> bool:
        """Mark a notification as read"""
        try:
            notification = Notification.query.filter_by(
                id=notification_id,
                tenant_id=tenant_id
            ).first()

            if notification and not notification.read_at:
                notification.read_at = datetime.utcnow()
                notification.status = 'read'
                db.session.commit()
                return True

            return False

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to mark notification as read: {str(e)}")
            return False

    def get_user_preferences(self, tenant_id: int, user_id: int) -> Optional[NotificationPreference]:
        """Get user notification preferences"""
        try:
            prefs = NotificationPreference.query.filter_by(
                tenant_id=tenant_id,
                user_id=user_id
            ).first()

            # Create default preferences if none exist
            if not prefs:
                prefs = NotificationPreference(
                    tenant_id=tenant_id,
                    user_id=user_id
                )
                db.session.add(prefs)
                db.session.commit()

            return prefs

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to get user preferences: {str(e)}")
            return None

    def update_user_preferences(
        self,
        tenant_id: int,
        user_id: int,
        preferences: Dict[str, Any]
    ) -> bool:
        """Update user notification preferences"""
        try:
            prefs = self.get_user_preferences(tenant_id, user_id)
            if not prefs:
                return False

            # Update preferences
            for key, value in preferences.items():
                if hasattr(prefs, key):
                    setattr(prefs, key, value)

            prefs.updated_at = datetime.utcnow()
            db.session.commit()
            return True

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to update user preferences: {str(e)}")
            return False

    def _queue_notification_delivery(self, notification_id: int):
        """Queue notification for delivery (placeholder for Celery task)"""
        # This will be implemented with Celery tasks
        try:
            from ..tasks.notification_tasks import send_notification_task
            send_notification_task.delay(notification_id)
        except ImportError:
            # Fallback to immediate delivery if Celery not available
            self._deliver_notification_now(notification_id)

    def _deliver_notification_now(self, notification_id: int):
        """Deliver notification immediately (fallback)"""
        try:
            notification = Notification.query.get(notification_id)
            if not notification:
                return

            if notification.type == 'email':
                self._send_email_notification(notification)
            elif notification.type == 'push':
                self._send_push_notification(notification)

        except Exception as e:
            self.logger.error(f"Failed to deliver notification {notification_id}: {str(e)}")

    def _send_email_notification(self, notification: Notification):
        """Send email notification"""
        try:
            if not notification.user_id:
                return

            user = User.query.get(notification.user_id)
            if not user or not user.email:
                return

            msg = Message(
                subject=notification.title,
                recipients=[user.email],
                body=notification.message,
                sender=current_app.config.get('MAIL_DEFAULT_SENDER')
            )

            mail.send(msg)

            notification.status = 'sent'
            notification.sent_at = datetime.utcnow()
            db.session.commit()

            self.logger.info(f"Email notification {notification.id} sent to {user.email}")

        except Exception as e:
            notification.status = 'failed'
            notification.failed_reason = str(e)
            notification.retry_count += 1
            db.session.commit()
            self.logger.error(f"Failed to send email notification {notification.id}: {str(e)}")

    def _send_push_notification(self, notification: Notification):
        """Send push notification (placeholder)"""
        # This would integrate with a push notification service like FCM
        self.logger.info(f"Push notification {notification.id} queued (not implemented)")
        notification.status = 'sent'
        notification.sent_at = datetime.utcnow()
        db.session.commit()
