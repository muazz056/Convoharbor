import "./CreateAccount.css";
import robot from "../images/robot.png";
import logo from "../images/logo.png";
import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { validateEmail, validatePassword, validateConfirmPassword, validateName, validatePhone, getPasswordStrength, createRateLimiter } from "../../utils/validation";

// Create rate limiters for signup and resend confirmation
const signupRateLimiter = createRateLimiter(3, 15 * 60 * 1000); // 3 attempts per 15 minutes
const resendRateLimiter = createRateLimiter(5, 60 * 60 * 1000); // 5 attempts per hour

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
  const { signup, resendConfirmation } = useAuth();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    
    // Update password strength in real-time
    if (name === 'password') {
      setPasswordStrength(getPasswordStrength(value));
    }
    
    // Clear errors when user starts typing
    if (error) {
      setError('');
    }
    
    // Clear rate limit info when user starts typing
    if (rateLimitInfo) {
      setRateLimitInfo(null);
    }
  };

  const [fieldErrors, setFieldErrors] = useState({
    firstName: '',
    lastName: '',
    email: '',
    password: '',
    confirmPassword: '',
    phone: ''
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

    // Check if any field has an error
    const hasErrors = Object.values(newFieldErrors).some(error => error !== '');
    if (hasErrors) {
      setError('Please correct the errors in the form');
      return false;
    }
    
    return true;
  };

  const handleGoogleLogin = () => {
    // Construct the backend URL using environment variables for robustness
    const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:5001/api/v1';
    window.location.href = `${apiUrl}/auth/oauth/google/authorize`;
  };

  const handleResendConfirmation = async () => {
    // Check rate limiting
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
    
    if (!validateForm()) {
      return;
    }
    
    // Check rate limiting for signup
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
        role: 'admin'  // Hardcoded as admin since this is admin signup
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
    <div className="login-wrapper">
      <div className="left-pane">
        <a href="/home">
          <img
          src={logo}
          alt="LOGO"
          style={{
            position: "absolute",
            top: "1rem",
            left: "1rem",
            height: "40px", // adjust size as needed
            zIndex: 2,
          }}
        />
        </a>

        <img
          src={robot}
          alt="Robot"
          style={{
            position: "absolute",
            left: "32%",
            top: "50%",
            transform: "translate(-50%, -50%)",
            maxWidth: "100%",
            maxHeight: "100%",
            zIndex: 1,
            pointerEvents: "none",
          }}
        />
      </div>

      <div className="right-pane">
        <form className="form-box needs-validation" noValidate onSubmit={handleSubmit}>
          <h2 className="fw-bold mb-3">Create Admin Account</h2>
          <p className="mb-4">Create your administrator account for document management</p>

          {signupSuccess ? (
            <div className="alert alert-success mb-4" role="alert">
              <h4 className="alert-heading mb-2">✉️ Check Your Email!</h4>
              <p className="mb-0">We've sent a confirmation link to <strong>{formData.email}</strong></p>
            </div>
          ) : unconfirmedEmail ? (
            <div className="alert alert-warning mb-4" role="alert">
              <h4 className="alert-heading mb-2">⚠️ Email Not Confirmed</h4>
              <p className="mb-2">This email is already registered but not confirmed.</p>
              <button 
                onClick={handleResendConfirmation}
                className="btn btn-warning btn-sm"
                disabled={loading}
              >
                {loading ? 'Sending...' : 'Resend Confirmation Email'}
              </button>
            </div>
          ) : error ? (
            <div className="alert alert-danger mb-3" role="alert">
              {error}
            </div>
          ) : null}

          {rateLimitInfo && (
            <div className="alert alert-warning mb-3" role="alert">
              <h6 className="alert-heading mb-2">⏰ Rate Limited</h6>
              <p className="mb-0">{rateLimitInfo.message}</p>
            </div>
          )}

          <div className="mb-3 d-flex">
            <div className="flex-grow-1">
              <input
                type="text"
                className={`form-control ${fieldErrors.firstName ? 'is-invalid' : ''}`}
                id="firstName"
                name="firstName"
                value={formData.firstName}
                onChange={handleChange}
                placeholder="first name"
                required
              />
              {fieldErrors.firstName && (
                <div className="invalid-feedback">{fieldErrors.firstName}</div>
              )}
            </div>
            <div className="flex-grow-1 ms-2">
              <input
                type="text"
                className={`form-control ${fieldErrors.lastName ? 'is-invalid' : ''}`}
                id="lastName"
                name="lastName"
                value={formData.lastName}
                onChange={handleChange}
                placeholder="last name"
                required
              />
              {fieldErrors.lastName && (
                <div className="invalid-feedback">{fieldErrors.lastName}</div>
              )}
            </div>
          </div>
          <div className="mb-3 d-flex">
            <div className="flex-grow-1">
              <input
                type="email"
                className={`form-control ${fieldErrors.email ? 'is-invalid' : ''}`}
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="email@example.com"
                required
              />
              {fieldErrors.email && (
                <div className="invalid-feedback">{fieldErrors.email}</div>
              )}
            </div>
            <div className="flex-grow-1 ms-2">
              <input
                type="tel"
                className={`form-control ${fieldErrors.phone ? 'is-invalid' : ''}`}
                id="phone"
                name="phone"
                value={formData.phone}
                onChange={handleChange}
                placeholder="phone (optional)"
              />
              {fieldErrors.phone && (
                <div className="invalid-feedback">{fieldErrors.phone}</div>
              )}
            </div>
          </div>



          <div className="mb-3 position-relative">
            <input
              type={showPassword ? "text" : "password"}
              className={`form-control ${fieldErrors.password ? 'is-invalid' : ''}`}
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="password"
              required
            />
            <span
              onClick={() => setShowPassword(!showPassword)}
              className="position-absolute top-50 end-0 translate-middle-y me-3"
              style={{ cursor: "pointer", zIndex: 5 }}
            >
              <i
                className={`fa ${
                  showPassword ? "fa-eye-slash" : "fa-eye"
                } text-secondary`}
              ></i>
            </span>
            {fieldErrors.password && (
              <div className="invalid-feedback">{fieldErrors.password}</div>
            )}
            {passwordStrength && formData.password && (
              <div className="password-strength-indicator mt-2">
                <div className="d-flex justify-content-between align-items-center mb-1">
                  <small className="text-muted">Password Strength:</small>
                  <small style={{ color: passwordStrength.color, fontWeight: 'bold' }}>
                    {passwordStrength.label}
                  </small>
                </div>
                <div className="progress" style={{ height: '4px' }}>
                  <div 
                    className="progress-bar" 
                    style={{ 
                      width: `${passwordStrength.percentage}%`,
                      backgroundColor: passwordStrength.color 
                    }}
                  ></div>
                </div>
              </div>
            )}
          </div>

          <div className="mb-3 position-relative">
            <input
              type={showConfirmPassword ? "text" : "password"}
              className={`form-control ${fieldErrors.confirmPassword ? 'is-invalid' : ''}`}
              id="confirmPassword"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              placeholder="confirm password"
              required
            />
            <span
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              className="position-absolute top-50 end-0 translate-middle-y me-3"
              style={{ cursor: "pointer", zIndex: 5 }}
            >
              <i
                className={`fa ${
                  showConfirmPassword ? "fa-eye-slash" : "fa-eye"
                } text-secondary`}
              ></i>
            </span>
            {fieldErrors.confirmPassword && (
              <div className="invalid-feedback">{fieldErrors.confirmPassword}</div>
            )}
          </div>

          {signupSuccess ? (
            <Link 
              to="/login" 
              className="btn w-100 mb-3"
              style={{
                backgroundColor: '#4CAF50',
                color: 'white',
                textDecoration: 'none'
              }}
            >
              Go to Login Page
            </Link>
          ) : (
            <button 
              className="btn w-100 mb-3" 
              type="submit" 
              id="login_button"
              disabled={loading}
            >
              {loading ? 'Creating Account...' : 'Create'}
            </button>
          )}

          <p className="text-left">
            Already have an account?
            <Link to="/login" className="text-white">
              {" "}
              Login
            </Link>
          </p>

          <div className="text-center my-2">OR</div>
          
          <div className="social-login">
              <button 
                type="button" 
                className="btn btn-outline-light w-100"
                onClick={handleGoogleLogin}
              >
                <i className="fab fa-google me-2"></i>Sign Up with Google
              </button>
          </div>

        </form>

        
      </div>
    </div>
  );
};

export default CreateAccount;
