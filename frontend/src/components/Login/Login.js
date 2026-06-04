import "./Login.css";
import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { validateEmail } from "../../utils/validation";
import Navbar from "../navbar/navbar";

const Login = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    rememberMe: false
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const [fieldErrors, setFieldErrors] = useState({
    email: '',
    password: ''
  });

  const validateForm = () => {
    const newFieldErrors = {
      email: validateEmail(formData.email),
      password: formData.password ? '' : 'Password is required'
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    if (!validateForm()) {
      return;
    }

    setLoading(true);

    try {
      const result = await login(formData.email, formData.password);
      if (result.success) {
        navigate('/chatbot');
      } else {
        setError(result.error || 'Login failed');
      }
    } catch (err) {
      setError('Network error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <Navbar />
      <div className="auth-container">
        <div className="auth-card" data-aos="fade-up">
          <div className="auth-header">
            <h1 className="auth-title">Welcome Back</h1>
            <p className="auth-subtitle">Sign in to your account</p>
          </div>

          {error && (
            <div className="auth-alert auth-alert-error">
              <i className="fas fa-exclamation-circle me-2"></i>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
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
              <label htmlFor="password">Password</label>
              <div className="auth-input-wrapper">
                <i className="fas fa-lock"></i>
                <input
                  type={showPassword ? "text" : "password"}
                  id="password"
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="Enter your password"
                  className={fieldErrors.password ? 'auth-input error' : 'auth-input'}
                  required
                />
                <button
                  type="button"
                  className="auth-eye-btn"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  <i className={`fa ${showPassword ? "fa-eye-slash" : "fa-eye"}`}></i>
                </button>
              </div>
              {fieldErrors.password && <span className="auth-error">{fieldErrors.password}</span>}
            </div>

            <div className="auth-options">
              <label className="auth-checkbox">
                <input
                  type="checkbox"
                  name="rememberMe"
                  checked={formData.rememberMe}
                  onChange={handleChange}
                />
                <span>Remember me</span>
              </label>
              <Link to="/forget_password" className="auth-forgot">Forgot password?</Link>
            </div>

            <button 
              type="submit" 
              className="auth-btn-primary"
              disabled={loading}
            >
              {loading ? (
                <><i className="fas fa-spinner fa-spin me-2"></i>Signing in...</>
              ) : (
                <><i className="fas fa-sign-in-alt me-2"></i>Sign In</>
              )}
            </button>
          </form>

          <div className="auth-divider">
            <span>or continue with</span>
          </div>

          <button 
            type="button" 
            className="auth-btn-google"
            onClick={handleGoogleLogin}
          >
            <i className="fab fa-google me-2"></i>Google
          </button>

          <p className="auth-footer-text">
            Don't have an account?{' '}
            <Link to="/signup" className="auth-link">Create one</Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
