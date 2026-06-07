# app/api/jit_access.py

"""
JIT Access API Endpoints
Provides REST API for Just-In-Time access management.
"""

from flask import request, jsonify, g, current_app
from flasgger import swag_from
from . import api
from ..decorators import login_required, super_admin_required
from ..services.jit_access_service import JITAccessService
from ..models.jit_access import JITAccessRequest


@api.route('/jit-access/request', methods=['POST'])
@login_required
@swag_from({
    'tags': ['JIT Access'],
    'summary': 'Request temporary elevated access',
    'description': 'Create a JIT access request for temporary privilege elevation',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'required': ['requested_level', 'resource_type', 'justification'],
            'properties': {
                'requested_level': {
                    'type': 'string',
                    'enum': ['read', 'write', 'admin', 'super_admin'],
                    'description': 'Level of access requested'
                },
                'resource_type': {
                    'type': 'string',
                    'description': 'Type of resource (tenant, chatbot, system, etc.)'
                },
                'resource_id': {
                    'type': 'integer',
                    'description': 'Specific resource ID (optional)'
                },
                'justification': {
                    'type': 'string',
                    'description': 'Reason for requesting access'
                },
                'duration_minutes': {
                    'type': 'integer',
                    'default': 60,
                    'description': 'Duration in minutes (max 1440 = 24 hours)'
                }
            }
        }
    }],
    'responses': {
        '201': {'description': 'Access request created'},
        '400': {'description': 'Invalid request data'},
        '401': {'description': 'Unauthorized'}
    }
})
def request_jit_access():
    """Request temporary elevated access."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate required fields
        required_fields = ['requested_level', 'resource_type', 'justification']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Create access request
        access_request = JITAccessService.request_access(
            requester_id=g.user_id,
            requested_level=data['requested_level'],
            resource_type=data['resource_type'],
            justification=data['justification'],
            duration_minutes=data.get('duration_minutes', 60),
            resource_id=data.get('resource_id')
        )

        return jsonify({
            'message': 'Access request created successfully',
            'request': access_request.to_dict()
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error creating JIT access request: {e}")
        return jsonify({'error': 'Failed to create access request'}), 500


@api.route('/jit-access/requests', methods=['GET'])
@login_required
@swag_from({
    'tags': ['JIT Access'],
    'summary': 'List JIT access requests',
    'description': 'Get all JIT access requests (filtered by role)',
    'parameters': [{
        'name': 'status',
        'in': 'query',
        'type': 'string',
        'enum': ['pending', 'approved', 'rejected', 'expired', 'revoked'],
        'description': 'Filter by status'
    }],
    'responses': {
        '200': {'description': 'List of access requests'}
    }
})
def list_jit_access_requests():
    """List JIT access requests."""
    try:
        status_filter = request.args.get('status')

        # Super admins can see all requests, others only their own
        if g.is_super_admin:
            query = JITAccessRequest.query
        else:
            query = JITAccessRequest.query.filter_by(requester_id=g.user_id)

        if status_filter:
            query = query.filter_by(status=status_filter)

        requests_list = query.order_by(JITAccessRequest.requested_at.desc()).all()

        return jsonify({
            'requests': [req.to_dict() for req in requests_list],
            'total': len(requests_list)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error listing JIT access requests: {e}")
        return jsonify({'error': 'Failed to list access requests'}), 500


@api.route('/jit-access/requests/<int:request_id>', methods=['GET'])
@login_required
@swag_from({
    'tags': ['JIT Access'],
    'summary': 'Get JIT access request details',
    'responses': {
        '200': {'description': 'Access request details'},
        '404': {'description': 'Request not found'}
    }
})
def get_jit_access_request(request_id):
    """Get details of a specific JIT access request."""
    try:
        access_request = JITAccessRequest.query.get_or_404(request_id)

        # Check permissions
        if not g.is_super_admin and access_request.requester_id != g.user_id:
            return jsonify({'error': 'Access denied'}), 403

        return jsonify(access_request.to_dict()), 200

    except Exception as e:
        current_app.logger.error(f"Error getting JIT access request: {e}")
        return jsonify({'error': 'Failed to get access request'}), 500


@api.route('/jit-access/requests/<int:request_id>/approve', methods=['POST'])
@login_required
@super_admin_required
@swag_from({
    'tags': ['JIT Access'],
    'summary': 'Approve JIT access request',
    'description': 'Approve a pending JIT access request (Super Admin only)',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'approval_reason': {
                    'type': 'string',
                    'description': 'Optional reason for approval'
                }
            }
        }
    }],
    'responses': {
        '200': {'description': 'Request approved'},
        '400': {'description': 'Invalid request state'},
        '403': {'description': 'Forbidden - Super admin access required'}
    }
})
def approve_jit_access_request(request_id):
    """Approve a JIT access request."""
    try:
        data = request.get_json() or {}

        access_request = JITAccessService.approve_request(
            request_id=request_id,
            approver_id=g.user_id,
            approval_reason=data.get('approval_reason')
        )

        return jsonify({
            'message': 'Access request approved',
            'request': access_request.to_dict()
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error approving JIT access request: {e}")
        return jsonify({'error': 'Failed to approve access request'}), 500


@api.route('/jit-access/requests/<int:request_id>/reject', methods=['POST'])
@login_required
@super_admin_required
@swag_from({
    'tags': ['JIT Access'],
    'summary': 'Reject JIT access request',
    'description': 'Reject a pending JIT access request (Super Admin only)',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'required': ['rejection_reason'],
            'properties': {
                'rejection_reason': {
                    'type': 'string',
                    'description': 'Reason for rejection'
                }
            }
        }
    }],
    'responses': {
        '200': {'description': 'Request rejected'},
        '400': {'description': 'Invalid request state'},
        '403': {'description': 'Forbidden - Super admin access required'}
    }
})
def reject_jit_access_request(request_id):
    """Reject a JIT access request."""
    try:
        data = request.get_json()

        if not data or 'rejection_reason' not in data:
            return jsonify({'error': 'rejection_reason is required'}), 400

        access_request = JITAccessService.reject_request(
            request_id=request_id,
            approver_id=g.user_id,
            rejection_reason=data['rejection_reason']
        )

        return jsonify({
            'message': 'Access request rejected',
            'request': access_request.to_dict()
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error rejecting JIT access request: {e}")
        return jsonify({'error': 'Failed to reject access request'}), 500


@api.route('/jit-access/requests/<int:request_id>/revoke', methods=['POST'])
@login_required
@super_admin_required
@swag_from({
    'tags': ['JIT Access'],
    'summary': 'Revoke active JIT access',
    'description': 'Revoke an active JIT access grant (Super Admin only)',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'schema': {
            'type': 'object',
            'properties': {
                'reason': {
                    'type': 'string',
                    'description': 'Optional reason for revocation'
                }
            }
        }
    }],
    'responses': {
        '200': {'description': 'Access revoked'},
        '400': {'description': 'Invalid request state'},
        '403': {'description': 'Forbidden - Super admin access required'}
    }
})
def revoke_jit_access(request_id):
    """Revoke an active JIT access grant."""
    try:
        data = request.get_json() or {}

        access_request = JITAccessService.revoke_access(
            request_id=request_id,
            reason=data.get('reason')
        )

        return jsonify({
            'message': 'Access revoked',
            'request': access_request.to_dict()
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error revoking JIT access: {e}")
        return jsonify({'error': 'Failed to revoke access'}), 500


@api.route('/jit-access/active', methods=['GET'])
@login_required
@swag_from({
    'tags': ['JIT Access'],
    'summary': 'Get active JIT accesses',
    'description': 'Get all active JIT access grants for current user',
    'responses': {
        '200': {'description': 'List of active accesses'}
    }
})
def get_active_jit_accesses():
    """Get active JIT accesses for current user."""
    try:
        accesses = JITAccessService.get_active_accesses(user_id=g.user_id)

        return jsonify({
            'active_accesses': accesses,
            'total': len(accesses)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting active JIT accesses: {e}")
        return jsonify({'error': 'Failed to get active accesses'}), 500


@api.route('/jit-access/audit-logs', methods=['GET'])
@login_required
@super_admin_required
@swag_from({
    'tags': ['JIT Access'],
    'summary': 'Get JIT access audit logs',
    'description': 'Get audit logs for JIT access activities (Super Admin only)',
    'parameters': [
        {
            'name': 'user_id',
            'in': 'query',
            'type': 'integer',
            'description': 'Filter by user ID'
        },
        {
            'name': 'access_request_id',
            'in': 'query',
            'type': 'integer',
            'description': 'Filter by access request ID'
        },
        {
            'name': 'limit',
            'in': 'query',
            'type': 'integer',
            'default': 100,
            'description': 'Maximum number of results'
        }
    ],
    'responses': {
        '200': {'description': 'List of audit logs'},
        '403': {'description': 'Forbidden - Super admin access required'}
    }
})
def get_jit_audit_logs():
    """Get JIT access audit logs."""
    try:
        user_id = request.args.get('user_id', type=int)
        access_request_id = request.args.get('access_request_id', type=int)
        limit = request.args.get('limit', default=100, type=int)

        logs = JITAccessService.get_audit_logs(
            user_id=user_id,
            access_request_id=access_request_id,
            limit=min(limit, 1000)  # Cap at 1000
        )

        return jsonify({
            'logs': logs,
            'total': len(logs)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting JIT audit logs: {e}")
        return jsonify({'error': 'Failed to get audit logs'}), 500
