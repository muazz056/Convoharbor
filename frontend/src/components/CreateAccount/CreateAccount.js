import "./CreateAccount.css";
import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { validateEmail, validatePassword, validateConfirmPassword, validateName, validatePhone, getPasswordStrength, createRateLimiter } from "../../utils/validation";
import Navbar from "../navbar/navbar";

const signupRateLimiter = createRateLimiter(3, 15 * 60 * 1000);
const resendRateLimiter = createRateLimiter(5, 60 * 60 * 1000);

const CreateAccount = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    password: '',
    confirmPassword: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [signupSuccess, setSignupSuccess] = useState(false);
  const [unconfirmedEmail, setUnconfirmedEmail] = useState(false);
  const [passwordStrength, setPasswordStrength] = useState(null);
  const [rateLimitInfo, setRateLimitInfo] = useState(null);
  
  const navigate = useNavigate();
  const { signup, resendConfirmation, isAuthenticated } = useAuth();

  // If user is already logged in, redirect to dashboard
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/chatbot', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    
    if (name === 'password') {
      setPasswordStrength(getPasswordStrength(value));
    }
    if (error) setError('');
    if (rateLimitInfo) setRateLimitInfo(null);
  };

  const [fieldErrors, setFieldErrors] = useState({
    firstName: '', lastName: '', email: '', password: '', confirmPassword: '', phone: ''
  });

  const validateForm = () => {
    const newFieldErrors = {
      firstName: validateName(formData.firstName, 'First name'),
      lastName: validateName(formData.lastName, 'Last name'),
      email: validateEmail(formData.email),
      password: validatePassword(formData.password),
      confirmPassword: validateConfirmPassword(formData.password, formData.confirmPassword),
      phone: validatePhone(formData.phone)
    };

    setFieldErrors(newFieldErrors);
    const hasErrors = Object.values(newFieldErrors).some(error => error !== '');
    if (hasErrors) {
      setError('Please correct the errors in the form');
      return false;
    }
    return true;
  };

  const handleGoogleLogin = () => {
    const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
    window.location.href = `${apiUrl}/auth/oauth/google/authorize`;
  };

  const handleResendConfirmation = async () => {
    const rateLimit = resendRateLimiter(formData.email);
    if (!rateLimit.allowed) {
      setRateLimitInfo({
        type: 'resend',
        timeLeft: rateLimit.timeLeft,
        message: `Please wait ${rateLimit.timeLeft} seconds before requesting another confirmation email`
      });
      return;
    }
    
    try {
      setLoading(true);
      setError('');
      setRateLimitInfo(null);
      
      const result = await resendConfirmation(formData.email);
      
      if (result.success) {
        setSignupSuccess(true);
        setUnconfirmedEmail(false);
      } else {
        setError(result.error || 'Failed to resend confirmation email. Please try again.');
      }
    } catch (err) {
      setError('Network error occurred. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setUnconfirmedEmail(false);
    setRateLimitInfo(null);
    
    if (!validateForm()) return;
    
    const rateLimit = signupRateLimiter(formData.email);
    if (!rateLimit.allowed) {
      setRateLimitInfo({
        type: 'signup',
        timeLeft: rateLimit.timeLeft,
        message: `Too many signup attempts. Please wait ${Math.ceil(rateLimit.timeLeft / 60)} minutes before trying again`
      });
      return;
    }
    
    setLoading(true);

    try {
      const userData = {
        firstName: formData.firstName,
        lastName: formData.lastName,
        email: formData.email,
        phone: formData.phone,
        password: formData.password,
        role: 'admin'
      };
      
      const result = await signup(userData);
      if (result.success) {
        setSignupSuccess(true);
      } else {
        setError(result.error || 'Signup failed');
      }
    } catch (err) {
      if (err.message?.includes('not confirmed')) {
        setUnconfirmedEmail(true);
        setError('This email is already registered but not confirmed.');
      } else {
        setError(err.message || 'Network error occurred');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <Navbar />
      <div className="auth-container">
        <div className="auth-card auth-card-wide">
          <div className="auth-header">
            <h1 className="auth-title">Create Account</h1>
            <p className="auth-subtitle">Get started with your free account</p>
          </div>

          {signupSuccess ? (
            <div className="auth-alert auth-alert-success">
              <i className="fas fa-check-circle me-2"></i>
              <div>
                <strong>Check your email!</strong>
                <p className="mb-0 mt-1">We've sent a confirmation link to <strong>{formData.email}</strong></p>
              </div>
            </div>
          ) : unconfirmedEmail ? (
            <div className="auth-alert auth-alert-warning">
              <i className="fas fa-exclamation-triangle me-2"></i>
              <div>
                <strong>Email not confirmed</strong>
                <p className="mb-2 mt-1">This email is already registered but not confirmed.</p>
                <button onClick={handleResendConfirmation} className="auth-btn-resend" disabled={loading}>
                  {loading ? 'Sending...' : 'Resend Confirmation'}
                </button>
              </div>
            </div>
          ) : error ? (
            <div className="auth-alert auth-alert-error">
              <i className="fas fa-exclamation-circle me-2"></i>
              {error}
            </div>
          ) : null}

          {rateLimitInfo && (
            <div className="auth-alert auth-alert-warning">
              <i className="fas fa-clock me-2"></i>
              {rateLimitInfo.message}
            </div>
          )}

          {!signupSuccess && (
            <form onSubmit={handleSubmit}>
              <div className="auth-row">
                <div className="auth-field">
                  <label htmlFor="firstName">First Name</label>
                  <div className="auth-input-wrapper">
                    <i className="fas fa-user"></i>
                    <input
                      type="text"
                      id="firstName"
                      name="firstName"
                      value={formData.firstName}
                      onChange={handleChange}
                      placeholder="John"
                      className={fieldErrors.firstName ? 'auth-input error' : 'auth-input'}
                      required
                    />
                  </div>
                  {fieldErrors.firstName && <span className="auth-error">{fieldErrors.firstName}</span>}
                </div>
                <div className="auth-field">
                  <label htmlFor="lastName">Last Name</label>
                  <div className="auth-input-wrapper">
                    <i className="fas fa-user"></i>
                    <input
                      type="text"
                      id="lastName"
                      name="lastName"
                      value={formData.lastName}
                      onChange={handleChange}
                      placeholder="Doe"
                      className={fieldErrors.lastName ? 'auth-input error' : 'auth-input'}
                      required
                    />
                  </div>
                  {fieldErrors.lastName && <span className="auth-error">{fieldErrors.lastName}</span>}
                </div>
              </div>

              <div className="auth-row">
                <div className="auth-field">
                  <label htmlFor="email">Email Address</label>
                  <div className="auth-input-wrapper">
                    <i className="fas fa-envelope"></i>
                    <input
                      type="email"
                      id="email"
                      name="email"
                      value={formData.email}
                      onChange={handleChange}
                      placeholder="name@example.com"
                      className={fieldErrors.email ? 'auth-input error' : 'auth-input'}
                      required
                    />
                  </div>
                  {fieldErrors.email && <span className="auth-error">{fieldErrors.email}</span>}
                </div>
                <div className="auth-field">
                  <label htmlFor="phone">Phone (optional)</label>
                  <div className="auth-input-wrapper">
                    <i className="fas fa-phone"></i>
                    <input
                      type="tel"
                      id="phone"
                      name="phone"
                      value={formData.phone}
                      onChange={handleChange}
                      placeholder="+1 234 567 890"
                      className={fieldErrors.phone ? 'auth-input error' : 'auth-input'}
                    />
                  </div>
                  {fieldErrors.phone && <span className="auth-error">{fieldErrors.phone}</span>}
                </div>
              </div>

              <div className="auth-field">
                <label htmlFor="password">Password</label>
                <div className="auth-input-wrapper">
                  <i className="fas fa-lock"></i>
                  <input
                    type={showPassword ? "text" : "password"}
                    id="password"
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="Create a strong password"
                    className={fieldErrors.password ? 'auth-input error' : 'auth-input'}
                    required
                  />
                  <button type="button" className="auth-eye-btn" onClick={() => setShowPassword(!showPassword)}>
                    <i className={`fa ${showPassword ? "fa-eye-slash" : "fa-eye"}`}></i>
                  </button>
                </div>
                {fieldErrors.password && <span className="auth-error">{fieldErrors.password}</span>}
                {passwordStrength && formData.password && (
                  <div className="auth-strength">
                    <div className="auth-strength-bar">
                      <div 
                        className="auth-strength-fill" 
                        style={{ width: `${passwordStrength.percentage}%`, backgroundColor: passwordStrength.color }}
                      ></div>
                    </div>
                    <span style={{ color: passwordStrength.color, fontSize: '12px', fontWeight: 600 }}>
                      {passwordStrength.label}
                    </span>
                  </div>
                )}
              </div>

              <div className="auth-field">
                <label htmlFor="confirmPassword">Confirm Password</label>
                <div className="auth-input-wrapper">
                  <i className="fas fa-lock"></i>
                  <input
                    type={showConfirmPassword ? "text" : "password"}
                    id="confirmPassword"
                    name="confirmPassword"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    placeholder="Confirm your password"
                    className={fieldErrors.confirmPassword ? 'auth-input error' : 'auth-input'}
                    required
                  />
                  <button type="button" className="auth-eye-btn" onClick={() => setShowConfirmPassword(!showConfirmPassword)}>
                    <i className={`fa ${showConfirmPassword ? "fa-eye-slash" : "fa-eye"}`}></i>
                  </button>
                </div>
                {fieldErrors.confirmPassword && <span className="auth-error">{fieldErrors.confirmPassword}</span>}
              </div>

              <button type="submit" className="auth-btn-primary" disabled={loading}>
                {loading ? (
                  <><i className="fas fa-spinner fa-spin me-2"></i>Creating account...</>
                ) : (
                  <><i className="fas fa-user-plus me-2"></i>Create Account</>
                )}
              </button>
            </form>
          )}

          {signupSuccess && (
            <Link to="/login" className="auth-btn-primary" style={{ display: 'block', textAlign: 'center', textDecoration: 'none' }}>
              <i className="fas fa-sign-in-alt me-2"></i>Go to Login
            </Link>
          )}

          <div className="auth-divider">
            <span>or continue with</span>
          </div>

          <button type="button" className="auth-btn-google" onClick={handleGoogleLogin}>
            <i className="fab fa-google me-2"></i>Google
          </button>

          <p className="auth-footer-text">
            Already have an account?{' '}
            <Link to="/login" className="auth-link">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default CreateAccount;
