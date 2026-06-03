import "./Login.css";
import robot from "../images/robot.png";
import logo from "../images/logo.png";
import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { validateEmail } from "../../utils/validation";

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
        <form className="form-box" noValidate onSubmit={handleSubmit}>
          <h2 className="fw-bold mb-3">Login</h2>
          <p className="mb-4">Login to your account</p>

          {error && (
            <div className="alert alert-danger mb-3" role="alert">
              {error}
            </div>
          )}

          <div className="mb-3">
            <input
              type="email"
              className={`form-control ${fieldErrors.email ? 'is-invalid' : ''}`}
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="name@example.com"
              required
            />
            {fieldErrors.email && (
              <div className="invalid-feedback">{fieldErrors.email}</div>
            )}
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
          </div>

          <div className="d-flex justify-content-between align-items-center mb-4">
            <div className="form-check">
              <input
                className="form-check-input"
                type="checkbox"
                name="rememberMe"
                checked={formData.rememberMe}
                onChange={handleChange}
                id="rememberMe"
              />
              <label className="form-check-label" htmlFor="rememberMe">
                Remember me
              </label>
            </div>
            <Link to="/forget_password" className="text-white">
              Forget Password?
            </Link>
          </div>

          <button 
            className="btn w-100 mb-3" 
            type="submit" 
            id="login_button"
            disabled={loading}
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>

          <p className="text-left">
            Don't have an account?
            <Link to="/signup" className="text-white">
              {" "}
              Create
            </Link>
          </p>

          <div className="text-center my-2">OR</div>

          <div className="social-login">
            <button 
              type="button" 
              className="btn btn-outline-light w-100"
              onClick={handleGoogleLogin}
            >
              <i className="fab fa-google me-2"></i>Sign In with Google
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Login;
