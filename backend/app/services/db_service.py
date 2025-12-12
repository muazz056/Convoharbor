# Alias for database_service to maintain compatibility
from .database_service import DatabaseService

# Create instance for easy importing
db_service = DatabaseService()

# Export the service methods for direct access
init_tenant_db = db_service.init_tenant_db
get_tenant_db_url = db_service.get_tenant_db_url
get_engine = db_service.get_engine
get_session = db_service.get_session
tenant_context = db_service.tenant_context
cleanup = db_service.cleanup
