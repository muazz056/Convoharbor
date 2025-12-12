import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

const ProtectedRoute = ({ 
  children, 
  requiredPermissions = [], 
  requireTenantAdmin = false,
  requireSuperAdmin = false,
  fallbackPath = null
}) => {
  const { isAuthenticated, loading, hasPermissions, isTenantAdmin, isSuperAdmin } = useAuth();
  const location = useLocation();

  // Show loading spinner while checking authentication
  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ height: '100vh' }}>
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check super admin requirement
  if (requireSuperAdmin && !isSuperAdmin()) {
    return (
      <div className="container mt-5">
        <div className="alert alert-danger" role="alert">
          <h4 className="alert-heading">Access Denied</h4>
          <p>You don't have permission to access this page. Super admin privileges are required.</p>
          <hr />
          <p className="mb-0">Please contact your administrator if you believe this is an error.</p>
        </div>
      </div>
    );
  }

  // Check tenant admin requirement
  if (requireTenantAdmin && !isTenantAdmin() && !isSuperAdmin()) {
    return (
      <div className="container mt-5">
        <div className="alert alert-danger" role="alert">
          <h4 className="alert-heading">Access Denied</h4>
          <p>You don't have permission to access this page. Tenant admin privileges are required.</p>
          <hr />
          <p className="mb-0">Please contact your administrator if you believe this is an error.</p>
        </div>
      </div>
    );
  }

  // Check specific permissions
  if (requiredPermissions.length > 0 && !hasPermissions(requiredPermissions)) {
    if (fallbackPath) {
      return <Navigate to={fallbackPath} replace />;
    }
    return (
      <div className="container mt-5">
        <div className="alert alert-warning" role="alert">
          <h4 className="alert-heading">Insufficient Permissions</h4>
          <p>You don't have the required permissions to access this page.</p>
          <p><strong>Required permissions:</strong> {requiredPermissions.join(', ')}</p>
          <hr />
          <p className="mb-0">Please contact your administrator to request access.</p>
        </div>
      </div>
    );
  }

  // If all checks pass, render the protected component
  return children;
};

export default ProtectedRoute;
