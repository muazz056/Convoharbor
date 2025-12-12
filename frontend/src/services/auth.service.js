import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';

// Configure axios defaults
axios.defaults.headers.common['Content-Type'] = 'application/json';
axios.defaults.withCredentials = true;

class AuthService {
    constructor() {
        // Initialize auth headers if user is already logged in
        const currentUser = this.getCurrentUser();
        if (currentUser?.token) {
            this.setupAxiosInterceptors(currentUser.token);
        }
    }
    async login(email, password) {
        const response = await axios.post(`${API_URL}/auth/login`, {
            email,
            password
        });
        
        if (response.data.token) {
            // Use the same keys as AuthContext
            localStorage.setItem('authToken', response.data.token);
            localStorage.setItem('userData', JSON.stringify(response.data.user));
            this.setupAxiosInterceptors(response.data.token);
        }
        
        return response.data;
    }
    
    logout() {
        localStorage.removeItem('authToken');
        localStorage.removeItem('userData');
        delete axios.defaults.headers.common['Authorization'];
    }
    
    async register(userData) {
        try {
            const response = await axios.post(`${API_URL}/auth/signup`, userData);
            return response.data;
        } catch (error) {
            // Check if it's an email already registered error
            if (error.response?.status === 409) {
                // Try to check if the email is unconfirmed
                try {
                    const checkResponse = await axios.post(`${API_URL}/auth/check-email`, {
                        email: userData.email
                    });
                    
                    if (checkResponse.data.status === 'unconfirmed') {
                        throw new Error(
                            'This email is already registered but not confirmed. ' +
                            'Please check your email for the confirmation link, or request a new one.'
                        );
                    }
                } catch (checkError) {
                    // If check-email fails, throw the original conflict error
                    throw new Error('This email address is already registered.');
                }
            }
            // For other errors, throw the original error
            throw error;
        }
    }
    
    getCurrentUser() {
        // Use the same keys as AuthContext
        const token = localStorage.getItem('authToken');
        const userData = localStorage.getItem('userData');
        
        if (token && userData) {
            try {
                const user = JSON.parse(userData);
                return { ...user, token };
            } catch (error) {
                console.error('Error parsing user data:', error);
                return null;
            }
        }
        return null;
    }
    
    isAuthenticated() {
        const user = this.getCurrentUser();
        return !!user && !!user.token;
    }
    
    setupAxiosInterceptors(token) {
        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        
        axios.interceptors.response.use(
            response => response,
            error => {
                if (error.response?.status === 401) {
                    this.logout();
                    window.location.href = '/login';
                }
                return Promise.reject(error);
            }
        );
    }
    
    hasPermission(permission) {
        const user = this.getCurrentUser();
        return user?.permissions?.[permission] || false;
    }
    
    isSuperAdmin() {
        const user = this.getCurrentUser();
        return user?.role === 'super_admin';
    }
    
    isTenantAdmin() {
        const user = this.getCurrentUser();
        return user?.role === 'admin'; // Changed from tenant_admin to admin as per current role system
    }

    // Error Handling
    async resendConfirmation(email) {
        try {
            const response = await axios.post(`${API_URL}/auth/resend-confirmation`, { email });
            return {
                success: true,
                message: 'Confirmation email has been resent. Please check your inbox.'
            };
        } catch (error) {
            throw new Error('Failed to resend confirmation email. Please try again later.');
        }
    }

    handleError(error) {
        if (error.response) {
            // Server responded with error
            const { status, data } = error.response;
            switch (status) {
                case 400:
                    return { error: 'Invalid request', details: data.error };
                case 401:
                    return { error: 'Authentication required' };
                case 403:
                    return { error: 'Access denied', details: data.error };
                case 404:
                    return { error: 'Resource not found' };
                case 409:
                    if (data.status === 'unconfirmed') {
                        return {
                            error: 'Email not confirmed',
                            details: 'Please check your email for confirmation link or request a new one.',
                            unconfirmed: true
                        };
                    }
                    return { error: 'Resource conflict', details: data.error };
                default:
                    return { error: 'Server error', details: data.error };
            }
        }
        // Network error
        return { error: 'Network error', details: error.message };
    }
}

export default new AuthService();
