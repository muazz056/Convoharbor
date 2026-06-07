import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import axios from 'axios';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    // Return default values instead of throwing error for public routes
    return {
      user: null,
      loading: false,
      isAuthenticated: false,
      login: () => {},
      logout: () => {},
      signup: () => {},
      refreshToken: () => {},
      updateUser: () => {}
    };
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const tokenValidationInterval = useRef(null);
  const isLoggingOut = useRef(false);

  // Auto-logout function for deleted/disabled users
  const forceLogout = (reason = 'Session expired') => {
    if (isLoggingOut.current) return; // Prevent multiple simultaneous logouts
    isLoggingOut.current = true;
    
    console.warn(`Force logout triggered: ${reason}`);
    
    // Clear all auth data
    localStorage.removeItem('authToken');
    localStorage.removeItem('userData');
    localStorage.removeItem('test_chat_active_id');
    setUser(null);
    setIsAuthenticated(false);
    
    // Clear validation interval
    if (tokenValidationInterval.current) {
      clearInterval(tokenValidationInterval.current);
      tokenValidationInterval.current = null;
    }
    
    // Show user-friendly message
    alert(`You have been logged out: ${reason}`);
    
    // Redirect to login
    window.location.href = '/login';
    
    isLoggingOut.current = false;
  };

  // Setup axios interceptor for automatic logout on 401/403
  useEffect(() => {
    const interceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response) {
          const { status, data } = error.response;
          
          // Handle authentication errors
          if (status === 401) {
            if (data.message?.toLowerCase().includes('user not found') || 
                data.message?.toLowerCase().includes('user deleted') ||
                data.message?.toLowerCase().includes('account disabled')) {
              forceLogout('Your account has been deleted or disabled');
            } else if (data.message?.toLowerCase().includes('token') && 
                       data.message?.toLowerCase().includes('invalid')) {
              forceLogout('Invalid authentication token');
            } else {
              forceLogout('Authentication expired');
            }
          } else if (status === 403) {
            if (data.message?.toLowerCase().includes('user not found') ||
                data.message?.toLowerCase().includes('account disabled')) {
              forceLogout('Your account has been disabled');
            }
          }
        }
        
        return Promise.reject(error);
      }
    );

    // Cleanup interceptor on unmount
    return () => {
      axios.interceptors.response.eject(interceptor);
    };
  }, []);

  // Periodic token validation
  const startTokenValidation = () => {
    if (tokenValidationInterval.current) return; // Already running
    
    tokenValidationInterval.current = setInterval(async () => {
      const token = localStorage.getItem('authToken');
      if (!token || !isAuthenticated) {
        clearInterval(tokenValidationInterval.current);
        tokenValidationInterval.current = null;
        return;
      }
      
      try {
        const response = await fetch('http://127.0.0.1:5001/api/v1/auth/validate-token', {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });
        
        if (!response.ok) {
          const data = await response.json();
          if (response.status === 401 || response.status === 403) {
            forceLogout(data.message || 'Session validation failed');
          }
        }
      } catch (error) {
        console.warn('Token validation failed:', error);
        // Don't force logout on network errors, only on auth errors
      }
    }, 5 * 60 * 1000); // Check every 5 minutes
  };

  // Check if user is logged in on app start
  useEffect(() => {
    const token = localStorage.getItem('authToken');
    const userData = localStorage.getItem('userData');
    
    if (token && userData) {
      try {
        const parsedUser = JSON.parse(userData);
        setUser(parsedUser);
        setIsAuthenticated(true);
        
        // Start periodic token validation
        startTokenValidation();
      } catch (error) {
        console.error('Error parsing user data:', error);
        localStorage.removeItem('authToken');
        localStorage.removeItem('userData');
      }
    }
    setLoading(false);
  }, []);

  const login = async (emailOrToken, passwordOrUser) => {
    try {
      // If we received a token and user object directly (from email confirmation)
      if (typeof emailOrToken === 'string' && typeof passwordOrUser === 'object') {
        const token = emailOrToken;
        const userData = passwordOrUser;
        
        localStorage.setItem('authToken', token);
        localStorage.setItem('userData', JSON.stringify(userData));
        
        setUser(userData);
        setIsAuthenticated(true);
        
        // Start token validation for new login
        startTokenValidation();
        
        return { success: true, data: { token, user: userData } };
      }
      
      // Regular login with email and password
      const response = await fetch('http://127.0.0.1:5001/api/v1/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          email: emailOrToken, 
          password: passwordOrUser 
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const { token, user: userData } = data;
        
        localStorage.setItem('authToken', token);
        localStorage.setItem('userData', JSON.stringify(userData));
        
        setUser(userData);
        setIsAuthenticated(true);
        
        // Start token validation for regular login
        startTokenValidation();
        
        return { success: true, data };
      } else {
        const errorData = await response.json();
        return { success: false, error: errorData.message || 'Login failed' };
      }
    } catch (error) {
      console.error('Login error:', error);
      return { success: false, error: 'Network error occurred' };
    }
  };

  const logout = async () => {
    try {
      // Call backend logout endpoint
      const response = await fetch('http://127.0.0.1:5001/api/v1/auth/logout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        }
      });

      // Clear local storage and state regardless of response
      localStorage.removeItem('authToken');
      localStorage.removeItem('userData');
      localStorage.removeItem('test_chat_active_id');
      setUser(null);
      setIsAuthenticated(false);

      // Clear token validation interval
      if (tokenValidationInterval.current) {
        clearInterval(tokenValidationInterval.current);
        tokenValidationInterval.current = null;
      }

      if (response.ok) {
        return { success: true };
      } else {
        console.warn('Logout request failed, but local state was cleared');
        return { success: true };
      }
    } catch (error) {
      console.warn('Logout request failed, but local state was cleared:', error);
      // Still clear everything even if request fails
      localStorage.removeItem('authToken');
      localStorage.removeItem('userData');
      localStorage.removeItem('test_chat_active_id');
      setUser(null);
      setIsAuthenticated(false);

      // Clear token validation interval
      if (tokenValidationInterval.current) {
        clearInterval(tokenValidationInterval.current);
        tokenValidationInterval.current = null;
      }

      return { success: true };
    }
  };

  const signup = async (userData) => {
    try {
      // API endpoint for Flask backend
      const response = await fetch('http://127.0.0.1:5001/api/v1/auth/signup', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(userData),
      });

      const data = await response.json();
      
      if (response.ok) {
        // Don't store token or user data - account needs email confirmation
        return { 
          success: true, 
          data,
          message: data.message || 'Please check your email to confirm your account.'
        };
      } else if (response.status === 409) {
        // Handle unconfirmed email case
        if (data.status === 'unconfirmed') {
          throw new Error('not confirmed');
        }
        return {
          success: false,
          error: data.error || 'Email already registered'
        };
      } else {
        return { 
          success: false, 
          error: data.error || data.message || 'Signup failed' 
        };
      }
    } catch (error) {
      if (error.message === 'not confirmed') {
        throw error; // Re-throw for CreateAccount component to handle
      }
      console.error('Signup error:', error);
      return { success: false, error: 'Network error occurred' };
    }
  };

  const hasPermission = (permission) => {
    if (!user || !user.permissions) return false;
    // Handle both array and object formats for permissions
    if (Array.isArray(user.permissions)) {
      return user.permissions.includes(permission);
    }
    // Handle object format from backend
    return user.permissions[permission] === true;
  };

  const hasPermissions = (permissions) => {
    if (!permissions || permissions.length === 0) return true;
    return permissions.every(permission => hasPermission(permission));
  };

  const isTenantAdmin = () => {
    return user && user.role === 'tenant_admin';
  };

  const isSuperAdmin = () => {
    const result = user && user.role === 'super_admin';
    console.log('🔍 AuthContext: isSuperAdmin check:', { user: user?.email, role: user?.role, result });
    return result;
  };

  const resendConfirmation = async (email) => {
    try {
      const response = await fetch('http://127.0.0.1:5001/api/v1/auth/resend-confirmation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });

      const data = await response.json();
      if (response.ok) {
        return { 
          success: true, 
          message: data.message || 'Confirmation email sent successfully' 
        };
      } else {
        return { 
          success: false, 
          error: data.error || data.message || 'Failed to resend confirmation email' 
        };
      }
    } catch (error) {
      console.error('Resend confirmation error:', error);
      return { 
        success: false, 
        error: 'Network error occurred. Please check your connection and try again.' 
      };
    }
  };

  const updateUser = (updatedUserData) => {
    try {
      // Update the user state
      setUser(updatedUserData);
      
      // Update localStorage
      localStorage.setItem('userData', JSON.stringify(updatedUserData));
      
      console.log('✅ User data updated successfully');
    } catch (error) {
      console.error('❌ Error updating user data:', error);
    }
  };

  const value = {
    user,
    isAuthenticated,
    loading,
    login,
    logout,
    signup,
    resendConfirmation,
    forceLogout,
    updateUser,
    hasPermission,
    hasPermissions,
    isTenantAdmin,
    isSuperAdmin,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;
