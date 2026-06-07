from flask import request, current_app, jsonify, g
from . import api
from ..decorators import super_admin_required, tenant_admin_required, login_required


@api.route('/tenants', methods=['POST'])
@super_admin_required
def create_tenant():
    """Create a new tenant."""
    data = request.get_json()

    # Validate required fields
    required_fields = ['name', 'domain', 'type', 'admin_email', 'admin_password']
    if not all(field in data for field in required_fields):
        return jsonify({
            'error': 'Missing required fields',
            'required': required_fields
        }), 400

    try:
        tenant = current_app.tenant_service.create_tenant(
            name=data['name'],
            domain=data['domain'],
            tenant_type=data['type'],
            admin_email=data['admin_email'],
            admin_password=data['admin_password']
        )

        return jsonify({
            'message': 'Tenant created successfully',
            'tenant': {
                'id': tenant.id,
                'tenant_id': tenant.tenant_id,
                'name': tenant.name,
                'domain': tenant.domain,
                'type': tenant.type,
                'status': tenant.status
            }
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@api.route('/tenants', methods=['GET'])
@super_admin_required
def list_tenants():
    """List all tenants with pagination and filtering."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    # Get filter parameters
    filters = {}
    if 'type' in request.args:
        filters['type'] = request.args['type']
    if 'status' in request.args:
        filters['status'] = request.args['status']

    pagination = current_app.tenant_service.list_tenants(
        page=page,
        per_page=per_page,
        filters=filters
    )

    tenants = pagination.items

    return jsonify({
        'tenants': [{
            'id': t.id,
            'tenant_id': t.tenant_id,
            'name': t.name,
            'domain': t.domain,
            'type': t.type,
            'status': t.status,
            'created_at': t.created_at.isoformat()
        } for t in tenants],
        'pagination': {
            'page': pagination.page,
            'pages': pagination.pages,
            'total': pagination.total,
            'per_page': pagination.per_page
        }
    })


@api.route('/tenants/<tenant_id>', methods=['GET'])
@login_required
def get_tenant(tenant_id):
    """Get tenant details."""
    tenant = current_app.tenant_service.get_tenant(tenant_id)
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Only allow super admins or users from the same tenant
    if g.role != 'super_admin' and g.tenant_id != tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    return jsonify({
        'id': tenant.id,
        'tenant_id': tenant.tenant_id,
        'name': tenant.name,
        'domain': tenant.domain,
        'type': tenant.type,
        'status': tenant.status,
        'created_at': tenant.created_at.isoformat(),
        'config': tenant.config
    })


@api.route('/tenants/<tenant_id>', methods=['PUT'])
@tenant_admin_required
def update_tenant(tenant_id):
    """Update tenant details."""
    tenant = current_app.tenant_service.get_tenant(tenant_id)
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    # Only allow super admins or admins from the same tenant
    if (g.role != 'super_admin'
            and (g.tenant_id != tenant.id or g.role != 'tenant_admin')):
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()

    try:
        updated_tenant = current_app.tenant_service.update_tenant(tenant_id, data)
        return jsonify({
            'message': 'Tenant updated successfully',
            'tenant': {
                'id': updated_tenant.id,
                'tenant_id': updated_tenant.tenant_id,
                'name': updated_tenant.name,
                'status': updated_tenant.status,
                'config': updated_tenant.config
            }
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@api.route('/tenants/<tenant_id>', methods=['DELETE'])
@super_admin_required
def delete_tenant(tenant_id):
    """Delete a tenant."""
    success = current_app.tenant_service.delete_tenant(tenant_id)
    if not success:
        return jsonify({'error': 'Failed to delete tenant'}), 400

    return jsonify({'message': 'Tenant deleted successfully'})
