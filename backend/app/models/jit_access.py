# app/models/jit_access.py

"""
Just-In-Time (JIT) Access System Models
Provides time-bound privilege elevation with audit logging.
"""

from datetime import datetime, timedelta
from enum import Enum
from .. import db


class AccessLevel(Enum):
    """Access levels for JIT requests."""
    READ = 'read'
    WRITE = 'write'
    ADMIN = 'admin'
    SUPER_ADMIN = 'super_admin'


class AccessRequestStatus(Enum):
    """Status of access requests."""
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    EXPIRED = 'expired'
    REVOKED = 'revoked'


class JITAccessRequest(db.Model):
    """
    JIT Access Request - Temporary privilege elevation requests.
    """
    __tablename__ = 'jit_access_requests'

    id = db.Column(db.Integer, primary_key=True)

    # Requester information
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    requester = db.relationship('User', foreign_keys=[requester_id], backref='access_requests')

    # Approver information
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approver = db.relationship('User', foreign_keys=[approver_id])

    # Access details
    requested_level = db.Column(db.String(50), nullable=False)  # AccessLevel enum
    resource_type = db.Column(db.String(100), nullable=False)  # 'tenant', 'chatbot', 'system', etc.
    resource_id = db.Column(db.Integer, nullable=True)  # Specific resource ID (optional)

    # Justification and metadata
    justification = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='pending', nullable=False)

    # Time bounds
    requested_duration = db.Column(db.Integer, nullable=False)  # Duration in minutes
    valid_from = db.Column(db.DateTime, nullable=True)  # When access starts (after approval)
    valid_until = db.Column(db.DateTime, nullable=True)  # When access expires

    # Approval details
    approval_reason = db.Column(db.Text, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    # Timestamps
    requested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime, nullable=True)  # When approved/rejected
    revoked_at = db.Column(db.DateTime, nullable=True)

    # Auto-revocation
    auto_revoke = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f'<JITAccessRequest {self.id}: {self.requester_id} -> {self.requested_level}>'

    def is_active(self) -> bool:
        """Check if this access grant is currently active."""
        if self.status != 'approved':
            return False

        now = datetime.utcnow()

        if not self.valid_from or not self.valid_until:
            return False

        return self.valid_from <= now < self.valid_until

    def is_expired(self) -> bool:
        """Check if this access grant has expired."""
        if self.status != 'approved':
            return False

        if not self.valid_until:
            return False

        return datetime.utcnow() >= self.valid_until

    def time_remaining(self) -> timedelta:
        """Get remaining time for this access grant."""
        if not self.is_active():
            return timedelta(0)

        return self.valid_until - datetime.utcnow()

    def approve(self, approver_id: int, reason: str = None):
        """Approve this access request."""
        self.status = 'approved'
        self.approver_id = approver_id
        self.approval_reason = reason
        self.reviewed_at = datetime.utcnow()
        self.valid_from = datetime.utcnow()
        self.valid_until = self.valid_from + timedelta(minutes=self.requested_duration)

    def reject(self, approver_id: int, reason: str):
        """Reject this access request."""
        self.status = 'rejected'
        self.approver_id = approver_id
        self.rejection_reason = reason
        self.reviewed_at = datetime.utcnow()

    def revoke(self, reason: str = None):
        """Revoke this access grant."""
        self.status = 'revoked'
        self.revoked_at = datetime.utcnow()
        self.rejection_reason = reason or 'Access revoked'

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'requester_id': self.requester_id,
            'requester_email': self.requester.email if self.requester else None,
            'approver_id': self.approver_id,
            'approver_email': self.approver.email if self.approver else None,
            'requested_level': self.requested_level,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'justification': self.justification,
            'status': self.status,
            'requested_duration': self.requested_duration,
            'valid_from': self.valid_from.isoformat() if self.valid_from else None,
            'valid_until': self.valid_until.isoformat() if self.valid_until else None,
            'approval_reason': self.approval_reason,
            'rejection_reason': self.rejection_reason,
            'requested_at': self.requested_at.isoformat(),
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'revoked_at': self.revoked_at.isoformat() if self.revoked_at else None,
            'is_active': self.is_active(),
            'is_expired': self.is_expired(),
            'time_remaining_minutes': int(self.time_remaining().total_seconds() / 60) if self.is_active() else 0
        }


class JITAccessAuditLog(db.Model):
    """
    Audit log for JIT access activities.
    Tracks all privileged actions taken during elevated access periods.
    """
    __tablename__ = 'jit_access_audit_logs'

    id = db.Column(db.Integer, primary_key=True)

    # User and access request
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref='jit_audit_logs')

    access_request_id = db.Column(db.Integer, db.ForeignKey('jit_access_requests.id'), nullable=False)
    access_request = db.relationship('JITAccessRequest', backref='audit_logs')

    # Action details
    action_type = db.Column(db.String(100), nullable=False)  # 'read', 'write', 'delete', 'update', etc.
    resource_type = db.Column(db.String(100), nullable=False)
    resource_id = db.Column(db.Integer, nullable=True)

    # Action metadata
    action_description = db.Column(db.Text, nullable=True)
    action_data = db.Column(db.JSON, nullable=True)  # Additional structured data

    # Request details
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)

    # Result
    success = db.Column(db.Boolean, default=True, nullable=False)
    error_message = db.Column(db.Text, nullable=True)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<JITAccessAuditLog {self.id}: {self.user_id} - {self.action_type}>'

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_email': self.user.email if self.user else None,
            'access_request_id': self.access_request_id,
            'action_type': self.action_type,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'action_description': self.action_description,
            'action_data': self.action_data,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'success': self.success,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat()
        }


class TemporaryRole(db.Model):
    """
    Temporary role assignments for JIT access.
    Automatically expires based on access request duration.
    """
    __tablename__ = 'temporary_roles'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref='temporary_roles')

    access_request_id = db.Column(db.Integer, db.ForeignKey('jit_access_requests.id'), nullable=False)
    access_request = db.relationship('JITAccessRequest', backref='temporary_roles')

    # Role details
    role_name = db.Column(db.String(100), nullable=False)
    permissions = db.Column(db.JSON, nullable=True)  # List of granted permissions

    # Time bounds (copied from access request for denormalization)
    valid_from = db.Column(db.DateTime, nullable=False)
    valid_until = db.Column(db.DateTime, nullable=False)

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<TemporaryRole {self.id}: {self.user_id} - {self.role_name}>'

    def is_currently_valid(self) -> bool:
        """Check if this temporary role is currently valid."""
        if not self.is_active:
            return False

        now = datetime.utcnow()
        return self.valid_from <= now < self.valid_until

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_email': self.user.email if self.user else None,
            'access_request_id': self.access_request_id,
            'role_name': self.role_name,
            'permissions': self.permissions,
            'valid_from': self.valid_from.isoformat(),
            'valid_until': self.valid_until.isoformat(),
            'is_active': self.is_active,
            'revoked_at': self.revoked_at.isoformat() if self.revoked_at else None,
            'created_at': self.created_at.isoformat(),
            'is_currently_valid': self.is_currently_valid()
        }
