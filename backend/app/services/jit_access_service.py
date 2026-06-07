# app/services/jit_access_service.py

"""
Just-In-Time (JIT) Access Service
Manages temporary privilege elevation with approval workflows and audit logging.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from flask import request
from .. import db
from ..models.jit_access import (
    JITAccessRequest,
    JITAccessAuditLog,
    TemporaryRole
)

logger = logging.getLogger(__name__)


class JITAccessService:
    """Service for managing Just-In-Time access requests and temporary privileges."""

    @staticmethod
    def request_access(
        requester_id: int,
        requested_level: str,
        resource_type: str,
        justification: str,
        duration_minutes: int = 60,
        resource_id: Optional[int] = None
    ) -> JITAccessRequest:
        """
        Create a new JIT access request.

        Args:
            requester_id: ID of user requesting access
            requested_level: Level of access ('read', 'write', 'admin', 'super_admin')
            resource_type: Type of resource ('tenant', 'chatbot', 'system', etc.)
            justification: Reason for requesting access
            duration_minutes: How long access is needed (default 1 hour)
            resource_id: Specific resource ID (optional)

        Returns:
            Created JITAccessRequest
        """
        try:
            # Validate duration (max 24 hours)
            if duration_minutes > 1440:
                duration_minutes = 1440

            # Validate access level
            valid_levels = ['read', 'write', 'admin', 'super_admin']
            if requested_level not in valid_levels:
                raise ValueError(f"Invalid access level: {requested_level}")

            # Create request
            access_request = JITAccessRequest(
                requester_id=requester_id,
                requested_level=requested_level,
                resource_type=resource_type,
                resource_id=resource_id,
                justification=justification,
                requested_duration=duration_minutes,
                status='pending'
            )

            db.session.add(access_request)
            db.session.commit()

            logger.info(f"✅ JIT access request created: {access_request.id} by user {requester_id}")

            return access_request

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Failed to create JIT access request: {e}")
            raise

    @staticmethod
    def approve_request(
        request_id: int,
        approver_id: int,
        approval_reason: Optional[str] = None
    ) -> JITAccessRequest:
        """
        Approve a JIT access request.

        Args:
            request_id: ID of the request to approve
            approver_id: ID of user approving the request
            approval_reason: Optional reason for approval

        Returns:
            Updated JITAccessRequest
        """
        try:
            access_request = JITAccessRequest.query.get_or_404(request_id)

            if access_request.status != 'pending':
                raise ValueError(f"Request is not pending (status: {access_request.status})")

            # Approve the request
            access_request.approve(approver_id, approval_reason)

            # Create temporary role
            temp_role = TemporaryRole(
                user_id=access_request.requester_id,
                access_request_id=access_request.id,
                role_name=access_request.requested_level,
                permissions=JITAccessService._get_permissions_for_level(access_request.requested_level),
                valid_from=access_request.valid_from,
                valid_until=access_request.valid_until,
                is_active=True
            )

            db.session.add(temp_role)
            db.session.commit()

            logger.info(f"✅ JIT access request {request_id} approved by user {approver_id}")

            # Log the approval
            JITAccessService.log_action(
                user_id=approver_id,
                access_request_id=request_id,
                action_type='approve_access',
                resource_type='jit_access_request',
                resource_id=request_id,
                action_description=f"Approved access request for user {access_request.requester_id}",
                success=True
            )

            return access_request

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Failed to approve JIT access request {request_id}: {e}")
            raise

    @staticmethod
    def reject_request(
        request_id: int,
        approver_id: int,
        rejection_reason: str
    ) -> JITAccessRequest:
        """
        Reject a JIT access request.

        Args:
            request_id: ID of the request to reject
            approver_id: ID of user rejecting the request
            rejection_reason: Reason for rejection

        Returns:
            Updated JITAccessRequest
        """
        try:
            access_request = JITAccessRequest.query.get_or_404(request_id)

            if access_request.status != 'pending':
                raise ValueError(f"Request is not pending (status: {access_request.status})")

            # Reject the request
            access_request.reject(approver_id, rejection_reason)
            db.session.commit()

            logger.info(f"✅ JIT access request {request_id} rejected by user {approver_id}")

            # Log the rejection
            JITAccessService.log_action(
                user_id=approver_id,
                access_request_id=request_id,
                action_type='reject_access',
                resource_type='jit_access_request',
                resource_id=request_id,
                action_description=f"Rejected access request for user {access_request.requester_id}: {rejection_reason}",
                success=True
            )

            return access_request

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Failed to reject JIT access request {request_id}: {e}")
            raise

    @staticmethod
    def revoke_access(request_id: int, reason: Optional[str] = None) -> JITAccessRequest:
        """
        Revoke an active JIT access grant.

        Args:
            request_id: ID of the request to revoke
            reason: Optional reason for revocation

        Returns:
            Updated JITAccessRequest
        """
        try:
            access_request = JITAccessRequest.query.get_or_404(request_id)

            if access_request.status != 'approved':
                raise ValueError(f"Request is not approved (status: {access_request.status})")

            # Revoke the request
            access_request.revoke(reason)

            # Deactivate temporary roles
            temp_roles = TemporaryRole.query.filter_by(
                access_request_id=request_id,
                is_active=True
            ).all()

            for role in temp_roles:
                role.is_active = False
                role.revoked_at = datetime.utcnow()

            db.session.commit()

            logger.info(f"✅ JIT access {request_id} revoked")

            return access_request

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Failed to revoke JIT access {request_id}: {e}")
            raise

    @staticmethod
    def check_user_access(
        user_id: int,
        required_level: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None
    ) -> bool:
        """
        Check if a user has active JIT access for a specific level/resource.

        Args:
            user_id: User ID to check
            required_level: Required access level
            resource_type: Type of resource (optional)
            resource_id: Specific resource ID (optional)

        Returns:
            True if user has active access, False otherwise
        """
        try:
            now = datetime.utcnow()

            # Build query
            query = TemporaryRole.query.filter(
                TemporaryRole.user_id == user_id,
                TemporaryRole.role_name == required_level,
                TemporaryRole.is_active.is_(True),
                TemporaryRole.valid_from <= now,
                TemporaryRole.valid_until > now
            )

            # Filter by resource if specified
            if resource_type:
                query = query.join(JITAccessRequest).filter(
                    JITAccessRequest.resource_type == resource_type
                )

                if resource_id:
                    query = query.filter(JITAccessRequest.resource_id == resource_id)

            has_access = query.count() > 0

            return has_access

        except Exception as e:
            logger.error(f"❌ Failed to check JIT access for user {user_id}: {e}")
            return False

    @staticmethod
    def get_active_accesses(user_id: int) -> List[Dict[str, Any]]:
        """
        Get all active JIT accesses for a user.

        Args:
            user_id: User ID

        Returns:
            List of active access grants
        """
        try:
            now = datetime.utcnow()

            temp_roles = TemporaryRole.query.filter(
                TemporaryRole.user_id == user_id,
                TemporaryRole.is_active.is_(True),
                TemporaryRole.valid_from <= now,
                TemporaryRole.valid_until > now
            ).all()

            return [role.to_dict() for role in temp_roles]

        except Exception as e:
            logger.error(f"❌ Failed to get active accesses for user {user_id}: {e}")
            return []

    @staticmethod
    def expire_old_accesses():
        """
        Background task to expire old access grants.
        Should be run periodically (e.g., via Celery beat).
        """
        try:
            now = datetime.utcnow()

            # Find expired but still marked as active
            expired_roles = TemporaryRole.query.filter(
                TemporaryRole.is_active.is_(True),
                TemporaryRole.valid_until <= now
            ).all()

            expired_count = 0
            for role in expired_roles:
                role.is_active = False
                expired_count += 1

            # Update corresponding access requests
            if expired_roles:
                access_request_ids = [role.access_request_id for role in expired_roles]
                JITAccessRequest.query.filter(
                    JITAccessRequest.id.in_(access_request_ids),
                    JITAccessRequest.status == 'approved'
                ).update({'status': 'expired'}, synchronize_session=False)

            db.session.commit()

            if expired_count > 0:
                logger.info(f"✅ Expired {expired_count} old JIT access grants")

            return expired_count

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Failed to expire old accesses: {e}")
            return 0

    @staticmethod
    def log_action(
        user_id: int,
        access_request_id: int,
        action_type: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        action_description: Optional[str] = None,
        action_data: Optional[Dict] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> JITAccessAuditLog:
        """
        Log a privileged action taken during JIT access.

        Args:
            user_id: User performing the action
            access_request_id: JIT access request ID
            action_type: Type of action ('read', 'write', 'delete', etc.)
            resource_type: Type of resource affected
            resource_id: ID of resource affected (optional)
            action_description: Human-readable description
            action_data: Additional structured data
            success: Whether the action succeeded
            error_message: Error message if action failed

        Returns:
            Created audit log entry
        """
        try:
            audit_log = JITAccessAuditLog(
                user_id=user_id,
                access_request_id=access_request_id,
                action_type=action_type,
                resource_type=resource_type,
                resource_id=resource_id,
                action_description=action_description,
                action_data=action_data,
                ip_address=request.remote_addr if request else None,
                user_agent=request.user_agent.string if request and request.user_agent else None,
                success=success,
                error_message=error_message
            )

            db.session.add(audit_log)
            db.session.commit()

            return audit_log

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Failed to create audit log: {e}")
            raise

    @staticmethod
    def get_audit_logs(
        user_id: Optional[int] = None,
        access_request_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get audit logs with optional filters.

        Args:
            user_id: Filter by user ID
            access_request_id: Filter by access request ID
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of results

        Returns:
            List of audit log entries
        """
        try:
            query = JITAccessAuditLog.query

            if user_id:
                query = query.filter(JITAccessAuditLog.user_id == user_id)

            if access_request_id:
                query = query.filter(JITAccessAuditLog.access_request_id == access_request_id)

            if start_date:
                query = query.filter(JITAccessAuditLog.created_at >= start_date)

            if end_date:
                query = query.filter(JITAccessAuditLog.created_at <= end_date)

            logs = query.order_by(JITAccessAuditLog.created_at.desc()).limit(limit).all()

            return [log.to_dict() for log in logs]

        except Exception as e:
            logger.error(f"❌ Failed to get audit logs: {e}")
            return []

    @staticmethod
    def _get_permissions_for_level(level: str) -> List[str]:
        """
        Get list of permissions for a given access level.

        Args:
            level: Access level ('read', 'write', 'admin', 'super_admin')

        Returns:
            List of permission strings
        """
        permissions_map = {
            'read': ['read:chatbots', 'read:conversations', 'read:users', 'read:analytics'],
            'write': ['read:chatbots', 'read:conversations', 'read:users', 'read:analytics',
                      'write:chatbots', 'write:conversations', 'write:datasources'],
            'admin': ['read:chatbots', 'read:conversations', 'read:users', 'read:analytics',
                      'write:chatbots', 'write:conversations', 'write:datasources',
                      'admin:tenant', 'admin:users', 'admin:settings'],
            'super_admin': ['*']  # All permissions
        }

        return permissions_map.get(level, [])
