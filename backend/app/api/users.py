from flask import request, current_app, jsonify, g
from . import api
from ..decorators import tenant_admin_required, login_required
from ..models import User
from .. import db

@api.route('/users', methods=['GET'])
@tenant_admin_required
def list_users():
    """List users for the current tenant."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Build query
    query = User.query.filter_by(tenant_id=g.tenant_id)
    
    # Apply filters
    if 'role' in request.args:
        query = query.filter_by(role=request.args['role'])
    if 'status' in request.args:
        query = query.filter_by(status=request.args['status'])
        
    # Execute paginated query
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    users = pagination.items
    
    return jsonify({
        'users': [{
            'id': u.id,
            'email': u.email,
            'role': u.role,
            'status': u.status,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'last_login': u.last_login.isoformat() if u.last_login else None
        } for u in users],
        'pagination': {
            'page': pagination.page,
            'pages': pagination.pages,
            'total': pagination.total,
            'per_page': pagination.per_page
        }
    })
    
@api.route('/users/<int:user_id>', methods=['GET'])
@login_required
def get_user(user_id):
    """Get user details."""
    user = User.query.get_or_404(user_id)
    
    # Only allow access to users in the same tenant
    if g.tenant_id != user.tenant_id:
        return jsonify({'error': 'Access denied'}), 403
        
    # Regular users can only view their own profile
    if g.role == 'user' and g.user_id != user_id:
        return jsonify({'error': 'Access denied'}), 403
        
    return jsonify({
        'id': user.id,
        'email': user.email,
        'role': user.role,
        'status': user.status,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'last_login': user.last_login.isoformat() if user.last_login else None,
        'permissions': current_app.auth_service.get_user_permissions(user)
    })
    
@api.route('/users/<int:user_id>', methods=['PUT'])
@tenant_admin_required
def update_user(user_id):
    """Update user details."""
    user = User.query.get_or_404(user_id)
    
    # Only allow updates to users in the same tenant
    if g.tenant_id != user.tenant_id:
        return jsonify({'error': 'Access denied'}), 403
        
    data = request.get_json()
    
    # Prevent role escalation
    if 'role' in data and g.role != 'super_admin':
        if data['role'] == 'super_admin' or (
            g.role == 'tenant_admin' and data['role'] == 'tenant_admin'
        ):
            return jsonify({'error': 'Cannot assign this role'}), 403
            
    # Update allowed fields
    allowed_fields = {'first_name', 'last_name', 'role', 'status'}
    for field in allowed_fields:
        if field in data:
            setattr(user, field, data[field])
            
    # Update password if provided
    if 'password' in data:
        user.password_hash = current_app.auth_service.hash_password(data['password'])
        
    db.session.commit()
    
    return jsonify({
        'message': 'User updated successfully',
        'user': {
            'id': user.id,
            'email': user.email,
            'role': user.role,
            'status': user.status,
            'first_name': user.first_name,
            'last_name': user.last_name
        }
    })
    
@api.route('/users/<int:user_id>', methods=['DELETE'])
@tenant_admin_required
def delete_user(user_id):
    """Delete a user."""
    user = User.query.get_or_404(user_id)
    
    # Only allow deletion of users in the same tenant
    if g.tenant_id != user.tenant_id:
        return jsonify({'error': 'Access denied'}), 403
        
    # Prevent self-deletion and deletion of other admins
    if user.id == g.user_id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    if user.role == 'tenant_admin' and g.role != 'super_admin':
        return jsonify({'error': 'Cannot delete admin users'}), 403
        
    # Soft delete
    user.status = 'deleted'
    db.session.commit()
    
    return jsonify({'message': 'User deleted successfully'})

@api.route('/users/profile', methods=['GET'])
@login_required
def get_profile():
    """Get current user's profile data."""
    user = User.query.get_or_404(g.user_id)
    
    current_app.logger.info(f"🔍 Profile GET: User {user.email}")
    current_app.logger.info(f"🔍 Profile GET: first_name = '{user.first_name}'")
    current_app.logger.info(f"🔍 Profile GET: last_name = '{user.last_name}'")
    current_app.logger.info(f"🔍 Profile GET: first_name is None = {user.first_name is None}")
    current_app.logger.info(f"🔍 Profile GET: last_name is None = {user.last_name is None}")
    
    return jsonify({
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
        'status': user.status,
        'last_login': user.last_login.isoformat() if user.last_login else None,
        'permissions': current_app.auth_service.get_user_permissions(user)
    })

@api.route('/users/profile', methods=['PUT'])
@login_required
def update_profile():
    """Update current user's profile."""
    user = User.query.get_or_404(g.user_id)
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        # Update allowed profile fields
        if 'first_name' in data:
            user.first_name = data['first_name'].strip() if data['first_name'] else None
        if 'last_name' in data:
            user.last_name = data['last_name'].strip() if data['last_name'] else None
        
        # Handle password change
        if 'new_password' in data and data['new_password']:
            current_app.logger.info(f"🔐 Password change requested for user {user.email}")
            
            # Verify current password
            if not data.get('current_password'):
                current_app.logger.warning("❌ Current password not provided")
                return jsonify({'error': 'Current password is required'}), 400
            
            # Check if current password is correct
            password_valid = current_app.auth_service.verify_password(user.password_hash, data['current_password'])
            current_app.logger.info(f"🔍 Current password verification: {password_valid}")
            
            if not password_valid:
                current_app.logger.warning("❌ Current password verification failed")
                return jsonify({'error': 'Current password is incorrect'}), 400
            
            # Validate new password
            if len(data['new_password']) < 6:
                current_app.logger.warning("❌ New password too short")
                return jsonify({'error': 'New password must be at least 6 characters long'}), 400
            
            # Update password
            old_hash = user.password_hash
            user.password_hash = current_app.auth_service.hash_password(data['new_password'])
            current_app.logger.info(f"✅ Password hash updated for user {user.email}")
            current_app.logger.info(f"🔍 Old hash: {old_hash[:20]}...")
            current_app.logger.info(f"🔍 New hash: {user.password_hash[:20]}...")
        
        # Save changes
        db.session.commit()
        
        # Update localStorage data
        updated_user_data = {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'tenant_id': user.tenant_id,
            'permissions': current_app.auth_service.get_user_permissions(user)
        }
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': updated_user_data
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating profile: {e}")
        return jsonify({'error': 'Failed to update profile'}), 500