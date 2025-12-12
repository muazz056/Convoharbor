from flask import current_app, g
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from contextlib import contextmanager
from typing import Optional

class DatabaseService:
    """
    Service for managing database connections in a multi-tenant environment.
    Handles dynamic database routing based on tenant context.
    """
    def __init__(self):
        self._engines = {}
        self._sessions = {}
        
    def get_tenant_db_url(self, tenant_id: str) -> str:
        """Get the database URL for a specific tenant."""
        from app.models import Tenant
        
        # Query the tenant from the main database
        tenant = Tenant.query.filter_by(tenant_id=tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
            
        # Return tenant-specific database URL or fall back to main database
        return tenant.database_url or current_app.config['SQLALCHEMY_DATABASE_URI']
        
    def get_engine(self, tenant_id: Optional[str] = None):
        """Get or create SQLAlchemy engine for a tenant."""
        if tenant_id is None:
            # Return main application engine for system-level operations
            return current_app.extensions['sqlalchemy'].get_engine()
            
        if tenant_id not in self._engines:
            db_url = self.get_tenant_db_url(tenant_id)
            self._engines[tenant_id] = create_engine(
                db_url,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=1800
            )
        return self._engines[tenant_id]
        
    def get_session(self, tenant_id: Optional[str] = None):
        """Get a scoped session for a tenant."""
        if tenant_id not in self._sessions:
            engine = self.get_engine(tenant_id)
            session_factory = sessionmaker(bind=engine)
            self._sessions[tenant_id] = scoped_session(session_factory)
        return self._sessions[tenant_id]
        
    @contextmanager
    def tenant_context(self, tenant_id: str):
        """Context manager for tenant-specific database operations."""
        previous_session = getattr(g, 'db_session', None)
        try:
            g.db_session = self.get_session(tenant_id)
            yield g.db_session
        finally:
            if previous_session:
                g.db_session = previous_session
            else:
                delattr(g, 'db_session')
                
    def init_tenant_db(self, tenant_id: str):
        """Initialize a new tenant database."""
        from app.models import Tenant
        
        tenant = Tenant.query.filter_by(tenant_id=tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
            
        # Create database if it doesn't exist
        engine = self.get_engine(tenant_id)
        from app.models.tenant import Base
        Base.metadata.create_all(engine)
        
    def cleanup(self):
        """Cleanup database connections."""
        for session in self._sessions.values():
            session.remove()
        self._sessions.clear()
        self._engines.clear()
