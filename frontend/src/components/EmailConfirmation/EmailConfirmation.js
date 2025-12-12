import React, { useEffect, useState, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import './EmailConfirmation.css';

const EmailConfirmation = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [status, setStatus] = useState('verifying'); // verifying, success, error, expired
  const [message, setMessage] = useState('');
  const [retryCount, setRetryCount] = useState(0);
  const [userEmail, setUserEmail] = useState('');
  
  const isConfirming = useRef(false);

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) {
      setStatus('error');
      setMessage('Invalid confirmation link');
      return;
    }

    const confirmEmail = async () => {
      try {
        console.log('Confirming email with token:', token);
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
        
        const response = await fetch(`http://127.0.0.1:5001/api/v1/auth/confirm-email/${encodeURIComponent(token)}`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Origin': 'http://localhost:3000'
          },
          mode: 'cors',
          credentials: 'include',
          signal: controller.signal
        });

        clearTimeout(timeoutId);
        const data = await response.json();
        console.log('Response:', response.status, data);

        if (response.ok && data.success === true) {
          console.log('Setting success state', data);
          setStatus('success');
          setMessage(data.message || 'Email confirmed successfully! Redirecting to dashboard...');
          setUserEmail(data.user?.email || '');
          
          // If we got a token and user data, log in automatically
          if (data.token && data.user) {
            console.log('Logging in with token and user data');
            // Use the auth context to log in
            login(data.token, data.user);
            
            // Redirect to chatbot dashboard after 2 seconds
            setTimeout(() => {
              navigate('/chatbot');
            }, 2000);
          } else {
            // Fallback to login if no token
            setMessage('Email confirmed successfully! Please log in.');
            setTimeout(() => {
              navigate('/login');
            }, 3000);
          }
        } else if (response.status === 400 && data.message?.toLowerCase().includes('expired')) {
          // Handle expired token
          setStatus('expired');
          setMessage('Your confirmation link has expired. Please request a new one.');
          setUserEmail(data.email || '');
        } else if (response.status === 400 && data.message?.toLowerCase().includes('invalid')) {
          // Handle invalid token
          setStatus('error');
          setMessage('This confirmation link is invalid or has already been used.');
        } else {
          console.log('Setting error state', data);
          setStatus('error');
          setMessage(data.message || 'Failed to confirm email');
        }
      } catch (error) {
        console.error('Error during confirmation:', error);
        
        if (error.name === 'AbortError') {
          setStatus('error');
          setMessage('The confirmation request timed out. Please check your connection and try again.');
        } else if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
          setStatus('error');
          setMessage('Unable to connect to the server. Please check your internet connection.');
        } else {
          setStatus('error');
          setMessage('An unexpected error occurred while confirming your email. Please try again.');
        }
      }
    };

    if (status === 'verifying' && !isConfirming.current) {
      isConfirming.current = true;
      confirmEmail().finally(() => {
        isConfirming.current = false;
      });
    }
  }, [searchParams, navigate, status]);

  const handleRetry = () => {
    if (retryCount < 3) {
      setRetryCount(prev => prev + 1);
      setStatus('verifying');
      setMessage('');
      isConfirming.current = false;
    } else {
      setMessage('Maximum retry attempts reached. Please request a new confirmation email.');
    }
  };

  const requestNewConfirmation = async () => {
    try {
      const email = userEmail || prompt('Please enter your email address:');
      if (!email) return;

      const response = await fetch('http://127.0.0.1:5001/api/v1/auth/resend-confirmation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });

      const data = await response.json();
      if (response.ok) {
        setMessage('A new confirmation email has been sent. Please check your inbox.');
      } else {
        setMessage(data.error || 'Failed to send confirmation email. Please try again.');
      }
    } catch (error) {
      setMessage('Network error. Please check your connection and try again.');
    }
  };

  return (
    <div className="email-confirmation-container">
      <div className="confirmation-box">
        {status === 'verifying' && (
          <>
            <div className="spinner"></div>
            <h2>Verifying your email...</h2>
            <p>Please wait while we confirm your email address.</p>
          </>
        )}
        
        {status === 'success' && (
          <>
            <div className="success-icon">✓</div>
            <h2>Email Confirmed!</h2>
            <p>{message}</p>
            <p className="redirect-text">
              {message.includes('dashboard') ? 'Redirecting to dashboard...' : 'Redirecting to login page...'}
            </p>
          </>
        )}
        
        {status === 'expired' && (
          <>
            <div className="warning-icon">⏰</div>
            <h2>Link Expired</h2>
            <p>{message}</p>
            <div className="button-group">
              <button 
                className="primary-button"
                onClick={requestNewConfirmation}
              >
                Send New Link
              </button>
              <button 
                className="secondary-button"
                onClick={() => navigate('/login')}
              >
                Go to Login
              </button>
            </div>
          </>
        )}
        
        {status === 'error' && (
          <>
            <div className="error-icon">✕</div>
            <h2>Verification Failed</h2>
            <p>{message}</p>
            <div className="button-group">
              {retryCount < 3 && (
                <button 
                  className="secondary-button"
                  onClick={handleRetry}
                >
                  Retry ({3 - retryCount} attempts left)
                </button>
              )}
              <button 
                className="primary-button"
                onClick={() => navigate('/login')}
              >
                Go to Login
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default EmailConfirmation;
