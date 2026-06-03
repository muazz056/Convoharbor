import React, { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import './OAuthCallback.css';

const OAuthCallback = () => {
    const { login } = useAuth();
    const location = useLocation();

    const decodeJwtPayload = (token) => {
        try {
            const parts = token.split('.');
            if (parts.length !== 3) return null;
            const payload = parts[1];
            const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
            return JSON.parse(decoded);
        } catch {
            return null;
        }
    };

    useEffect(() => {
        const params = new URLSearchParams(location.search);
        const token = params.get('token');

        if (token) {
            try {
                const payload = decodeJwtPayload(token);
                const user = {
                    id: payload.user_id,
                    email: payload.email,
                    firstName: payload.first_name,
                    lastName: payload.last_name,
                    role: payload.role,
                    tenant_id: payload.tenant_id,
                    permissions: payload.permissions || {}
                };
                login(token, user);
                window.location.href = '/overview';
            } catch (error) {
                console.error("OAuth callback error:", error);
                window.location.href = '/login';
            }
        } else {
            console.error("OAuth callback is missing token.");
            window.location.href = '/login';
        }
    }, []);

    return (
        <div className="oauth-callback-container">
            <div className="loading-spinner"></div>
            <p>Please wait while we securely log you in...</p>
        </div>
    );
};

export default OAuthCallback;
