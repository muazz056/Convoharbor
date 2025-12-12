# app/api/notifications.py

from datetime import datetime
from flask import request, jsonify, g, current_app
from . import api
from ..decorators import login_required
from ..models.notification import Notification, NotificationPreference
from ..models.tenant import Tenant
from ..services.notification_service import NotificationService
from .. import db


@api.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    """Get notifications for the current user"""
    try:
        # Convert tenant UUID to integer ID
        tenant = Tenant.query.filter_by(uuid=g.user_tenant_id).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        
        tenant_id = tenant.id
        
        # Get query parameters
        limit = min(int(request.args.get('limit', 50)), 100)
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        category = request.args.get('category')
        
        # Build query
        query = Notification.query.filter_by(tenant_id=tenant_id)
        
        # Filter by user (get user-specific and system-wide notifications)
        if hasattr(g, 'user_id') and g.user_id:
            query = query.filter(
                (Notification.user_id == g.user_id) | (Notification.user_id.is_(None))
            )
        
        # Filter by category if specified
        if category:
            query = query.filter_by(category=category)
        
        # Filter by read status
        if unread_only:
            query = query.filter(Notification.read_at.is_(None))
        
        # Get notifications
        notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()
        
        # Get unread count
        unread_count = Notification.query.filter_by(tenant_id=tenant_id).filter(
            Notification.read_at.is_(None)
        ).count()
        
        return jsonify({
            'notifications': [notification.to_dict() for notification in notifications],
            'unread_count': unread_count,
            'total_count': len(notifications)
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get notifications: {str(e)}")
        return jsonify({'error': 'Failed to retrieve notifications'}), 500


@api.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    try:
        # Convert tenant UUID to integer ID
        tenant = Tenant.query.filter_by(uuid=g.user_tenant_id).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        
        tenant_id = tenant.id
        
        notification_service = NotificationService()
        success = notification_service.mark_as_read(notification_id, tenant_id)
        
        if success:
            return jsonify({'message': 'Notification marked as read'})
        else:
            return jsonify({'error': 'Notification not found or already read'}), 404
        
    except Exception as e:
        current_app.logger.error(f"Failed to mark notification as read: {str(e)}")
        return jsonify({'error': 'Failed to mark notification as read'}), 500


@api.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read for the current user"""
    try:
        # Convert tenant UUID to integer ID
        tenant = Tenant.query.filter_by(uuid=g.user_tenant_id).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        
        tenant_id = tenant.id
        
        # Update all unread notifications
        query = Notification.query.filter_by(tenant_id=tenant_id).filter(
            Notification.read_at.is_(None)
        )
        
        # Filter by user if available
        if hasattr(g, 'user_id') and g.user_id:
            query = query.filter(
                (Notification.user_id == g.user_id) | (Notification.user_id.is_(None))
            )
        
        updated_count = query.update({
            'read_at': datetime.utcnow(),
            'status': 'read'
        })
        
        db.session.commit()
        
        return jsonify({
            'message': f'Marked {updated_count} notifications as read',
            'updated_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to mark all notifications as read: {str(e)}")
        return jsonify({'error': 'Failed to mark notifications as read'}), 500


@api.route('/notifications/preferences', methods=['GET'])
@login_required
def get_notification_preferences():
    """Get notification preferences for the current user"""
    try:
        # Convert tenant UUID to integer ID
        tenant = Tenant.query.filter_by(uuid=g.user_tenant_id).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        
        tenant_id = tenant.id
        user_id = getattr(g, 'user_id', tenant.owner_id)
        
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        notification_service = NotificationService()
        preferences = notification_service.get_user_preferences(tenant_id, user_id)
        
        if preferences:
            return jsonify(preferences.to_dict())
        else:
            return jsonify({'error': 'Failed to get preferences'}), 500
        
    except Exception as e:
        current_app.logger.error(f"Failed to get notification preferences: {str(e)}")
        return jsonify({'error': 'Failed to retrieve preferences'}), 500


@api.route('/notifications/preferences', methods=['PUT'])
@login_required
def update_notification_preferences():
    """Update notification preferences for the current user"""
    try:
        # Convert tenant UUID to integer ID
        tenant = Tenant.query.filter_by(uuid=g.user_tenant_id).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        
        tenant_id = tenant.id
        user_id = getattr(g, 'user_id', tenant.owner_id)
        
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        notification_service = NotificationService()
        success = notification_service.update_user_preferences(tenant_id, user_id, data)
        
        if success:
            # Return updated preferences
            preferences = notification_service.get_user_preferences(tenant_id, user_id)
            return jsonify(preferences.to_dict())
        else:
            return jsonify({'error': 'Failed to update preferences'}), 500
        
    except Exception as e:
        current_app.logger.error(f"Failed to update notification preferences: {str(e)}")
        return jsonify({'error': 'Failed to update preferences'}), 500


@api.route('/notifications/test', methods=['POST'])
@login_required
def send_test_notification():
    """Send a test notification (for testing purposes)"""
    try:
        # Convert tenant UUID to integer ID
        tenant = Tenant.query.filter_by(uuid=g.user_tenant_id).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        
        tenant_id = tenant.id
        user_id = getattr(g, 'user_id', tenant.owner_id)
        
        data = request.get_json() or {}
        notification_type = data.get('type', 'in_app')
        
        notification_service = NotificationService()
        
        notification = notification_service.create_notification(
            tenant_id=tenant_id,
            user_id=user_id,
            category='system_updates',
            title='Test Notification',
            message='This is a test notification to verify your notification settings are working correctly.',
            notification_type=notification_type,
            data={
                'test': True,
                'sent_at': datetime.utcnow().isoformat()
            }
        )
        
        return jsonify({
            'message': 'Test notification sent successfully',
            'notification': notification.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to send test notification: {str(e)}")
        return jsonify({'error': 'Failed to send test notification'}), 500


@api.route('/notifications/stats', methods=['GET'])
@login_required
def get_notification_stats():
    """Get notification statistics for the current tenant"""
    try:
        # Convert tenant UUID to integer ID
        tenant = Tenant.query.filter_by(uuid=g.user_tenant_id).first()
        if not tenant:
            return jsonify({'error': 'Tenant not found'}), 404
        
        tenant_id = tenant.id
        
        # Get notification counts by category and status
        from sqlalchemy import func
        
        # Count by category
        category_stats = db.session.query(
            Notification.category,
            func.count(Notification.id).label('count')
        ).filter_by(tenant_id=tenant_id).group_by(Notification.category).all()
        
        # Count by status
        status_stats = db.session.query(
            Notification.status,
            func.count(Notification.id).label('count')
        ).filter_by(tenant_id=tenant_id).group_by(Notification.status).all()
        
        # Count by type
        type_stats = db.session.query(
            Notification.type,
            func.count(Notification.id).label('count')
        ).filter_by(tenant_id=tenant_id).group_by(Notification.type).all()
        
        # Recent activity (last 7 days)
        from datetime import timedelta
        recent_date = datetime.utcnow() - timedelta(days=7)
        recent_count = Notification.query.filter(
            Notification.tenant_id == tenant_id,
            Notification.created_at >= recent_date
        ).count()
        
        return jsonify({
            'category_stats': {stat.category: stat.count for stat in category_stats},
            'status_stats': {stat.status: stat.count for stat in status_stats},
            'type_stats': {stat.type: stat.count for stat in type_stats},
            'recent_activity': recent_count,
            'total_notifications': sum(stat.count for stat in status_stats)
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get notification stats: {str(e)}")
        return jsonify({'error': 'Failed to retrieve notification statistics'}), 500
