import React, { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import './OAuthCallback.css';

const OAuthCallback = () => {
    const { login } = useAuth();
    const location = useLocation();
    const navigate = useNavigate();

    useEffect(() => {
        const handleOAuthCallback = () => {
            const params = new URLSearchParams(location.search);
            const token = params.get('token');
            const userParam = params.get('user');

            if (token && userParam) {
                try {
                    const user = JSON.parse(userParam);
                    // Use the login function from AuthContext to set the session
                    login(token, user);
                    // Redirect to the main dashboard or overview page after successful login
                    navigate('/overview');
                } catch (error) {
                    console.error("Failed to parse user data from URL", error);
                    // Redirect to login page on error
                    navigate('/login');
                }
            } else {
                console.error("OAuth callback is missing token or user data.");
                // Redirect to login page if token/user is missing
                navigate('/login');
            }
        };

        handleOAuthCallback();
    }, [location, login, navigate]);

    return (
        <div className="oauth-callback-container">
            <div className="loading-spinner"></div>
            <p>Please wait while we securely log you in...</p>
        </div>
    );
};

export default OAuthCallback;
