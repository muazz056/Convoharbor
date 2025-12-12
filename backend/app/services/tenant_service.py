from typing import Optional, List, Dict, Any
from flask import current_app
from sqlalchemy.exc import IntegrityError
from ..models import Tenant, User
from . import db_service, auth_service

class TenantService:
    """Service for managing tenants and their resources."""
    
    def create_tenant(self, name: str, domain: str, tenant_type: str,
                     admin_email: str, admin_password: str) -> Tenant:
        """Create a new tenant with an admin user."""
        try:
            # Create tenant
            tenant = Tenant(
                name=name,
                domain=domain,
                type=tenant_type,
                status='active'
            )
            current_app.db.session.add(tenant)
            current_app.db.session.flush()  # Get tenant ID without committing
            
            # Create admin user
            admin = User(
                tenant_id=tenant.id,
                email=admin_email,
                password_hash=auth_service.hash_password(admin_password),
                role='tenant_admin',
                status='active'
            )
            current_app.db.session.add(admin)
            
            # Initialize tenant database if using separate databases
            if tenant_type == 'managed':
                # Generate unique database URL for managed tenants
                db_name = f"tenant_{tenant.tenant_id.replace('-', '_')}"
                tenant.database_url = self._generate_db_url(db_name)
                db_service.init_tenant_db(tenant.tenant_id)
                
            current_app.db.session.commit()
            return tenant
            
        except IntegrityError:
            current_app.db.session.rollback()
            raise ValueError(f"Tenant with domain {domain} already exists")
            
    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get a tenant by ID."""
        return Tenant.query.filter_by(tenant_id=tenant_id).first()
        
    def update_tenant(self, tenant_id: str, updates: Dict[str, Any]) -> Optional[Tenant]:
        """Update tenant details."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return None
            
        # Update allowed fields
        allowed_fields = {'name', 'status', 'config'}
        for field in allowed_fields:
            if field in updates:
                setattr(tenant, field, updates[field])
                
        current_app.db.session.commit()
        return tenant
        
    def delete_tenant(self, tenant_id: str) -> bool:
        """Delete a tenant and all associated data."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False
            
        try:
            # Soft delete - mark as deleted but keep records
            tenant.status = 'deleted'
            current_app.db.session.commit()
            
            # TODO: Schedule hard delete after grace period
            # This would involve:
            # 1. Backing up tenant data
            # 2. Dropping tenant database if using separate DBs
            # 3. Removing tenant records from main database
            
            return True
        except Exception as e:
            current_app.logger.error(f"Failed to delete tenant {tenant_id}: {e}")
            current_app.db.session.rollback()
            return False
            
    def list_tenants(self, page: int = 1, per_page: int = 20,
                     filters: Optional[Dict[str, Any]] = None) -> List[Tenant]:
        """List tenants with pagination and filtering."""
        query = Tenant.query
        
        # Apply filters
        if filters:
            if 'type' in filters:
                query = query.filter_by(type=filters['type'])
            if 'status' in filters:
                query = query.filter_by(status=filters['status'])
                
        return query.paginate(page=page, per_page=per_page, error_out=False)
        
    def _generate_db_url(self, db_name: str) -> str:
        """Generate a database URL for a new tenant."""
        base_url = current_app.config['SQLALCHEMY_DATABASE_URI']
        if 'sqlite' in base_url:
            # For development, use SQLite with different file names
            return f"sqlite:///{current_app.config['UPLOAD_FOLDER']}/{db_name}.db"
        else:
            # For production, create new database in PostgreSQL
            # Remove database name from base URL
            base_url = base_url.rsplit('/', 1)[0]
            return f"{base_url}/{db_name}"
