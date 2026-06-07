# app/models/notification.py

from datetime import datetime
from .. import db


class NotificationTemplate(db.Model):
    """Template for different types of notifications"""
    __tablename__ = 'notification_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    type = db.Column(db.String(50), nullable=False)  # email, push, in_app
    subject_template = db.Column(db.String(200))
    body_template = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'subject_template': self.subject_template,
            'body_template': self.body_template,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Notification(db.Model):
    """Individual notification instances"""
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # null for system notifications
    chatbot_id = db.Column(db.Integer, db.ForeignKey('chatbots.id'), nullable=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=True)

    type = db.Column(db.String(50), nullable=False)  # email, push, in_app
    category = db.Column(db.String(50), nullable=False)  # conversation_started, feedback_received, usage_alert, etc.
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, urgent

    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    data = db.Column(db.JSON)  # Additional data for the notification

    # Status tracking
    status = db.Column(db.String(20), default='pending')  # pending, sent, failed, read
    sent_at = db.Column(db.DateTime)
    read_at = db.Column(db.DateTime)
    failed_reason = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref='notifications')
    user = db.relationship('User', backref='notifications')
    chatbot = db.relationship('Chatbot', backref='notifications')
    conversation = db.relationship('Conversation', backref='notifications')

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'chatbot_id': self.chatbot_id,
            'conversation_id': self.conversation_id,
            'type': self.type,
            'category': self.category,
            'priority': self.priority,
            'title': self.title,
            'message': self.message,
            'data': self.data,
            'status': self.status,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'failed_reason': self.failed_reason,
            'retry_count': self.retry_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class NotificationPreference(db.Model):
    """User preferences for notifications"""
    __tablename__ = 'notification_preferences'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Notification categories
    conversation_started = db.Column(db.Boolean, default=True)
    feedback_received = db.Column(db.Boolean, default=True)
    usage_alerts = db.Column(db.Boolean, default=True)
    system_updates = db.Column(db.Boolean, default=True)
    weekly_reports = db.Column(db.Boolean, default=True)

    # Delivery preferences
    email_enabled = db.Column(db.Boolean, default=True)
    push_enabled = db.Column(db.Boolean, default=True)
    in_app_enabled = db.Column(db.Boolean, default=True)

    # Timing preferences
    quiet_hours_start = db.Column(db.Time)  # e.g., 22:00
    quiet_hours_end = db.Column(db.Time)    # e.g., 08:00
    timezone = db.Column(db.String(50), default='UTC')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref='notification_preferences')
    user = db.relationship('User', backref='notification_preferences')

    # Unique constraint
    __table_args__ = (db.UniqueConstraint('tenant_id', 'user_id', name='unique_tenant_user_prefs'),)

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'conversation_started': self.conversation_started,
            'feedback_received': self.feedback_received,
            'usage_alerts': self.usage_alerts,
            'system_updates': self.system_updates,
            'weekly_reports': self.weekly_reports,
            'email_enabled': self.email_enabled,
            'push_enabled': self.push_enabled,
            'in_app_enabled': self.in_app_enabled,
            'quiet_hours_start': self.quiet_hours_start.strftime('%H:%M') if self.quiet_hours_start else None,
            'quiet_hours_end': self.quiet_hours_end.strftime('%H:%M') if self.quiet_hours_end else None,
            'timezone': self.timezone,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
