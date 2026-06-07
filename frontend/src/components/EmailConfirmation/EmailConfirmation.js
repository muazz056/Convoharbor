import React, { useEffect, useState, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import './EmailConfirmation.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
const FRONTEND_URL = process.env.REACT_APP_FRONTEND_URL || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000');

const EmailConfirmation = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [status, setStatus] = useState('verifying'); // verifying, success, error, expired
  const [message, setMessage] = useState('');
  const [retryCount, setRetryCount] = useState(0);
  const [userEmail, setUserEmail] = useState('');
  const [resendEmail, setResendEmail] = useState('');
  const [resendStatus, setResendStatus] = useState('idle'); // idle, sending, sent, error
  const [resendMessage, setResendMessage] = useState('');

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
        const timeoutId = setTimeout(() => controller.abort(), 10000);

        const response = await fetch(`${API_URL}/auth/confirm-email/${encodeURIComponent(token)}`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Origin': FRONTEND_URL
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

          if (data.token && data.user) {
            console.log('Logging in with token and user data');
            login(data.token, data.user);
            setTimeout(() => {
              navigate('/chatbot');
            }, 2000);
          } else {
            setMessage('Email confirmed successfully! Please log in.');
            setTimeout(() => {
              navigate('/login');
            }, 3000);
          }
        } else if (response.status === 400 && data.message?.toLowerCase().includes('expired')) {
          setStatus('expired');
          setMessage('Your confirmation link has expired. Please request a new one.');
          setUserEmail(data.email || '');
        } else if (response.status === 400 && data.message?.toLowerCase().includes('invalid')) {
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
  }, [searchParams, navigate, status, login]);

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

  const requestNewConfirmation = async (e) => {
    if (e) e.preventDefault();
    const email = (resendEmail || userEmail || '').trim().toLowerCase();
    if (!email) {
      setResendStatus('error');
      setResendMessage('Please enter your email address.');
      return;
    }

    setResendStatus('sending');
    setResendMessage('');
    try {
      const response = await fetch(`${API_URL}/auth/resend-confirmation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });

      const data = await response.json().catch(() => ({}));
      if (response.ok) {
        setResendStatus('sent');
        setResendMessage('A new confirmation email has been sent. Please check your inbox.');
      } else {
        setResendStatus('error');
        setResendMessage(data.error || 'Failed to send confirmation email. Please try again.');
      }
    } catch (error) {
      setResendStatus('error');
      setResendMessage('Network error. Please check your connection and try again.');
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
            <form onSubmit={requestNewConfirmation} className="resend-form">
              <label htmlFor="resend-email">Email Address</label>
              <input
                id="resend-email"
                type="email"
                value={resendEmail || userEmail}
                onChange={(e) => setResendEmail(e.target.value)}
                placeholder="name@example.com"
                required
              />
              {resendMessage && (
                <div className={`resend-msg resend-msg-${resendStatus}`}>
                  {resendMessage}
                </div>
              )}
              <div className="button-group">
                <button
                  type="submit"
                  className="primary-button"
                  disabled={resendStatus === 'sending'}
                >
                  {resendStatus === 'sending' ? 'Sending...' : 'Send New Link'}
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => navigate('/login')}
                >
                  Go to Login
                </button>
              </div>
            </form>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="error-icon">✕</div>
            <h2>Verification Failed</h2>
            <p>{message}</p>
            <form onSubmit={requestNewConfirmation} className="resend-form">
              <label htmlFor="resend-email-error">Request a new confirmation link</label>
              <input
                id="resend-email-error"
                type="email"
                value={resendEmail || userEmail}
                onChange={(e) => setResendEmail(e.target.value)}
                placeholder="name@example.com"
                required
              />
              {resendMessage && (
                <div className={`resend-msg resend-msg-${resendStatus}`}>
                  {resendMessage}
                </div>
              )}
              <div className="button-group">
                <button
                  type="submit"
                  className="primary-button"
                  disabled={resendStatus === 'sending'}
                >
                  {resendStatus === 'sending' ? 'Sending...' : 'Send New Link'}
                </button>
                {retryCount < 3 && (
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={handleRetry}
                  >
                    Retry ({3 - retryCount} attempts left)
                  </button>
                )}
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => navigate('/login')}
                >
                  Go to Login
                </button>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  );
};

export default EmailConfirmation;
